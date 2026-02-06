#!/usr/bin/env python3
"""
Frame Integrity Checker for UCL Eye render outputs.

Compares adjacent frames to detect corrupted renders (partial blackout,
missing particles, pure black frames, etc.) using multiple metrics.

READ-ONLY: This script never modifies any frame files.

Usage:
    python check_frames.py <frame_directory> [--output results.json]
    python check_frames.py --scan-all  # Scan all known continuous ranges
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
from PIL import Image


# ---------------------------------------------------------------------------
# Downscale factor — we don't need full 8K resolution to detect corruption.
# 1/8 of 8K ≈ 1K, which is plenty for statistical comparisons.
# ---------------------------------------------------------------------------
DOWNSCALE = 8

# Threshold for "dark" pixels (0-255 scale, per channel mean)
DARK_THRESHOLD = 10

# Known continuous step-1 frame ranges (drive_path, subdir, start, end)
def _update_downscale(val):
    global DOWNSCALE
    DOWNSCALE = val


KNOWN_RANGES = [
    ("/Volumes/Mo 4TB 2/render/16_final_path_fw_no_hero", "FW (Drive 2)", 4, 50062),
    ("/Volumes/Mo 4TB/render/16_final_path_fw_no_hero", "FW (Drive 1)", 50063, 65803),
    ("/Volumes/Mo 4TB 4/render/16_final_path_bw_no_hero", "BW (Drive 4)", 46, 7759),
    ("/Volumes/Mo 4TB 3/render/16_final_path_bw_no_hero", "BW (Drive 3)", 7750, 25710),
]


def load_frame(path, downscale=DOWNSCALE):
    """Load a JPEG frame as a numpy array, downscaled for efficiency."""
    img = Image.open(path)
    if downscale > 1:
        w, h = img.size
        img = img.resize((w // downscale, h // downscale), Image.BILINEAR)
    return np.array(img, dtype=np.float32)


def compute_frame_stats(path, downscale=DOWNSCALE):
    """Compute per-frame statistics (no comparison needed)."""
    arr = load_frame(path, downscale)
    # Mean across all channels
    mean_brightness = float(np.mean(arr))
    # Standard deviation
    std_dev = float(np.std(arr))
    # Dark pixel ratio: fraction of pixels where mean(R,G,B) < threshold
    pixel_means = np.mean(arr, axis=2)  # (H, W)
    dark_ratio = float(np.mean(pixel_means < DARK_THRESHOLD))
    return mean_brightness, std_dev, dark_ratio


def compute_pair_metrics(arr_a, arr_b):
    """Compute comparison metrics between two frames."""
    # 1. Mean Absolute Difference (MAD)
    mad = float(np.mean(np.abs(arr_a - arr_b)))

    # 2. Max local difference (divide into grid, find worst block)
    h, w = arr_a.shape[:2]
    block_h, block_w = max(1, h // 8), max(1, w // 8)
    max_block_diff = 0.0
    for y in range(0, h - block_h + 1, block_h):
        for x in range(0, w - block_w + 1, block_w):
            block_a = arr_a[y:y+block_h, x:x+block_w]
            block_b = arr_b[y:y+block_h, x:x+block_w]
            block_diff = float(np.mean(np.abs(block_a - block_b)))
            max_block_diff = max(max_block_diff, block_diff)

    # 3. Histogram chi-squared distance (grayscale)
    gray_a = np.mean(arr_a, axis=2).ravel()
    gray_b = np.mean(arr_b, axis=2).ravel()
    hist_a, _ = np.histogram(gray_a, bins=64, range=(0, 255))
    hist_b, _ = np.histogram(gray_b, bins=64, range=(0, 255))
    hist_a = hist_a.astype(np.float64) + 1e-10
    hist_b = hist_b.astype(np.float64) + 1e-10
    chi_sq = float(np.sum((hist_a - hist_b) ** 2 / (hist_a + hist_b)))

    # 4. Correlation coefficient
    flat_a = arr_a.ravel()
    flat_b = arr_b.ravel()
    # Subsample for speed (every 16th pixel)
    flat_a = flat_a[::16]
    flat_b = flat_b[::16]
    corr = float(np.corrcoef(flat_a, flat_b)[0, 1])

    # 5. Percentage of pixels with large per-pixel difference
    pixel_diff = np.mean(np.abs(arr_a - arr_b), axis=2)  # mean across channels
    large_diff_ratio = float(np.mean(pixel_diff > 30))

    return {
        "mad": mad,
        "max_block_diff": max_block_diff,
        "hist_chi_sq": chi_sq,
        "correlation": corr,
        "large_diff_ratio": large_diff_ratio,
    }


def analyze_single_frame(args):
    """Worker function for parallel processing. Analyzes one frame and its
    comparison with the previous frame."""
    frame_path, prev_path, downscale = args
    frame_num = int(Path(frame_path).stem)

    result = {"frame": frame_num, "path": str(frame_path)}

    try:
        arr = load_frame(frame_path, downscale)
        mean_b, std_d, dark_r = float(np.mean(arr)), float(np.std(arr)), float(
            np.mean(np.mean(arr, axis=2) < DARK_THRESHOLD)
        )
        result["mean_brightness"] = round(mean_b, 2)
        result["std_dev"] = round(std_d, 2)
        result["dark_ratio"] = round(dark_r, 6)

        if prev_path is not None:
            arr_prev = load_frame(prev_path, downscale)
            pair = compute_pair_metrics(arr_prev, arr)
            result["mad"] = round(pair["mad"], 4)
            result["max_block_diff"] = round(pair["max_block_diff"], 4)
            result["hist_chi_sq"] = round(pair["hist_chi_sq"], 2)
            result["correlation"] = round(pair["correlation"], 6)
            result["large_diff_ratio"] = round(pair["large_diff_ratio"], 6)
        result["error"] = None
    except Exception as e:
        result["error"] = str(e)

    return result


def find_continuous_frames(directory, start=None, end=None):
    """Find all JPG frames in directory, sorted, filtered to [start, end]."""
    d = Path(directory)
    if not d.exists():
        return []
    frames = []
    for f in d.iterdir():
        if f.suffix.lower() == ".jpg" and not f.name.startswith("_"):
            try:
                num = int(f.stem)
                if start is not None and num < start:
                    continue
                if end is not None and num > end:
                    continue
                frames.append((num, f))
            except ValueError:
                continue
    frames.sort(key=lambda x: x[0])
    # Filter to only step-1 sequences
    if not frames:
        return []
    filtered = [frames[0]]
    for i in range(1, len(frames)):
        if frames[i][0] - frames[i - 1][0] == 1:
            filtered.append(frames[i])
        else:
            # Gap detected — only keep the longer run
            if len(filtered) < i:
                # We already have a run going, a gap means it broke
                break
    # Actually, let's just return consecutive frames and let the caller handle gaps
    return frames


def scan_range(directory, label, start, end, output_dir, workers=4, throttle=0):
    """Scan a continuous frame range and detect anomalies."""
    print(f"\n{'='*70}")
    print(f"Scanning: {label}")
    print(f"Directory: {directory}")
    print(f"Expected range: {start} -> {end}")
    print(f"{'='*70}")

    frames = find_continuous_frames(directory, start, end)
    if not frames:
        print(f"  ERROR: No frames found in {directory}")
        return None

    # Filter to step-1 only
    step1_frames = [frames[0]]
    for i in range(1, len(frames)):
        if frames[i][0] - frames[i - 1][0] == 1:
            step1_frames.append(frames[i])
        elif len(step1_frames) < 100:
            # Very short run, restart
            step1_frames = [frames[i]]
        else:
            break  # End of continuous run

    frames = step1_frames
    print(f"  Found {len(frames)} consecutive step-1 frames: {frames[0][0]} -> {frames[-1][0]}")

    # Build work items: (current_path, prev_path_or_None, downscale)
    work = []
    for i, (num, path) in enumerate(frames):
        prev_path = str(frames[i - 1][1]) if i > 0 else None
        work.append((str(path), prev_path, DOWNSCALE))

    # Process with progress reporting
    results = [None] * len(work)
    t0 = time.time()
    completed = 0

    if throttle > 0:
        # Sequential mode with throttling to reduce I/O pressure
        print(f"  Throttled mode: {throttle}s sleep between frames, {workers} worker(s)")
        for i, w in enumerate(work):
            results[i] = analyze_single_frame(w)
            completed += 1
            if completed % 500 == 0 or completed == len(work):
                elapsed = time.time() - t0
                fps = completed / elapsed if elapsed > 0 else 0
                eta = (len(work) - completed) / fps if fps > 0 else 0
                print(f"  Progress: {completed}/{len(work)} ({fps:.1f} frames/s, ETA {eta:.0f}s)")
            time.sleep(throttle)
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            future_to_idx = {executor.submit(analyze_single_frame, w): i for i, w in enumerate(work)}
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                results[idx] = future.result()
                completed += 1
                if completed % 500 == 0 or completed == len(work):
                    elapsed = time.time() - t0
                    fps = completed / elapsed if elapsed > 0 else 0
                    eta = (len(work) - completed) / fps if fps > 0 else 0
                    print(f"  Progress: {completed}/{len(work)} ({fps:.1f} frames/s, ETA {eta:.0f}s)")

    elapsed = time.time() - t0
    print(f"  Done in {elapsed:.1f}s ({len(work)/elapsed:.1f} frames/s)")

    # Detect anomalies using statistical outliers
    anomalies = detect_anomalies(results)

    # Save detailed results
    safe_label = label.replace(" ", "_").replace("(", "").replace(")", "")
    result_path = Path(output_dir) / f"results_{safe_label}.json"
    with open(result_path, "w") as f:
        json.dump({
            "label": label,
            "directory": directory,
            "frame_range": [frames[0][0], frames[-1][0]],
            "frame_count": len(frames),
            "scan_time_s": round(elapsed, 1),
            "anomalies": anomalies,
            "all_results": results,
        }, f, indent=2)
    print(f"  Results saved to: {result_path}")

    # Print anomalies
    if anomalies:
        print(f"\n  *** ANOMALIES DETECTED: {len(anomalies)} ***")
        for a in anomalies[:20]:
            print(f"    Frame {a['frame']}: {', '.join(a['reasons'])}")
        if len(anomalies) > 20:
            print(f"    ... and {len(anomalies) - 20} more")
    else:
        print(f"  No anomalies detected.")

    return anomalies


def detect_anomalies(results):
    """Detect anomalous frames using multiple criteria."""
    anomalies = []

    # Gather metric arrays (skip frames with errors)
    valid = [r for r in results if r and r.get("error") is None]

    # Per-frame metrics
    brightnesses = np.array([r["mean_brightness"] for r in valid])
    std_devs = np.array([r["std_dev"] for r in valid])
    dark_ratios = np.array([r["dark_ratio"] for r in valid])

    # Pair metrics (skip first frame which has no predecessor)
    pair_valid = [r for r in valid if "mad" in r]
    if pair_valid:
        mads = np.array([r["mad"] for r in pair_valid])
        max_blocks = np.array([r["max_block_diff"] for r in pair_valid])
        chi_sqs = np.array([r["hist_chi_sq"] for r in pair_valid])
        corrs = np.array([r["correlation"] for r in pair_valid])
        large_diffs = np.array([r["large_diff_ratio"] for r in pair_valid])

        # Compute robust statistics (median + MAD-based)
        mad_median = np.median(mads)
        mad_mad = np.median(np.abs(mads - mad_median)) * 1.4826  # scale to sigma

        block_median = np.median(max_blocks)
        block_mad = np.median(np.abs(max_blocks - block_median)) * 1.4826

        chi_median = np.median(chi_sqs)
        chi_mad = np.median(np.abs(chi_sqs - chi_median)) * 1.4826

        corr_median = np.median(corrs)
        corr_mad = np.median(np.abs(corrs - corr_median)) * 1.4826

    bright_median = np.median(brightnesses)
    bright_mad = np.median(np.abs(brightnesses - bright_median)) * 1.4826

    SIGMA_THRESH = 5  # Flag frames > 5 sigma from median

    for r in valid:
        reasons = []
        frame = r["frame"]

        # Check 1: Very dark frame
        if r["mean_brightness"] < 5:
            reasons.append(f"near-black frame (brightness={r['mean_brightness']:.1f})")
        elif bright_mad > 0:
            z = abs(r["mean_brightness"] - bright_median) / bright_mad
            if z > SIGMA_THRESH:
                reasons.append(f"unusual brightness ({r['mean_brightness']:.1f}, z={z:.1f})")

        # Check 2: High dark pixel ratio
        if r["dark_ratio"] > 0.5:
            reasons.append(f"majority dark pixels ({r['dark_ratio']:.1%})")

        # Check 3: Very low std dev (uniform frame)
        if r["std_dev"] < 5:
            reasons.append(f"very low variance (std={r['std_dev']:.1f})")

        # Pair-wise checks
        if "mad" in r and pair_valid:
            # Check 4: Large frame-to-frame difference
            if mad_mad > 0:
                z = (r["mad"] - mad_median) / mad_mad
                if z > SIGMA_THRESH:
                    reasons.append(f"high MAD ({r['mad']:.2f}, z={z:.1f})")

            # Check 5: Large block difference
            if block_mad > 0:
                z = (r["max_block_diff"] - block_median) / block_mad
                if z > SIGMA_THRESH:
                    reasons.append(f"high block diff ({r['max_block_diff']:.2f}, z={z:.1f})")

            # Check 6: Histogram shift
            if chi_mad > 0:
                z = (r["hist_chi_sq"] - chi_median) / chi_mad
                if z > SIGMA_THRESH:
                    reasons.append(f"histogram shift (chi²={r['hist_chi_sq']:.0f}, z={z:.1f})")

            # Check 7: Low correlation
            if corr_mad > 0 and r["correlation"] < corr_median - SIGMA_THRESH * corr_mad:
                z = (corr_median - r["correlation"]) / corr_mad
                reasons.append(f"low correlation ({r['correlation']:.4f}, z={z:.1f})")

            # Check 8: Many pixels changed significantly
            if r["large_diff_ratio"] > 0.3:
                reasons.append(f"widespread change ({r['large_diff_ratio']:.1%} pixels)")

        # Check for read errors
        if r.get("error"):
            reasons.append(f"read error: {r['error']}")

        if reasons:
            anomalies.append({"frame": frame, "reasons": reasons, "metrics": r})

    return anomalies


def main():
    parser = argparse.ArgumentParser(description="Frame integrity checker for UCL Eye renders")
    parser.add_argument("directory", nargs="?", help="Frame directory to scan")
    parser.add_argument("--scan-all", action="store_true", help="Scan all known continuous ranges")
    parser.add_argument("--start", type=int, help="Start frame number")
    parser.add_argument("--end", type=int, help="End frame number")
    parser.add_argument("--output-dir", default=None, help="Output directory for results")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--downscale", type=int, default=DOWNSCALE, help="Downscale factor")
    parser.add_argument("--throttle", type=float, default=0, help="Sleep seconds between frames to reduce I/O pressure")
    args = parser.parse_args()

    # Update module-level downscale if overridden
    if args.downscale != DOWNSCALE:
        _update_downscale(args.downscale)

    output_dir = args.output_dir or str(Path(__file__).parent / "results")
    os.makedirs(output_dir, exist_ok=True)

    all_anomalies = {}

    if args.scan_all:
        for directory, label, start, end in KNOWN_RANGES:
            if not Path(directory).exists():
                print(f"\nSKIPPING {label}: {directory} not mounted")
                continue
            anomalies = scan_range(directory, label, start, end, output_dir, args.workers, args.throttle)
            if anomalies is not None:
                all_anomalies[label] = anomalies
    elif args.directory:
        label = Path(args.directory).name
        anomalies = scan_range(args.directory, label, args.start, args.end, output_dir, args.workers, args.throttle)
        if anomalies is not None:
            all_anomalies[label] = anomalies
    else:
        parser.print_help()
        sys.exit(1)

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    total_anomalies = 0
    for label, anomalies in all_anomalies.items():
        print(f"  {label}: {len(anomalies)} anomalies")
        total_anomalies += len(anomalies)
    print(f"  TOTAL: {total_anomalies} anomalous frames")
    print(f"  Results saved in: {output_dir}/")


if __name__ == "__main__":
    main()
