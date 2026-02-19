#!/usr/bin/env python3
"""
Real-time corruption checker for 17_the_one render.
Monitors new EXR files as they appear, runs multi-layer checks, logs anomalies.

With 256 samples + OIDN, frame-to-frame variation is very tight,
making corruption much easier to detect than at 32 samples.

Checks:
1. File size vs rolling window (±5 neighbors per cluster)
2. oiiotool --printstats for scanline corruption
3. Brightness/StdDev vs rolling window
4. Zero-size / partial-write detection
"""
import os, glob, time, json, subprocess, re, sys
from collections import defaultdict

EXR_DIR = "/Volumes/Mo 4TB/render/17_the_one_EXR"
LOG_FILE = "/Users/mo/github/ucl_eye/frame_integrity_check/results/realtime_corruption_log.json"
POLL_INTERVAL = 30  # seconds between scans
MIN_SIZE_MB = 100   # files below this are mid-write or corrupt
EXPECTED_SIZE_MB = 162  # known good size for 256-sample DWAB 21-channel
SIZE_THRESH = 0.02  # 2% file size deviation (tight for 256 samples)
BRIGHT_THRESH = 0.01  # 1% brightness deviation
STDDEV_THRESH = 0.01  # 1% stddev deviation
WINDOW = 5  # neighbors each side for rolling comparison

def get_stats(filepath):
    """Get avg brightness, stddev, and check for corruption via oiiotool."""
    try:
        r = subprocess.run(['oiiotool', filepath, '--printstats'],
                          capture_output=True, text=True, timeout=30)
        combined = (r.stdout + r.stderr).lower()
        is_scanline_corrupt = 'corrupt' in combined or 'unable' in combined or 'error' in combined

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
        return avg, stddev, is_scanline_corrupt, r.stdout + r.stderr
    except Exception as e:
        return None, None, True, str(e)


def detect_clusters(frame_nums):
    """Group frame numbers into render process clusters (gap > 100 = new cluster)."""
    if not frame_nums:
        return []
    clusters = []
    current = [frame_nums[0]]
    for i in range(1, len(frame_nums)):
        if frame_nums[i] - frame_nums[i-1] > 100:
            clusters.append(current)
            current = [frame_nums[i]]
        else:
            current.append(frame_nums[i])
    clusters.append(current)
    return clusters


# State
checked = set()       # frames we've already verified
frame_data = {}       # frame_num -> {size, avg, stddev}
anomalies = []        # list of anomaly dicts
stats_checked = 0
stats_clean = 0
stats_flagged = 0

# Load previous log if exists
if os.path.exists(LOG_FILE):
    try:
        with open(LOG_FILE) as f:
            prev = json.load(f)
        anomalies = prev.get('anomalies', [])
        checked = set(prev.get('checked_frames', []))
        frame_data = {int(k): v for k, v in prev.get('frame_data', {}).items()}
        stats_checked = prev.get('stats_checked', 0)
        stats_clean = prev.get('stats_clean', 0)
        stats_flagged = prev.get('stats_flagged', 0)
        print(f"Resumed: {len(checked)} previously checked, {len(anomalies)} anomalies logged", flush=True)
    except:
        pass

print(f"Real-time corruption checker started at {time.strftime('%H:%M:%S')}", flush=True)
print(f"Watching: {EXR_DIR}", flush=True)
print(f"Thresholds: size>{SIZE_THRESH*100}%, brightness>{BRIGHT_THRESH*100}%, stddev>{STDDEV_THRESH*100}%", flush=True)
print(f"Log: {LOG_FILE}", flush=True)
print(f"Poll interval: {POLL_INTERVAL}s\n", flush=True)

def save_log():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    # Only save last 200 frame_data entries to keep file small
    recent_data = dict(sorted(frame_data.items())[-2000:])
    with open(LOG_FILE, 'w') as f:
        json.dump({
            'last_updated': time.strftime('%Y-%m-%d %H:%M:%S'),
            'stats_checked': stats_checked,
            'stats_clean': stats_clean,
            'stats_flagged': stats_flagged,
            'anomalies': anomalies,
            'checked_frames': sorted(checked)[-5000:],  # keep last 5000
            'frame_data': {str(k): v for k, v in recent_data.items()},
        }, f, indent=2)

