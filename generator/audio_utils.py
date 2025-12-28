import os
import subprocess
from functools import partial
from typing import Optional, cast

import av

from generator.ffmpeg_utils import find_ffmpeg, verify_ffmpeg


def segment_audio_with_ffmpeg(
    input_video: str, output_dir: str, segment_time: int = 10, ffmpeg_exec: str = "ffmpeg"
):
    """
    Splits audio into Ogg segments using ffmpeg.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    output_pattern = os.path.join(output_dir, "part_%d.ogg")
    cmd = [
        # fmt: off
        ffmpeg_exec, "-y",
        "-i", input_video,
        "-vn",
        "-c:a", "libvorbis",
        "-q:a", "3",
        "-f", "segment",
        "-segment_time", str(segment_time),
        output_pattern,
        # fmt: on
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    files = [f for f in os.listdir(output_dir) if f.startswith("part_") and f.endswith(".ogg")]
    files.sort(key=lambda x: int(x.removeprefix("part_").removesuffix(".ogg")))
    return files


def segment_audio_with_pyav(video_path: str, output_dir: str, segment_time: int = 10) -> list[str]:
    """
    Split audio into Ogg segments using PyAV.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    try:
        input_container = av.open(video_path)
        if not input_container.streams.audio:
            return []
        in_stream = input_container.streams.audio[0]

        sample_rate = 44100
        samples_per_segment = int(sample_rate * segment_time)

        current_segment_idx = 0
        current_samples_written = 0

        def open_next_segment(idx: int):
            path = os.path.join(output_dir, f"part_{idx}.ogg")
            container = av.open(path, "w")
            stream = cast(av.AudioStream, container.add_stream("libvorbis", rate=sample_rate))
            stream.layout = "stereo"
            return container, stream

        out_container, out_stream = open_next_segment(current_segment_idx)

        resampler = av.AudioResampler(
            format=out_stream.format,
            layout=out_stream.layout,
            rate=out_stream.rate,
        )

        for frame in input_container.decode(in_stream):
            out_frames = resampler.resample(frame)

            for out_frame in out_frames:
                # Simple segmentation: switch file when sample count exceeds limit.
                # Minor duration drift is acceptable for Minecraft.
                packets = out_stream.encode(out_frame)
                out_container.mux(packets)

                current_samples_written += out_frame.samples

                if current_samples_written >= samples_per_segment:
                    # Flush current container
                    packets = out_stream.encode(None)
                    out_container.mux(packets)
                    out_container.close()

                    # Start new segment
                    current_segment_idx += 1
                    current_samples_written = 0
                    out_container, out_stream = open_next_segment(current_segment_idx)

        # Finalize
        packets = out_stream.encode(None)
        out_container.mux(packets)
        out_container.close()
        input_container.close()

        print(f"[Audio] Segmentation complete, {current_segment_idx + 1} parts.")
        return [os.path.join(output_dir, f"part_{i}.ogg") for i in range(current_segment_idx + 1)]

    except Exception as e:
        print(f"[Audio] Segmentation failed: {e}")
        return []


def segment_audio(
    input_video: str,
    output_dir: str,
    segment_time: int = 10,
    prefer_ffmpeg: bool = True,
    ffmpeg_exec_path: Optional[str] = None,
):
    """
    Splits audio into Ogg segments using ffmpeg.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    ffmpeg_available = False
    if prefer_ffmpeg:
        if not ffmpeg_exec_path:
            ffmpeg_exec_path = find_ffmpeg()
        if ffmpeg_exec_path:
            ffmpeg_available = verify_ffmpeg(ffmpeg_exec_path)
            ffmpeg_available = True

    if ffmpeg_exec_path and ffmpeg_available:
        print(f"[Audio] Using ffmpeg at: {ffmpeg_exec_path}")
        _segment_audio = partial(
            segment_audio_with_ffmpeg, input_video, output_dir, segment_time, ffmpeg_exec=ffmpeg_exec_path
        )
        via = "ffmpeg"
    else:
        print("[Audio] FFmpeg not available, using fallback method.")
        _segment_audio = partial(segment_audio_with_pyav, input_video, output_dir, segment_time)
        via = "fallback"

    files = _segment_audio()
    print(f"[Audio] Split audio into {len(files)} segments ({segment_time} seconds each) via {via}...")
    return files
