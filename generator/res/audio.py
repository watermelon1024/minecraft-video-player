import json
import os
import subprocess


def segment_audio(input_video: str, output_dir: str, segment_time: int = 10):
    """
    Splits audio into multiple small segments (ogg format).
    segment_time: Length of each segment (seconds).
    """

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Output filename format: part_000.ogg, part_001.ogg ...
    output_pattern = os.path.join(output_dir, "part_%d.ogg")

    cmd = [
        # fmt: off
        "ffmpeg", "-y",
        "-i", input_video,
        "-vn",  # Audio only
        "-c:a", "libvorbis",  # Ogg encoding
        "-q:a", "3",  # Audio quality
        "-f", "segment",  # Enable segment mode
        "-segment_time", str(segment_time),  # Segment length
        output_pattern,
        # fmt: on
    ]

    print(f"[Audio] Splitting audio into {segment_time} second segments...")
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    # Count segments (for generating sounds.json)
    files = [f for f in os.listdir(output_dir) if f.startswith("part_") and f.endswith(".ogg")]
    return files


def generate_segmented_sounds_json(files: list[str], namespace: str = "video"):
    sounds_data = {}
    for i in range(len(files)):
        # Register each segment: video.part_0, video.part_1 ...
        sound_event = f"part_{i}"

        sounds_data[sound_event] = {
            "subtitle": f"Audio Part {i}",
            "sounds": [
                {
                    "name": f"{namespace}:part_{i}",  # Corresponds to part_%d.ogg
                    "stream": True,  # Stream enabled for safety, even for 10s clips
                }
            ],
        }

    json_path = os.path.join("res", "sounds.json")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(sounds_data, f, indent=2)
