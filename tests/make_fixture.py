"""Synthetic OpenRouter rankings-daily rows (schema-faithful) so OR code paths run without a key.
Usage: python tests/make_fixture.py <db_path>. Never point this at data/tokendash.duckdb."""
import sys, datetime as dt, numpy as np, pandas as pd
sys.path.insert(0, ".")
from tokendash import db
path = sys.argv[1]
assert "tokendash.duckdb" not in path
con = db.connect(path)
rng = np.random.default_rng(0)
models = con.execute("""SELECT model_id, created FROM or_pricing WHERE snapshot_date=(SELECT max(snapshot_date) FROM or_pricing)
                        ORDER BY created DESC LIMIT 80""").df()
start, end = dt.date(2025, 1, 1), dt.date.today() - dt.timedelta(days=1)
days = pd.date_range(start, end)
base = rng.lognormal(24, 1.2, len(models))
rows = []
for i, r in models.iterrows():
    rel = max(pd.Timestamp(r.created), pd.Timestamp(start))
    life = ((days - rel).days.values).astype(float)
    curve = np.where(life < 0, 0, base[i] * (1 - np.exp(-life / 20)) * np.exp(-life / 400) * np.exp(0.0025 * np.arange(len(days))))
    noise = rng.lognormal(0, 0.15, len(days))
    for d, v in zip(days, curve * noise):
        if v > 0:
            rows.append((d.date(), r.model_id, int(v)))
df = pd.DataFrame(rows, columns=["date", "permaslug", "tokens"])
top = df.sort_values(["date", "tokens"], ascending=[True, False]).groupby("date").head(50)
other = df[~df.index.isin(top.index)].groupby("date")["tokens"].sum().reset_index().assign(permaslug="other")
out = pd.concat([top, other]); out["pulled_at"] = pd.Timestamp.utcnow().tz_localize(None)
n = db.append_new(con, "or_daily", out, ["date", "permaslug"]); print("fixture rows", n)
apps = pd.DataFrame([dict(window_start=end - dt.timedelta(days=6), window_end=end, sort=s, category=c, rank=k + 1,
                          app_id=1000 + k, app=f"App {k+1}", tokens=int(1e12 / (k + 1)), requests=int(1e6 / (k + 1)),
                          pulled_at=pd.Timestamp.utcnow().tz_localize(None))
                     for s in ("popular", "trending") for c in ("all", "coding") for k in range(20)])
print("apps", db.append_new(con, "or_apps", apps, ["window_start", "window_end", "sort", "category", "app_id"]))
from tokendash import model_map; model_map.build(con)
con.close()
