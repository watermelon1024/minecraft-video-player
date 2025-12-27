import json
import subprocess
from typing import TYPE_CHECKING, Optional, TypedDict

import pysubs2

from .ffmpeg_utils import find_ffmpeg, find_ffprobe, verify_ffmpeg, verify_ffprobe

if TYPE_CHECKING:
    # not available at runtime if Python < 3.11
    from typing import NotRequired

try:
    import av

    pyav_available = True
except ImportError:
    pyav_available = False


class SubtitleTrack(TypedDict):
    index: int
    ffmpeg_index: "NotRequired[int]"
    language: str
    title: str
    source: str


# ---------------------------
# Listing Tracks
# ---------------------------
def get_subtitle_tracks_with_ffmpeg(video_path: str, ffprobe_exec: str = "ffprobe") -> list[SubtitleTrack]:
    """
    Detects subtitle tracks using FFprobe.
    Returns: List[Dict] -> [{'index': 0, 'lang': 'eng', 'title': '...'}, ...]
    """
    try:
        cmd = [
            # fmt: off
            ffprobe_exec,
            "-v", "error",
            "-select_streams", "s",
            "-show_entries", "stream=index:stream_tags=language,title",
            "-of", "json",
            video_path
            # fmt: on
        ]
        res = subprocess.run(cmd, capture_output=True, check=True)
        data = json.loads(res.stdout)

        tracks: list[SubtitleTrack] = []
        for i, stream in enumerate(data.get("streams", [])):
            tags = stream.get("tags", {})
            tracks.append(
                {
                    "index": i,
                    "ffmpeg_index": stream.get("index"),
                    "language": tags.get("language", "und"),
                    "title": tags.get("title", "Unknown"),
                    "source": "FFprobe",
                }
            )
        return tracks
    except Exception as e:
        print(f"[Subtitle] FFprobe detection failed: {e}")
        return []


def get_subtitle_tracks_with_pyav(video_path: str) -> list[SubtitleTrack]:
    """
    Detects subtitle tracks using PyAV.
    Returns: List[Dict] -> [{'index': 0, 'lang': 'eng', 'title': '...'}, ...]
    """
    try:
        container = av.open(video_path)
        tracks: list[SubtitleTrack] = []
        for i, stream in enumerate(container.streams.subtitles):
            tracks.append(
                {
                    "index": i,
                    "language": stream.metadata.get("language", "und"),
                    "title": stream.metadata.get("title", "Unknown"),
                    "source": "PyAV",
                }
            )
        container.close()
        return tracks
    except Exception as e:
        print(f"[Subtitle] PyAV detection failed: {e}")
        return []


# ---------------------------
# Extraction
# ---------------------------
def extract_subtitle_with_ffmpeg(video_path: str, track_index: int, ffmpeg_exec: str = "ffmpeg"):
    """
    Extracts specific subtitle track to SRT using FFmpeg.
    """
    try:
        cmd = [
            # fmt: off
            ffmpeg_exec,
            "-v", "error",
            "-i", video_path,
            "-map", f"0:s:{track_index}",
            "-f", "srt",
            "-"
            # fmt: on
        ]
        res = subprocess.run(cmd, capture_output=True, check=True)
        srt_content = res.stdout.decode("utf-8", errors="ignore")

        if not srt_content.strip():
            print("[Warn] FFmpeg extracted empty content.")
        else:
            return pysubs2.SSAFile.from_string(srt_content)
    except Exception as e:
        print(f"[Subtitle] FFmpeg extraction failed: {e}")
        return None


