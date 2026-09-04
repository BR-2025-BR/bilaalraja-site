# Result: MD&A tone change does not predict forward returns

**Frozen 2026-09-04.** Development window only. The holdout has not been opened.

## Outcome

**Null.** Not one of the five pre-registered specifications met the decision
rule fixed in section 7 before any return data existed.

| # | specification | n | spread | annualised | NW *t* | |
|---|---|---:|---:|---:|---:|---|
| 1 | primary, length-residualised | 38,542 | −1.40% | −9.74% | **−0.82** | fail |
| 2 | no length control | 38,542 | −1.63% | −11.29% | −0.89 | fail |
| 3 | 10-K only | 2,106 | −1.75% | −27.71% | −1.13 | fail |
| 4 | market cap ≥ $1bn | 16,038 | −1.07% | −3.07% | −0.90 | fail |
| 5 | tone level (straw man) | 38,542 | +0.76% | +11.89% | +1.98 | fail |

The rule required the spread to be negative **and** |*t*| > 2.5 with Newey-West
standard errors at 63 lags. Every spread except the straw man carries the
hypothesised sign; not one carries the significance.

## The finding underneath the finding

Without the overlap correction, specification 1 would have passed.

```
daily spread series, 1,153 sessions
  naive t        -3.42     <- clears the 2.5 bar
  Newey-West t   -0.82     <- does not
  ratio           4.2x
```

Each filing carries a 63-trading-day forward return, so filings a month apart
share two thirds of their window. Treating 38,542 of them as independent shrinks
the standard error by roughly the square root of the overlap and manufactures
significance from nothing. The correction was specified in advance precisely so
this decision could not be made after seeing the number.

The implementation was verified against synthetic series before use: on a
63-day moving average of noise it returned *t* = −0.42 where the naive statistic
read −2.53.

## Quintiles

Q1 is the most deteriorated tone. If the hypothesis held, abnormal returns would
fall monotonically from Q5 to Q1.

| quintile | n | median dtone | abnormal 63d |
|---|---:|---:|---:|
| Q1 | 7,716 | −0.143 | −1.76% |
| Q2 | 7,704 | −0.052 | −0.39% |
| Q3 | 7,706 | +0.002 | +0.45% |
| Q4 | 7,704 | +0.054 | −1.04% |
| Q5 | 7,712 | +0.142 | −0.36% |

Not monotonic. Q1 is the worst, which is the right direction, but Q4 sits below
Q3 and Q5, and the gradient the hypothesis predicts is absent.

## What was actually tested

- **2,320,170 sentences** through FinBERT, 106,801 filings, 7,549 companies.
- Signal: tone residualised on log(words) within company and form, differenced
  against the mean of the previous four filings **of the same form**.
- Exclusions, all counted: 6,858 filings on the extraction-quality filter
  (6.4%), 49,692 for fewer than four same-form priors.
- Outcome: return from close t+1 to close t+63, minus the equal-weighted return
  of every sample company over the identical two sessions.
- Prices are survivorship-free: 45.3M rows covering 20,961 tickers including
  14,659 delisted, with a −30% delisting return applied to 1,006 names that
  stopped trading inside a holding window.

## Limitations, as stated in advance and as found

- **Coverage.** 39,982 of 50,251 signal observations could be priced. 1,460
  companies are absent from the vendor's universe entirely and carry 20% of the
  filings the study would otherwise have used.
- **10-K sample is thin.** Form matching plus four priors needs five years of
  annual reports, leaving 2,106 observations for specification 3.
- **Specification 4 uses a substitute market cap.** Sharadar's DAILY table is
  outside this subscription, so market cap is the share count from each filing's
  own cover page multiplied by that day's close. Point-in-time and unrestatable,
  but available for only 26,440 of 39,982 observations, and those skew larger
  and longer-lived.

## The holdout stays sealed

Section 7 requires development significance **and** holdout confirmation. With
development failing, no holdout result could produce a pass, so opening it would
spend a single-use resource for nothing. It remains untouched and available for
a future pre-registered hypothesis.

## What this does and does not say

It says that on 38,542 filings from 2018 to 2022, a change in the tone of
management's own discussion, measured sentence-by-sentence by a finance-tuned
language model against the company's own history, did not predict the next
quarter's abnormal return at the standard this study set in advance.

It does not say tone is uninformative. It says this signal, at this horizon, on
this universe, at this bar, is not.
