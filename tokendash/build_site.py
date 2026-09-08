"""Static analytics page: one panel per dataset, each readable on its own terms.
Data is embedded as JSON; the page is a small vanilla-JS app with Plotly for charts."""
import json, datetime as dt
import numpy as np
import pandas as pd
from . import SITE
from . import metrics as M
from .model_map import canonical

PLOTLY = "https://cdnjs.cloudflare.com/ajax/libs/plotly.js/3.1.0/plotly.min.js"

SOURCES = [
    dict(id="openrouter", name="OpenRouter", what="Daily tokens for the top 50 models on the OpenRouter API marketplace, plus an 'other' bucket so the total is exact.",
         skew="Under 1% of the market. Skews hobbyist, open-weight, coding agents, cheap models. Token counts use each provider's own tokenizer.", unit="tokens / week"),
    dict(id="vercel", name="Vercel AI Gateway", what="Daily share of tokens, spend and requests by lab and by model through Vercel's gateway.",
         skew="Production web and B2B apps, closed-model heavy. Share only, no volumes, rolling 60-day window.", unit="% share / day"),
    dict(id="pricing", name="Pricing & quality", what="List prices on OpenRouter joined to Artificial Analysis quality indices.",
         skew="List prices, not negotiated. Indices are benchmark scores, not usage.", unit="$ per million tokens"),
    dict(id="cloudflare", name="Cloudflare Radar", what="Daily popularity rank of generative-AI services from 1.1.1.1 DNS traffic.",
         skew="Consumer and web traffic. Rank only. Undercounts services served from shared domains.", unit="rank"),
    dict(id="ramp", name="Ramp AI Index", what="Monthly share of US businesses on Ramp paying for AI, by vendor, sector and size, plus AI spend per employee and API spend share by model from Ramp's token spend product.",
         skew="Adoption, not volume. 70,000+ US firms on Ramp: VC-backed, tech-forward, mid-size. Model shares come from the subset connecting provider billing.", unit="% of businesses / $ per employee"),
    dict(id="disclosures", name="Company disclosures", what="Token figures stated on earnings calls and in lab posts, logged with the exact definition used.",
         skew="Marketing numbers with inconsistent definitions. Never connect the points.", unit="tokens"),
]


def _f(x):
    if x is None or x is pd.NA or (isinstance(x, (float, np.floating)) and np.isnan(x)):
        return None
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return float(x)
    return x


