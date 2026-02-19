#!/usr/bin/env python3
"""
Seamless Loop Stitcher for Forward/Backward Camera Passes

Creates a seamless loop by combining:
1. Forward pass: start_frame → crossover_frame (simulation forward)
2. Backward pass REVERSED: crossover_frame-step → start_frame (simulation backward)

The cameras use drivers:
- Forward:  100 * ((frame - 4) / 65536) + 2.8037
- Backward: 100 * (-(frame - 4) / 65536) + 2.8037

They meet at frames {4, 32772, 65540} (crossover at 0% and 50% of orbit)
"""

import os
import shutil
import argparse
import subprocess
from pathlib import Path


# Resolution presets (width x height)
RESOLUTION_PRESETS = {
    '8K': (7680, 4320),
    '4K': (3840, 2160),
    '2K': (2560, 1440),
    '1080p': (1920, 1080),
    '720p': (1280, 720),
}


def parse_resolution(res_str: str) -> tuple[int, int] | None:
    """Parse resolution string like '4K', '1080p', or '1920x1080'."""
    if not res_str:
        return None
    res_upper = res_str.upper()
    if res_upper in RESOLUTION_PRESETS:
        return RESOLUTION_PRESETS[res_upper]
    if 'X' in res_upper:
        parts = res_upper.split('X')
        if len(parts) == 2:
            try:
                return (int(parts[0]), int(parts[1]))
            except ValueError:
                pass
    raise ValueError(f"Invalid resolution: {res_str}. Use preset (4K, 1080p) or WxH format.")


def filter_frames_by_step(frames: list[int], step: int, start_offset: int = 4) -> list[int]:
    """Filter frame list to only include frames at consistent step intervals."""
    expected = set(range(start_offset, max(frames) + 1, step))
    filtered = [f for f in frames if f in expected]
    return sorted(filtered)


def get_frame_list(directory: Path, extension: str = ".jpg") -> list[int]:
    """Get sorted list of frame numbers from a directory."""
    frames = []
    for f in directory.iterdir():
        if f.suffix.lower() == extension:
            try:
                frames.append(int(f.stem))
            except ValueError:
                pass
    return sorted(frames)


def calculate_crossover(orbit_period: int) -> int:
    """Calculate the crossover frame where forward and backward cameras meet."""
    return orbit_period // 2


def find_nearest_frame(target: int, frames: list[int]) -> int:
    """Find the frame number nearest to target."""
    return min(frames, key=lambda x: abs(x - target))


def stitch_loop(
    fw_dir: Path,
    bw_dir: Path,
    output_dir: Path,
    orbit_period: int = 60000,
    crossover_frame: int | None = None,
    extension: str = ".jpg",
    dry_run: bool = False,
    skip_crossover: bool = True  # If False, include crossover frame in both sequences
) -> dict:
    """
    Stitch forward and backward passes into a seamless loop.

    Returns dict with statistics about the operation.
    """
    # Get available frames
    fw_frames = get_frame_list(fw_dir, extension)
    bw_frames = get_frame_list(bw_dir, extension)

    if not fw_frames or not bw_frames:
        raise ValueError("No frames found in one or both directories")

    # Verify frame lists match
    if fw_frames != bw_frames:
        print(f"Warning: Frame lists differ. FW: {len(fw_frames)}, BW: {len(bw_frames)}")

    # Calculate crossover if not specified
    if crossover_frame is None:
        crossover_frame = calculate_crossover(orbit_period)

    # Find nearest available crossover frame
    actual_crossover = find_nearest_frame(crossover_frame, fw_frames)
    crossover_idx = fw_frames.index(actual_crossover)

    # Determine frame step
    if len(fw_frames) > 1:
        step = fw_frames[1] - fw_frames[0]
    else:
        step = 1

    # Build sequence:
    # 1. Forward: start → crossover (inclusive)
    # 2. Backward REVERSED: crossover → start or crossover-step → start

    forward_sequence = fw_frames[:crossover_idx + 1]  # start to crossover inclusive

    # Backward reversed: include or skip crossover based on parameter
    if skip_crossover:
        # Skip crossover frame to avoid duplicate
        backward_for_reverse = bw_frames[:crossover_idx]  # start to crossover-1
    else:
        # Include crossover frame (will appear twice at splice point)
        backward_for_reverse = bw_frames[:crossover_idx + 1]  # start to crossover inclusive
    backward_sequence = list(reversed(backward_for_reverse))  # reverse it

    # Combined sequence
    sequence = []

    # Add forward frames
    for frame_num in forward_sequence:
        sequence.append(('fw', frame_num))

    # Add backward frames (reversed)
    for frame_num in backward_sequence:
        sequence.append(('bw', frame_num))

    # Create output directory
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    # Copy files with sequential numbering
    stats = {
        'total_frames': len(sequence),
        'forward_frames': len(forward_sequence),
        'backward_frames': len(backward_sequence),
        'crossover_frame': actual_crossover,
        'calculated_crossover': crossover_frame,
        'frame_step': step,
        'start_frame': fw_frames[0],
        'end_frame': fw_frames[-1],
    }

    print(f"Stitching seamless loop:")
    print(f"  Forward frames:  {len(forward_sequence)} ({fw_frames[0]} → {actual_crossover})")
    bw_start = actual_crossover - step if skip_crossover else actual_crossover
    print(f"  Backward frames: {len(backward_sequence)} ({bw_start} → {fw_frames[0]}, reversed)")
    print(f"  Total output:    {len(sequence)} frames")
    print(f"  Crossover at:    frame {actual_crossover} (target: {crossover_frame})")
    print(f"  Skip crossover:  {skip_crossover}")
    print()

    if dry_run:
        print("DRY RUN - no files copied")
        return stats

    # Copy files
    for out_idx, (source, frame_num) in enumerate(sequence, start=1):
        src_dir = fw_dir if source == 'fw' else bw_dir
        src_file = src_dir / f"{frame_num:04d}{extension}"
        dst_file = output_dir / f"{out_idx:04d}{extension}"

        if src_file.exists():
            shutil.copy2(src_file, dst_file)
        else:
            print(f"Warning: Source file not found: {src_file}")

    print(f"Copied {len(sequence)} frames to {output_dir}")
    return stats


