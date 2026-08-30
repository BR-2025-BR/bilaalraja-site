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
