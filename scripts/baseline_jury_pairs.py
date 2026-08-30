"""
Baseline metrics for the 10 fixed jury pairs
============================================
Runs the FROZEN (un-fine-tuned) paraphrase-multilingual-MiniLM-L12-v2 on the
10 fixed jury pairs and writes BEFORE-numbers to metrics/baseline_metrics.csv.

MUST run before any fine-tuning so the "before" is independent, not
reconstructed after the fact.
"""

import csv
import os
import sys

from sentence_transformers import SentenceTransformer, util

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

# Fixed 10 jury pairs. expected: MATCH or NOT_MATCH.
JURY_PAIRS = [
    # Romanized Hindi <-> English, same meaning
    ("Samudayik Bhavan Nirman", "Community Bhavan", "MATCH"),
    ("Bhavan", "Bhawan", "MATCH"),
    ("Nali Nirman", "Construction of drain", "MATCH"),
    ("Kharanja", "CC Road", "MATCH"),
    ("Shauchalaya Nirman", "Construction of toilet", "MATCH"),
    # Unrelated / hard non-matches (must stay far)
    ("Construction of school building at Village A", "Construction of school building at Village B", "NOT_MATCH"),
    ("Construction of road", "Supply of computers to school", "NOT_MATCH"),
    ("Khel Maidan Vikas", "Repair of water tank", "NOT_MATCH"),
    ("Aanganwadi Bhawan Nirman", "Solar street light installation", "NOT_MATCH"),
    ("Community Bhavan construction", "Vaccination camp for cattle", "NOT_MATCH"),
]


def main():
    out_dir = os.path.join(os.path.dirname(__file__), "..", "metrics")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "baseline_metrics.csv")

    print(f"Loading frozen model: {MODEL_NAME} ...")
    model = SentenceTransformer(MODEL_NAME)
    print("Done.\n")

    rows = []
    for text_a, text_b, expected in JURY_PAIRS:
        emb_a = model.encode(text_a, normalize_embeddings=True, convert_to_tensor=True)
        emb_b = model.encode(text_b, normalize_embeddings=True, convert_to_tensor=True)
        score = util.cos_sim(emb_a, emb_b).item()
        rows.append({
            "pair_a": text_a,
            "pair_b": text_b,
            "expected": expected,
            "cosine": round(score, 4),
            "stage": "BASELINE_UNFINE_TUNED",
        })
        print(f"{text_a[:38]:<40} <-> {text_b[:38]:<40} {score:.4f}  ({expected})")

    fields = ["stage", "pair_a", "pair_b", "expected", "cosine"]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    match_scores = [r["cosine"] for r in rows if r["expected"] == "MATCH"]
    nomatch_scores = [r["cosine"] for r in rows if r["expected"] == "NOT_MATCH"]
    print(f"\nBaseline written to {out_path}")
    print(f"MATCH pairs    avg cosine: {sum(match_scores)/len(match_scores):.4f}")
    print(f"NOT_MATCH pairs avg cosine: {sum(nomatch_scores)/len(nomatch_scores):.4f}")
    print(f"Separation (match - nonmatch): {(sum(match_scores)/len(match_scores)) - (sum(nomatch_scores)/len(nomatch_scores)):.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())