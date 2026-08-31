#!/usr/bin/env python3
"""Phase 2: score the stored corpus with FinBERT, per sentence.

GPU-bound, so it runs separately from the network-bound fetch. Sentences are
batched across filings rather than within one, because a single filing yields
only 30 sampled sentences and the GPU is dispatch-overhead-bound: small batches
waste most of the throughput.

Development window only by default. The holdout stays sealed until the
development result is written down and frozen.
"""
import gzip, json, os, re, sys, time
from pathlib import Path

try: os.setsid()
except Exception: pass

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

HERE   = Path(__file__).resolve().parent
CORPUS = HERE / "corpus"
DEV_END = "2023-01-01"          # holdout is everything from here on
SAMPLE = 30                     # sampled sentences per filing, evenly spaced
BATCH = 64
MODEL = "ProsusAI/finbert"

OUT = HERE / ("finbert_holdout.json" if "--holdout" in sys.argv else "finbert_dev.json")
WANT_HOLDOUT = "--holdout" in sys.argv

SENT = re.compile(r'(?<=[.!?])\s+')


def sentences(text):
    """Sentences sampled evenly across the whole filing.

    An earlier version took the first 15 and last 15, on the theory that tone
    concentrates in the overview and the outlook. It does -- positively. Those
    are the most upbeat passages in any MD&A, and sampling only them produced
    zero negative sentences in 180 across six filings. The middle, where
    management explains what went wrong, was exactly what was being excluded.

    Even spacing covers the whole document at identical cost.

    40-600 characters excludes headings, fragments and table debris.
    """
    s = [x.strip() for x in SENT.split(text) if 40 < len(x.strip()) < 600]
    if len(s) <= SAMPLE:
        return s
    step = len(s) / SAMPLE
    return [s[int(i * step)] for i in range(SAMPLE)]


def main():
    tok = AutoTokenizer.from_pretrained(MODEL)
    mdl = AutoModelForSequenceClassification.from_pretrained(MODEL)
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    mdl = mdl.to(dev).eval()
    lab = {v.lower(): k for k, v in mdl.config.id2label.items()}
    POS, NEG = lab["positive"], lab["negative"]
    print(f"model on {dev}; window={'holdout' if WANT_HOLDOUT else 'development'}",
          flush=True)

    done = json.loads(OUT.read_text()) if OUT.exists() else {}
    files = sorted(CORPUS.glob("*.json.gz"))
    todo = [p for p in files if p.stem.split(".")[0] not in done]
    print(f"corpus {len(files):,} companies | scored {len(done):,} | to do {len(todo):,}",
          flush=True)

    t0 = time.time(); nsent = 0; ncompany = 0
    for p in todo:
        cik = p.stem.split(".")[0]
        try:
            with gzip.open(p, "rt", encoding="utf-8") as fh:
                rec = json.load(fh)
        except Exception:
            continue
        out = []
        for f in rec.get("filings", []):
            in_hold = f["filed"] >= DEV_END
            if in_hold != WANT_HOLDOUT:            # sealed unless asked for
                continue
            sents = sentences(f.get("text") or "")
            if not sents:
                continue
            scores = []
            for i in range(0, len(sents), BATCH):
                chunk = sents[i:i + BATCH]
                enc = tok(chunk, padding=True, truncation=True,
                          max_length=128, return_tensors="pt").to(dev)
                with torch.no_grad():
                    pr = torch.softmax(mdl(**enc).logits, dim=-1)
                scores.extend((pr[:, POS] - pr[:, NEG]).tolist())
                nsent += len(chunk)
            n = len(scores)
            mean = sum(scores) / n
            var = sum((x - mean) ** 2 for x in scores) / n
            out.append({
                "form": f["form"], "filed": f["filed"], "period": f["period"],
                "words": f["words"], "lm_tone": f.get("lm_tone"),
                "n_sent": n,
                "fb_tone": round(mean, 6),
                "fb_share_neg": round(sum(1 for x in scores if x < -0.5) / n, 4),
                "fb_sd": round(var ** 0.5, 6),
            })
        done[cik] = out
        ncompany += 1
        if ncompany % 25 == 0:
            OUT.write_text(json.dumps(done))
            el = time.time() - t0
            rate = nsent / el
            left = (len(todo) - ncompany) / max(ncompany / el, 1e-9)
            print(f"  {ncompany}/{len(todo)}  sentences={nsent:,}  "
                  f"{rate:.0f}/s  eta {left/3600:.1f}h", flush=True)
    OUT.write_text(json.dumps(done))
    print(f"DONE {len(done):,} companies, {nsent:,} sentences scored")


if __name__ == "__main__":
    main()
