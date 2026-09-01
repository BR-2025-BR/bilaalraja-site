# Pre-registration: MD&A tone change and forward returns

**Written before any historical filing text was fetched or examined.**
The git commit timestamp is the evidence. Nothing in this file may be revised
after data collection begins; revisions, if any, are appended as dated
amendments below with reasons.

---

## 1. Question

Does a change in the tone of management's own discussion, measured against that
company's own recent history, predict its forward stock return?

## 2. Hypothesis (directional, falsifiable)

**H1.** Companies whose MD&A tone deteriorates most, relative to their own prior
four filings, underperform companies whose tone improves most, over the quarter
following the filing date.

**Null.** No difference beyond noise. A null result is a valid outcome and will
be reported as such, as with the previous 13-construct study.

## 3. Data

- **Text.** Item 7 / Item 2 MD&A extracted from 10-K and 10-Q filings on SEC
  EDGAR. Public domain. Immutable: prose is never restated, which is why this
  signal can be tested honestly where a fundamentals-based one cannot.
- **Universe.** The 2,581 companies in the current panel. See limitations.
- **Period.** Filings dated 2018-01-01 to 2026-06-30.
- **Prices.** Daily adjusted closes.

## 4. Signal definition (fixed now)

For filing *i* by company *c* on date *t*:

- `tone(i)` = Loughran-McDonald polarity of the MD&A text,
  `(pos - neg) / (pos + neg)`, using the LM word lists as distributed in
  `pysentiment2`. LM specifically, not a general-purpose sentiment lexicon,
  because general lexicons misclassify ordinary accounting vocabulary.
- `baseline(c,t)` = mean `tone` of company *c*'s previous **four** filings,
  all strictly before *t*.
- **`dtone(i) = tone(i) - baseline(c,t)`** — the signal.
- Filings with fewer than four priors are **excluded**, not zero-filled.
- MD&A shorter than 500 words is **excluded** as an extraction failure.

Measuring change against the company's own baseline is deliberate: it removes
persistent industry and house-style vocabulary, so the signal is a company
moving against itself rather than a proxy for sector.

## 5. Outcome

- **Primary.** Return from close on *t+1* trading day to close on *t+63*
  (about one quarter), minus the equal-weighted return of all sample companies
  over the identical window. *t+1* avoids same-day look-ahead.
- **Secondary.** The same at *t+21* and *t+126*. Secondary only; they cannot
  rescue a failed primary.

## 6. Development and holdout

- **Development:** filings dated 2018-01-01 to 2022-12-31.
- **Holdout:** filings dated 2023-01-01 to 2026-06-30. **Sealed.** Not loaded,
  summarised, plotted or inspected until the development analysis is complete
  and frozen in writing.
- The holdout is tested **once**. If it fails, the result is a null. There is no
  second look and no revised specification afterwards.

## 7. Decision rule (fixed now)

Sort filings into quintiles by `dtone` within each calendar quarter.

**Success requires all three:**
1. Development: bottom-quintile minus top-quintile spread is **negative**
   (deteriorating tone underperforms), consistent with H1.
2. Development: |t| > 2.5 on that spread, using Newey-West standard errors with
   63-day lags to account for overlapping return windows.
3. Holdout: same sign, |t| > 2.0.

Anything short of all three is a **null**, reported as a null.

## 8. Multiple testing

At most **five** specifications will be run in development. They are named now:

1. Primary as specified above.
2. Baseline of eight prior filings rather than four.
3. 10-K filings only.
4. Excluding companies below $1bn market capitalisation.
5. Tone level rather than tone change (a deliberate straw man: if the level
   works and the change does not, the likeliest explanation is a sector or size
   proxy, not information).

No sixth. Any further idea is recorded as future work and is not tested here.
The holdout is run on specification 1 only.

## 9. Known limitations, stated before seeing results

- **Survivorship, the most serious.** The universe is today's constituents, so
  companies that failed or delisted between 2018 and 2026 are absent. This
  biases any historical result favourably and cannot be fully corrected without
  licensed historical index membership. Magnitude will be estimated by
  reporting how many sample companies have filings ceasing before 2026.
