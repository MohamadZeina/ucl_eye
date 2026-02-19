#!/usr/bin/env python3
"""
Test each anomaly frame: is it real corruption or natural scene variation?
Compare frame vs neighbor, then two clean neighbors as baseline.
Ratio >> 1 = corrupt. Ratio ~1 = natural variation.
"""
import os, subprocess, json, time, re

with open('/tmp/anomaly_scan_results.json') as f:
    anomalies = json.load(f)

# Add frame 45
anomalies.append({'frame': 45, 'drive': 'D4_BW', 'brightness_dev_pct': 0.8, 'stddev_dev_pct': 0.7, 'size_dev_pct': 0.0})

DRIVE_PATHS = {
    'D1_FW': '/Volumes/Mo 4TB/render/16_final_path_fw_no_hero_EXR',
    'D2_FW': '/Volumes/Mo 4TB 2/render/16_final_path_fw_no_hero_EXR',
    'D3_BW': '/Volumes/Mo 4TB 3/render/16_final_path_bw_no_hero_EXR',
    'D4_BW': '/Volumes/Mo 4TB 4/render/16_final_path_bw_no_hero_EXR',
}

D4_STAGING = '/Volumes/Mo 4TB 4/render/staging_anomaly_d4_exr'
d4_staged_frames = set()
if os.path.exists(D4_STAGING):
    for f in os.listdir(D4_STAGING):
        if f.endswith('.exr') and not f.startswith('.'):
            d4_staged_frames.add(int(f.replace('.exr', '')))

anomaly_sets = {}
for a in anomalies:
    anomaly_sets.setdefault(a['drive'], set()).add(a['frame'])

def find_exr(drive, frame):
    d = DRIVE_PATHS[drive]
    for fmt in [f'{frame:04d}.exr', f'{frame:05d}.exr', f'{frame:06d}.exr', f'{frame}.exr']:
        p = os.path.join(d, fmt)
        if os.path.exists(p):
            return p
    # For D4 staged originals
    if drive == 'D4_BW' and frame in d4_staged_frames:
        for fmt in [f'{frame:04d}.exr', f'{frame:05d}.exr']:
            p = os.path.join(D4_STAGING, fmt)
            if os.path.exists(p):
                return p
    return None

def mean_error(a, b):
    try:
        r = subprocess.run(['oiiotool', a, b, '--diff'],
                          capture_output=True, text=True, timeout=30)
        for line in r.stdout.split('\n'):
            if 'Mean error' in line:
                nums = re.findall(r'[\d.]+e[+\-]?\d+|[\d.]+', line)
                if nums:
                    return float(nums[0])
    except:
        pass
    return None

print(f"Started at {time.strftime('%H:%M:%S')}, testing {len(anomalies)} frames", flush=True)

results = []
corrupt = []
skipped = 0

for i, a in enumerate(sorted(anomalies, key=lambda x: (x['drive'], x['frame']))):
    frame = a['frame']
    drive = a['drive']
    aset = anomaly_sets[drive]

    frame_path = find_exr(drive, frame)
    if not frame_path:
        skipped += 1
        continue

    # Find two clean neighbors (not in anomaly set)
    na_path = nb_path = None
    na_frame = nb_frame = None
    for off in range(2, 20):
        candidate = frame - off
        if candidate < 0:
            break
        if candidate in aset:
            continue
        p = find_exr(drive, candidate)
        if not p:
            continue
        if na_path is None:
            na_path, na_frame = p, candidate
        elif nb_path is None:
            nb_path, nb_frame = p, candidate
            break

    if not na_path or not nb_path:
        skipped += 1
        continue

    err_frame = mean_error(frame_path, na_path)
    err_base = mean_error(na_path, nb_path)

    if err_frame is None or err_base is None or err_base == 0:
        skipped += 1
        continue

    ratio = err_frame / err_base
    is_corrupt = ratio > 2.0

    entry = {
        'frame': frame, 'drive': drive,
        'err_vs_neighbor': err_frame, 'baseline': err_base,
        'ratio': round(ratio, 3),
        'likely_corrupt': is_corrupt,
    }
    results.append(entry)

    tag = "*** CORRUPT ***" if is_corrupt else "clean"
    if is_corrupt:
        corrupt.append(entry)

    if (i + 1) % 10 == 0 or is_corrupt:
        print(f"  [{i+1}/{len(anomalies)}] Frame {frame} ({drive}): ratio={ratio:.3f}x  {tag}", flush=True)

print(f"\n{'='*60}", flush=True)
print(f"DONE at {time.strftime('%H:%M:%S')}", flush=True)
print(f"Tested: {len(results)}, Skipped: {skipped}, Likely corrupt: {len(corrupt)}", flush=True)

if corrupt:
    print(f"\nCORRUPT FRAMES:", flush=True)
    for r in sorted(corrupt, key=lambda x: -x['ratio']):
        print(f"  Frame {r['frame']} ({r['drive']}): ratio {r['ratio']:.2f}x", flush=True)
else:
    print(f"\nNo real corruption — all anomalies are natural scene variation.", flush=True)

if results:
    ratios = sorted(r['ratio'] for r in results)
    print(f"\nRatio distribution:", flush=True)
    print(f"  Min:    {ratios[0]:.3f}x", flush=True)
    print(f"  Median: {ratios[len(ratios)//2]:.3f}x", flush=True)
    print(f"  95th:   {ratios[int(len(ratios)*0.95)]:.3f}x", flush=True)
    print(f"  Max:    {ratios[-1]:.3f}x", flush=True)

with open('/tmp/corruption_test_results.json', 'w') as f:
    json.dump({'results': results, 'corrupt': corrupt}, f, indent=2, default=str)
print(f"Saved to /tmp/corruption_test_results.json", flush=True)
