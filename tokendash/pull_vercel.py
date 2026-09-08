"""Vercel AI Gateway leaderboard export. No key. CC BY 4.0. Publishes SHARE (%), not volume,
and only a rolling ~60-day window, so weekly snapshots are what build history."""
import datetime as dt
import pandas as pd
from .http import get_json, snapshot
from .db import append_new, log

URL = "https://vercel.com/api/ai/leaderboard-export"


def pull(con) -> int:
    added = 0
    now = pd.Timestamp.utcnow().tz_localize(None)
    for ds in ("models", "labs"):
        js = get_json(URL, {"dataset": ds, "modality": "text", "format": "json"})
        snapshot("vercel", ds, js)
        df = pd.DataFrame(js["rows"]).rename(columns={"name": "entity", "share_percent": "share"})
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df["dataset"] = ds
        df["pulled_at"] = now
        n = append_new(con, "vercel_daily", df, ["date", "dataset", "entity", "metric"])
        added += n
        log(con, f"vercel_{ds}", n, f"{df.date.min()}..{df.date.max()}")
    today = dt.date.today()
    for ds in ("apps", "providers"):
        js = get_json(URL, {"dataset": ds, "modality": "text", "format": "json"})
        snapshot("vercel", ds, js)
        df = pd.DataFrame(js["rows"]).rename(columns={"name": "entity"})
        df["snapshot_date"], df["dataset"], df["pulled_at"] = today, ds, now
        n = append_new(con, "vercel_rank", df, ["snapshot_date", "dataset", "ranked_by", "rank"])
        added += n
        log(con, f"vercel_{ds}", n)
    return added