- **Extraction quality.** MD&A boundaries are parsed heuristically; some
  extractions will capture too much or too little.
- **Costs and capacity.** Not modelled. A spread concentrated in small
  companies may not be tradeable, and no claim of tradeability is made.
- **Prices.** Sourced from yfinance, which is a licensing grey area and not a
  basis for any commercial use of this result.

## 10. What this cannot show

Nothing here establishes causation, and a positive result would not constitute
investment advice or a strategy. It would establish only that a measurable
relationship existed in a sample, subject to every limitation above.

---

# Amendment 1 — 2026-08-30, before any return data was touched

A three-company smoke test of the extraction (NVDA, AAPL, GOOG; 105 filings)
exposed two defects in the specification above. **No price or return data has
been fetched, loaded or examined at the time of writing.** The amendment is
therefore pre-outcome. It is recorded here rather than made silently.

## Defect A — the baseline mixed filing forms

10-K tone is systematically below 10-Q tone, because annual reports carry more
risk and legal discussion:

| | 10-K median | 10-Q median | gap |
|---|---|---|---|
| NVDA | -0.182 | -0.124 | -0.058 |
| AAPL | -0.247 | -0.105 | -0.142 |
| GOOG | -0.378 | -0.309 | -0.069 |
| all | -0.250 | -0.200 | -0.050 |

Filings alternate 10-Q, 10-Q, 10-Q, 10-K. A baseline of "the previous four
filings" is therefore mostly 10-Qs when scoring a 10-K, and contains a 10-K when
scoring the next 10-Q. Every annual report would have shown deteriorating tone
and every following quarter improving tone, on the calendar alone. That artefact
would likely have dominated the result.

**Change.** `baseline(c,t)` is now the mean tone of the company's previous four
filings **of the same form**. A 10-K is compared with 10-Ks, a 10-Q with 10-Qs.

## Defect B — extraction length drives tone

Correlation between MD&A word count and tone, within company:

| | word range | ratio | corr(words, tone) |
|---|---|---|---|
| NVDA | 3,352-6,240 | 1.9x | -0.35 |
| AAPL | 2,152-33,561 | 15.6x | -0.49 |
| GOOG | 5,064-36,079 | 7.1x | -0.54 |

Consistent in sign and material in size: a longer extraction is a more negative
one, because it captures more risk boilerplate. GOOG's 2023 10-K extracted at
5,064 words against a company median of 14,930 and scored -0.012 against a norm
near -0.31 — a +0.30 swing produced by truncation, not by management. Quintile
sorting would have concentrated precisely these failures in the extreme buckets.

**Change, two parts.**

1. **Extraction-quality filter.** A filing is excluded if its word count is
   below 50% or above 200% of that company's median word count for that form.
   Excluded filings are counted and reported, not silently dropped.
2. **Length control.** The primary signal is now tone residualised on
   `log(words)` within company and form, so `dtone` measures a change in
   language rather than a change in how much of it was captured.

## Effect on the specification list

Section 8 permitted five specifications. Amended, still five, holdout still
tested on specification 1 only:

1. Primary: form-matched baseline, quality filter, length-residualised.
2. Form-matched baseline, quality filter, **without** length residualisation
   (to show what the control is doing).
3. 10-K filings only.
4. Excluding companies below $1bn market capitalisation.
5. Tone level rather than tone change (the straw man, unchanged).

Specification 2 in the original list (eight-filing baseline) is dropped: with
form matching, eight prior 10-Ks would require eight years of history and would
gut the sample.

## Standing

Sections 1 to 7 and 9 to 10 are otherwise unchanged. The holdout
(2023-01-01 onward) remains sealed and untouched.

---

# Amendment 2 — 2026-08-31, universe. Still before any return data.

**No price or return data has been fetched, loaded or examined.** This remains
a pre-outcome amendment.

## The finding

Section 9 named survivorship as the most serious limitation and undertook to
quantify it. Quantified, it is fatal to the original design.

Only 20 of the 3,000 companies in the panel stop filing before 2026 — 0.7%
attrition over eight and a half years, against a realistic 30-50%. Reading it
from SEC's own quarterly full-index rather than from the panel:

| | |
|---|---|
| companies filing a 10-K or 10-Q in 2018 | 7,329 |
| of those, present in today's panel | 2,146 (29.3%) |
| **absent** | **5,183 (70.7%)** |
| distinct filers 2018-2026 | 12,122 |
| 10-K/10-Q filings over the period | 225,501 |

Seven in ten companies that were filing in 2018 are missing, because the
universe was defined as today's constituents and survival is therefore built
into it.

## Why this specifically destroys this hypothesis

H1 is that deteriorating tone predicts underperformance. The companies where
that should appear most strongly are those whose language soured and which then
failed. Every one of them has been excluded by construction. The test is
stripped of its own best evidence, so a null would be uninformative and a
positive result would mean only "among companies that survived regardless".

## Change

The universe becomes **every company that filed a 10-K or 10-Q between
2018-01-01 and 2026-09-30**, taken from SEC's quarterly full-index: 12,122
filers, including those that later delisted, were acquired or went bankrupt.
The panel's 3,000 are a subset. 9,123 companies remain to be fetched.

Consequences, accepted:

- The sample roughly quadruples, to an expected ~225,000 filings.
- The universe is no longer restricted to Russell 3000-scale companies. Many
  additions are small, illiquid, or both. **Specification 4 (excluding
  companies below $1bn market capitalisation) therefore becomes the more
  important robustness check rather than an afterthought**, since any effect
  concentrated in microcaps is unlikely to be tradeable.
- Companies without a current market capitalisation, because they no longer
  exist, are retained for the signal and simply cannot be sorted on size.
- Delisting returns are not modelled. A company whose price series ends is
  treated as missing after that date, not as a total loss. This is itself a
  bias and is stated here rather than discovered later.

## Standing

Sections 1 to 8 and 10, and Amendment 1, are unchanged. The holdout
(2023-01-01 onward) remains sealed and untouched.

---

# Amendment 3 — 2026-08-31, scoring model. Still before any return data.

**No price or return data has been fetched, loaded or examined.** Pre-outcome.

## Change

The signal is scored with **FinBERT** (`ProsusAI/finbert`) rather than the
Loughran-McDonald lexicon. Decided on the grounds that a transformer handles
negation and context, which a bag-of-words cannot: "not profitable" contains
"profitable", and LM counts it as positive.

## What FinBERT actually costs, measured not assumed

Benchmarked on this machine (Apple M1, MPS) with proper GPU synchronisation:

| | |
|---|---|
| throughput | **8-9 sequences/sec** (~110 ms each, 512 tokens) |
| MD&A mean length | 8,964 words ≈ 11,400 tokens ≈ 23 chunks |
| whole-document scoring | 5.2M sequences ≈ **160 hours** |

An initial benchmark reported 2,860/sec. That was wrong: MPS is asynchronous,
so it timed how fast Python queued work rather than how fast the GPU did it.
The corrected figure is roughly 300x lower.

## Chunking and aggregation, fixed now

Scoring all 23 chunks is eight days including the re-fetch. Instead:

- Each MD&A is tokenised and the **first and last 512-token chunks** are scored.
  Rationale: MD&A tone concentrates in the opening overview and the closing
  outlook; the middle is largely discussion of tables.
- Document score = **mean of `P(positive) - P(negative)`** across those two
  chunks, from FinBERT's three-way head (positive / negative / neutral).
- Where a filing yields only one chunk, that chunk is the score.

This reduces inference to ~14 hours.

## The corpus is now kept

The previous fetcher discarded text and stored only scores, which is why
changing the model forced a complete re-fetch. **Extracted MD&A text is now
stored, gzipped, per company.** Re-scoring with a different model, more chunks,
or a different aggregation becomes an inference job rather than another 35
hours of downloading.

This makes the chunking choice above reversible, which is the main reason for
accepting it.

## Loughran-McDonald is retained as specification 6

LM is scored alongside FinBERT at no meaningful cost, since the text is in hand.
It is not the primary any more, but it is kept because it is the standard in the
published literature, so a result can be compared with existing work, and
because disagreement between the two is itself informative about whether any
finding depends on the instrument.