cycle = 0
while True:
    try:
        files = glob.glob(os.path.join(EXR_DIR, "*.exr"))
    except:
        time.sleep(POLL_INTERVAL)
        continue

    # Build frame map
    frame_map = {}
    for f in files:
        try:
            num = int(os.path.basename(f).replace('.exr', ''))
            frame_map[num] = f
        except:
            pass

    # Find unchecked frames that are likely finished writing
    to_check = []
    for num, path in sorted(frame_map.items()):
        if num in checked:
            continue
        try:
            sz = os.path.getsize(path)
            sz_mb = sz / (1024 * 1024)
        except:
            continue

        # Skip if file is still being written (< 100MB or very recent mtime)
        if sz_mb < MIN_SIZE_MB:
            # But flag zero-size immediately
            if sz == 0:
                anomalies.append({
                    'frame': num, 'type': 'zero_size',
                    'severity': 'HIGH', 'size_mb': 0,
                    'time': time.strftime('%H:%M:%S'),
                    'message': 'Zero-size EXR placeholder'
                })
                stats_flagged += 1
                checked.add(num)
                print(f"  *** ZERO-SIZE: frame {num} ***", flush=True)
            continue

        # Check mtime - skip if modified in last 5 seconds (still writing)
        try:
            mtime = os.path.getmtime(path)
            if time.time() - mtime < 5:
                continue
        except:
            continue

        to_check.append((num, path, sz_mb))

    if not to_check:
        cycle += 1
        if cycle % 10 == 0:  # status every ~5 min
            print(f"[{time.strftime('%H:%M:%S')}] Checked: {stats_checked}, Clean: {stats_clean}, Flagged: {stats_flagged}, Watching: {len(frame_map)} total frames", flush=True)
        time.sleep(POLL_INTERVAL)
        continue

    new_checks = 0
    new_flags = 0

    for num, path, sz_mb in to_check:
        issues = []

        # --- Check 1: File size ---
        frame_data[num] = {'size_mb': sz_mb}

        # Find neighbors in same cluster
        all_nums = sorted(frame_data.keys())
        # Find nearby frames (within 50 of this frame)
        neighbors = [n for n in all_nums if n != num and abs(n - num) < 50 and n in frame_data]
        if len(neighbors) >= 3:
            neighbor_sizes = [frame_data[n]['size_mb'] for n in neighbors[-WINDOW*2:]]
            avg_size = sum(neighbor_sizes) / len(neighbor_sizes)
            if avg_size > 0:
                size_dev = abs(sz_mb - avg_size) / avg_size
                if size_dev > SIZE_THRESH:
                    issues.append(f"size_deviation={size_dev*100:.2f}% ({sz_mb:.1f} vs avg {avg_size:.1f}MB)")

        # Gross size check vs expected
        if sz_mb < EXPECTED_SIZE_MB * 0.5:
            issues.append(f"extremely_small={sz_mb:.1f}MB (expected ~{EXPECTED_SIZE_MB}MB)")

        # --- Check 2: oiiotool printstats (scanline corruption + brightness) ---
        avg, stddev, is_scanline_corrupt, raw_output = get_stats(path)

        if is_scanline_corrupt:
            issues.append("scanline_corruption_detected")

        if avg:
            frame_data[num]['avg'] = avg
        if stddev:
            frame_data[num]['stddev'] = stddev

        # --- Check 3: Brightness/StdDev vs neighbors ---
        if avg and stddev and len(neighbors) >= 3:
            neighbor_avgs = [frame_data[n]['avg'] for n in neighbors[-WINDOW*2:] if 'avg' in frame_data[n]]
            neighbor_stds = [frame_data[n]['stddev'] for n in neighbors[-WINDOW*2:] if 'stddev' in frame_data[n]]

            if len(neighbor_avgs) >= 3:
                for ch, ch_name in enumerate(['R', 'G', 'B']):
                    n_avg = sum(a[ch] for a in neighbor_avgs) / len(neighbor_avgs)
                    if n_avg > 1e-6:
                        br_dev = abs(avg[ch] - n_avg) / n_avg
                        if br_dev > BRIGHT_THRESH:
                            issues.append(f"brightness_{ch_name}={br_dev*100:.2f}% (frame={avg[ch]:.4f} vs neighbors={n_avg:.4f})")

            if len(neighbor_stds) >= 3:
                for ch, ch_name in enumerate(['R', 'G', 'B']):
                    n_std = sum(s[ch] for s in neighbor_stds) / len(neighbor_stds)
                    if n_std > 1e-6:
                        sd_dev = abs(stddev[ch] - n_std) / n_std
                        if sd_dev > STDDEV_THRESH:
                            issues.append(f"stddev_{ch_name}={sd_dev*100:.2f}% (frame={stddev[ch]:.4f} vs neighbors={n_std:.4f})")

        checked.add(num)
        stats_checked += 1
        new_checks += 1

        if issues:
            severity = "HIGH" if any('scanline' in i or 'extremely_small' in i or 'zero' in i for i in issues) else "MEDIUM"
            entry = {
                'frame': num, 'type': 'anomaly',
                'severity': severity,
                'issues': issues,
                'size_mb': round(sz_mb, 2),
                'avg_rgb': [round(x, 6) for x in avg] if avg else None,
                'stddev_rgb': [round(x, 6) for x in stddev] if stddev else None,
                'time': time.strftime('%H:%M:%S'),
            }
            anomalies.append(entry)
            stats_flagged += 1
            new_flags += 1
            tag = "***" if severity == "HIGH" else "**"
            print(f"  {tag} FRAME {num} [{severity}]: {'; '.join(issues)}", flush=True)
        else:
            stats_clean += 1

    if new_checks > 0:
        print(f"[{time.strftime('%H:%M:%S')}] Checked {new_checks} new frames: {new_checks - new_flags} clean, {new_flags} flagged | Total: {stats_checked} checked, {stats_flagged} flagged", flush=True)
        save_log()

    time.sleep(POLL_INTERVAL)
