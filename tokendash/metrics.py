"""Derived metrics. Every function returns a pandas frame from the DuckDB tables; nothing is fused across
sources except in `agreement()`, where the cells stay per-source."""
import numpy as np
import pandas as pd

CORE_LABS = ["Anthropic", "OpenAI", "Google", "DeepSeek", "xAI", "Meta", "Qwen", "Mistral"]
LAB_OPEN_DEFAULT = {  # lab-level flag used for Vercel, which only publishes lab names
    "OpenAI": False, "Anthropic": False, "Google": False, "xAI": False, "Amazon": False, "Cohere": False,
    "Perplexity": False, "ByteDance": False, "Inception": False, "Morph": False, "Interfaze": False,
}


CF_SERVICE_LAB = {"ChatGPT / OpenAI": "OpenAI", "Claude / Anthropic": "Anthropic", "Google Gemini": "Google",
                  "Grok / xAI": "xAI", "Meta AI": "Meta", "DeepSeek": "DeepSeek", "Mistral": "Mistral", "Qwen": "Qwen"}


def _lab_bucket(lab):
    return lab if lab in CORE_LABS else "Other"


# ---------------- OpenRouter ----------------

def or_daily(con) -> pd.DataFrame:
    df = con.execute("""
        SELECT d.date, d.permaslug, d.tokens::DOUBLE AS tokens,
               coalesce(m.canonical_model, d.permaslug) AS model,
               coalesce(m.lab, CASE WHEN d.permaslug='other' THEN 'Other (outside top 50)' END) AS lab,
               coalesce(m.open_weights, NULL) AS open_weights, coalesce(m.is_free_variant, false) AS is_free,
               m.release_date
        FROM or_daily d LEFT JOIN model_map m USING (permaslug)""").df()
    df["date"] = pd.to_datetime(df["date"])
    return df


def or_weekly(con, complete_only=True) -> pd.DataFrame:
    d = or_daily(con)
    if d.empty:
        return d
    d["week"] = d["date"] - pd.to_timedelta(d["date"].dt.weekday, unit="D")
    if complete_only:
        n = d.groupby("week")["date"].nunique()
        d = d[d["week"].isin(n[n == 7].index)]
    return d


def or_lab_weekly(con, bucket=False) -> pd.DataFrame:
    """Weekly tokens per lab. bucket=True folds non-core labs into 'Other' (for the cross-source board only)."""
    w = or_weekly(con)
    if w.empty:
        return w
    w["lab_b"] = w["lab"].fillna("Other").map(lambda l: l if (not bucket or l == "Other (outside top 50)") else _lab_bucket(l))
    g = w.groupby(["week", "lab_b"])["tokens"].sum().reset_index().rename(columns={"lab_b": "lab"})
    g["share"] = g["tokens"] / g.groupby("week")["tokens"].transform("sum")
    return g


def or_totals(con) -> pd.DataFrame:
    w = or_weekly(con)
    if w.empty:
        return w
    t = w.groupby("week")["tokens"].sum().rename("tokens").to_frame()
    lt = np.log(t["tokens"])
    t["wow"] = np.exp(lt.diff(1)) - 1
    t["g4w"] = np.exp(lt.diff(4)) - 1
    t["g13w"] = np.exp(lt.diff(13)) - 1
    t["top50_cov"] = 1 - w[w.permaslug == "other"].groupby("week")["tokens"].sum() / t["tokens"]
    return t.reset_index()


def or_open_share(con) -> pd.DataFrame:
    w = or_weekly(con)
    if w.empty:
        return w
    known = w[w.permaslug != "other"].dropna(subset=["open_weights"])
    g = known.groupby(["week", "open_weights"])["tokens"].sum().unstack(fill_value=0)
    g["open_share"] = g.get(True, 0) / g.sum(axis=1)
    return g.reset_index()[["week", "open_share"]]


def or_hhi(con) -> pd.DataFrame:
    w = or_weekly(con)
    if w.empty:
        return w
    g = w.groupby(["week", "model"])["tokens"].sum().reset_index()
    g["s"] = g["tokens"] / g.groupby("week")["tokens"].transform("sum")
    return (g["s"] ** 2).groupby(g["week"]).sum().rename("hhi").reset_index()