def create_video(
    input_dir: Path,
    output_file: Path,
    fps: int = 24,
    extension: str = ".jpg",
    crf: int = 18,
    resolution: tuple[int, int] | None = None
):
    """
    Create video from frame sequence using ffmpeg.

    If resolution is specified, creates BOTH:
    - Native resolution video (original filename)
    - Downscaled video (with resolution suffix, e.g., _4K.mp4)
    """
    # Always create native resolution first
    cmd_native = [
        'ffmpeg', '-y',
        '-framerate', str(fps),
        '-i', str(input_dir / f'%04d{extension}'),
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', str(crf),
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart',
        str(output_file)
    ]

    print(f"Creating video (native): {output_file}")
    subprocess.run(cmd_native, check=True)
    print(f"Video created: {output_file}")

    # If resolution specified, also create downscaled version
    if resolution:
        width, height = resolution
        # Generate resolution suffix
        res_name = None
        for name, (w, h) in RESOLUTION_PRESETS.items():
            if w == width and h == height:
                res_name = name
                break
        if not res_name:
            res_name = f"{width}x{height}"

        # Create scaled output filename
        stem = output_file.stem
        scaled_file = output_file.with_name(f"{stem}_{res_name}{output_file.suffix}")

        cmd_scaled = [
            'ffmpeg', '-y',
            '-framerate', str(fps),
            '-i', str(input_dir / f'%04d{extension}'),
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', str(crf),
            '-pix_fmt', 'yuv420p',
            '-vf', f'scale={width}:{height}:flags=lanczos',
            '-movflags', '+faststart',
            str(scaled_file)
        ]

        print(f"Creating video ({res_name}): {scaled_file}")
        subprocess.run(cmd_scaled, check=True)
        print(f"Video created: {scaled_file}")


def stitch_both_crossovers(
    fw_dir: Path,
    bw_dir: Path,
    output_base: Path,
    orbit_period: int = 60000,
    extension: str = ".jpg",
    fps: int = 24,
    dry_run: bool = False,
    skip_crossover: bool = True,
    resolution: tuple[int, int] | None = None
) -> dict:
    """
    Create videos for BOTH crossover points:
    1. Crossover at 50% (halfway) - cameras meet on opposite side
    2. Crossover at 0% (start) - cameras meet at starting position

    Returns dict with stats for both videos.
    """
    results = {}

    # Get available frames to determine the actual range
    fw_frames = get_frame_list(fw_dir, extension)
    start_frame = fw_frames[0]
    end_frame = fw_frames[-1]

    # Crossover 1: At halfway point (50%)
    crossover_halfway = orbit_period // 2
    output_dir_1 = Path(f"{output_base}_crossover_50pct")
    video_1 = Path(f"{output_base}_crossover_50pct.mp4")

    print("=" * 60)
    print("CROSSOVER 1: Position 50% (opposite side of orbit)")
    print("=" * 60)

    results['crossover_50pct'] = stitch_loop(
        fw_dir=fw_dir,
        bw_dir=bw_dir,
        output_dir=output_dir_1,
        orbit_period=orbit_period,
        crossover_frame=crossover_halfway,
        extension=extension,
        dry_run=dry_run,
        skip_crossover=skip_crossover
    )

    if not dry_run:
        create_video(output_dir_1, video_1, fps=fps, extension=extension, resolution=resolution)

    # Crossover 2: At start point (0% / 100%)
    # Target is orbit_period (60000) where cameras meet at 0%
    # find_nearest_frame will pick the closest available frame
    crossover_start = orbit_period  # Target the actual meeting point

    output_dir_2 = Path(f"{output_base}_crossover_0pct")
    video_2 = Path(f"{output_base}_crossover_0pct.mp4")

    print("\n" + "=" * 60)
    print("CROSSOVER 2: Position ~0% (near starting position)")
    print("=" * 60)

    results['crossover_0pct'] = stitch_loop(
        fw_dir=fw_dir,
        bw_dir=bw_dir,
        output_dir=output_dir_2,
        orbit_period=orbit_period,
        crossover_frame=crossover_start,
        extension=extension,
        dry_run=dry_run,
        skip_crossover=skip_crossover
    )

    if not dry_run:
        create_video(output_dir_2, video_2, fps=fps, extension=extension, resolution=resolution)

    return results


