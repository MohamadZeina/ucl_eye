#!/usr/bin/env python3
"""
Real-time frame integrity monitor for render 17 (512-sample forward pass).

Continuously monitors both JPG and EXR outputs for corruption:

COARSE CHECKS:
  - File size anomaly vs rolling window of neighbors
  - Zero-size / extremely small file detection
  - EXR scanline corruption via oiiotool --printstats
  - Missing pair detection (JPG exists without EXR or vice versa)

SENSITIVE CHECKS (pixel-level, JPG):
  - Frame-to-frame Mean Absolute Difference (MAD)
  - Max local block difference (8x8 grid)
  - Correlation coefficient between consecutive frames
  - Per-frame brightness and contrast anomalies
  - Large-diff pixel ratio (% of pixels changing > threshold)

SENSITIVE CHECKS (EXR):
  - Per-channel brightness deviation vs neighbors
  - Per-channel stddev deviation vs neighbors

Multi-frontier aware: detects render clusters via frame gaps,
only compares within the same cluster.

READ-ONLY: Never modifies or deletes any frame files.

Usage:
    python3 render17_monitor.py                  # default paths
    python3 render17_monitor.py --poll 60        # check every 60s
    python3 render17_monitor.py --batch          # one-shot scan, no loop
"""

import os, sys, glob, time, json, subprocess, re, argparse
import numpy as np
from PIL import Image
from collections import defaultdict

# ─── Configuration ───────────────────────────────────────────────────────────

JPG_DIR = "/Volumes/Mo 4TB 2/render/17_fw_the_one_512s"
EXR_DIR = "/Volumes/Mo 4TB 2/render/17_fw_the_one_512s_EXR"
LOG_FILE = "/Users/mo/github/ucl_eye/frame_integrity_check/results/render17_monitor.json"

POLL_INTERVAL = 30          # seconds between scans
DOWNSCALE = 8               # 8K → 1K for JPG pixel analysis
CLUSTER_GAP = 100           # frame gap > this = new render frontier

# Coarse thresholds
JPG_SIZE_THRESH = 0.10      # 10% JPG size deviation (JPGs vary more than EXR)
EXR_SIZE_THRESH = 0.02      # 2% EXR size deviation
EXR_MIN_SIZE_MB = 50        # EXR below this is suspect (512s ~65 MB)
JPG_MIN_SIZE_KB = 500       # JPG below this is suspect

# Sensitive thresholds (pixel-level, 512 samples = tight)
PIXEL_SIGMA = 5             # z-score threshold for MAD/block/correlation outliers
BRIGHT_THRESH_EXR = 0.01    # 1% EXR brightness deviation
STDDEV_THRESH_EXR = 0.01    # 1% EXR stddev deviation
WINDOW = 5                  # neighbors each side for rolling comparisons
MAX_PER_CYCLE = 50          # max frames to process per poll cycle (prevents stalls)

# ─── Helpers ─────────────────────────────────────────────────────────────────