def or_movers(con, n=15) -> pd.DataFrame:
    """4-week change in weekly tokens per canonical model (free variants merged), with sparkline of last 13 weeks."""
    w = or_weekly(con)
    if w.empty:
        return w
    w = w[w.permaslug != "other"]
    g = w.groupby(["week", "model"])["tokens"].sum().unstack(fill_value=0)
    if len(g) < 5:
        return pd.DataFrame()
    last, prev = g.iloc[-1], g.iloc[-5]
    share = g.div(g.sum(axis=1), axis=0)
    meta = w.drop_duplicates("model").set_index("model")[["lab", "open_weights", "release_date"]]
    price = con.execute("""SELECT model_id, prompt_price*1e6 AS p_in, completion_price*1e6 AS p_out FROM or_pricing
                           WHERE snapshot_date=(SELECT max(snapshot_date) FROM or_pricing)""").df().set_index("model_id")
    out = pd.DataFrame({"tokens": last, "delta": last - prev, "pct": (last / prev.replace(0, np.nan)) - 1,
                        "share": share.iloc[-1], "share_prev": share.iloc[-5]})
    out["share_delta_pp"] = (out["share"] - out["share_prev"]) * 100
    out["new"] = (g.iloc[:-4] == 0).all() & (last > 0)
    out = out.join(meta).join(price, how="left")
    out["spark"] = [g[m].iloc[-13:].tolist() for m in out.index]
    out = out[out["tokens"] > 0].sort_values("delta")
    return pd.concat([out.tail(n).iloc[::-1].assign(side="gainer"), out.head(n).assign(side="loser")]).reset_index()


def or_launches(con, k=5, horizon=28) -> pd.DataFrame:
    """Share of OR tokens over the first `horizon` days for the last k launches vs. the lab's prior-14d share."""
    d = or_daily(con)
    if d.empty:
        return d
    tot = d.groupby("date")["tokens"].sum()
    rel = d.dropna(subset=["release_date"]).drop_duplicates("model")[["model", "lab", "release_date"]]
    rel["release_date"] = pd.to_datetime(rel["release_date"])
    rel = rel[(rel.release_date >= d.date.min()) & (rel.release_date <= d.date.max() - pd.Timedelta(days=7))]
    rel = rel.sort_values("release_date").tail(k)
    rows = []
    for _, r in rel.iterrows():
        m = d[d.model == r.model].groupby("date")["tokens"].sum()
        win = pd.date_range(r.release_date, r.release_date + pd.Timedelta(days=horizon))
        s = (m.reindex(win, fill_value=0) / tot.reindex(win)).fillna(0)
        prior = d[(d.lab == r.lab) & (d.date < r.release_date) & (d.date >= r.release_date - pd.Timedelta(days=14))]
        prior_share = prior.tokens.sum() / tot[(tot.index < r.release_date) & (tot.index >= r.release_date - pd.Timedelta(days=14))].sum()
        for i, (dt_, v) in enumerate(s.items()):
            rows.append(dict(model=r.model, lab=r.lab, release_date=r.release_date, day=i, date=dt_, share=v,
                             lab_prior_share=prior_share))
    return pd.DataFrame(rows)


def or_apps(con) -> pd.DataFrame:
    df = con.execute("""SELECT * FROM or_apps WHERE window_end=(SELECT max(window_end) FROM or_apps)""").df()
    return df


# ---------------- Vercel ----------------

def vercel_labs(con) -> pd.DataFrame:
    df = con.execute("""SELECT v.date, v.metric, coalesce(l.lab, v.entity) AS lab, v.share/100 AS share
                        FROM vercel_daily v LEFT JOIN read_csv_auto('config/vercel_lab_map.csv') l
                        ON v.entity = l.vercel_lab WHERE v.dataset='labs'""").df()
    df["date"] = pd.to_datetime(df["date"])
    return df


