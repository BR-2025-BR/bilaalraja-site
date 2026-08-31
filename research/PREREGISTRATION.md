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
