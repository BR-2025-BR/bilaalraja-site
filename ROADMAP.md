# Roadmap

Things deliberately deferred, with the investigation already done so the next
attempt does not start from nothing.

---

## 1. Parse material facts out of 8-K filings  — NEXT PRIORITY

**Asked for:** instead of the item label ("unregistered share sale"), state what
actually happened — "2,500,000 shares issued at $12.50".

**Investigated 2026-08-31 on two live filings. Findings:**

- **The iXBRL trap.** SEC links documents through a viewer at `/ix?doc=...`,
  which is a JavaScript shell. Fetching it returns ~75 characters and looks
  like an empty filing. The real document is the path after `?doc=`. Any
  extractor must unwrap this first.
- **The numbers are usually in tables.** Brookfield's Item 3.02 stated
  "aggregate consideration of approximately $3,074,000" in prose, but the
  per-unit detail — exactly the "X at $Y" wanted here — was in a table.
  `mdna_extract.to_text` strips tables deliberately, because they were numeric
  noise for MD&A work. An 8-K extractor needs a different text pass that keeps
  them.
- **Section headings are unreliable.** One of two sampled filings had its
  Item 5.02 heading not located at all, in 5,307 characters of clean text.
  Filers format headings inconsistently, so anchoring on `Item 5.02` misses.

**Architecture constraint.** The ticker is served per visitor from an edge
function. Parsing bodies means pulling multi-megabyte documents, forty per
request, which cannot run at the edge. It needs a background job that processes
new 8-Ks and writes a static JSON the ticker reads.

**Recommended approach.** Narrow and conservative. Handle the item types where
the fact is reliably in prose — aggregate consideration (3.02), principal and
rate (2.03), amount (2.06), name and role (5.02) — and **print nothing rather
than guess** when confidence is low, falling back to the plain item label.

A wrong figure stated as fact is worse than no figure, particularly on a site
whose argument is that every number traces to a primary source.

**The reliable alternative** is an LLM reading each filing: accurate, but needs
an API key, a per-filing cost and a runtime dependency. Different project.

---

## 2. Event study: do 8-K filings move prices?

Deferred until the MD&A tone study reports, deliberately — it reuses the same
machinery, and if LM scoring carries no signal it is better to know that before
building a second study on the same foundations.

**Established already:** of 39 sampled live 8-Ks, **none** were filed during
market hours (90% pre-market, 10% after close). "Immediate aftermath" therefore
means the next open, not the moment of filing.

Causation is not recoverable; the honest measure is abnormal return against a
market or sector model. Note Item 2.02 filings *are* the earnings release, so
any move is the earnings, not the filing.

Should be pre-registered, like the tone study.

---

## 3. Smaller, known items

- **`&amp;` double-escape** on company names containing an ampersand (JPM,
  P&G). Display only, confined to those names.
- **Ticker does not refresh.** It fetches once on load; no polling, no
  refresh on visibility change. The strip says "Live" and is only live at the
  moment the page opens.
- **Successor CIKs.** XOM at $644bn, SpaceX, Honeywell Aerospace and Imperial
  Oil are excluded because a new entity lacks four quarters of history while
  the predecessor CIK holds thousands of facts. A real design decision, not a
  bug.
- **Incremental panel build** reuses a row only when price is unchanged, and
  price changes every refresh, so it reuses almost nothing. Needs fundamentals
  separated from price-derived fields.
- **`streamed-tui/`** is untracked in the repo. Move it out or gitignore it.
