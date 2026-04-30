#!/usr/bin/env python3
"""
Generate seamless loop videos at 50% and 100% crossover points.

Uses ffmpeg concat demuxer — no file copies needed.
Reads FW frames forward, then BW frames reversed.

Meeting frames: {4, 32772, 65540} (0%, 50%, 100% of orbit)
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path

FW_JPG = Path("/Volumes/Mo 4TB 2/render/17_fw_the_one_512s")
BW_JPG = Path("/Volumes/Mo 4TB 3/render/17_bw_the_one_512s")
OUTPUT_DIR = Path("/Volumes/Mo 4TB 2/render/crossover_videos")

FPS = 30
CRF = 18
FRAME_DURATION = f"{1/FPS:.10f}"

# Orbit geometry
START_FRAME = 4
MEETING_50 = 32772
MEETING_100 = 65540


def frame_path(base_dir: Path, num: int) -> Path:
    return base_dir / f"{num:04d}.jpg"


def build_concat_list(fw_dir: Path, bw_dir: Path, crossover_frame: int) -> list[str]:
    """Build ordered list of frame paths for the concat demuxer."""
    paths = []

    # Forward: START_FRAME → crossover_frame (inclusive)
    for f in range(START_FRAME, crossover_frame + 1):
        p = frame_path(fw_dir, f)
        if p.exists():
            paths.append(str(p))

    # Backward reversed: crossover_frame-1 → START_FRAME (skip crossover to avoid dupe)
    for f in range(crossover_frame - 1, START_FRAME - 1, -1):
        p = frame_path(bw_dir, f)
        if p.exists():
            paths.append(str(p))

    return paths


def write_concat_file(paths: list[str], output_path: Path):
    """Write ffmpeg concat demuxer file."""
    with open(output_path, 'w') as f:
        for i, p in enumerate(paths):
            # Escape single quotes in path
            escaped = p.replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
            if i < len(paths) - 1:
                f.write(f"duration {FRAME_DURATION}\n")
    print(f"Wrote concat list: {output_path} ({len(paths)} frames)")


def encode_video(concat_file: Path, output_file: Path, scale: str = None):
    """Run ffmpeg to encode video from concat list.
    If scale is None, encodes at native resolution (no distortion).
    If scale is e.g. '3840:-2', scales preserving aspect ratio."""
    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', str(concat_file),
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', str(CRF),
        '-pix_fmt', 'yuv420p',
    ]
    if scale:
        cmd.extend(['-vf', f'scale={scale}:flags=lanczos'])
    cmd.extend(['-movflags', '+faststart', str(output_file)])
    res_label = scale if scale else "native (7040x3240)"
    print(f"\nEncoding: {output_file}")
    print(f"  Resolution: {res_label}")
    print(f"  Command: {' '.join(cmd[:8])}...")
    sys.stdout.flush()
    subprocess.run(cmd, check=True)
    sz = os.path.getsize(output_file) / (1024 * 1024 * 1024)
    print(f"Done: {output_file} ({sz:.1f} GB)")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for label, crossover in [("50pct", MEETING_50), ("100pct", MEETING_100)]:
        print(f"\n{'='*60}")
        print(f"  CROSSOVER {label} (frame {crossover})")
        print(f"{'='*60}")

        paths = build_concat_list(FW_JPG, BW_JPG, crossover)
        fw_count = crossover - START_FRAME + 1
        bw_count = len(paths) - fw_count
        duration_sec = len(paths) / FPS
        duration_min = duration_sec / 60

        print(f"  FW frames: {fw_count} ({START_FRAME}→{crossover})")
        print(f"  BW frames: {bw_count} ({crossover-1}→{START_FRAME}, reversed)")
        print(f"  Total: {len(paths)} frames = {duration_min:.1f} min at {FPS}fps")

        # Write concat file
        concat_file = OUTPUT_DIR / f"concat_{label}.txt"
        write_concat_file(paths, concat_file)

        # Encode at native resolution (no aspect ratio distortion)
        video_file = OUTPUT_DIR / f"render17_seamless_{label}_native.mp4"
        encode_video(concat_file, video_file, scale=None)

        # Also encode 4K preserving aspect ratio
        video_file_4k = OUTPUT_DIR / f"render17_seamless_{label}_4K.mp4"
        encode_video(concat_file, video_file_4k, scale="3840:-2")

    print(f"\nAll videos saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
