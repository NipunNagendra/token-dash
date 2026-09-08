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
tokendash/metrics.py       growth, share, HHI, open share, movers, launch reaction, pricing frontier, agreement matrix
tokendash/build_site.py    static page (Plotly from a pinned CDN build)
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
