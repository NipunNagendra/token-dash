"""Ramp AI Index. There is no feed; the monthly series are embedded in the page as React server props
(adoptionOverall, adoptionVendor, adoptionIndustry, adoptionSize, adoptionState, adoptionUsEstimate,
spendPerEmployee, modelBreakdown, modelShareCurated). Fetch the page, locate the object, parse it."""
import json, re
import pandas as pd
import requests
from .http import UA, snapshot
from .db import append_new, log

URL = "https://ramp.com/data/ai-index"
MARK = '{\\"adoptionOverall\\"'


def fetch_props() -> dict:
    html = requests.get(URL, headers={"User-Agent": UA}, timeout=60).text
    i = html.find(MARK)
    if i < 0:
        raise RuntimeError("Ramp page layout changed: adoptionOverall marker not found")
    un = html[i:].encode().decode("unicode_escape")
    dec, out, pos = json.JSONDecoder(), {}, 1
    key = re.compile(r'"(\w+)":')
    while True:
        m = key.match(un, pos)
        if not m:
            break
        v, e = dec.raw_decode(un, m.end())
        out[m.group(1)] = v
        pos = e + 1
        if un[e] == "}":
            break
    return out


def pull(con) -> int:
    props = fetch_props()
    snapshot("ramp", "ai-index-props", {k: v for k, v in props.items() if isinstance(v, list)})
    now = pd.Timestamp.utcnow().tz_localize(None)
    rows = []
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    add = lambda month, vendor, metric, segment, value: rows.append(dict(month=pd.to_datetime(month).date(), vendor=vendor, metric=metric, segment=segment, value=float(value), loaded_at=now))
    for r in props.get("adoptionOverall", []):
        add(r["date_month"], "all", "adoption_pct", "all", r["adoption_rate_pct"])
    for r in props.get("adoptionVendor", []):
        add(r["date_month"], r["vendor"], "adoption_pct", "all", r["adoption_rate_pct"])
    for r in props.get("adoptionIndustry", []):
        add(r["date_month"], "all", "adoption_pct", f"sector:{r['naics_sector']}", r["adoption_rate_pct"])
    for r in props.get("adoptionSize", []):
        add(r["date_month"], "all", "adoption_pct", f"size:{r['business_size']}", r["adoption_rate_pct"])
    for r in props.get("adoptionState", []):
        add(r["date_month"], "all", "adoption_pct", f"state:{r['state_code']}", r["adoption_rate_pct"])
    for r in props.get("adoptionUsEstimate", []):
        if num(r.get("adoption_rate_pct")):
            add(r["date_month"], "census", "adoption_pct", "all", r["adoption_rate_pct"])
    for r in props.get("spendPerEmployee", []):
        for k, v in r.items():
            if k != "date_month" and num(v):
                add(r["date_month"], "all", k, "all", v)
    for r in props.get("spendPerEmployeeCurated", []):
        seg = f"{r.get('dimension_type')}:{r.get('dimension_value')}"
        for k, v in r.items():
            if k not in ("date_month", "display_order") and num(v):
                add(r["date_month"], "all", k, seg, v)
    df = pd.DataFrame(rows)
    n1 = append_new(con, "ramp_monthly", df, ["month", "vendor", "metric", "segment"])
    ms = []
    for src, dim in (("modelBreakdown", False), ("modelShareCurated", True)):
        for r in props.get(src, []):
            ms.append(dict(month=pd.to_datetime(r["date_month"]).date(), provider=r["ai_provider"], model_key=r["model_bucket_key"],
                           model_label=r["model_label"], dimension_type=(r.get("dimension_type") if dim else "all"),
                           dimension_value=(r.get("dimension_value") if dim else "all"), share=float(r["model_share"]), loaded_at=now))
    n2 = append_new(con, "ramp_model_share", pd.DataFrame(ms), ["month", "model_key", "dimension_type", "dimension_value"])
    log(con, "ramp_monthly", n1, f"latest={df.month.max()}")
    log(con, "ramp_model_share", n2)
    return n1 + n2
