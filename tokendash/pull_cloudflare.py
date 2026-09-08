"""Cloudflare Radar: daily rank of Generative AI services by 1.1.1.1 DNS popularity. Rank only.
Needs CF_API_TOKEN with Radar read. Skipped cleanly when absent."""
import os, datetime as dt
import pandas as pd
from .http import get_json, snapshot
from .db import append_new, log

BASE = "https://api.cloudflare.com/client/v4/radar/ranking/internet_services"


def pull(con) -> int:
    tok = os.environ.get("CF_API_TOKEN", "").strip()
    if not tok:
        log(con, "cf_rank", 0, "skipped: CF_API_TOKEN not set")
        return 0
    h = {"Authorization": f"Bearer {tok}"}
    now = pd.Timestamp.utcnow().tz_localize(None)
    # timeseries_groups gives rank per service per day over the range
    js = get_json(f"{BASE}/timeseries_groups",
                  {"serviceCategory": "Generative AI", "dateRange": "52w", "limit": 20}, h)
    snapshot("cloudflare", "genai_timeseries", js)
    res = js["result"]
    grp = res.get("serviceTop_0") or next(v for k, v in res.items() if k != "meta")
    ts = grp["timestamps"]
    rows = []
    for svc, ranks in grp.items():
        if svc == "timestamps":
            continue
        for t, r in zip(ts, ranks):
            if r is not None and int(r) > 0:  # -1 = not ranked that day
                rows.append(dict(date=pd.to_datetime(t).date(), service=svc, rank=int(r), pulled_at=now))
    n = append_new(con, "cf_rank", pd.DataFrame(rows), ["date", "service"])
    log(con, "cf_rank", n)
    return n