def build(con):
    today = dt.date.today().isoformat()
    D = {"built": today, "sources": {}, "labColors": {}}

    # ---------- OpenRouter ----------
    w = M.or_weekly(con)
    ors = {"ok": not w.empty}
    if not w.empty:
        weeks = sorted(w.week.unique())
        wk = [str(pd.Timestamp(x).date()) for x in weeks]
        lab_t = w.assign(lab=w.lab.fillna("Other")).groupby(["week", "lab"])["tokens"].sum().unstack(fill_value=0).reindex(weeks, fill_value=0)
        mod = w[w.permaslug != "other"].groupby(["week", "model"])["tokens"].sum().unstack(fill_value=0).reindex(weeks, fill_value=0)
        meta = w[w.permaslug != "other"].drop_duplicates("model").set_index("model")
        ors.update(weeks=wk, total=[float(x) for x in lab_t.sum(axis=1)],
                   labs={l: [float(x) for x in lab_t[l]] for l in lab_t.columns},
                   models={m: dict(lab=str(meta.lab.get(m, "Other")), open=_f(meta.open_weights.get(m)),
                                   rel=(str(meta.release_date.get(m)) if pd.notna(meta.release_date.get(m)) else None),
                                   v=[float(x) for x in mod[m]]) for m in mod.columns},
                   asof=wk[-1])
        ors["coverage"] = float(1 - w[w.permaslug == "other"].tokens.sum() / w.tokens.sum())
    apps = M.or_apps(con)
    if not apps.empty:
        ors["apps"] = {f"{r['sort']}_{r.category}": [] for _, r in apps.iterrows()}
        for r in apps.sort_values("rank").itertuples():
            ors["apps"][f"{r.sort}_{r.category}"].append(dict(rank=int(r.rank), app=str(r.app), tokens=float(r.tokens), requests=int(r.requests or 0)))
        ors["apps_window"] = f"{apps.window_start.max()} to {apps.window_end.max()}"
    D["openrouter"] = ors

    # ---------- Vercel ----------
    vd = M.vercel_labs(con)
    vs = {"ok": not vd.empty}
    if not vd.empty:
        dates = sorted(vd.date.unique()); ds = [str(pd.Timestamp(x).date()) for x in dates]
        labs = {}
        for lab, g in vd.groupby("lab"):
            p = g.pivot(index="date", columns="metric", values="share").reindex(dates)
            labs[lab] = {m: [_f(x) for x in p[m]] for m in p.columns}
        vm = con.execute("SELECT date, entity, metric, share/100 AS share FROM vercel_daily WHERE dataset='models'").df()
        vm["date"] = pd.to_datetime(vm.date)
        models = {}
        for ent, g in vm.groupby("entity"):
            p = g.pivot(index="date", columns="metric", values="share").reindex(dates)
            models[ent] = {m: [_f(x) for x in p[m]] for m in p.columns}
        rk = con.execute("SELECT dataset, ranked_by, rank, entity, url, snapshot_date FROM vercel_rank WHERE snapshot_date=(SELECT max(snapshot_date) FROM vercel_rank) ORDER BY dataset, rank").df()
        vs.update(dates=ds, labs=labs, models=models, asof=ds[-1],
                  ranks={d: [dict(rank=int(r.rank), name=str(r.entity), by=str(r.ranked_by), url=str(r.url or "")) for r in g.itertuples()] for d, g in rk.groupby("dataset")})
    D["vercel"] = vs

    # ---------- Pricing ----------
    pr = M.pricing(con)
    ps = {"ok": not pr.empty}
    if not pr.empty:
        last = {}
        if not w.empty:
            last = w[w.week == w.week.max()].groupby("model")["tokens"].sum().to_dict()
        ps["rows"] = [dict(model=r.model_id, name=r.name, lab=r.lab, open=_f(r.open_weights), idx=_f(r.intelligence_idx), coding=_f(r.coding_idx),
                           agentic=_f(r.agentic_idx), pin=_f(r.p_in), pout=_f(r.p_out), pcache=_f(r.p_cache), blended=_f(r.blended),
                           created=(str(pd.Timestamp(r.created).date()) if pd.notna(r.created) else None),
                           or_tokens=float(last.get(canonical(r.model_id), 0))) for r in pr.itertuples()]
        fr = M.frontier(pr)
        ps["frontier"] = [dict(idx=_f(r.intelligence_idx), blended=_f(r.blended), model=r.model_id) for r in fr.itertuples()]
        pc = M.price_changes(con)
        ps["changes"] = [dict(model=r.model_id, in_old=_f(r.in_old), in_new=_f(r.in_new), out_old=_f(r.out_old), out_new=_f(r.out_new)) for r in pc.itertuples()]
        ps["asof"] = str(con.execute("SELECT max(snapshot_date) FROM or_pricing").fetchone()[0])
        ps["n_snapshots"] = int(con.execute("SELECT count(DISTINCT snapshot_date) FROM or_pricing").fetchone()[0])
    D["pricing"] = ps

    # ---------- Cloudflare ----------
    cf = con.execute("SELECT date, service, rank FROM cf_rank WHERE rank > 0 ORDER BY date").df()
    cs = {"ok": not cf.empty}
    if not cf.empty:
        cf["date"] = pd.to_datetime(cf.date)
        p = cf.pivot(index="date", columns="service", values="rank")
        cs.update(dates=[str(x.date()) for x in p.index], services={s: [_f(x) for x in p[s]] for s in p.columns}, asof=str(p.index[-1].date()))
    D["cloudflare"] = cs

    # ---------- Ramp ----------
    rp = con.execute("SELECT month, vendor, metric, segment, value FROM ramp_monthly ORDER BY month").df()
    rs = {"ok": not rp.empty}
    if not rp.empty:
        rp["month"] = rp.month.astype(str)
        months = sorted(rp[rp.metric == "adoption_pct"].month.unique())
        def series(sub, key):
            out = {}
            for k, g in sub.groupby(key):
                m = g.set_index("month").value
                out[k] = [_f(m.get(x)) for x in months]
            return out
        a = rp[(rp.metric == "adoption_pct")]
        rs["months"] = months
        rs["vendors"] = series(a[a.segment == "all"], "vendor")
        rs["sectors"] = series(a[a.segment.str.startswith("sector:")].assign(seg=lambda d: d.segment.str[7:]), "seg")
        rs["sizes"] = series(a[a.segment.str.startswith("size:")].assign(seg=lambda d: d.segment.str[5:]), "seg")
        sp = rp[(rp.segment == "all") & (rp.vendor == "all") & (rp.metric != "adoption_pct")]
        rs["spend"] = series(sp, "metric")
        ms = con.execute("SELECT month, provider, model_label, share FROM ramp_model_share WHERE dimension_type='all' ORDER BY month").df()
        ms["month"] = ms.month.astype(str)
        mm = sorted(ms.month.unique())
        rs["model_months"] = mm
        rs["models"] = {}
        for (prov, lab), g in ms.groupby(["provider", "model_label"]):
            m = g.set_index("month").share
            rs["models"][lab] = dict(provider=prov, v=[_f(m.get(x)) for x in mm])
        rs["asof"] = months[-1]
    D["ramp"] = rs

    # ---------- Disclosures ----------
    dc = con.execute("SELECT date, company, metric, value, unit, definition, source_url FROM disclosures ORDER BY date").df()
    dsx = {"ok": not dc.empty}
    if not dc.empty:
        dsx["rows"] = [dict(date=str(r.date), company=r.company, metric=r.metric, value=_f(r.value), unit=r.unit, definition=r.definition, url=r.source_url) for r in dc.itertuples()]
        dsx["asof"] = str(dc.date.max())
    D["disclosures"] = dsx

    # ---------- Cross-source board ----------
    ag = M.agreement(con)
    if not ag.empty:
        cols = [c for c in ag.columns if c not in ("n_up", "n_sources")]
        D["agreement"] = dict(labs=list(ag.index), cols=cols, z=[[_f(v) for v in row] for row in ag[cols].values])

    # ---------- status ----------
    st = M.source_status(con)
    D["runlog"] = [dict(source=r.source, last=str(r.last_run)[:16], rows=int(r.rows_added), note=str(r.last_note or "")) for r in st.itertuples()]
    for s in SOURCES:
        s2 = dict(s); s2["ok"] = bool(D.get(s["id"], {}).get("ok")); s2["asof"] = D.get(s["id"], {}).get("asof")
        D["sources"][s["id"]] = s2
    D["sourceOrder"] = [s["id"] for s in SOURCES]

    page = TEMPLATE.replace("{{DATA}}", json.dumps(D, separators=(",", ":"), default=lambda o: _f(o) if _f(o) is not o else str(o))).replace("{{PLOTLY}}", PLOTLY).replace("{{DATE}}", today)
    SITE.mkdir(exist_ok=True)
    out = SITE / "index.html"
    out.write_text(page)
    return out


TEMPLATE = open(__file__.replace("build_site.py", "template.html")).read()
