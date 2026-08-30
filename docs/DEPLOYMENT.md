# DEPLOYMENT — Make the MPLADS detection demo go live ($0 tier)

The detection pipeline is **deterministic over static files** — that is our superpower
for a demo. 99% of the product can go live without any always-on compute:

- The heavy lifting (fine-tuned embedding + fuzzy duplicate sweep + Isolation Forest +
  rules + fraud classification + legal-route lookup) is all **pre-computed** in this
  repo (`metrics/flags.csv`, `metrics/mp_aggregate.csv`, `metrics/worst_offenders.csv`,
  `evidence/*.md`).
- The only piece that needs a live model is the **optional** "type a new work → how
  risky / duplicate-like is it?" box. That is hosted **free** on Hugging Face Spaces.

Result: a three-part $0 stack — **Cloudflare Pages** (dashboard), **Cloudflare
Workers** (thin JSON API), **Hugging Face Space** (embedding model, optional).

> LOCKED GUARDRAILS (do not ship without these)
> 1. UI text everywhere: "possible fraud **pattern** — verification required by the
>    scheme authority". Never "fraud", never "guilty", never a court/penalty claim.
> 2. `legal_route` is rendered **verbatim from the hardcoded table** — the frontend must
>    not let the model or any free-text explain law.
> 3. `NA-` work IDs are flagged by design; do not hide them to make numbers look better.

---

## 1. Push the fine-tuned embedding model to Hugging Face (one time)

The best checkpoint (`models/best/epoch_4.0`, val_acc 0.963) is already a full
sentence-transformers model (`modules.json`, `1_Pooling`, `model.safetensors`,
tokenizer) — it loads directly. No re-export needed:

```bash
pip install sentence-transformers
python3 -c "
from sentence_transformers import SentenceTransformer
m = SentenceTransformer('models/best/epoch_4.0')   # smoke test: must not error
print(m.encode('query: concrete road')).shape
"
```

Push it (private keeps the weights from being copied by randoms; a Space we own can
still load a private model):

```bash
huggingface-cli login          # token with write scope
huggingface-cli repo create sIH26102/mplads-minilm-embed-v1 --type model --private
# upload the whole checkpoint directory:
for f in models/best/epoch_4.0/*; do huggingface-cli upload sIH26102/mplads-minilm-embed-v1 "$f" "$(basename $f)"; done
```

## 2. Host the model on a free Hugging Face Space (optional live-check box)

Create a Space: **Docker SDK**, and drop a tiny Gradio API:

```yaml
# space/README.md (this is the YAML header — HF Spaces config)
---
title: mplads-embed
emoji: 🛰️
colorFrom: indigo
colorTo: red
sdk: docker
pinned: false
license: apache-2.0
---
```

```dockerfile
# space/Dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -q -r requirements.txt gradio sentence-transformers
COPY app.py .
CMD ["python", "app.py"]
```

```python
# space/app.py  — exposes encode() so our Worker calls it over HTTP
import gradio as gr
from sentence_transformers import SentenceTransformer
import numpy as np

m = SentenceTransformer("sIH26102/mplads-minilm-embed-v1")

def encode(text: str, normalize: bool = True):
    e = m.encode("query: " + text, normalize_embeddings=normalize)
    return np.round(e, 6).tolist()

gr.Interface(fn=encode, inputs="text", outputs="json", live=False).launch()
```

Public URL: `https://zeroij-sih26102-mplads-embed.hf.space`. Guard it with a value in
the Worker secret `HF_TOKEN` (Spaces token) so randoms can't burn your free quota.

## 3. Cloudflare Worker — thin JSON API (the backend)

Everything the dashboard needs is a filter/serve of static artifacts. New dir:

```
webapp/
├── worker/            # the Cloudflare Worker
│   ├── wrangler.toml
│   ├── src/index.js
│   └── package.json
└── dashboard/         # static SPA built to dist/ (any framework → static)
    └── dist/
```

`webapp/worker/wrangler.toml`:

```toml
name = "mplads-api"
main = "src/index.js"
compatibility_date = "2025-01-01"

[[kv_namespaces]]
binding = "MPLADS"
id = "REPLACE_ME"          # wrangler kv:namespace create MPLADS

[vars]
HF_SPACE = "https://zeroij-sih26102-mplads-embed.hf.space"
```

`webapp/worker/src/index.js` — rough but complete:

