# bilaalraja.com

Static site. Everything under `docs/` is what gets served; nothing else is.

## Refresh after reindexing

    python3 publish.py

That regenerates the dashboard from the current data in the R3000 pipeline,
restages `docs/`, and stamps every page with the build date and the latest
filing date carried in the data itself.

    python3 publish.py --no-build

Restages the existing HTML without regenerating — use when only the site
wrapper has changed.

## Deploy

    git add -A && git commit -m "refresh" && git push

GitHub Pages serves `docs/` on the `main` branch. `docs/CNAME` holds the
custom domain.

## Where the dates come from

`make_r3k_dash.py` derives them from the data, not the clock alone:

* `latest_filing` — the most recent filing date present in `r3k_scored.json`
* `latest_end`    — the most recent fiscal period end
* `built`         — when the page was generated

The page therefore cannot claim to be fresher than the filings behind it.
