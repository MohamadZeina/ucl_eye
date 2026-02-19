#!/usr/bin/env python3
"""
Symlink Sequence Generator for Seamless Loop Grading

Creates a directory of sequentially-numbered symlinks that combine
forward and backward camera passes into a single seamless loop.

Handles:
- Crossover logic (forward to meeting point, backward reversed to start)
- Frame step sizes (step-4, step-2, step-1) — easily switch as render progresses
- Multi-drive source directories (frames split across drives)
- Both JPG and EXR formats

The output can be imported directly into DaVinci Resolve, Topaz Video AI,
or any application expecting a continuous frame sequence.

Camera driver equations (Blender):
  Forward:  100 * ((frame - 4) / 65536) + 2.8037
  Backward: 100 * (-(frame - 4) / 65536) + 2.8037

Meeting frames: {4, 32772, 65540}
  - 50% crossover at frame 32772 → 1 visual orbit per loop
  - 0% crossover at frame 65540 → 2 visual orbits per loop
"""

import os
import argparse
from pathlib import Path


def find_frame(frame_num: int, directories: list[Path], extension: str) -> Path | None:
    """Find a frame file across multiple source directories."""
    name = f"{frame_num:04d}{extension}"
    for d in directories:
        path = d / name
        if path.exists() and path.stat().st_size > 0:
            return path
    return None


