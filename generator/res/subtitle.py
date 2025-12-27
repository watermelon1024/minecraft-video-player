import pysubs2


def generate_subtitle_init_mcfunction(subtitle: pysubs2.SSAFile, fps: float):
    """
    根據影片路徑產生對應的字幕檔路徑
    例如: video/subtitles/{video_filename}_subtitles.srt
    """
    subtitles_dict: dict[int, str] = {}

    for line in subtitle:
        # 將時間轉換為 frame index
        start_sec = int(line.start / 1000 * fps)
        end_sec = int(line.end / 1000 * fps)
        text = line.text.replace(r"\N", "\n")  # 處理換行

        subtitles_dict[start_sec] = text
        subtitles_dict[end_sec] = ""  # 清除字幕

    storage = ",".join(f'{k}:"{v}"' for k, v in subtitles_dict.items())
    return "\n".join(
        [
            'summon minecraft:text_display ~ ~ ~1 {Tags:["video_player","subtitle"],text:"SUBTITLE",background:0x60808080}',
            "data merge storage video_player:subtitle {%s}" % storage,
        ]
    )
