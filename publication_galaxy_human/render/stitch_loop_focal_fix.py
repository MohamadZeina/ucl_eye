#!/usr/bin/env python3
"""
Stitch with focal length correction.
Crops BW frames (14mm) to match FW frames (18mm) before stitching.
"""

import subprocess
import shutil
import tempfile
from pathlib import Path
import sys

# Focal length parameters
FW_FOCAL = 18
BW_FOCAL = 14
WIDTH = 7680
HEIGHT = 4320

# Calculate crop
SCALE = BW_FOCAL / FW_FOCAL
CROP_W = int(WIDTH * SCALE) - (int(WIDTH * SCALE) % 2)
CROP_H = int(HEIGHT * SCALE) - (int(HEIGHT * SCALE) % 2)
OFFSET_X = (WIDTH - CROP_W) // 2
OFFSET_Y = (HEIGHT - CROP_H) // 2

CROP_FILTER = f"crop={CROP_W}:{CROP_H}:{OFFSET_X}:{OFFSET_Y},scale={WIDTH}:{HEIGHT}:flags=lanczos"


def process_bw_frame(src: Path, dst: Path):
    """Apply focal length correction to a BW frame."""
    cmd = [
        'ffmpeg', '-y', '-i', str(src),
        '-vf', CROP_FILTER,
        '-q:v', '2',  # High quality JPEG
        str(dst)
    ]
    subprocess.run(cmd, capture_output=True, check=True)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Stitch with focal length correction')
    parser.add_argument('fw_dir', type=Path)
    parser.add_argument('bw_dir', type=Path)
    parser.add_argument('output_base', type=Path)
    parser.add_argument('--orbit-period', type=int, default=65536)
    parser.add_argument('--step', type=int, default=256)
    parser.add_argument('--fps', type=int, default=24)
    parser.add_argument('--resolution', type=str, default=None, help='Also create downscaled (e.g., 4K)')

    args = parser.parse_args()

    print(f"Focal length correction: {BW_FOCAL}mm -> {FW_FOCAL}mm")
    print(f"Crop filter: {CROP_FILTER}")
    print()

    # Get common frames at specified step
    fw_frames = set(int(f.stem) for f in args.fw_dir.iterdir()
                    if f.suffix == '.jpg' and not f.name.startswith('.'))
    bw_frames = set(int(f.stem) for f in args.bw_dir.iterdir()
                    if f.suffix == '.jpg' and not f.name.startswith('.'))
    common = sorted(fw_frames & bw_frames)

    # Filter to step
    expected = set(range(4, 65541, args.step))
    filtered = sorted(set(common) & expected)

    print(f"Common frames: {len(common)}")
    print(f"Filtered to step {args.step}: {len(filtered)} frames")

    # Create temp directory for processed BW frames
    with tempfile.TemporaryDirectory(prefix='bw_focal_fix_') as bw_temp:
        bw_temp = Path(bw_temp)

        print(f"\nProcessing BW frames with focal correction...")
        for i, frame in enumerate(filtered):
            src = args.bw_dir / f"{frame:04d}.jpg"
            dst = bw_temp / f"{frame:04d}.jpg"
            if src.exists():
                process_bw_frame(src, dst)
                if (i + 1) % 20 == 0:
                    print(f"  Processed {i + 1}/{len(filtered)} BW frames")
        print(f"  Done processing {len(filtered)} BW frames")

        # Create temp FW directory with symlinks
        with tempfile.TemporaryDirectory(prefix='fw_filtered_') as fw_temp:
            fw_temp = Path(fw_temp)
            for frame in filtered:
                src = args.fw_dir / f"{frame:04d}.jpg"
                if src.exists():
                    (fw_temp / f"{frame:04d}.jpg").symlink_to(src)

            # Now run the regular stitch script
            print("\nRunning stitch...")

            stitch_cmd = [
                sys.executable,
                str(Path(__file__).parent / 'stitch_loop.py'),
                str(fw_temp),
                str(bw_temp),
                str(args.output_base),
                '--orbit-period', str(args.orbit_period),
                '--fps', str(args.fps),
                '--both-crossovers'
            ]

            if args.resolution:
                stitch_cmd.extend(['--resolution', args.resolution])

            subprocess.run(stitch_cmd, check=True)

    print("\nDone!")


if __name__ == '__main__':
    main()
