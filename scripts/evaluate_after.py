"""
Compare fine-tuned model vs baseline on the 10 fixed jury pairs.
================================================================
Loads best model from /mplads/models/best (picked by fit's save_best_model),
scores the same 10 jury pairs used in baseline_jury_pairs.py, writes
metrics/after_metrics.csv, and prints a BEFORE/AFTER table.
"""

import csv
import os
import sys

import pandas as pd
from sentence_transformers import SentenceTransformer, util

BASE_DIR = "/home/zeroij/mplads"
BEST_DIR = f"{BASE_DIR}/models/best"
BASELINE = f"{BASE_DIR}/metrics/baseline_metrics.csv"
AFTER = f"{BASE_DIR}/metrics/after_metrics.csv"

JURY_PAIRS = [
    ("Samudayik Bhavan Nirman", "Community Bhavan", "MATCH"),
    ("Bhavan", "Bhawan", "MATCH"),
    ("Nali Nirman", "Construction of drain", "MATCH"),
    ("Kharanja", "CC Road", "MATCH"),
    ("Shauchalaya Nirman", "Construction of toilet", "MATCH"),
    ("Construction of school building at Village A", "Construction of school building at Village B", "NOT_MATCH"),
    ("Construction of road", "Supply of computers to school", "NOT_MATCH"),
    ("Khel Maidan Vikas", "Repair of water tank", "NOT_MATCH"),
    ("Aanganwadi Bhawan Nirman", "Solar street light installation", "NOT_MATCH"),
    ("Community Bhavan construction", "Vaccination camp for cattle", "NOT_MATCH"),
]


def load_best_model():
    best_txt = os.path.join(BEST_DIR, "best.txt")
    if os.path.exists(best_txt):
        with open(best_txt) as f:
            p = f.read().strip()
        if os.path.isdir(p) and os.path.exists(os.path.join(p, "config.json")):
            return p, [p]
    candidates = []
    if os.path.isdir(BEST_DIR):
        for name in os.listdir(BEST_DIR):
            p = os.path.join(BEST_DIR, name)
            if os.path.isdir(p) and os.path.exists(os.path.join(p, "config.json")):
                candidates.append(p)
        if candidates:
            return max(candidates, key=os.path.getmtime), candidates
    return None, candidates


def main():
    model, candidates = load_best_model()
    if model is None:
        print(f"No fine-tuned model found under {BEST_DIR}")
        print("Run: python scripts/finetune.py")
        return 1
    print(f"Using fine-tuned model: {model}\n")

    model_st = SentenceTransformer(model)
    baseline = pd.read_csv(BASELINE)
    after_rows = []
    for a, b, expected in JURY_PAIRS:
        emb_a = model_st.encode(a, normalize_embeddings=True, convert_to_tensor=True)
        emb_b = model_st.encode(b, normalize_embeddings=True, convert_to_tensor=True)
        score = float(util.cos_sim(emb_a, emb_b).item())
        b_row = baseline[(baseline["pair_a"] == a) & (baseline["pair_b"] == b)]
        before = b_row["cosine"].iloc[0] if not b_row.empty else float("nan")
        after_rows.append({"pair_a": a, "pair_b": b, "expected": expected, "before": before, "after": round(score, 4)})

    with open(AFTER, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["pair_a", "pair_b", "expected", "before", "after"])
        w.writeheader()
        w.writerows(after_rows)

    print(f"{'pair a':<44} {'pair b':<44} {'expt':<10} {'before':>7} {'after':>7}")
    for r in after_rows:
        print(f"{r['pair_a'][:43]:<44} {r['pair_b'][:43]:<44} {r['expected']:<10} {r['before']:>7.3f} {r['after']:>7.3f}")
    print(f"\nafter_metrics.csv -> {AFTER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())