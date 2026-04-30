#!/usr/bin/env python3
"""
Retrospective EXR pair diff scanner.
Diffs all consecutive EXR pairs (Composite RGB only) and flags z-score outliers.
Outputs results to JSON and prints flagged frames.

Usage:
    python3 exr_diff_retro.py                    # default paths
    python3 exr_diff_retro.py --workers 4        # parallel workers
"""

import os, sys, glob, re, json, time, argparse
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np

EXR_DIR = "/Volumes/Mo 4TB 2/render/17_fw_the_one_512s_EXR"
OUTPUT = "/Users/mo/github/ucl_eye/frame_integrity_check/results/exr_diff_retro.json"
CLUSTER_GAP = 100
PIXEL_SIGMA = 5


def exr_pair_diff(pair):
    """Diff two EXR files, return (frame_num, result_dict)."""
    num, path_a, path_b = pair
    try:
        r = subprocess.run(
            ['oiiotool',
             path_a, '--ch', 'Composite.R,Composite.G,Composite.B',
             path_b, '--ch', 'Composite.R,Composite.G,Composite.B',
             '--diff'],
            capture_output=True, text=True, timeout=60
        )
        output = r.stdout + r.stderr
        result = {}
        for line in output.split('\n'):
            if 'Mean error' in line:
                m = re.search(r'Mean error\s*=\s*([\d.eE+\-]+)', line)
                if m:
                    result['mean_error'] = float(m.group(1))
            elif 'RMS error' in line:
                m = re.search(r'RMS error\s*=\s*([\d.eE+\-]+)', line)
                if m:
                    result['rms_error'] = float(m.group(1))
            elif 'Peak SNR' in line:
                m = re.search(r'Peak SNR\s*=\s*([\d.eE+\-]+)', line)
                if m:
                    result['peak_snr'] = float(m.group(1))
            elif 'Max error' in line:
                m = re.search(r'Max error\s*=\s*([\d.eE+\-]+)', line)
                if m:
                    result['max_error'] = float(m.group(1))
        return (num, result if result else None)
    except Exception as e:
        return (num, None)


def robust_z(value, arr):
    median = np.median(arr)
    mad = np.median(np.abs(arr - median)) * 1.4826
    if mad < 1e-10:
        return 0.0
    return (value - median) / mad


def main():
    parser = argparse.ArgumentParser(description="Retrospective EXR pair diff scanner")
    parser.add_argument("--exr-dir", default=EXR_DIR)
    parser.add_argument("--workers", type=int, default=3, help="Parallel workers (each uses ~2s CPU)")
    parser.add_argument("--output", default=OUTPUT)
    args = parser.parse_args()

    exr_files = {}
    for f in glob.glob(os.path.join(args.exr_dir, "*.exr")):
        try:
            num = int(os.path.basename(f).replace('.exr', ''))
            if os.path.getsize(f) > 0:
                exr_files[num] = f
        except:
            pass

    sorted_nums = sorted(exr_files.keys())
    print(f"Found {len(sorted_nums)} EXRs, range {sorted_nums[0]}-{sorted_nums[-1]}")

    # Build pairs (consecutive within same cluster)
    pairs = []
    for i in range(1, len(sorted_nums)):
        num = sorted_nums[i]
        prev = sorted_nums[i - 1]
        if num - prev <= CLUSTER_GAP:
            pairs.append((num, exr_files[prev], exr_files[num]))

    print(f"Will diff {len(pairs)} consecutive pairs with {args.workers} workers")
    print(f"Estimated time: {len(pairs) * 2.2 / args.workers / 60:.0f} minutes")
    print()

    results = {}
    done = 0
    t0 = time.time()

    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(exr_pair_diff, p): p[0] for p in pairs}
        for future in as_completed(futures):
            num, diff = future.result()
            done += 1
            if diff:
                results[num] = diff

            if done % 500 == 0:
                elapsed = time.time() - t0
                rate = done / elapsed
                remaining = (len(pairs) - done) / rate if rate > 0 else 0
                print(f"  [{done}/{len(pairs)}] {rate:.1f} pairs/s, ETA {remaining/60:.0f} min", flush=True)

    elapsed = time.time() - t0
    print(f"\nDiffed {len(pairs)} pairs in {elapsed/60:.1f} minutes ({len(pairs)/elapsed:.1f}/s)")

    # Compute z-scores
    rms_values = np.array([r['rms_error'] for r in results.values() if 'rms_error' in r])
    max_values = np.array([r['max_error'] for r in results.values() if 'max_error' in r])
    mean_values = np.array([r['mean_error'] for r in results.values() if 'mean_error' in r])

    print(f"\nRMS error:  median={np.median(rms_values):.4f}, MAD*1.48={np.median(np.abs(rms_values - np.median(rms_values)))*1.4826:.4f}")
    print(f"Max error:  median={np.median(max_values):.2f}, MAD*1.48={np.median(np.abs(max_values - np.median(max_values)))*1.4826:.2f}")
    print(f"Mean error: median={np.median(mean_values):.6f}, MAD*1.48={np.median(np.abs(mean_values - np.median(mean_values)))*1.4826:.6f}")

    flagged = []
    for num, diff in sorted(results.items()):
        issues = []
        if 'rms_error' in diff:
            z = robust_z(diff['rms_error'], rms_values)
            diff['rms_z'] = round(z, 2)
            if z > PIXEL_SIGMA:
                issues.append(f"rms_z={z:.1f} (val={diff['rms_error']:.4f})")
        if 'max_error' in diff:
            z = robust_z(diff['max_error'], max_values)
            diff['maxerr_z'] = round(z, 2)
            if z > PIXEL_SIGMA:
                issues.append(f"maxerr_z={z:.1f} (val={diff['max_error']:.2f})")
        if 'mean_error' in diff:
            z = robust_z(diff['mean_error'], mean_values)
            diff['mean_z'] = round(z, 2)
            if z > PIXEL_SIGMA:
                issues.append(f"mean_z={z:.1f} (val={diff['mean_error']:.6f})")

        if issues:
            flagged.append({'frame': num, 'issues': issues, 'diff': diff})

    print(f"\nFlagged {len(flagged)} frames (z > {PIXEL_SIGMA}):")
    for f in flagged[:50]:
        print(f"  Frame {f['frame']}: {'; '.join(f['issues'])}")
    if len(flagged) > 50:
        print(f"  ... and {len(flagged) - 50} more")

    # Save full results
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w') as fp:
        json.dump({
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_pairs': len(pairs),
            'total_results': len(results),
            'flagged_count': len(flagged),
            'sigma': PIXEL_SIGMA,
            'stats': {
                'rms_median': round(float(np.median(rms_values)), 6),
                'rms_mad': round(float(np.median(np.abs(rms_values - np.median(rms_values))) * 1.4826), 6),
                'max_median': round(float(np.median(max_values)), 4),
                'max_mad': round(float(np.median(np.abs(max_values - np.median(max_values))) * 1.4826), 4),
            },
            'flagged': flagged,
            'all_results': {str(k): v for k, v in sorted(results.items())},
        }, fp, indent=2)
    print(f"\nFull results saved to {args.output}")


if __name__ == '__main__':
    main()
