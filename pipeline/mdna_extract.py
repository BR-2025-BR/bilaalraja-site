"""Extract the Results-of-Operations passage from a 10-Q or 10-K.

Full MD&A runs 15-30k characters; embedding that for 2,544 companies would be
~50MB against a 16MB artifact cap. What carries the actual explanation is a much
smaller slice -- the prose immediately under "Results of Operations", where
filers write "revenue increased X% driven by Y".

Two traps this handles:
  - The first match for "Management's Discussion and Analysis" is the TABLE OF
    CONTENTS entry, not the section. A naive search returns 97 characters of
    contents listing.
  - Financial tables flatten into long runs of digits when tags are stripped,
    which swamp the prose. They are removed before the text is extracted.
"""
import re, html

# Heading conventions vary by filer. Wells Fargo's 10-Q contains ZERO instances
# of "Management's Discussion and Analysis" -- it titles the section "Financial
# Review" -- so anchoring on one phrase silently loses whole companies.
# Anchors are tiered. "Results of Operations" is weak because it also heads
# footnote subsections; using it at the same priority as a real MD&A heading is
# how Caterpillar returned a leases note and P&G returned goodwill allocation.
STRONG = re.compile(r"Management.{0,3}s\s+Discussion\s+and\s+Analysis"
                    r"|Financial\s+Review", re.I)
WEAK   = re.compile(r"Earnings\s+Performance|Results\s+of\s+Operations"
                    r"|Overview\s+of\s+(Financial|Results)", re.I)
HEAD   = STRONG
END   = re.compile(r"Item\s+[347]A?\s*[\.—:-]|Quantitative\s+and\s+Qualitative\s+Disclosures"
                   r"|Controls\s+and\s+Procedures", re.I)
ROO   = re.compile(r"Results\s+of\s+Operations", re.I)

