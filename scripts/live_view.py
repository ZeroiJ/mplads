import os
import shutil
import subprocess
import time

BASE = "/home/zeroij/mplads"
LOG = f"{BASE}/run.log"
METRICS = f"{BASE}/metrics/metrics.csv"
BEST = f"{BASE}/models/best/best.txt"


def tail_lines(path, n=1):
    if not os.path.exists(path):
        return []
    with open(path, "r", errors="ignore") as f:
        return f.read().replace("\r", "\n").strip().splitlines()[-n:]


def gpu_line():
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5)
        return out.stdout.strip()
    except Exception:
        return "nvidia-smi unavailable"


def main():
    width = shutil.get_terminal_size((120, 20)).columns
    while True:
        print("\033[2J\033[H", end="")
        print("=" * width)
        print("  MPLADS FINE-TUNE  |  live view (Ctrl-C to quit)")
        print("=" * width)

        last = tail_lines(LOG, 1)
        print(f"\n  progress  : {last[0][: width - 12] if last else 'no run.log yet'}")

        heat = [ln for ln in tail_lines(LOG, 5000) if "[heartbeat]" in ln]
        if heat:
            s = heat[-1]
            idx = s.find("[heartbeat]")
            print(f"  heartbeat : {s[idx:idx+60]}")

        print(f"\n  gpu       : {gpu_line()}")

        st = "-"
        alive = any("finetune.py" in ln for ln in
                    subprocess.run(["ps", "aux"], capture_output=True, text=True).stdout.splitlines())
        print(f"  process   : {'RUNNING' if alive else 'NOT RUNNING'}")

        print("\n  epoch rows (metrics.csv):")
        if os.path.exists(METRICS):
            rows = tail_lines(METRICS, 8)
            for r in rows:
                print(f"    {r[: width - 6]}")
        else:
            print("    (no row yet - first epoch ~30 min)")

        if os.path.exists(BEST):
            print(f"\n  best so far: {open(BEST).read().strip()}")

        time.sleep(2)


if __name__ == "__main__":
    main()