def vercel_lab_weekly(con) -> pd.DataFrame:
    d = vercel_labs(con)
    if d.empty:
        return d
    d["week"] = d["date"] - pd.to_timedelta(d["date"].dt.weekday, unit="D")
    d["lab_b"] = d["lab"].map(_lab_bucket)
    g = d.groupby(["week", "metric", "lab_b"])["share"].sum().reset_index().rename(columns={"lab_b": "lab"})
    # weekly = mean of the daily shares present that week (share, so mean not sum across days)
    n = d.groupby(["week", "metric"])["date"].nunique().rename("ndays").reset_index()
    g = g.merge(n, on=["week", "metric"])
    g["share"] = g["share"] / g["ndays"]
    return g.drop(columns="ndays")


def vercel_open_share(con) -> pd.DataFrame:
    d = vercel_labs(con)
    if d.empty:
        return d
    d["open"] = d["lab"].map(lambda l: LAB_OPEN_DEFAULT.get(l, True))
    g = d.groupby(["date", "metric", "open"])["share"].sum().unstack(fill_value=0)
    g["open_share"] = g.get(True, 0) / g.sum(axis=1)
    return g.reset_index()[["date", "metric", "open_share"]]


def vercel_hhi(con) -> pd.DataFrame:
    d = vercel_labs(con)
    if d.empty:
        return d
    d = d[d.metric == "tokens"]
    return (d["share"] ** 2).groupby(d["date"]).sum().rename("hhi").reset_index()


def vercel_spend_gap(con) -> pd.DataFrame:
    d = vercel_labs(con)
    if d.empty:
        return d
    last7 = d[d.date > d.date.max() - pd.Timedelta(days=7)]
    p = last7.groupby(["lab", "metric"])["share"].mean().unstack(fill_value=0)
    p["gap_pp"] = (p.get("spend", 0) - p.get("tokens", 0)) * 100
    p["price_premium"] = p.get("spend", 0) / p.get("tokens", np.nan).replace(0, np.nan)
    return p.reset_index().sort_values("tokens", ascending=False)


# ---------------- Pricing ----------------

def pricing(con) -> pd.DataFrame:
    """Latest actual list prices, including models without a quality benchmark.

    Keep cache null when unlisted; do not invent a workload mix or effective price.
    Quality is the latest available AA snapshot, with its date disclosed separately.
    """
    return con.execute("""
        SELECT p.model_id, p.name, a.intelligence_idx, a.coding_idx, a.agentic_idx,
               p.prompt_price*1e6 AS p_in, p.completion_price*1e6 AS p_out,
               p.cache_read_price*1e6 AS p_cache, p.created,
               coalesce(m.lab, split_part(p.model_id,'/',1)) AS lab, m.open_weights
        FROM or_pricing p LEFT JOIN or_aa a ON a.model_id=p.model_id
          AND a.snapshot_date=(SELECT max(snapshot_date) FROM or_aa)
        LEFT JOIN model_map m ON m.permaslug=p.model_id
        WHERE p.snapshot_date=(SELECT max(snapshot_date) FROM or_pricing)
          AND p.prompt_price >= 0 AND p.completion_price >= 0
          AND p.modality LIKE '%text%' AND p.model_id NOT LIKE '%:%'
    """).df()


def frontier(df: pd.DataFrame) -> pd.DataFrame:
    """Lower price envelope: models where no other model is both smarter and cheaper."""
    d = df.sort_values(["intelligence_idx", "blended"], ascending=[False, True])
    best, keep = np.inf, []
    for _, r in d.iterrows():
        if r.blended < best:
            best = r.blended; keep.append(r.model_id)
    return df[df.model_id.isin(keep)].sort_values("intelligence_idx")


def frontier_cost_series(con, quantile=0.9) -> pd.DataFrame:
    """Per pricing snapshot: cheapest blended price among models at/above the top-decile intelligence index."""
    df = con.execute("""
        SELECT a.snapshot_date, a.model_id, a.intelligence_idx,
               0.7*coalesce(p.cache_read_price,p.prompt_price)*1e6 + 0.2*p.prompt_price*1e6 + 0.1*p.completion_price*1e6 AS blended
        FROM or_aa a JOIN or_pricing p USING (snapshot_date, model_id)
        WHERE a.intelligence_idx IS NOT NULL AND p.prompt_price > 0 AND a.model_id NOT LIKE '%:%'""").df()
    rows = []
    for sd, g in df.groupby("snapshot_date"):
        thr = g.intelligence_idx.quantile(quantile)
        top = g[g.intelligence_idx >= thr]
        rows.append(dict(snapshot_date=sd, threshold=thr, min_blended=top.blended.min(),
                         model=top.loc[top.blended.idxmin(), "model_id"], n=len(top)))
    return pd.DataFrame(rows)


