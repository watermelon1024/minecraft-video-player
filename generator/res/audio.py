import json
import os
import subprocess


def segment_audio(input_video: str, output_dir: str, segment_time: int = 10):
    """
    將音訊切分為多個小片段 (ogg 格式)
    segment_time: 每個片段的長度 (秒)
    """

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 輸出檔名格式: part_000.ogg, part_001.ogg ...
    output_pattern = os.path.join(output_dir, "part_%d.ogg")

    cmd = [
        # fmt: off
        "ffmpeg", "-y",
        "-i", input_video,
        "-vn",  # 只要聲音
        "-c:a", "libvorbis",  # Ogg 編碼
        "-q:a", "3",  # 音質
        "-f", "segment",  # 開啟切分模式
        "-segment_time", str(segment_time),  # 切分長度
        output_pattern,
        # fmt: on
    ]

    print(f"[Audio] 正在將音訊切分為每 {segment_time} 秒一段...")
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    # 計算切了幾段 (用於生成 sounds.json)
    files = [f for f in os.listdir(output_dir) if f.startswith("part_") and f.endswith(".ogg")]
    return files


def generate_segmented_sounds_json(files: list[str], namespace: str = "video"):
    sounds_data = {}
    for i in range(len(files)):
        # 註冊每一個片段: video.part_0, video.part_1 ...
        sound_event = f"part_{i}"

        sounds_data[sound_event] = {
            "subtitle": f"Audio Part {i}",
            "sounds": [
                {
                    "name": f"{namespace}:part_{i}",  # 對應 part_%d.ogg
                    "stream": True,  # 雖然只有10秒，但開 stream 比較保險
                }
            ],
        }

    json_path = os.path.join("res", "sounds.json")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(sounds_data, f, indent=2)
