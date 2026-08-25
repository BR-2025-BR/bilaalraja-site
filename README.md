# bilaalraja.com

Static site. Everything under `docs/` is what gets served; nothing else is.

## Refreshing the data

    cd pipeline
    python3 refresh.py

Reads the SEC daily filing index to find which companies have filed since the
last run, fetches only those, reprices, rebuilds the universe and the panel,
rescores, checks the result, and rebuilds the dashboard.

    python3 refresh.py --full         refetch every companyfacts file
    python3 refresh.py --prices-only  reprice without touching SEC data
    python3 refresh.py --force        promote despite a failed check

Incremental is the normal case and takes minutes. `--full` takes about an hour
and downloads roughly 3GB.

Then publish:

    cd .. && python3 publish.py
    git add -A && git commit -m "refresh" && git push

## The checks, and why each one exists

`refresh.py` refuses to promote a build that fails any of these. Every one of
them is here because that exact failure already happened.

* **Price consistency.** The price the panel used must match the snapshot. On
  25 August the build skipped `build_universe_v2`, so the panel carried prices
  from six days earlier while the page stamped the new date. Market cap came out
  byte-identical, which reads as "nothing moved" rather than as a fault, so this
  compares the prices directly rather than inferring anything.
* **Total market cap** must not move more than 12%.
* **Company count** must not move by more than 150.
* **Size floor** must not halve. A collapsing floor means large companies lost
  their price and the top-3000 cut reached further down.
* **Price coverage** must not drop by more than 100 names. A rate-limited fetch
  once dropped 471, including Alphabet, Meta and Berkshire.
* **Price date** must not go backwards.

`refresh_state.json` holds the previous run's figures and is what the checks
compare against.

## Where the dates on the pages come from

`make_r3k_dash.py` derives them from the data, not the clock alone:

* `latest_filing` — most recent filing date in `r3k_scored.json`
* `latest_end` — most recent fiscal period end
* `built` — when the page was generated

So a page cannot claim to be fresher than the filings behind it.

## Layout

    docs/          what gets served
    pipeline/      the data pipeline and its inputs
    publish.py     stages docs/ from pipeline output
    contacts.txt   tracked outreach links (local only, gitignored)
