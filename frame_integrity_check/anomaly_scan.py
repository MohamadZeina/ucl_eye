#!/usr/bin/env python3
"""
Two-phase anomaly detection across all drives.
Phase 1 (fast): File size analysis - flag frames with unusual sizes vs neighbors
Phase 2 (targeted): oiiotool stats on flagged frames to confirm blur/brightness anomalies
"""
import os, glob, sys, time, json, subprocess, re

DRIVES = [
    ("/Volumes/Mo 4TB/render/16_final_path_fw_no_hero_EXR", "D1_FW"),
    ("/Volumes/Mo 4TB 2/render/16_final_path_fw_no_hero_EXR", "D2_FW"),
    ("/Volumes/Mo 4TB 3/render/16_final_path_bw_no_hero_EXR", "D3_BW"),
    ("/Volumes/Mo 4TB 4/render/16_final_path_bw_no_hero_EXR", "D4_BW"),
]

WINDOW = 5        # neighbors each side
SIZE_THRESH = 0.001  # 0.1% file size deviation to flag for phase 2
BRIGHT_THRESH = 0.005  # 0.5% brightness deviation = anomaly
STDDEV_THRESH = 0.004  # 0.4% stddev deviation = blur anomaly

def get_frame_num(path):
    return int(os.path.basename(path).replace('.exr', ''))

def get_stats(filepath):
    """Get avg brightness and stddev from oiiotool"""
    result = subprocess.run(['oiiotool', filepath, '--printstats'],
                          capture_output=True, text=True, timeout=30)
    avg = stddev = None
    for line in result.stdout.split('\n'):
        if 'Stats Avg' in line:
            nums = re.findall(r'[\d.]+', line)
            if len(nums) >= 3:
                avg = (float(nums[0]), float(nums[1]), float(nums[2]))
        if 'Stats StdDev' in line:
            nums = re.findall(r'[\d.]+', line)
            if len(nums) >= 3:
                stddev = (float(nums[0]), float(nums[1]), float(nums[2]))
    return avg, stddev

print(f"Anomaly scan started at {time.strftime('%H:%M:%S')}", flush=True)

all_anomalies = []