The permitted specification count rises from five to six. The holdout is still
tested once, on specification 1 only.

## Standing

Sections 1 to 10 and Amendments 1 and 2 otherwise stand. Development remains
2018-2022, holdout 2023 onward, still sealed and untouched.

---

# Amendment 4 — 2026-08-31, sentence-level scoring. Still before any returns.

**No price or return data fetched, loaded or examined.** Pre-outcome.

## Change

FinBERT is applied to **sentences**, not to 512-token chunks.

FinBERT was fine-tuned on the Financial PhraseBank, a corpus of individual
financial sentences. Feeding it long slabs of continuous prose asks it to do
something it was not trained for. Scoring sentences uses it as intended, and
yields a *distribution* per document rather than one blended figure.

## Sampling, and why it is necessary

Measured on this machine: **32 sentences/sec** (M1, MPS, batch 64). Throughput
does not improve with larger batches — 30/sec at 128 — which indicates the
backend is dispatch-overhead-bound rather than compute-bound. CPU is slower
still at 12.6/sec, so the GPU is the ceiling.

A 5,187-word MD&A yields 188 usable sentences, so the 8,964-word mean gives
about 325. Across 225,000 filings that is 73 million sentences, or **26 days**.

Therefore: the **first 15 and last 15 sentences** of each MD&A are scored.
Chosen because tone concentrates in the opening overview and the closing
outlook, while the middle is largely discussion of tables. A sentence qualifies
if it is between 40 and 600 characters, which excludes headings, fragments and
table debris.

## Document score

For the sampled sentences of filing *i*:

- `tone(i)` = **mean of `P(positive) - P(negative)`** across sampled sentences,
  from FinBERT's three-way head.
- Also recorded, since sentence-level scoring makes them available and they
  cost nothing extra: **share of sentences classified negative**, and the
  **standard deviation** of sentence scores. Neither is the primary signal.
  They are logged for the specification list and for diagnostics.

Everything downstream is unchanged: `dtone` against a form-matched baseline of
four prior filings, the word-count quality filter, quintile sorting, and the
same decision rule.

## Order of work

The **development window (filings before 2023-01-01) is scored first**. The
holdout is sealed until the development analysis is frozen, so there is no
reason to spend inference on it beforehand, and if development returns a clear
null the holdout may never need scoring at all. This halves the immediate cost
to roughly **23 hours**.

## Reversibility

Because the corpus retains full text, the sampling is not a one-way door.
Scoring every sentence for a subset of companies later is a targeted job, not
another sweep.

## Standing

Sections 1 to 10 and Amendments 1 to 3 otherwise stand, except that FinBERT is
now applied per sentence rather than per chunk. Development remains 2018-2022,
holdout 2023 onward, sealed and untouched. Specification count remains six.

---

# Amendment 5 — 2026-08-31, sentence sampling. Still before any returns.

**No price or return data fetched, loaded or examined.** Pre-outcome.

## The defect

Amendment 4 sampled the **first 15 and last 15** sentences, reasoning that tone
concentrates in the opening overview and the closing outlook. It does — and it
concentrates *positively*. Those are the most upbeat passages in an MD&A, and
the middle, where management explains what went wrong, was exactly what the
sampler excluded.

Measured on six NVIDIA filings, 180 sentences: **not one** classified as
strongly negative. For a hypothesis about tone *deteriorating*, the instrument
could barely register bad news.

## The change

Thirty sentences sampled at **even intervals across the whole filing**, so the
middle is represented. Identical cost, identical sentence count, no extra
inference.

## Effect, same six filings

| filed | form | head + tail | evenly spaced |
|---|---|---|---|
| 2018-02-28 | 10-K | +0.3793, neg 0.00 | +0.1929, neg 0.13 |
| 2018-05-22 | 10-Q | +0.0579, neg 0.00 | +0.2561, neg 0.07 |
| 2018-08-16 | 10-Q | +0.0242, neg 0.00 | +0.2189, neg 0.13 |
| 2018-11-15 | 10-Q | +0.0202, neg 0.00 | +0.2804, neg 0.10 |
| 2019-02-21 | 10-K | +0.3920, neg 0.00 | +0.1653, neg 0.13 |
| 2019-05-16 | 10-Q | +0.0254, neg 0.00 | −0.0998, neg 0.30 |

