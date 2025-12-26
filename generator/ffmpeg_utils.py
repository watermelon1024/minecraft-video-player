import shutil
import subprocess
from typing import Optional


def find_ffmpeg() -> Optional[str]:
    """Return path to ffmpeg if found on PATH."""
    path = shutil.which("ffmpeg")
    return path


def verify_ffmpeg(ffmpeg_exec: str) -> bool:
    """Check if path points to a valid ffmpeg executable."""
    try:
        proc = subprocess.run(
            [ffmpeg_exec, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5
        )
        return proc.returncode == 0 and "ffmpeg version" in proc.stdout.lower()
    except Exception:
        return False


def find_ffprobe() -> Optional[str]:
    """Return path to ffprobe if found on PATH."""
    path = shutil.which("ffprobe")
    return path


def verify_ffprobe(ffprobe_exec: str) -> bool:
    """Check if path points to a valid ffprobe executable."""
    try:
        proc = subprocess.run(
            [ffprobe_exec, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5
        )
        return proc.returncode == 0 and "ffprobe version" in proc.stdout.lower()
    except Exception:
        return False
