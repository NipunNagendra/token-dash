# Manual inputs

Both files are append-only. The loader skips rows whose key already exists.

## ramp_ai_index.csv
Ramp AI Index (https://ramp.com/data/ai-index). Download the monthly table and paste rows.

| column | meaning |
|---|---|
| month | first of month, YYYY-MM-01 |
| vendor | as Ramp names it (OpenAI, Anthropic, ...) or `all` for aggregate series |
| metric | `adoption_pct` (% of US businesses paying), `spend_per_employee`, `share_subscriptions`, `share_coding_agents`, `share_api` |
| segment | `all`, or Ramp's sector/size/funding cut |
| value | number |

## disclosures.csv
Token-volume figures from earnings calls and lab posts. Store the definition verbatim.

| column | meaning |
|---|---|
| date | disclosure date |
| company | GOOGL, MSFT, AMZN, META, ORCL, OpenAI, Anthropic, ... |
| metric | `tokens_per_month`, `tokens_per_day`, `tokens_cumulative_quarter` |
| value | number |
| unit | `T` (trillion), `Q` (quadrillion) |
| definition | what they said they counted, quoted |
| source_url | transcript or post URL (Quartr link fine) |