def to_text(raw: str) -> str:
    """HTML to plain text, with tables dropped."""
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    s = re.sub(r"(?is)<table[^>]*>.*?</table>", " \n[TABLE] \n", s)   # numeric noise
    s = re.sub(r"(?i)<(br|/p|/div|/tr|/h\d)[^>]*>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\xa0]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()

def _qualifying(seg: str) -> int:
    """Count sentences that report a change -- the density of what we want."""
    n = 0
    for t in re.split(r"(?<=[.!?])\s+(?=[A-Z(\u201c])", seg[:120000]):
        if 45 < len(t) < 700 and SUBJ.search(t) and CHANGE.search(t) and PAST.search(t):
            n += 1
    return n

def mdna_block(txt: str):
    """The MD&A section, chosen by CONTENT rather than size.

    Size is the wrong criterion in both directions. Taking the largest candidate
    ran on into risk factors and accounting notes (DTE 155k, Trade Desk 129k).
    Capping at 90k then broke banks the other way -- JPMorgan's real MD&A is
    ~190k, so the cap rejected it and fell back to the document's GLOSSARY,
    yielding definitions of Alt-A loans instead of results commentary.

    Scoring each candidate by how many change-reporting sentences it contains
    picks the right block in both cases without needing a length assumption.
    """
    def scan(pattern):
        b, bn = None, -1
        for m in list(pattern.finditer(txt))[:40]:
            h = m.start()
            e = END.search(txt, h + 120)
            seg = txt[h: e.start() if e else min(h + 220000, len(txt))]
            if len(seg) < 1500: continue
            n = _qualifying(seg)
            if n > bn: b, bn = seg, n
        return b, bn
    # a real MD&A heading always wins over a weak one, even if the weak block
    # scores higher -- the footnotes score well precisely because they are notes
    best, best_n = scan(STRONG)
    if best is None or best_n <= 0:
        best, best_n = scan(WEAK)
    if best is not None and best_n > 0:
        return best
    # Last resort for filers matching no heading at all: slide a window over the
    # document and keep the densest. Slower, but it never returns nothing simply
    # because a company invented its own section title.
    W = 45000
    for i in range(0, max(len(txt) - W, 1), W // 2):
        seg = txt[i:i + W]
        n = _qualifying(seg)
        if n > best_n: best, best_n = seg, n
    return best if best_n > 0 else None

# A positional slice after "Results of Operations" returns the safe-harbour
# paragraph, not the discussion -- filers put boilerplate first. So select the
# sentences that actually carry an explanation instead of a fixed window.
SUBJ  = re.compile(r"\b(net sales|revenue|revenues|net income|gross margin|operating income|"
                   r"operating expenses|earnings|sales|margin|cash flow|free cash flow)\b", re.I)
CHANGE= re.compile(r"\b(increase[sd]?|decrease[sd]?|grew|growth|decline[sd]?|rose|fell|"
                   r"improved|higher|lower|up|down)\b", re.I)
DRIVER= re.compile(r"\b(driven by|due to|primarily|reflecting|attributable to|"
                   r"as a result of|partially offset|offset by|resulting from|led by)\b", re.I)
BOILER= re.compile(r"forward.looking|Private Securities Litigation|words such as|"
                   r"risks and uncertainties|undue reliance|except as required by law|"
                   r"see Part I|refer to Note|incorporated by reference|"
                   r"Item \d|Form 10-[KQ]", re.I)
# Risk factors and accounting policies both score well on the subject/driver
# patterns while explaining nothing about the period. They read as conditional
# or definitional rather than reporting what happened.
RISK  = re.compile(r"\b(may|might|could|would|if we|there can be no assurance|"
                   r"adversely affect|no guarantee|our ability to|we expect to|"
                   r"we intend|believe that we)\b", re.I)
POLICY= re.compile(r"\b(are primarily composed of|we account for|is recognized|"
                   r"are recorded|in accordance with|consist[s]? of|"
                   r"are measured|we define|is calculated as|represents )\b", re.I)
# Notes to the financial statements are dense in change-language ("goodwill
# decreased due to currency") and therefore beat MD&A on any naive scoring. They
# are recognisable by their subject matter.
FOOTNOTE = re.compile(r"goodwill|accumulated other comprehensive|performance obligation|"
                      r"fair value (hierarchy|measurement)|Level [123]\b|"
                      r"is allocated by|carrying (value|amount)|amortization of intangible|"
                      r"unrecognized (tax|compensation)|lease (liabilit|asset)|"
                      r"right.of.use|deferred tax asset|pension (plan|benefit)|"
                      r"stock.based compensation expense of|reportable segment[s]? as follows", re.I)
# Prefer the lines that describe the trading performance over tax or balance-sheet
# mechanics -- NVIDIA led with its effective tax rate under the old scoring.
CORE  = re.compile(r"\b(revenue|net sales|sales|gross margin|gross profit|"
                   r"operating income|net income|net earnings)\b", re.I)
MINOR = re.compile(r"\b(tax rate|effective tax|income tax|other comprehensive|"
                   r"interest expense|foreign currency translation)\b", re.I)
PAST  = re.compile(r"\b(increased|decreased|declined|rose|fell|grew|improved|"
                   r"was|were|compared (to|with)|versus|year.over.year)\b", re.I)

def results_slice(block: str, limit=2600):
    """Sentences from MD&A that explain a change, ranked and trimmed to a budget."""
    if not block: return None
    # Anchoring on "Results of Operations" narrows a big block to the relevant
    # part -- but in a very large block the first match can land near the end (a
    # late subsection or a contents line), leaving a boilerplate tail. Wells
    # Fargo's 171k-character block reduced to 5,598 characters that way, of which
    # 11 of 19 sentences were forward-looking boilerplate and nothing survived.
    # If the anchor leaves an implausibly small remainder, score the whole block.
    m = ROO.search(block)
    seg = block
    if m:
        cand = block[m.start():]
        if len(cand) >= min(15000, len(block) * 0.2):
            seg = cand
    seg = re.sub(r"\[TABLE\]", " ", seg)
    seg = re.sub(r"\s+", " ", seg).strip()
    sents = re.split(r"(?<=[.!?])\s+(?=[A-Z(\u201c])", seg)
    scored = []
    for s in sents:
        if len(s) < 45 or len(s) > 700: continue
        if BOILER.search(s): continue
        if RISK.search(s):   continue          # conditional -> a risk factor
        if POLICY.search(s): continue          # definitional -> an accounting note
        if FOOTNOTE.search(s): continue        # subject matter of a note, not MD&A
        digits = sum(c.isdigit() for c in s)
        if digits > len(s) * 0.35: continue          # a flattened table row
        sc = 0
        if SUBJ.search(s):   sc += 2
        if CHANGE.search(s): sc += 2
        if DRIVER.search(s): sc += 3
        if re.search(r"\d+(\.\d+)?\s*%", s): sc += 2   # carries a percentage
        if re.search(r"\$\s?\d", s): sc += 1
        if PAST.search(s):   sc += 2           # reports what happened
        if CORE.search(s):   sc += 3           # trading performance beats mechanics
        if MINOR.search(s) and not CORE.search(s): sc -= 3
        if sc >= 7: scored.append((sc, s))
    if not scored: return None
    out, used = [], 0
    for sc, s in scored:                              # document order, not score order
        if used + len(s) + 1 > limit: break
        out.append(s); used += len(s) + 1
    return " ".join(out) if out else None

def extract(raw: str, limit=2600):
    txt = to_text(raw)
    blk = mdna_block(txt)
    return {"chars_text": len(txt),
            "mdna_chars": len(blk) if blk else 0,
            "slice": results_slice(blk, limit)}