for exr_dir, label in DRIVES:
    print(f"\n{'='*60}", flush=True)
    print(f"Phase 1 (file sizes): {label} - {exr_dir}", flush=True)
    
    # Collect all file sizes
    t0 = time.time()
    files = sorted(glob.glob(os.path.join(exr_dir, "*.exr")))
    frames = []
    for f in files:
        try:
            num = get_frame_num(f)
            sz = os.path.getsize(f)
            frames.append((num, sz, f))
        except:
            pass
    
    frames.sort(key=lambda x: x[0])
    elapsed = time.time() - t0
    print(f"  {len(frames)} frames indexed in {elapsed:.1f}s", flush=True)
    
    # Flag frames with unusual file sizes vs rolling window
    flagged = []
    for i in range(WINDOW, len(frames) - WINDOW):
        num, sz, path = frames[i]
        # Get neighbor sizes
        neighbors = [frames[j][1] for j in range(i-WINDOW, i+WINDOW+1) if j != i]
        avg_neighbor = sum(neighbors) / len(neighbors)
        
        if avg_neighbor > 0:
            dev = abs(sz - avg_neighbor) / avg_neighbor
            if dev > SIZE_THRESH:
                flagged.append((num, sz, path, dev, avg_neighbor))
    
    print(f"  Phase 1: {len(flagged)} frames flagged (>{SIZE_THRESH*100}% size deviation)", flush=True)
    
    # Phase 2: oiiotool stats on flagged frames + their neighbors
    print(f"  Phase 2 (oiiotool stats on flagged + neighbors)...", flush=True)
    t0 = time.time()
    
    # Build set of frames to check: flagged + ±3 neighbors
    frame_lookup = {num: (sz, path) for num, sz, path in frames}
    frame_nums = [num for num, sz, path in frames]
    
    to_check = set()
    for num, sz, path, dev, avg_n in flagged:
        idx = frame_nums.index(num)
        for j in range(max(0, idx-3), min(len(frame_nums), idx+4)):
            to_check.add(frame_nums[j])
    
    # Get stats for all frames to check
    stats_cache = {}
    done = 0
    for num in sorted(to_check):
        sz, path = frame_lookup[num]
        try:
            avg, stddev = get_stats(path)
            if avg and stddev:
                stats_cache[num] = (avg, stddev)
        except:
            pass
        done += 1
        if done % 50 == 0:
            print(f"    {done}/{len(to_check)} stats collected", flush=True)
    
    # Now check each flagged frame for brightness/stddev anomaly
    drive_anomalies = []
    for num, sz, path, size_dev, avg_n_sz in flagged:
        if num not in stats_cache:
            continue
        avg, stddev = stats_cache[num]
        
        # Get neighbor stats
        idx = frame_nums.index(num)
        neighbor_avgs = []
        neighbor_stds = []
        for j in range(max(0, idx-3), min(len(frame_nums), idx+4)):
            n = frame_nums[j]
            if n != num and n in stats_cache:
                neighbor_avgs.append(stats_cache[n][0])
                neighbor_stds.append(stats_cache[n][1])
        
        if not neighbor_avgs:
            continue
        
        # Compare brightness
        n_avg_r = sum(a[0] for a in neighbor_avgs) / len(neighbor_avgs)
        n_avg_g = sum(a[1] for a in neighbor_avgs) / len(neighbor_avgs)
        n_avg_b = sum(a[2] for a in neighbor_avgs) / len(neighbor_avgs)
        
        br_dev_r = abs(avg[0] - n_avg_r) / max(n_avg_r, 1e-6)
        br_dev_g = abs(avg[1] - n_avg_g) / max(n_avg_g, 1e-6)
        br_dev_b = abs(avg[2] - n_avg_b) / max(n_avg_b, 1e-6)
        max_br_dev = max(br_dev_r, br_dev_g, br_dev_b)
        
        # Compare stddev (sharpness)
        n_std_r = sum(s[0] for s in neighbor_stds) / len(neighbor_stds)
        n_std_g = sum(s[1] for s in neighbor_stds) / len(neighbor_stds)
        n_std_b = sum(s[2] for s in neighbor_stds) / len(neighbor_stds)
        
        sd_dev_r = abs(stddev[0] - n_std_r) / max(n_std_r, 1e-6)
        sd_dev_g = abs(stddev[1] - n_std_g) / max(n_std_g, 1e-6)
        sd_dev_b = abs(stddev[2] - n_std_b) / max(n_std_b, 1e-6)
        max_sd_dev = max(sd_dev_r, sd_dev_g, sd_dev_b)
        
        is_anomaly = max_br_dev > BRIGHT_THRESH or max_sd_dev > STDDEV_THRESH
        
        if is_anomaly:
            drive_anomalies.append({
                'frame': num,
                'drive': label,
                'size_dev_pct': size_dev * 100,
                'brightness_dev_pct': max_br_dev * 100,
                'stddev_dev_pct': max_sd_dev * 100,
                'avg_rgb': avg,
                'stddev_rgb': stddev,
            })
            print(f"  ** ANOMALY: frame {num} - brightness {max_br_dev*100:.2f}%, blur {max_sd_dev*100:.2f}%, size {size_dev*100:.2f}%", flush=True)
    
    elapsed = time.time() - t0
    print(f"  Phase 2 done in {elapsed:.0f}s: {len(drive_anomalies)} anomalies confirmed", flush=True)
    all_anomalies.extend(drive_anomalies)

print(f"\n{'='*60}", flush=True)
print(f"SCAN COMPLETE at {time.strftime('%H:%M:%S')}", flush=True)
print(f"Total anomalies across all drives: {len(all_anomalies)}", flush=True)
for a in all_anomalies:
    print(f"  Frame {a['frame']} ({a['drive']}): brightness {a['brightness_dev_pct']:.2f}%, blur {a['stddev_dev_pct']:.2f}%", flush=True)

with open('/tmp/anomaly_scan_results.json', 'w') as f:
    json.dump(all_anomalies, f, indent=2, default=str)
print("Results saved to /tmp/anomaly_scan_results.json", flush=True)