def main():
    parser = argparse.ArgumentParser(description='Stitch forward/backward passes into seamless loop')
    parser.add_argument('fw_dir', type=Path, help='Forward pass directory')
    parser.add_argument('bw_dir', type=Path, help='Backward pass directory')
    parser.add_argument('output_dir', type=Path, help='Output directory for combined frames')
    parser.add_argument('--orbit-period', type=int, default=60000, help='Frames per orbit (default: 60000)')
    parser.add_argument('--crossover', type=int, help='Override crossover frame (default: orbit_period/2)')
    parser.add_argument('--extension', default='.jpg', help='File extension (default: .jpg)')
    parser.add_argument('--fps', type=int, default=24, help='Video framerate (default: 24)')
    parser.add_argument('--video', type=Path, help='Output video file (optional)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without copying')
    parser.add_argument('--both-crossovers', action='store_true',
                        help='Generate videos for both crossover points (50%% and 0%%)')
    parser.add_argument('--no-skip-crossover', action='store_true',
                        help='Include crossover frame in both sequences (creates 1-frame pause at splice)')
    parser.add_argument('--step', type=int,
                        help='Filter frames to consistent step interval (e.g., 1024, 2048)')
    parser.add_argument('--resolution', type=str,
                        help='Also create downscaled video (e.g., 4K, 1080p, 1920x1080). Native always saved.')

    args = parser.parse_args()
    skip_crossover = not args.no_skip_crossover
    resolution = parse_resolution(args.resolution) if args.resolution else None

    # If step filtering requested, create filtered temp directories
    fw_dir = args.fw_dir
    bw_dir = args.bw_dir
    temp_dirs = []

    if args.step:
        import tempfile
        # Get frames from both directories
        fw_frames = get_frame_list(args.fw_dir, args.extension)
        bw_frames = get_frame_list(args.bw_dir, args.extension)

        # Find common frames
        common_frames = sorted(set(fw_frames) & set(bw_frames))

        # Detect start offset from first frame
        start_offset = common_frames[0] if common_frames else 0

        # Filter to consistent step
        filtered_frames = filter_frames_by_step(common_frames, args.step, start_offset)

        if not filtered_frames:
            raise ValueError(f"No frames found at step {args.step}")

        print(f"Filtering to step {args.step}: {len(filtered_frames)} frames "
              f"(from {len(common_frames)} common frames)")

        # Create temp directories with symlinks to filtered frames
        fw_temp = Path(tempfile.mkdtemp(prefix='stitch_fw_'))
        bw_temp = Path(tempfile.mkdtemp(prefix='stitch_bw_'))
        temp_dirs = [fw_temp, bw_temp]

        for frame in filtered_frames:
            fw_src = args.fw_dir / f"{frame:04d}{args.extension}"
            bw_src = args.bw_dir / f"{frame:04d}{args.extension}"
            if fw_src.exists():
                (fw_temp / f"{frame:04d}{args.extension}").symlink_to(fw_src)
            if bw_src.exists():
                (bw_temp / f"{frame:04d}{args.extension}").symlink_to(bw_src)

        fw_dir = fw_temp
        bw_dir = bw_temp

    try:
        if args.both_crossovers:
            # Generate both crossover videos
            results = stitch_both_crossovers(
                fw_dir=fw_dir,
                bw_dir=bw_dir,
                output_base=args.output_dir,
                orbit_period=args.orbit_period,
                extension=args.extension,
                fps=args.fps,
                dry_run=args.dry_run,
                skip_crossover=skip_crossover,
                resolution=resolution
            )
            return results
        else:
            # Single crossover (original behavior)
            stats = stitch_loop(
                fw_dir=fw_dir,
                bw_dir=bw_dir,
                output_dir=args.output_dir,
                orbit_period=args.orbit_period,
                crossover_frame=args.crossover,
                extension=args.extension,
                dry_run=args.dry_run,
                skip_crossover=skip_crossover
            )

            if args.video and not args.dry_run:
                create_video(args.output_dir, args.video, fps=args.fps, extension=args.extension,
                             resolution=resolution)

            return stats
    finally:
        # Clean up temp directories
        for temp_dir in temp_dirs:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)


if __name__ == '__main__':
    main()