Negative sentences now appear in every filing. The spurious 10-K inflation
disappears — head-and-tail scored annual reports at +0.38 against +0.02 for
quarterlies, an artefact that would have fought the form-matched baseline of
Amendment 1. And the final row changes sign: a quarter the old sampler called
mildly positive is 30% negative once the middle of the document is visible.

## Throughput correction

Measured in practice at **23.5 sentences/sec**, not the 32 a synthetic
benchmark suggested. The development window is therefore about **30 hours**.

## Standing

Sections 1 to 10 and Amendments 1 to 4 otherwise stand, except that sampling is
even rather than head-and-tail. Holdout sealed.

---

# Amendment 6 — 2026-09-01, universe. Still before any return data.

**No price or return data fetched, loaded or examined.** Pre-outcome.

## The finding

Phase 1 finished on 2026-09-01 at 06:55: 50,945 MD&A blocks with text, across
the 4,408-company viable universe. Auditing it before scoring, 990 companies had
listed 10-K/10-Q filings but yielded no MD&A at all, and 32.6% of all listed
filings produced nothing.

That first reads as an extraction defect. It is not. Resolving SIC codes for the
whole universe shows what those companies are:

| SIC | description | companies | filings listed | MD&A kept | yield |
|---|---|---:|---:|---:|---:|
| 6189 | Asset-Backed Securities | 516 | 4,297 | 0 | **0.0%** |
| 6770 | Blank Checks | 587 | 5,706 | 966 | 16.9% |

Asset-backed issuers file under Regulation AB, which prescribes servicing and
compliance disclosures and **contains no MD&A item**. The 0.0% is not a sampling
artefact: across 4,297 filings the extractor found an MD&A block zero times. The
worst single case, Santander Drive Auto Receivables (CIK 1383094), listed 236
filings; its 10-K is a 9,000-character document in which the strings
"management's discussion", "item 7" and "results of operations" each appear
exactly zero times. Blank-cheque shells are the same story with a partial
exception: a SPAC that has completed a merger sometimes files a real MD&A, which
is why the yield is 16.9% rather than zero.

## Why this matters to the hypothesis

Neither entity type has tradeable common equity whose forward return the study
could measure, so both were always going to drop out at the return join. Leaving
them in the corpus would have meant reporting a 67.4% extraction yield and a
990-company gap as though they were defects in the instrument, when almost all of
it is the instrument behaving correctly.

## Change

Exclude SIC **6189** (Asset-Backed Securities) and **6770** (Blank Checks) from
the universe. Effective for phase 2 scoring and everything downstream.

| | before | after |
|---|---:|---:|
| companies | 4,408 | **3,270** |
| filings listed | 75,531 | 65,228 |
| MD&A blocks | 50,945 | **49,957** |
| companies yielding nothing | 990 | 171 |
| extraction yield | 67.4% | **76.6%** |

The exclusion removes 26% of companies but only **1.9% of the scored data**,
which is the point: these entities contributed almost nothing but accounted for
83% of the apparent failure.

Companies with at least one usable filing: **3,099**.

The retained universe is written to `universe_final.json`; the excluded CIKs and
their SIC descriptions to `excluded_ciks.json`, so the exclusion is auditable
rather than asserted. SIC codes come from the SEC submissions endpoint and are
cached in `sic_map.json`; all 4,408 resolved, none unknown.

## What this does not fix

171 retained companies still yield no MD&A, and the retained extraction yield is
76.6%, not 100%. Those are genuine gaps and are **not** being excluded — doing so
would be selecting on an outcome of the instrument. They stay in the universe and
simply contribute no observations. Checked before this amendment and stated here:
the kept blocks are evenly distributed across filing years (5,343–6,777 per year
for 2018–2025, 2026 partial) and split 36,543 10-Q to 14,402 10-K, so the loss
carries no obvious temporal or form bias.

## Standing

Sections 1 to 10 and Amendments 1 to 5 otherwise stand, with the universe as
amended. Holdout sealed; phase 2 has not been run.
