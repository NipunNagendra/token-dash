# token-dash

Weekly dashboard of LLM token usage across the public slices that exist: OpenRouter (model-level daily
tokens), Vercel AI Gateway (share by lab/model incl. spend), Artificial Analysis quality indices with
OpenRouter pricing, Cloudflare Radar GenAI ranks, Ramp AI Index adoption, and a hand-kept log of
company token disclosures. No source is the market; the page shows them side by side with their skew
labelled and leads with share *changes*, not levels.

## Run

```bash
pip install -r requirements.txt
cp .env.example .env        # add OPENROUTER_API_KEY (any inference key); CF_API_TOKEN optional
python run.py               # pull everything, rebuild model_map, write site/index.html
python run.py site          # rebuild the page only
open site/index.html
```

Each pull is isolated: a failing source is logged in `run_log` and shown in the page footer; the rest
still build. OpenRouter rankings backfill from 2025-01-01 automatically on the first keyed run.

## Layout

```
run.py                     orchestrator (pull | site | all)
tokendash/db.py            DuckDB schema; append_new() = insert-if-absent, nothing is overwritten
tokendash/pull_*.py        one file per source, raw JSON kept in data/raw/
tokendash/load_manual.py   data/manual/ramp_ai_index.csv, disclosures.csv (see data/manual/README.md)
tokendash/model_map.py     permaslug -> canonical model / lab / open-weights; config/lab_map.csv + overrides
tokendash/metrics.py       data extraction, actual list prices, dated price changes, collection status
tokendash/build_site.py    embedded source data and static page (Plotly from a pinned CDN)
tokendash/terminal_core.js calendar-exact comparisons, complete Vercel weeks, price envelope
tokendash/terminal.js      weekly desk and price explorer; source views in template.html
tokendash/terminal.css     responsive terminal theme and print stylesheet
data/tokendash.duckdb      committed weekly by the Actions job
.github/workflows/weekly.yml   Monday cron, commits data + site, deploys to Pages
tests/make_fixture.py      synthetic OpenRouter rows for exercising OR code paths without a key
```

## Deploy

Repo secrets: `OPENROUTER_API_KEY`, optionally `CF_API_TOKEN`. Enable GitHub Pages with source
"GitHub Actions". The workflow commits `data/` and `site/` and deploys `site/`.

## Attribution

OpenRouter data: "Source: OpenRouter (openrouter.ai/rankings), as of {date}" (CC BY 4.0).
Vercel AI Gateway leaderboard: CC BY 4.0. Quality indices: Artificial Analysis. The page footer carries all of this.

## Weekly desk

The default screen is a single weekly read: OpenRouter demand and growth momentum, open/closed/unknown
weight shares, lab capture across independent sources, model movers, recent catalog listings, actual
input/output prices, and enterprise/consumer context. All existing source explorers remain accessible.
The 1W / 4W / 13W controls change share comparisons. The volume reading always shows current and prior
WoW growth. The leading 12 labs are shown by default; expand or filter to see all labs. Print / PDF
uses the browser print dialog with a dense landscape layout.

- **Denominators:** OpenRouter shares use all observed tokens, including the unnamed bucket. Open
  and closed classifications follow catalog/model-map heuristics. Unclassified tokens remain visible.
  Free-variant share is an overlapping cut, not an additional weight class.
- **Calendar periods:** OpenRouter uses complete Monday–Sunday weeks. Vercel uses seven-day means
  of daily shares, not volume-weighted weekly share. Missing comparison periods stay unavailable;
  Cloudflare compares exact dates even when its returned observations are weekly. Ramp comparisons
  use the previous calendar month. Each board column shows its dates and unit.
- **Cross-source interpretation:** Vercel metrics are one population. No consensus score, global
  token estimate, cloud allocation, or token-to-GPU conversion is displayed. The weekly read describes
  observed volume changes and source divergences without asserting causality.
- **Pricing:** All priced text models remain visible, including zero-cost and unbenchmarked models.
  AA scores carry a separate observation date. Input/output/cache prices are separate; an unlisted
  cache price stays blank. The selected price/quality envelope excludes zero prices on its log axis.
  Same-model history and before/after dates replace any assumed blended cost. One snapshot cannot
  establish deflation.
- **Listings:** Catalog creation is not a verified model release date. The recent-listing table shows
  observed model and lab share changes; these alone cannot prove share capture caused by a release.
- **Availability:** Observation dates are distinct from the build date. Daily/weekly sources are stale
  after 10 days, monthly Ramp after 75 days. Collection failures leave existing observations readable.
  Source data and tables are embedded; charts require the pinned Plotly CDN. No client-side API keys.

## Validation

```bash
python -m pytest tests -q
node tests/test_terminal_core.cjs
python run.py site
node tests/test_render.cjs
```

The smoke fixture builds into a temporary output directory and never replaces the real dashboard.
Calculation tests cover missing calendar periods, incomplete Vercel weeks, unknown weight coverage,
rank direction, and actual price history. The render test executes all source views with stored data
and empty-source states through a minimal adapter; it is not browser or visual testing.
