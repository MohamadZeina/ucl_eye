#!/usr/bin/env python3
"""Full EXR scan of D2 only, running in parallel."""
import os, subprocess, time, json, glob

exr_dir = "/Volumes/Mo 4TB 2/render/16_final_path_fw_no_hero_EXR"
label = "FW_D2_parallel"

exrs = sorted(glob.glob(os.path.join(exr_dir, "*.exr")))
total = len(exrs)
print(f"Parallel D2 scan: {total} EXRs in {exr_dir}", flush=True)

corrupt = []
t0 = time.time()
for i, filepath in enumerate(exrs):
    try:
        result = subprocess.run(
            ["oiiotool", filepath, "--printstats"],
            capture_output=True, text=True, timeout=30
        )
        combined = result.stdout + result.stderr
        if "corrupt" in combined.lower() or "unable" in combined.lower():
            fname = os.path.basename(filepath)
            corrupt.append(fname)
            print(f"  CORRUPT: {fname}", flush=True)
    except Exception as e:
        fname = os.path.basename(filepath)
        corrupt.append(fname)
        print(f"  ERROR: {fname} -- {e}", flush=True)

    if (i + 1) % 500 == 0:
        elapsed = time.time() - t0
        rate = (i + 1) / elapsed
        remaining = total - (i + 1)
        eta = remaining / rate / 60 if rate > 0 else 0
        print(f"  {label}: {i+1}/{total} ({rate:.1f}/s, ETA {eta:.0f}m)", flush=True)

elapsed = time.time() - t0
print(f"\n{label} DONE: {total} scanned in {elapsed/60:.1f}m, {len(corrupt)} corrupt", flush=True)
if corrupt:
    print(f"CORRUPT FILES: {corrupt}", flush=True)

with open("/tmp/d2_parallel_scan_results.json", "w") as f:
    json.dump({"drive": "D2", "total": total, "corrupt": corrupt, "elapsed_min": elapsed/60}, f, indent=2)
print("Results saved to /tmp/d2_parallel_scan_results.json", flush=True)