```js
const f = async (env, name) => {         // flags.csv / mp_aggregate.csv / worst_offenders.csv
  return await env.MPLADS.get(`csv:${name}`);          // uploaded into KV (step 5)
};

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);

    // CORS for the Pages origin
    const headers = { "Access-Control-Allow-Origin": "*", "Content-Type": "application/json" };
    const json = (o, h) => new Response(typeof o === "string" ? o : JSON.stringify(o), { headers: h });

    if (url.pathname === "/api/works") {
      const csv = await f(env, "flags.csv");
      const rows = csvToObjects(csv);
      const { mp, state, risk_min = "0", type = "", page = "1" } = Object.fromEntries(url.searchParams);
      const out = rows
        .filter(r => (!mp || r.mp_name?.includes(mp)))
        .filter(r => (!state || r.state === state))
        .filter(r => (+r.risk_score ?? 0) >= +risk_min)
        .filter(r => (!type || r.fraud_type === type));
      return json(paginate(out, +page), headers);
    }

    if (url.pathname === "/api/mps")       return json(await f(env, "mp_aggregate.csv"), headers);
    if (url.pathname === "/api/offenders") return json(await f(env, "worst_offenders.csv"), headers);

    if (url.pathname === "/api/similar" && url.searchParams.get("desc")) {
      // OPTIONAL live check: embed desc on HF Space, compare to flagged anchors
      const emb = await (await fetch(env.HF_SPACE + "/predict?data=" + encodeURIComponent(JSON.stringify([url.searchParams.get("desc")])))).json();
      const anchors = JSON.parse(await f(env, "anchors.json"));   // precomputed: work_id+embedding of flagged works
      const top = topK(emb[0], anchors, 5);
      return json({ desc: url.searchParams.get("desc"), similar: top }, headers);
    }

    return json({ ok: true, service: "mplads-api" }, headers);
  }
};
```

Deploy + load data:

```bash
cd webapp/worker
npm i
npx wrangler kv:namespace create MPLADS          # copy id into wrangler.toml
npx wrangler login
# one-time seed of KV from the committed artifacts:
npx wrangler kv:key put MPLADS "csv:flags.csv" --path ../../metrics/flags.csv
npx wrangler kv:key put MPLADS "csv:mp_aggregate.csv" --path ../../metrics/mp_aggregate.csv
npx wrangler kv:key put MPLADS "csv:worst_offenders.csv" --path ../../metrics/worst_offenders.csv
# anchors.json (work_id -> embedding, for the live box) — generate with export script
npx wrangler secret put HF_TOKEN
npx wrangler deploy
```

## 4. Cloudflare Pages — the judge-facing dashboard

Dashboard is a **static build** (any SPA; Vite/React or a single index.html + chart.js).
Pick one page that consumes the API and matches the architecture diagram's UI:

- **Flagged cases list** — filters: MP / State / fraud type / min risk. Row → case detail.
- **Case detail** — show the evidence dossier content rendered from
  `GET /api/work/{id}` (serve the MD as JSON from KV) including the FC1 "why it
  looks wrong" + the **verbatim** LG1 legal section + the verification checklist.
- **MP scoreboard** — top worst offenders from `/api/offenders`. Columns are `cumulative_risk_points`
  (sum across the MP's works — NOT a 0-100 scale) and `avg_risk_per_work` (the 0-100-per-work average,
  comparable to the per-work `risk_score`). Never render both under the same "risk score" label.

```bash
# example pure-static build with vite
cd webapp/dashboard && npm i && npm run build   # outputs dist/
npx wrangler pages deploy dist --project-name mplads-dashboard
```

Point the dashboard at `https://mplads-api.<your-subdomain>.workers.dev`.
A custom domain (`dashboard.mplads.in`) is a one-click Pages setting — optional.

## 5. Smoke test checklist (before demo day)

- [ ] `curl "https://<workers-dev>/api/works?type=duplicate_claim&page=1"` returns JSON
- [ ] `/api/mps` top row == Chandra Prakash Choudhary, cumulative_risk_points 2039, avg_risk_per_work 48.8 (matches `worst_offenders.csv`; per-work scale stays 0-100 in `flags.csv`)
- [ ] A dossier opens and shows BOTH sections: FC1 + LG1 verbatim
- [ ] Live `/api/similar?desc=construction of concrete road near ...` returns on an MP-lead
- [ ] No "guilty"/"jail"/"penalty" strings anywhere in the UI (grep your build)
- [ ] CORS header present; mobile view OK (judges browse from phones)

## Why this survives a judge Q&A

- "Is this live?" → Yes: dashboard + API live on $0 infra; model on HF Spaces.
- "How do you keep it legal?" → LG1 table is hardcoded and auditable; the model
  literally cannot emit legal citations (rule locked in AGENT.md).
- "Cost?" → $0 infra + free ray.compute budget courtesy of demo credit / Spaces free tier.

## Files feeding the demo (all committed in this repo)

| Artifact | File |
|---|---|
| Work-level flags + risk + fraud_type + legal_route | `metrics/flags.csv` |
| MP aggregate | `metrics/mp_aggregate.csv` |
| Worst-offender ranking | `metrics/worst_offenders.csv` |
| Evidence dossiers (FC1 + LG1) | `evidence/*.md`, `evidence/dossiers.md` |
| Fine-tuned checkpoint (best epoch_4.0) | `models/best/epoch_4.0` (gitignored, on disk) |