import json
import math
import os

import cv2

from ..video_utils import FrameData, FrameIndex, TimestampSec, VideoMetadata
from .audio import generate_segmented_sounds_json, segment_audio

MAX_W = 256
MAX_H = 256
PIXEL_SCALE = 0.025  # 1 px = 0.025 blocks
ROW_HEIGHT_BLOCKS = MAX_H * PIXEL_SCALE  # 6.4


def processing_callback(frame: FrameData, index: FrameIndex, timestamp: TimestampSec):
    """
    Splits a single frame into multiple small tiles < 256x256 and saves them.
    Filename format: assets/minecraft/textures/font/f{index}_r{row}_c{col}.png
    """

    # Get original dimensions
    h, w, _ = frame.shape

    # Calculate rows and columns needed (Ceiling division)
    cols = math.ceil(w / MAX_W)
    rows = math.ceil(h / MAX_H)

    # Ensure output directory exists
    output_dir = "frame"
    os.makedirs(output_dir, exist_ok=True)

    # --- Start slicing and saving ---
    for r in range(rows):
        for c in range(cols):
            # Calculate crop range
            x_start = c * MAX_W
            y_start = r * MAX_H
            x_end = min(x_start + MAX_W, w)
            y_end = min(y_start + MAX_H, h)

            # [Core] Slice using NumPy (very fast)
            # frame[y:y, x:x]
            tile = frame[y_start:y_end, x_start:x_end]

            # Save file
            # Filename example: f0_r0_c0.png
            filepath = os.path.join(output_dir, f"f{index}_r{r}_c{c}.png")

            # Save using cv2 (default compression is fine)
            cv2.imwrite(filepath, tile)


def finish_callback(meta: VideoMetadata):
    """
    Generates custom font json and text_display init mcfunction based on total frames and dimensions.
    Uses 1 px = 0.025 blocks measurement for automatic alignment.
    """

    target_w = meta["width"]
    target_h = meta["height"]
    fps = meta["fps"]
    total_frames = meta["frame_count"]
    # Calculate rows and columns
    cols = math.ceil(target_w / MAX_W)
    rows = math.ceil(target_h / MAX_H)

    # --- 1. Generate custom font json ---
    fonts: dict[str, list] = {}
    start_char = 0xE000

    print(f"[Info] Generating config... (Grid: {rows} rows x {cols} cols)")

    for i in range(total_frames):
        for r in range(rows):
            current_h = min((r + 1) * MAX_H, target_h) - (r * MAX_H)
            for c in range(cols):
                # Set Ascent to 0
                # This means the baseline is at the top of the image.
                # The image will render downwards from the entity's Y coordinate for current_h length.
                fonts.setdefault(f"frame_r{r}_c{c}", []).append(
                    {
                        "type": "bitmap",
                        "file": f"video:frame/f{i}_r{r}_c{c}.png",
                        "ascent": 0,  # Top aligned
                        "height": current_h,  # Actual pixel height
                        "chars": [chr(start_char + i)],
                    }
                )

    font_dir = "res/font"
    os.makedirs(font_dir, exist_ok=True)
    for name, providers in fonts.items():
        json_path = os.path.join(font_dir, f"{name}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"providers": providers}, f, separators=(",", ":"), ensure_ascii=False)

    print(f"[Done] Generated resource pack config: {font_dir}")

    # --- 2. Output summon commands (Row-based) ---
    print("[Info] Generating summon commands...")
    # # Calculate total width (for centering)
    # total_width_blocks = target_w * PIXEL_SCALE

    # # Start X: Shift left by half of total width
    # trans_x = -(total_width_blocks / 2)

    # Start Y: Since ascent=0 means image grows downwards, place the first row at the highest point.
    # Assuming feet at 0, screen bottom aligned with eye height (1.6), or floating.
    # Here set as: Top of first row at Y + total height (so screen bottom is approx at Y=0).
    total_height_blocks = target_h * PIXEL_SCALE
    start_y = total_height_blocks

    init_cmds: list[str] = []

    # Generate one entity per row
    for r in range(rows):
        # 1. Calculate Y coordinate for this row
        # Since each row is fully 256px high (except the last one, but its start is relative to previous end)
        # And ascent=0, so next row start is Current_Y - 6.4
        trans_y = start_y - (r * ROW_HEIGHT_BLOCKS)

        # 3. Generate initialization text for this row (placeholder, replaced during playback)
        # We don't need to know Unicode here, as that's playback logic.
        # But for testing, we can insert the character for the first frame.
        cmd = (
            "summon minecraft:text_display ~ ~ ~ "
            '{Tags:["video_player","frame"],'
            "transformation:{"
            "right_rotation:[0f,0f,0f,1f],"
            "left_rotation:[0f,0f,0f,1f],"
            f"translation:[0f,{trans_y}f,0f],"
            "scale:[1f,1f,1f]},"
            'text:["",'
            + ',{"text":"\\u200c","font":"video:nosplit"},'.join(
                '{"text":"\\uE000","font":"video:frame_r%d_c%d"}' % (r, c) for c in range(cols)
            )
            + "],line_width:2147483647,background:0}"
        )
        init_cmds.append(cmd)

    # --- 3. Generate frame Unicode mapping table ---
    frames_unicode = ",".join(f'"\\u{start_char + i:04x}"' for i in range(total_frames))
    init_cmds.insert(0, "data merge storage video_player:frame {frames:[%s]}" % frames_unicode)

    init_cmds.append("scoreboard players set frame video_player 0")
    init_cmds.append(f"scoreboard players set end_frame video_player {total_frames - 1}")

    # audio segment time (seconds)
    segment_time = 10  # seconds
    init_cmds.append(f"scoreboard players set audio_segment video_player {int(segment_time * fps)}")

    mcfunction_dir = "dtp/function"
    os.makedirs(mcfunction_dir, exist_ok=True)

    init_path = os.path.join(mcfunction_dir, "init.mcfunction")
    with open(init_path, "w", encoding="utf-8") as f:
        f.write("\n".join(init_cmds))
    print(f"[Done] Generated init commands: {init_path}")

    play_loop_path = os.path.join(mcfunction_dir, "play_frame.mcfunction")
    with open(play_loop_path, "w", encoding="utf-8") as f:
        f.write(
            "\n".join(
                f"$data modify entity @s text.extra[{c * 2}].text set from storage video_player:frame frames[$(frame)]"
                for c in range(cols)
            )
        )
    print(f"[Done] Generated play frame commands: {play_loop_path}")

    # -- Sounds JSON generation is moved to sound.py ---
    sounds_dir = os.path.join("res", "sounds")
    audio_files = segment_audio(meta["path"], sounds_dir, segment_time=segment_time)
    generate_segmented_sounds_json(audio_files, namespace="video")
