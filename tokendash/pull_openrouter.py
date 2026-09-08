"""OpenRouter Data API: rankings-daily (backfilled from 2025-01-01), app-rankings, /models pricing + AA indices.
Attribution required: "Source: OpenRouter (openrouter.ai/rankings), as of {as_of}."
"""
import os, datetime as dt, time
import pandas as pd
from .http import get_json, snapshot
from .db import append_new, log

BASE = "https://openrouter.ai/api/v1"
FLOOR = dt.date(2025, 1, 1)


def _hdr():
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    return {"Authorization": f"Bearer {key}"}


def pull_rankings_daily(con, chunk_days=90) -> int:
    """Backfill from the later of (dataset floor, last date in DB - 3d) to yesterday, in chunks."""
    last = con.execute("SELECT max(date) FROM or_daily").fetchone()[0]
    start = FLOOR if last is None else max(FLOOR, last - dt.timedelta(days=3))
    end = dt.date.today() - dt.timedelta(days=1)
    added, as_of = 0, None
    cur = start
    while cur <= end:
        stop = min(cur + dt.timedelta(days=chunk_days - 1), end)
        js = get_json(f"{BASE}/datasets/rankings-daily",
                      {"start_date": cur.isoformat(), "end_date": stop.isoformat(), "period": "day"}, _hdr())
        snapshot("openrouter", f"rankings-daily_{cur}_{stop}", js)
        as_of = js.get("meta", {}).get("as_of")
        df = pd.DataFrame(js["data"])
        if not df.empty:
            df = df.rename(columns={"model_permaslug": "permaslug", "total_tokens": "tokens"})
            df["date"] = pd.to_datetime(df["date"]).dt.date
            df["tokens"] = df["tokens"].astype("int64")
            df["pulled_at"] = pd.Timestamp.utcnow().tz_localize(None)
            added += append_new(con, "or_daily", df, ["date", "permaslug"])
        cur = stop + dt.timedelta(days=1)
        time.sleep(2.5)  # 30/min budget
    log(con, "or_daily", added, f"as_of={as_of}")
    return added


def pull_app_rankings(con, days=7) -> int:
    end = dt.date.today() - dt.timedelta(days=1)
    start = end - dt.timedelta(days=days - 1)
    added = 0
    for sort in ("popular", "trending"):
        for category in (None, "coding"):
            p = {"start_date": start.isoformat(), "end_date": end.isoformat(), "sort": sort, "limit": 50}
            if category:
                p["category"] = category
            js = get_json(f"{BASE}/datasets/app-rankings", p, _hdr())
            snapshot("openrouter", f"app-rankings_{sort}_{category or 'all'}_{end}", js)
            df = pd.DataFrame(js["data"])
            if df.empty:
                continue
            df = df.rename(columns={"app_name": "app", "total_tokens": "tokens", "total_requests": "requests"})
            df["tokens"] = df["tokens"].astype("int64")
            df["window_start"], df["window_end"] = start, end
            df["sort"], df["category"] = sort, category or "all"
            df["pulled_at"] = pd.Timestamp.utcnow().tz_localize(None)
            added += append_new(con, "or_apps", df, ["window_start", "window_end", "sort", "category", "app_id"])
            time.sleep(2.5)
    log(con, "or_apps", added, f"window={start}..{end}")
    return added


def pull_models(con) -> int:
    """Public endpoint, no key. Pricing snapshot + Artificial Analysis indices (attached by OpenRouter)."""
    js = get_json(f"{BASE}/models")
    snapshot("openrouter", "models", js)
    today = dt.date.today()
    now = pd.Timestamp.utcnow().tz_localize(None)
    rows, aa = [], []
    for m in js["data"]:
        p = m.get("pricing", {}) or {}
        f = lambda k: float(p[k]) if p.get(k) not in (None, "") else None
        rows.append(dict(
            snapshot_date=today, model_id=m["id"], canonical_slug=m.get("canonical_slug"), name=m.get("name"),
            created=pd.to_datetime(m.get("created"), unit="s") if m.get("created") else None,
            prompt_price=f("prompt"), completion_price=f("completion"),
            cache_read_price=f("input_cache_read"), cache_write_price=f("input_cache_write"),
            context=m.get("context_length"), modality=(m.get("architecture") or {}).get("modality"),
            hugging_face_id=m.get("hugging_face_id") or None, pulled_at=now))
        b = ((m.get("benchmarks") or {}).get("artificial_analysis") or {})
        if b:
            aa.append(dict(snapshot_date=today, model_id=m["id"], intelligence_idx=b.get("intelligence_index"),
                           coding_idx=b.get("coding_index"), agentic_idx=b.get("agentic_index"),
                           prompt_price=f("prompt"), completion_price=f("completion"), pulled_at=now))
    n1 = append_new(con, "or_pricing", pd.DataFrame(rows), ["snapshot_date", "model_id"])
    n2 = append_new(con, "or_aa", pd.DataFrame(aa), ["snapshot_date", "model_id"])
    log(con, "or_pricing", n1); log(con, "or_aa", n2)
    return n1 + n2