def extract_subtitle_with_pyav(video_path: str, track_index: int):
    """
    Extracts specific subtitle track using PyAV.
    """
    try:
        container = av.open(video_path)
        if track_index >= len(container.streams.subtitles):
            return None

        stream = container.streams.subtitles[track_index]
        codec_name = stream.codec_context.name
        subs = pysubs2.SSAFile()

        for packet in container.demux(stream):
            if packet.pts is None or stream.time_base is None:
                continue

            start_ms = float(packet.pts * stream.time_base) * 1000
            duration_ms = float(packet.duration * stream.time_base) * 1000 if packet.duration else 2000
            end_ms = start_ms + duration_ms

            raw_bytes = bytes(packet)
            text = ""

            # Basic mov_text handling
            if codec_name == "mov_text" and len(raw_bytes) > 2:
                # Strip length bytes (rough heuristic)
                text_len = int.from_bytes(raw_bytes[:2], "big")
                if text_len == len(raw_bytes) - 2:
                    text = raw_bytes[2:].decode("utf-8", errors="ignore")
                else:
                    text = raw_bytes.decode("utf-8", errors="ignore")
            else:
                text = raw_bytes.decode("utf-8", errors="ignore").strip()

            if text:
                event = pysubs2.SSAEvent(start=int(start_ms), end=int(end_ms), text=text)
                subs.append(event)

        container.close()
        return subs
    except Exception as e:
        print(f"[Subtitle] PyAV extraction failed: {e}")
        return None


# ---------------------------
# Orchestrator Function
# ---------------------------
def extract_and_parse_subtitles_from_video(
    video_path: str,
    prefer_ffmpeg: bool = True,
    ffmpeg_exec: Optional[str] = None,
    ffprobe_exec: Optional[str] = None,
):
    ffmpeg_available = False  # if user don't prefer ffmpeg, skip checking and assume False
    ffprobe_available = False
    if prefer_ffmpeg:
        if not ffmpeg_exec:
            ffmpeg_exec = find_ffmpeg()
        if ffmpeg_exec:
            ffmpeg_available = verify_ffmpeg(ffmpeg_exec)

        if not ffprobe_exec:
            ffprobe_exec = find_ffprobe()
            # if still None, try to deduce from ffmpeg path
            if not ffprobe_exec and ffmpeg_exec:
                ffprobe_exec = ffmpeg_exec.replace("ffmpeg", "ffprobe")
        if ffprobe_exec:
            ffprobe_available = verify_ffprobe(ffprobe_exec)

    # --- Step A: Detect tracks ---
    tracks_info: list[SubtitleTrack] = []
    print("[Subtitle] Scanning for embedded subtitles...")
    if ffprobe_exec and ffprobe_available:
        tracks_info = get_subtitle_tracks_with_ffmpeg(video_path, ffprobe_exec=ffprobe_exec)
    elif pyav_available:
        tracks_info = get_subtitle_tracks_with_pyav(video_path)
    else:
        print("[Warn] No subtitle detection tool found (FFprobe / PyAV).")
        tracks_info = [
            {"index": 0, "language": "und", "title": "Unknown", "source": "Assumed"}
        ]  # Assume first track

    if not tracks_info:
        print("[Subtitle] No embedded subtitles found or detection failed.")
        return None

    # --- Step B: Select and extract ---
    print(f"[Subtitle] Detected {len(tracks_info)} subtitle tracks.")
    for i, t in enumerate(tracks_info, start=1):
        print(f"\t[{i}] {t['language']} - {t['title']} (Source: {t['source']})")

    if len(tracks_info) > 1:
        target_index_str = input(f"Select subtitle track (1-{len(tracks_info)}, default 1): ").strip()
        try:
            target_index = int(target_index_str) - 1
            if target_index < 0 or target_index >= len(tracks_info):
                print("Invalid selection, defaulting to 1.")
                target_index = 0
        except Exception:
            target_index = 0
    else:
        target_index = 0

    target_index = tracks_info[target_index]["index"]
    lang = tracks_info[target_index]["language"]
    print(f"[Subtitle] Extracting track {target_index} ({lang})...")

    if ffmpeg_exec and ffmpeg_available:
        subs = extract_subtitle_with_ffmpeg(video_path, target_index, ffmpeg_exec=ffmpeg_exec)
    elif pyav_available:
        subs = extract_subtitle_with_pyav(video_path, target_index)
    else:
        print("[Error] No subtitle extraction tool available (FFmpeg / PyAV).")
        return None

    if subs is None:
        print("[Subtitle] Extraction or parsing failed.")
        return None

    print(f"[Subtitle] Successfully extracted and parsed {len(subs)} entries.")
    return subs


def load_subtitles_from_file(path: str):
    print(f"[Subtitle] Loading subtitle from file: {path}")
    try:
        return pysubs2.load(path)
    except Exception as e:
        print(f"[Subtitle] Failed to load subtitle file: {e}")
        return None