def price_changes(con) -> pd.DataFrame:
    return con.execute("""
        WITH s AS (SELECT DISTINCT snapshot_date FROM or_pricing ORDER BY 1 DESC LIMIT 2)
        SELECT a.model_id, b.snapshot_date AS old_date, a.snapshot_date AS new_date,
               b.prompt_price*1e6 AS in_old, a.prompt_price*1e6 AS in_new,
               b.completion_price*1e6 AS out_old, a.completion_price*1e6 AS out_new
        FROM or_pricing a JOIN or_pricing b USING (model_id)
        WHERE a.snapshot_date=(SELECT max(snapshot_date) FROM s) AND b.snapshot_date=(SELECT min(snapshot_date) FROM s)
          AND a.snapshot_date<>b.snapshot_date
          AND (a.prompt_price IS DISTINCT FROM b.prompt_price OR a.completion_price IS DISTINCT FROM b.completion_price)
        ORDER BY (a.prompt_price - b.prompt_price)/nullif(b.prompt_price,0)""").df()


# ---------------- Cross-source ----------------

def agreement(con, weeks=4) -> pd.DataFrame:
    """Labs x sources, cell = change in share (pp) over `weeks`, or rank change for Cloudflare. NaN = no data."""
    cols = {}
    o = or_lab_weekly(con, bucket=True)
    if not o.empty and o.week.nunique() > weeks:
        p = o.pivot(index="week", columns="lab", values="share").fillna(0)
        cols["OR tokens"] = (p.iloc[-1] - p.iloc[-1 - weeks]) * 100
    v = vercel_lab_weekly(con)
    if not v.empty:
        for metric, label in (("tokens", "Vercel tokens"), ("spend", "Vercel spend"), ("requests", "Vercel req.")):
            p = v[v.metric == metric].pivot(index="week", columns="lab", values="share").fillna(0)
            if len(p) > weeks:
                cols[label] = (p.iloc[-1] - p.iloc[-1 - weeks]) * 100
    r = con.execute("SELECT month, vendor, value FROM ramp_monthly WHERE metric='adoption_pct' AND segment='all' AND vendor NOT IN ('all','census')").df()
    if not r.empty:
        p = r.pivot(index="month", columns="vendor", values="value")
        if len(p) >= 2:
            cols["Ramp adoption (1m)"] = p.iloc[-1] - p.iloc[-2]
    c = con.execute("SELECT date, service, rank FROM cf_rank WHERE rank > 0").df()
    if not c.empty:
        c["lab"] = c.service.map(CF_SERVICE_LAB)
        c = c.dropna(subset=["lab"])
        p = c.pivot(index="date", columns="lab", values="rank")
        if len(p) > weeks * 7:
            cols["CF rank Δ (−=up)"] = (p.iloc[-1] - p.iloc[-1 - weeks * 7])
    if not cols:
        return pd.DataFrame()
    m = pd.DataFrame(cols)
    order = [l for l in CORE_LABS if l in m.index] + [l for l in m.index if l not in CORE_LABS and l != "Other" and not str(l).startswith("Other")]
    m = m.reindex(order)
    m["n_up"] = (m.drop(columns=[c for c in m.columns if "rank" in c], errors="ignore") > 0).sum(axis=1)
    m["n_sources"] = m.drop(columns=["n_up"]).notna().sum(axis=1)
    return m


def source_status(con) -> pd.DataFrame:
    return con.execute("""
        WITH normalized AS (
          SELECT CASE source WHEN 'or_rankings_daily' THEN 'or_daily'
                   WHEN 'or_app_rankings' THEN 'or_apps' WHEN 'cloudflare' THEN 'cf_rank'
                   ELSE source END AS source, run_at, rows_added, note
          FROM run_log
        )
        SELECT source, run_at AS last_run, rows_added, note AS last_note FROM normalized
        QUALIFY row_number() OVER (PARTITION BY source ORDER BY run_at DESC)=1
        ORDER BY source""").df()
