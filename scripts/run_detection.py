"""Run the full detection pipeline: flags -> MP aggregate -> evidence dossiers.

Usage:
    python scripts/run_detection.py            # full run
    python scripts/run_detection.py --dossiers 0    # skip evidence dossiers
    python scripts/run_detection.py --dossiers 20   # only 20 dossiers
"""

import argparse
import json
import sys

sys.path.insert(0, "/home/zeroij/mplads")

from src.mplads import config, engine, aggregate, evidence  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dossiers", type=int, default=50,
                    help="max dossiers to build (default 50 top-risk; None = all flagged)")
    args = ap.parse_args()

    flags = engine.run_engine(save=True)
    summary = engine.summarize(flags)
    print("=== DETECTION ENGINE ===")
    print(json.dumps(summary, indent=2))

    agg = aggregate.run(flags, save=True)
    print("\n=== TOP 5 WORST-OFFENDER MPS (by risk) ===")
    cols = ["mp_no", "mp_name", "mp_state", "works", "stalled", "dup_leads", "anomalies", "risk", "risk_rank"]
    print(agg[cols].head(5).to_string(index=False))

    n = args.dossiers
    if n is None:
        n = int(summary["flagged"])
    idx = evidence.build_dossiers(flags, limit=n)
    print(f"\n=== EVIDENCE DOSSIERS: {len(idx)} written -> {config.EVIDENCE_DIR}/ ===")
    print(f"\nflags -> {config.FLAGS_CSV}")
    print(f"MP aggregate -> {config.MP_AGGREGATE_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())