def load_jpg(path):
    """Load JPG downscaled for pixel analysis."""
    img = Image.open(path)
    w, h = img.size
    img = img.resize((w // DOWNSCALE, h // DOWNSCALE), Image.BILINEAR)
    return np.array(img, dtype=np.float32)


def jpg_pair_metrics(arr_a, arr_b):
    """Pixel-level comparison between two consecutive JPG frames."""
    # MAD
    mad = float(np.mean(np.abs(arr_a - arr_b)))

    # Max block diff (8x8 grid)
    h, w = arr_a.shape[:2]
    bh, bw = max(1, h // 8), max(1, w // 8)
    max_block = 0.0
    for y in range(0, h - bh + 1, bh):
        for x in range(0, w - bw + 1, bw):
            d = float(np.mean(np.abs(arr_a[y:y+bh, x:x+bw] - arr_b[y:y+bh, x:x+bw])))
            max_block = max(max_block, d)

    # Correlation (subsampled for speed)
    fa, fb = arr_a.ravel()[::16], arr_b.ravel()[::16]
    corr = float(np.corrcoef(fa, fb)[0, 1]) if len(fa) > 10 else 1.0

    # Large-diff pixel ratio
    pixel_diff = np.mean(np.abs(arr_a - arr_b), axis=2)
    large_diff_ratio = float(np.mean(pixel_diff > 30))

    return {
        "mad": round(mad, 4),
        "max_block_diff": round(max_block, 4),
        "correlation": round(corr, 6),
        "large_diff_ratio": round(large_diff_ratio, 6),
    }


def jpg_frame_stats(arr):
    """Per-frame brightness and contrast stats."""
    mean_brightness = float(np.mean(arr))
    std_dev = float(np.std(arr))
    dark_ratio = float(np.mean(np.mean(arr, axis=2) < 10))
    return {
        "mean_brightness": round(mean_brightness, 2),
        "std_dev": round(std_dev, 2),
        "dark_ratio": round(dark_ratio, 6),
    }


def exr_stats(filepath):
    """Get EXR brightness/stddev and check scanline integrity via oiiotool."""
    try:
        r = subprocess.run(['oiiotool', filepath, '--printstats'],
                          capture_output=True, text=True, timeout=30)
        combined = (r.stdout + r.stderr).lower()
        is_corrupt = 'corrupt' in combined or 'unable' in combined or 'error' in combined

        avg = stddev = None
        for line in r.stdout.split('\n'):
            if 'Stats Avg' in line:
                nums = re.findall(r'[\d.]+', line)
                if len(nums) >= 3:
                    avg = tuple(float(x) for x in nums[:3])
            if 'Stats StdDev' in line:
                nums = re.findall(r'[\d.]+', line)
                if len(nums) >= 3:
                    stddev = tuple(float(x) for x in nums[:3])
        return avg, stddev, is_corrupt
    except Exception as e:
        return None, None, True


def detect_clusters(frame_nums):
    """Group frame numbers into render frontier clusters."""
    if not frame_nums:
        return []
    sorted_nums = sorted(frame_nums)
    clusters = [[sorted_nums[0]]]
    for i in range(1, len(sorted_nums)):
        if sorted_nums[i] - sorted_nums[i-1] > CLUSTER_GAP:
            clusters.append([sorted_nums[i]])
        else:
            clusters[-1].append(sorted_nums[i])
    return clusters


def find_cluster_neighbors(frame_num, frame_data, all_sorted, window=WINDOW):
    """Find neighbors within the same cluster for comparison."""
    idx = None
    for i, n in enumerate(all_sorted):
        if n == frame_num:
            idx = i
            break
    if idx is None:
        return []

    neighbors = []
    # Look backward
    for i in range(idx - 1, max(0, idx - window - 1) - 1, -1):
        n = all_sorted[i]
        if frame_num - n > CLUSTER_GAP:
            break
        if n in frame_data:
            neighbors.append(n)
    # Look forward
    for i in range(idx + 1, min(len(all_sorted), idx + window + 1)):
        n = all_sorted[i]
        if n - frame_num > CLUSTER_GAP:
            break
        if n in frame_data:
            neighbors.append(n)
    return neighbors


def prev_frame_in_cluster(frame_num, all_sorted):
    """Find the immediately preceding frame in the same cluster."""
    idx = None
    for i, n in enumerate(all_sorted):
        if n == frame_num:
            idx = i
            break
    if idx is None or idx == 0:
        return None
    prev = all_sorted[idx - 1]
    if frame_num - prev > CLUSTER_GAP:
        return None
    return prev


# ─── State ───────────────────────────────────────────────────────────────────

checked_jpg = set()
checked_exr = set()
frame_data = {}        # frame_num -> {jpg_size, exr_size, jpg_stats, exr_avg, ...}
pair_metrics = {}      # frame_num -> {mad, max_block_diff, correlation, ...}
anomalies = []
stats = {"checked": 0, "clean": 0, "flagged": 0}

# Running statistics for z-score computation (updated as we go)
mad_history = []
block_history = []
corr_history = []
brightness_history = []


def load_state():
    global checked_jpg, checked_exr, frame_data, pair_metrics, anomalies, stats
    global mad_history, block_history, corr_history, brightness_history
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE) as f:
                prev = json.load(f)
            checked_jpg = set(prev.get('checked_jpg', []))
            checked_exr = set(prev.get('checked_exr', []))
            frame_data = {int(k): v for k, v in prev.get('frame_data', {}).items()}
            pair_metrics = {int(k): v for k, v in prev.get('pair_metrics', {}).items()}
            anomalies = prev.get('anomalies', [])
            stats = prev.get('stats', stats)
            mad_history = prev.get('mad_history', [])
            block_history = prev.get('block_history', [])
            corr_history = prev.get('corr_history', [])
            brightness_history = prev.get('brightness_history', [])
            print(f"Resumed: {len(checked_jpg)} JPG + {len(checked_exr)} EXR checked, "
                  f"{len(anomalies)} anomalies", flush=True)
        except Exception as e:
            print(f"Could not load state: {e}", flush=True)


def save_state():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    # Keep recent frame_data to limit file size
    recent = dict(sorted(frame_data.items())[-3000:])
    recent_pairs = dict(sorted(pair_metrics.items())[-3000:])
    with open(LOG_FILE, 'w') as f:
        json.dump({
            'last_updated': time.strftime('%Y-%m-%d %H:%M:%S'),
            'jpg_dir': JPG_DIR,
            'exr_dir': EXR_DIR,
            'stats': stats,
            'anomalies': anomalies,
            'checked_jpg': sorted(checked_jpg)[-5000:],
            'checked_exr': sorted(checked_exr)[-5000:],
            'frame_data': {str(k): v for k, v in recent.items()},
            'pair_metrics': {str(k): v for k, v in recent_pairs.items()},
            'mad_history': mad_history[-500:],
            'block_history': block_history[-500:],
            'corr_history': corr_history[-500:],
            'brightness_history': brightness_history[-500:],
        }, f, indent=2)


def robust_z(value, history):
    """Compute z-score using median absolute deviation."""
    if len(history) < 20:
        return 0.0
    arr = np.array(history)
    median = np.median(arr)
    mad = np.median(np.abs(arr - median)) * 1.4826
    if mad < 1e-10:
        return 0.0
    return (value - median) / mad


# ─── Main scan logic ────────────────────────────────────────────────────────

def scan_cycle():
    global stats

    # Discover all frames
    jpg_files = {}
    for f in glob.glob(os.path.join(JPG_DIR, "*.jpg")):
        try:
            num = int(os.path.basename(f).replace('.jpg', ''))
            jpg_files[num] = f
        except:
            pass

    exr_files = {}
    for f in glob.glob(os.path.join(EXR_DIR, "*.exr")):
        try:
            num = int(os.path.basename(f).replace('.exr', ''))
            exr_files[num] = f
        except:
            pass

    all_frames = sorted(set(jpg_files.keys()) | set(exr_files.keys()))
    all_checked_data = sorted(frame_data.keys())

    new_checks = 0
    new_flags = 0

    # ── 1. Check new JPGs ────────────────────────────────────────────────
    new_jpgs = sorted(n for n in jpg_files if n not in checked_jpg)
    if new_jpgs:
        remaining = len(new_jpgs)
        new_jpgs = new_jpgs[:MAX_PER_CYCLE]
        if remaining > MAX_PER_CYCLE:
            print(f"[{time.strftime('%H:%M:%S')}] JPG backlog: {remaining} unchecked, processing {MAX_PER_CYCLE} this cycle", flush=True)
    for num in new_jpgs:
        path = jpg_files[num]
        try:
            sz = os.path.getsize(path)
            mtime = os.path.getmtime(path)
        except:
            continue

        # Skip if still being written
        if time.time() - mtime < 5:
            continue
        sz_kb = sz / 1024

        issues = []

        # -- Coarse: file size --
        if sz == 0:
            issues.append("ZERO_SIZE_JPG")
        elif sz_kb < JPG_MIN_SIZE_KB:
            issues.append(f"tiny_jpg={sz_kb:.0f}KB")

        neighbors = find_cluster_neighbors(num, frame_data, all_checked_data)
        if len(neighbors) >= 3:
            neighbor_sizes = [frame_data[n].get('jpg_size_kb', 0) for n in neighbors
                            if 'jpg_size_kb' in frame_data.get(n, {})]
            if len(neighbor_sizes) >= 3:
                avg_sz = sum(neighbor_sizes) / len(neighbor_sizes)
                if avg_sz > 0:
                    dev = abs(sz_kb - avg_sz) / avg_sz
                    if dev > JPG_SIZE_THRESH:
                        issues.append(f"jpg_size_dev={dev*100:.1f}% ({sz_kb:.0f} vs {avg_sz:.0f}KB)")

        # -- Sensitive: pixel analysis --
        try:
            arr = load_jpg(path)
            fs = jpg_frame_stats(arr)

            if num not in frame_data:
                frame_data[num] = {}
            frame_data[num].update({
                'jpg_size_kb': round(sz_kb, 1),
                'mean_brightness': fs['mean_brightness'],
                'std_dev': fs['std_dev'],
                'dark_ratio': fs['dark_ratio'],
            })

            brightness_history.append(fs['mean_brightness'])

            # Per-frame anomalies
            if fs['mean_brightness'] < 5:
                issues.append(f"near_black_frame brightness={fs['mean_brightness']:.1f}")
            elif len(brightness_history) >= 20:
                z = robust_z(fs['mean_brightness'], brightness_history)
                if abs(z) > PIXEL_SIGMA:
                    issues.append(f"brightness_z={z:.1f} (val={fs['mean_brightness']:.1f})")

            if fs['dark_ratio'] > 0.5:
                issues.append(f"majority_dark_pixels={fs['dark_ratio']:.1%}")
            if fs['std_dev'] < 5:
                issues.append(f"very_low_variance std={fs['std_dev']:.1f}")

            # -- Pair comparison with previous frame --
            prev_num = prev_frame_in_cluster(num, all_checked_data + [num])
            if prev_num is not None and prev_num in jpg_files:
                try:
                    arr_prev = load_jpg(jpg_files[prev_num])
                    pm = jpg_pair_metrics(arr_prev, arr)
                    pair_metrics[num] = pm

                    mad_history.append(pm['mad'])
                    block_history.append(pm['max_block_diff'])
                    corr_history.append(pm['correlation'])

                    # Z-score checks
                    if len(mad_history) >= 20:
                        z_mad = robust_z(pm['mad'], mad_history)
                        if z_mad > PIXEL_SIGMA:
                            issues.append(f"high_MAD z={z_mad:.1f} (val={pm['mad']:.2f})")

                    if len(block_history) >= 20:
                        z_block = robust_z(pm['max_block_diff'], block_history)
                        if z_block > PIXEL_SIGMA:
                            issues.append(f"high_block_diff z={z_block:.1f} (val={pm['max_block_diff']:.2f})")

                    if len(corr_history) >= 20:
                        z_corr = robust_z(pm['correlation'], corr_history)
                        if z_corr < -PIXEL_SIGMA:
                            issues.append(f"low_correlation z={z_corr:.1f} (val={pm['correlation']:.4f})")

                    if pm['large_diff_ratio'] > 0.3:
                        issues.append(f"widespread_change={pm['large_diff_ratio']:.1%}")

                except Exception as e:
                    pass  # prev frame might be mid-write

        except Exception as e:
            issues.append(f"jpg_read_error: {e}")

        checked_jpg.add(num)
        new_checks += 1

        if issues:
            severity = "HIGH" if any(k in str(issues) for k in ['ZERO', 'scanline', 'near_black', 'read_error']) else "MEDIUM"
            anomalies.append({
                'frame': num, 'source': 'jpg',
                'severity': severity, 'issues': issues,
                'time': time.strftime('%H:%M:%S'),
            })
            stats['flagged'] += 1
            new_flags += 1
            tag = "***" if severity == "HIGH" else "**"
            print(f"  {tag} JPG {num} [{severity}]: {'; '.join(issues)}", flush=True)
        else:
            stats['clean'] += 1

        stats['checked'] += 1

    # ── 2. Check new EXRs ────────────────────────────────────────────────
    new_exrs = sorted(n for n in exr_files if n not in checked_exr)
    if new_exrs:
        remaining = len(new_exrs)
        new_exrs = new_exrs[:MAX_PER_CYCLE]
        if remaining > MAX_PER_CYCLE:
            print(f"[{time.strftime('%H:%M:%S')}] EXR backlog: {remaining} unchecked, processing {MAX_PER_CYCLE} this cycle", flush=True)
    for num in new_exrs:
        path = exr_files[num]
        try:
            sz = os.path.getsize(path)
            mtime = os.path.getmtime(path)
        except:
            continue

        if time.time() - mtime < 5:
            continue
        sz_mb = sz / (1024 * 1024)

        issues = []

        # -- Coarse: file size --
        if sz == 0:
            issues.append("ZERO_SIZE_EXR")
        elif sz_mb < EXR_MIN_SIZE_MB:
            issues.append(f"small_exr={sz_mb:.1f}MB (expected ~65MB)")

        neighbors = find_cluster_neighbors(num, frame_data, all_checked_data)
        if len(neighbors) >= 3:
            neighbor_sizes = [frame_data[n].get('exr_size_mb', 0) for n in neighbors
                            if 'exr_size_mb' in frame_data.get(n, {})]
            if len(neighbor_sizes) >= 3:
                avg_sz = sum(neighbor_sizes) / len(neighbor_sizes)
                if avg_sz > 0:
                    dev = abs(sz_mb - avg_sz) / avg_sz
                    if dev > EXR_SIZE_THRESH:
                        issues.append(f"exr_size_dev={dev*100:.2f}% ({sz_mb:.1f} vs {avg_sz:.1f}MB)")

        # -- oiiotool integrity + brightness --
        avg, stddev, is_corrupt = exr_stats(path)

        if is_corrupt:
            issues.append("scanline_corruption_detected")

        if num not in frame_data:
            frame_data[num] = {}
        frame_data[num]['exr_size_mb'] = round(sz_mb, 2)
        if avg:
            frame_data[num]['exr_avg'] = [round(x, 6) for x in avg]
        if stddev:
            frame_data[num]['exr_stddev'] = [round(x, 6) for x in stddev]

        # -- Brightness/stddev vs neighbors --
        if avg and stddev and len(neighbors) >= 3:
            neighbor_avgs = [frame_data[n].get('exr_avg') for n in neighbors
                           if frame_data.get(n, {}).get('exr_avg')]
            neighbor_stds = [frame_data[n].get('exr_stddev') for n in neighbors
                           if frame_data.get(n, {}).get('exr_stddev')]

            if len(neighbor_avgs) >= 3:
                for ch, ch_name in enumerate(['R', 'G', 'B']):
                    n_avg = sum(a[ch] for a in neighbor_avgs) / len(neighbor_avgs)
                    if n_avg > 1e-6:
                        dev = abs(avg[ch] - n_avg) / n_avg
                        if dev > BRIGHT_THRESH_EXR:
                            issues.append(f"exr_bright_{ch_name}={dev*100:.2f}%")

            if len(neighbor_stds) >= 3:
                for ch, ch_name in enumerate(['R', 'G', 'B']):
                    n_std = sum(s[ch] for s in neighbor_stds) / len(neighbor_stds)
                    if n_std > 1e-6:
                        dev = abs(stddev[ch] - n_std) / n_std
                        if dev > STDDEV_THRESH_EXR:
                            issues.append(f"exr_stddev_{ch_name}={dev*100:.2f}%")

        checked_exr.add(num)
        new_checks += 1

        if issues:
            severity = "HIGH" if any(k in str(issues) for k in ['ZERO', 'scanline', 'small_exr']) else "MEDIUM"
            anomalies.append({
                'frame': num, 'source': 'exr',
                'severity': severity, 'issues': issues,
                'time': time.strftime('%H:%M:%S'),
            })
            stats['flagged'] += 1
            new_flags += 1
            tag = "***" if severity == "HIGH" else "**"
            print(f"  {tag} EXR {num} [{severity}]: {'; '.join(issues)}", flush=True)
        else:
            stats['clean'] += 1

        stats['checked'] += 1

    # ── 3. Cross-check: missing pairs ────────────────────────────────────
    # Only check frames that have been fully checked on at least one side
    # and are old enough that both should exist
    for num in sorted(checked_jpg & checked_exr):
        pass  # both exist, fine

    # Frames with JPG but no EXR (and not at a frontier edge)
    jpg_only = checked_jpg - set(exr_files.keys())
    for num in sorted(jpg_only):
        # Only flag if neighbors on both sides have EXRs (not a frontier edge)
        has_prev = any(n in exr_files for n in range(num - 5, num))
        has_next = any(n in exr_files for n in range(num + 1, num + 6))
        if has_prev and has_next:
            if not any(a['frame'] == num and 'missing_exr' in str(a.get('issues', ''))
                      for a in anomalies):
                anomalies.append({
                    'frame': num, 'source': 'cross_check',
                    'severity': 'MEDIUM',
                    'issues': ['missing_exr_for_existing_jpg'],
                    'time': time.strftime('%H:%M:%S'),
                })
                print(f"  ** FRAME {num}: JPG exists but no EXR (neighbors have EXRs)", flush=True)
                new_flags += 1

    # ── 4. Report clusters ───────────────────────────────────────────────
    if new_checks > 0:
        clusters = detect_clusters(sorted(jpg_files.keys()))
        cluster_info = []
        for c in clusters:
            cluster_info.append(f"{c[0]}..{c[-1]} ({len(c)})")
        print(f"[{time.strftime('%H:%M:%S')}] +{new_checks} checked ({new_flags} flagged) | "
              f"Total: {stats['checked']} checked, {stats['flagged']} flagged | "
              f"JPGs: {len(jpg_files)}, EXRs: {len(exr_files)} | "
              f"Frontiers: {', '.join(cluster_info)}", flush=True)
        save_state()

    return new_checks


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    global JPG_DIR, EXR_DIR, POLL_INTERVAL

    parser = argparse.ArgumentParser(description="Render 17 real-time frame monitor")
    parser.add_argument("--poll", type=int, default=POLL_INTERVAL, help="Poll interval in seconds")
    parser.add_argument("--batch", action="store_true", help="One-shot scan, no loop")
    parser.add_argument("--jpg-dir", default=JPG_DIR, help="JPG directory")
    parser.add_argument("--exr-dir", default=EXR_DIR, help="EXR directory")
    args = parser.parse_args()

    JPG_DIR = args.jpg_dir
    EXR_DIR = args.exr_dir
    POLL_INTERVAL = args.poll

    print(f"Render 17 Frame Monitor", flush=True)
    print(f"  JPG: {JPG_DIR}", flush=True)
    print(f"  EXR: {EXR_DIR}", flush=True)
    print(f"  Log: {LOG_FILE}", flush=True)
    print(f"  Poll: {POLL_INTERVAL}s | Downscale: {DOWNSCALE}x | Sigma: {PIXEL_SIGMA}", flush=True)
    print(f"  Thresholds: JPG size>{JPG_SIZE_THRESH*100}%, EXR size>{EXR_SIZE_THRESH*100}%, "
          f"EXR bright>{BRIGHT_THRESH_EXR*100}%, EXR stddev>{STDDEV_THRESH_EXR*100}%", flush=True)
    print(flush=True)

    load_state()

    if args.batch:
        scan_cycle()
        print(f"\nBatch scan complete. {stats['checked']} checked, {stats['flagged']} flagged.", flush=True)
        if anomalies:
            print(f"\nAnomalies:", flush=True)
            for a in anomalies[-20:]:
                print(f"  Frame {a['frame']} [{a['source']}] [{a['severity']}]: {'; '.join(a['issues'])}", flush=True)
        return

    cycle = 0
    while True:
        try:
            n = scan_cycle()
        except KeyboardInterrupt:
            print("\nStopping...", flush=True)
            save_state()
            break
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Error in scan cycle: {e}", flush=True)

        cycle += 1
        if n == 0 and cycle % 10 == 0:
            print(f"[{time.strftime('%H:%M:%S')}] Idle — {stats['checked']} checked, "
                  f"{stats['flagged']} flagged, waiting for new frames...", flush=True)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
