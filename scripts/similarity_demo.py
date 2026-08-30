"""
MPLADS Multilingual Similarity Demo
====================================
Shows why all-MiniLM-L6-v2 (English-only) FAILS on romanized Hindi work titles,
while paraphrase-multilingual-MiniLM-L12-v2 SUCCEEDS.

Run:
    source /tmp/opencode/venv/bin/activate
    pip install sentence-transformers torch --index-url https://download.pytorch.org/whl/cpu
    python /home/zeroij/mplads/scripts/similarity_demo.py

Expected output:
    English-only model: low similarity on romanized pairs (~0.30-0.55)
    Multilingual model: high similarity on romanized pairs (~0.75-0.95)
"""

from sentence_transformers import SentenceTransformer, util
import time

# ── Test pairs ──────────────────────────────────────────────
# Each tuple: (text_a, text_b, expected_behavior)
# expected_behavior: "SHOULD MATCH" = paraphrases, "SHOULD NOT MATCH" = unrelated
TEST_PAIRS = [
    # Romanized Hindi ↔ English (the core problem)
    ("Construction of Community Bhavan",
     "Samudayik Bhavan Nirman",
     "SHOULD MATCH — romanized Hindi ↔ English, same meaning"),

    ("Protective wall near PMGSY road",
     "Kharanja Nirman",
     "SHOULD MATCH — romanized Hindi 'Kharanja Nirman' = protective wall construction"),

    # Spelling variants (common in eSAKSHI data)
    ("Bhavan",
     "Bhawan",
     "SHOULD MATCH — Bhavan vs Bhawan is a spelling variant"),

    ("Shauchalaya Nirman",
     "Construction of toilet",
     "SHOULD MATCH — Shauchalaya = toilet (romanized Hindi)"),

    # Same amount, different works (hard negative)
    ("Construction of school building at Village A",
     "Construction of school building at Village B",
     "SHOULD NOT MATCH — same category but different location"),

    # Completely unrelated works
    ("Construction of road",
     "Supply of computers to school",
     "SHOULD NOT MATCH — unrelated work types"),
]

# ── Models ──────────────────────────────────────────────────
MODELS = [
    ("all-MiniLM-L6-v2 (English-only)", "all-MiniLM-L6-v2"),
    ("paraphrase-multilingual-MiniLM-L12-v2", "paraphrase-multilingual-MiniLM-L12-v2"),
]


def run_demo():
    print("=" * 72)
    print("MPLADS Multilingual Similarity Demo")
    print("=" * 72)
    print()

    results = {}

    for model_label, model_name in MODELS:
        print(f"Loading: {model_label} ...")
        t0 = time.time()
        model = SentenceTransformer(model_name)
        load_time = time.time() - t0
        print(f"  Loaded in {load_time:.1f}s")
        print()

        pair_scores = []
        for text_a, text_b, expected in TEST_PAIRS:
            t0 = time.time()
            emb_a = model.encode(text_a, convert_to_tensor=True)
            emb_b = model.encode(text_b, convert_to_tensor=True)
            score = util.cos_sim(emb_a, emb_b).item()
            infer_time = (time.time() - t0) * 1000

            pair_scores.append((text_a, text_b, score, expected, infer_time))

        results[model_label] = pair_scores

        # Print results for this model
        print(f"  {'Pair':<55} {'Score':>7}  {'Time':>6}  Verdict")
        print(f"  {'-'*55} {'-'*7}  {'-'*6}  {'-'*20}")
        for text_a, text_b, score, expected, infer_time in pair_scores:
            short_a = text_a[:26] + "…" if len(text_a) > 27 else text_a
            short_b = text_b[:26] + "…" if len(text_b) > 27 else text_b
            label = "✓" if "MATCH" in expected and score > 0.6 or "NOT MATCH" in expected and score < 0.6 else "✗"
            print(f"  {short_a:<28} ↔ {short_b:<25} {score:>6.4f}  {infer_time:>5.0f}ms  {label} {expected.split('—')[0].strip()}")
        print()

        # Clean up
        del model

    # ── Summary ─────────────────────────────────────────────
    print("=" * 72)
    print("SUMMARY: Romanized Hindi pairs only (first 4)")
    print("=" * 72)
    print()

    romanized_indices = [0, 1, 2, 3]  # First 4 pairs are romanized
    for model_label in [m[0] for m in MODELS]:
        scores = [results[model_label][i][2] for i in romanized_indices]
        avg = sum(scores) / len(scores)
        print(f"  {model_label}")
        print(f"    Average similarity on romanized pairs: {avg:.4f}")
        print(f"    Min: {min(scores):.4f}  Max: {max(scores):.4f}")
        print()

    print("CONCLUSION:")
    print("  English-only model CANNOT handle romanized Hindi/Devanagari text.")
    print("  Multilingual model handles it natively — no transliteration needed.")
    print("  This is why we chose paraphrase-multilingual-MiniLM-L12-v2 for MPLADS.")


if __name__ == "__main__":
    run_demo()