def generate_sequence(
    fw_dirs: list[Path],
    bw_dirs: list[Path],
    output_dir: Path,
    step: int = 4,
    orbit_period: int = 65536,
    frame_offset: int = 4,
    extension: str = ".exr",
    crossover_pct: int = 50,
    dry_run: bool = False,
) -> dict:
    """
    Generate symlink sequence for a seamless loop.

    The sequence plays forward camera frames from 0% to the crossover,
    then backward camera frames (reversed) from the crossover back to 0%.
    When looped, this creates continuous camera motion with the simulation
    playing forward then backward.

    50% crossover (default): 1 visual orbit per loop
    0% crossover: 2 visual orbits per loop
    """
    # Calculate crossover frame
    if crossover_pct == 50:
        crossover = orbit_period // 2 + frame_offset  # 32772
    elif crossover_pct == 0:
        crossover = orbit_period + frame_offset  # 65540
    else:
        crossover = int(orbit_period * crossover_pct / 100) + frame_offset

    # Snap crossover to step grid
    remainder = (crossover - frame_offset) % step
    if remainder != 0:
        crossover = crossover - remainder

    # Build forward sequence: frame_offset to crossover (inclusive)
    fw_frames = list(range(frame_offset, crossover + 1, step))

    # Build backward sequence (will be reversed):
    # frame_offset to crossover - step (skip crossover to avoid duplicate)
    bw_frames_ascending = list(range(frame_offset, crossover, step))
    bw_frames_reversed = list(reversed(bw_frames_ascending))

    # For a perfect loop, also skip frame_offset at the end of backward
    # (it would duplicate the first frame of forward when looping)
    if bw_frames_reversed and bw_frames_reversed[-1] == frame_offset:
        bw_frames_reversed = bw_frames_reversed[:-1]

    # Full sequence: forward then backward reversed
    sequence = [(f, 'fw') for f in fw_frames] + [(f, 'bw') for f in bw_frames_reversed]

    # Check which frames exist
    missing_fw = []
    missing_bw = []
    found_sequence = []

    for frame_num, source in sequence:
        dirs = fw_dirs if source == 'fw' else bw_dirs
        path = find_frame(frame_num, dirs, extension)
        if path:
            found_sequence.append((frame_num, source, path))
        else:
            if source == 'fw':
                missing_fw.append(frame_num)
            else:
                missing_bw.append(frame_num)

    stats = {
        'total_sequence': len(sequence),
        'found': len(found_sequence),
        'missing_fw': len(missing_fw),
        'missing_bw': len(missing_bw),
        'crossover_frame': crossover,
        'step': step,
        'fw_count': len(fw_frames),
        'bw_count': len(bw_frames_reversed),
    }

    print(f"Seamless loop sequence (step {step}, {crossover_pct}% crossover):")
    print(f"  Forward:  {len(fw_frames)} frames ({frame_offset} → {crossover})")
    print(f"  Backward: {len(bw_frames_reversed)} frames ({crossover - step} → {frame_offset + step}, reversed)")
    print(f"  Total:    {len(sequence)} frames")
    print(f"  Found:    {len(found_sequence)} / {len(sequence)}")
    if missing_fw:
        print(f"  Missing forward:  {len(missing_fw)} (first: {missing_fw[0]}, last: {missing_fw[-1]})")
    if missing_bw:
        print(f"  Missing backward: {len(missing_bw)} (first: {missing_bw[0]}, last: {missing_bw[-1]})")
    print(f"  Crossover at frame {crossover}")
    print()

    if dry_run:
        print("DRY RUN — no symlinks created")
        return stats

    # Create output directory (clean it first if it exists)
    if output_dir.exists():
        # Remove old symlinks only
        for f in output_dir.iterdir():
            if f.is_symlink():
                f.unlink()
        print(f"  Cleaned existing symlinks in {output_dir}")
    else:
        output_dir.mkdir(parents=True)

    # Create sequentially-numbered symlinks (0-indexed for DaVinci compatibility)
    for out_idx, (frame_num, source, src_path) in enumerate(found_sequence, start=0):
        link_name = f"{out_idx:06d}{extension}"
        link_path = output_dir / link_name
        link_path.symlink_to(src_path.resolve())

    print(f"Created {len(found_sequence)} symlinks in {output_dir}")
    print(f"  First: 000000{extension} → frame {found_sequence[0][0]} ({found_sequence[0][1]})")
    print(f"  Last:  {len(found_sequence) - 1:06d}{extension} → frame {found_sequence[-1][0]} ({found_sequence[-1][1]})")

    stats['output_dir'] = str(output_dir)
    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Generate symlink sequence for seamless loop grading',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Step-4 EXR sequence for DaVinci grading
  %(prog)s --step 4 --ext .exr --output /Volumes/Mo\\ 4TB/render/loop_step4_EXR

  # Step-2 when more frames are available
  %(prog)s --step 2 --ext .exr --output /Volumes/Mo\\ 4TB/render/loop_step2_EXR

  # Step-1 final full sequence
  %(prog)s --step 1 --ext .exr --output /Volumes/Mo\\ 4TB/render/loop_step1_EXR

  # JPG preview sequence
  %(prog)s --step 4 --ext .jpg --output /Volumes/Mo\\ 4TB/render/loop_step4_JPG

  # Dry run to see what would happen
  %(prog)s --step 4 --dry-run
        """
    )

    parser.add_argument('--step', type=int, default=4, help='Frame step size (default: 4)')
    parser.add_argument('--ext', default='.exr', help='File extension (default: .exr)')
    parser.add_argument('--output', type=Path, help='Output directory for symlinks')
    parser.add_argument('--crossover', type=int, default=50, choices=[0, 50],
                        help='Crossover position: 50 = half orbit (default), 0 = full orbit')
    parser.add_argument('--orbit-period', type=int, default=65536, help='Orbit period in frames')
    parser.add_argument('--frame-offset', type=int, default=4, help='First frame number')
    parser.add_argument('--dry-run', action='store_true', help='Show sequence without creating symlinks')

    # Source directories (with defaults for the UCL Eye render setup)
    parser.add_argument('--fw-dirs', type=Path, nargs='+',
                        help='Forward pass directories (searched in order)')
    parser.add_argument('--bw-dirs', type=Path, nargs='+',
                        help='Backward pass directories (searched in order)')

    args = parser.parse_args()

    # Defaults for UCL Eye render drives
    ext_suffix = 'EXR' if args.ext == '.exr' else args.ext.lstrip('.').upper()

    if args.fw_dirs:
        fw_dirs = args.fw_dirs
    else:
        fw_dirs = [
            Path(f'/Volumes/Mo 4TB/render/16_final_path_fw_no_hero_{ext_suffix}'),
            Path(f'/Volumes/Mo 4TB 2/render/16_final_path_fw_no_hero_{ext_suffix}'),
        ]
        # For JPG, directory name doesn't have the suffix
        if args.ext == '.jpg':
            fw_dirs = [
                Path('/Volumes/Mo 4TB/render/16_final_path_fw_no_hero'),
                Path('/Volumes/Mo 4TB 2/render/16_final_path_fw_no_hero'),
            ]

    if args.bw_dirs:
        bw_dirs = args.bw_dirs
    else:
        bw_dirs = [
            Path(f'/Volumes/Mo 4TB 4/render/16_final_path_bw_no_hero_{ext_suffix}'),
            Path(f'/Volumes/Mo 4TB 3/render/16_final_path_bw_no_hero_{ext_suffix}'),
            Path(f'/Volumes/Mo 4TB/render/16_final_path_bw_no_hero_{ext_suffix}'),
        ]
        if args.ext == '.jpg':
            bw_dirs = [
                Path('/Volumes/Mo 4TB 4/render/16_final_path_bw_no_hero'),
                Path('/Volumes/Mo 4TB 3/render/16_final_path_bw_no_hero'),
                Path('/Volumes/Mo 4TB/render/16_final_path_bw_no_hero'),
            ]

    # Filter to directories that actually exist
    fw_dirs = [d for d in fw_dirs if d.exists()]
    bw_dirs = [d for d in bw_dirs if d.exists()]

    print(f"Forward dirs:  {[str(d) for d in fw_dirs]}")
    print(f"Backward dirs: {[str(d) for d in bw_dirs]}")
    print()

    if not fw_dirs:
        print("ERROR: No forward pass directories found")
        return
    if not bw_dirs:
        print("ERROR: No backward pass directories found")
        return

    # Default output directory
    if args.output is None:
        ext_label = ext_suffix if args.ext != '.jpg' else 'JPG'
        args.output = Path(f'/Volumes/Mo 4TB/render/seamless_loop_step{args.step}_{ext_label}')

    stats = generate_sequence(
        fw_dirs=fw_dirs,
        bw_dirs=bw_dirs,
        output_dir=args.output,
        step=args.step,
        orbit_period=args.orbit_period,
        frame_offset=args.frame_offset,
        extension=args.ext,
        crossover_pct=args.crossover,
        dry_run=args.dry_run,
    )

    return stats


if __name__ == '__main__':
    main()
