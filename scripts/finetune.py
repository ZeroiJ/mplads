"""
Fine-tune paraphrase-multilingual-MiniLM-L12-v2 on MPLADS duplicate pairs.
===========================================================================
Loss: CosineSimilarityLoss on labeled 1.0/0.0 pairs from data/pairs.csv.

Per epoch -> metrics/metrics.csv:
    epoch, train_loss, val_loss, val_cosine_accuracy, test_precision_at_k,
    elapsed_sec, lr, model_path

Models saved to /mplads/models/best/epoch_N/ and the best-scoring epoch path
is recorded in /mplads/models/best/best.txt.
"""

import csv
import os
import random
import sys
import time

import pandas as pd
import torch
from sentence_transformers import (
    InputExample,
    SentenceTransformer,
    SimilarityFunction,
    losses,
    util,
)
from sentence_transformers.evaluation import EmbeddingSimilarityEvaluator
from torch.utils.data import DataLoader

BASE_DIR = "/home/zeroij/mplads"
PAIRS = f"{BASE_DIR}/data/pairs.csv"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
OUT_DIR = f"{BASE_DIR}/metrics"
BEST_DIR = f"{BASE_DIR}/models/best"
EPOCHS = int(os.environ.get("MPLADS_EPOCHS", "4"))
BATCH_SIZE = int(os.environ.get("MPLADS_BATCH", "16"))
LR = float(os.environ.get("MPLADS_LR", "2e-5"))
SEED = 42
PK_QUERIES = 300
PK_K = 20


class LoggedCosineLoss(losses.CosineSimilarityLoss):
    HEARTBEAT_EVERY = 100

    def __init__(self, model):
        super().__init__(model)
        self.batch_loss = 0.0
        self.n_batches = 0

    def forward(self, sentence_features, labels):
        loss = super().forward(sentence_features, labels)
        self.batch_loss += float(loss)
        self.n_batches += 1
        if self.n_batches % self.HEARTBEAT_EVERY == 0:
            print(f"[heartbeat] step {self.n_batches} loss={loss.item():.4f} (running_mean={self.mean_loss:.4f})", flush=True)
        return loss

    @property
    def mean_loss(self):
        return self.batch_loss / max(1, self.n_batches)

    def reset_log(self):
        self.batch_loss = 0.0
        self.n_batches = 0


def make_examples(df, split):
    sub = df[df["split"] == split]
    return [InputExample(texts=[r["anchor_text"], r["other_text"]], label=float(r["label"])) for _, r in sub.iterrows()]


def val_accuracy(model, val_ex):
    texts = [t for ex in val_ex for t in ex.texts]
    labels = [ex.label for ex in val_ex]
    emb = model.encode(texts, batch_size=BATCH_SIZE, convert_to_tensor=True, normalize_embeddings=True)
    sims = util.cos_sim(emb[0::2], emb[1::2]).diagonal()
    preds = (sims >= 0.5).int().cpu().tolist()
    labs = [int(l) for l in labels]
    acc = sum(p == l for p, l in zip(preds, labs)) / max(1, len(labs))
    return round(acc, 4)


def precision_at_k(model, test_df, k=PK_K, n_queries=PK_QUERIES, seed=SEED):
    pos = test_df[test_df["label"] == 1]
    if pos.empty:
        return 0.0
    corpus = test_df["other_text"].tolist()
    queries = pos["anchor_text"].tolist()
    rng = random.Random(seed)
    rng.shuffle(queries)
    queries = queries[:n_queries]
    q_emb = model.encode(queries, batch_size=BATCH_SIZE, convert_to_tensor=True, normalize_embeddings=True)
    c_emb = model.encode(corpus, batch_size=BATCH_SIZE, convert_to_tensor=True, normalize_embeddings=True)
    target = {}
    for _, r in pos.iterrows():
        target.setdefault(r["anchor_text"], r["other_text"])
    sims = util.cos_sim(q_emb, c_emb)
    corpus_idx = {t: i for i, t in enumerate(corpus)}
    hits = total = 0
    for i, q in enumerate(queries):
        t = target.get(q)
        if t is None or t not in corpus_idx:
            continue
        topk = [corpus[j] for j in sims[i].topk(k).indices.tolist()]
        total += 1
        if t in topk:
            hits += 1
    return round(hits / max(1, total), 4)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(BEST_DIR, exist_ok=True)
    torch.manual_seed(SEED)

    df = pd.read_csv(PAIRS)
    train_ex = make_examples(df, "train")
    val_ex = make_examples(df, "val")
    test_df = df[df["split"] == "test"].reset_index(drop=True)
    print(f"train={len(train_ex)} val={len(val_ex)} test={len(test_df)}")

    model = SentenceTransformer(MODEL_NAME)
    train_dl = DataLoader(train_ex, shuffle=True, batch_size=BATCH_SIZE)
    loss = LoggedCosineLoss(model)

    val_scores = [(ex.texts[0], ex.texts[1], ex.label) for ex in val_ex]
    evaluator = EmbeddingSimilarityEvaluator(
        [s[0] for s in val_scores], [s[1] for s in val_scores], [s[2] for s in val_scores],
        main_similarity=SimilarityFunction.COSINE, name="val",
    )

    metrics_path = f"{OUT_DIR}/metrics.csv"
    with open(metrics_path, "w", newline="") as f:
        csv.DictWriter(f, fieldnames=["epoch", "train_loss", "val_loss", "val_cosine_accuracy", "test_precision_at_k", "elapsed_sec", "lr", "model_path"]).writeheader()

    t_start = time.time()
    last_step = -1
    best_acc = -1.0
    best_path = ""

    def callback(score, epoch, steps):
        nonlocal last_step, best_acc, best_path
        step = int(steps)
        if step == last_step:
            return
        last_step = step
        acc = val_accuracy(model, val_ex)
        pk = precision_at_k(model, test_df)
        elapsed = round(time.time() - t_start, 1)
        epoch_dir = f"{BEST_DIR}/epoch_{epoch}"
        model.save(epoch_dir)
        if acc > best_acc:
            best_acc = acc
            best_path = epoch_dir
            with open(f"{BEST_DIR}/best.txt", "w") as f:
                f.write(best_path + "\n")
        row = {
            "epoch": epoch,
            "train_loss": round(loss.mean_loss, 4),
            "val_loss": "",
            "val_cosine_accuracy": acc,
            "test_precision_at_k": pk,
            "elapsed_sec": elapsed,
            "lr": LR,
            "model_path": best_path,
        }
        with open(metrics_path, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=list(row)).writerow(row)
        print(f"  epoch {epoch}: train_loss={row['train_loss']} val_acc={acc} p@{PK_K}={pk} ({elapsed}s) best={best_path}")

    total_steps = len(train_dl) * EPOCHS
    model.fit(
        train_objectives=[(train_dl, loss)],
        evaluator=evaluator,
        epochs=EPOCHS,
        evaluation_steps=len(train_dl),
        warmup_steps=max(0, int(0.1 * total_steps)),
        optimizer_params={"lr": LR},
        save_best_model=False,
        max_grad_norm=1.0,
        callback=callback,
        show_progress_bar=True,
    )

    print(f"\nBest val acc: {best_acc:.4f} -> {best_path}")
    print(f"metrics.csv -> {metrics_path}")
    print("Compare vs baseline: python scripts/evaluate_after.py")


if __name__ == "__main__":
    sys.exit(main())