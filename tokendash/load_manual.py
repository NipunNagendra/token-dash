"""Hand-maintained CSVs in data/manual/. See data/manual/README.md for columns."""
import pandas as pd
from . import MANUAL
from .db import append_new, log


def load(con) -> int:
    now = pd.Timestamp.utcnow().tz_localize(None)
    added = 0
    f = MANUAL / "ramp_ai_index.csv"
    if f.exists():
        df = pd.read_csv(f)
        if not df.empty:
            df["month"] = pd.to_datetime(df["month"]).dt.date
            df["segment"] = df.get("segment", pd.Series(["all"] * len(df))).fillna("all")
            df["loaded_at"] = now
            n = append_new(con, "ramp_monthly", df, ["month", "vendor", "metric", "segment"])
            log(con, "ramp_monthly", n); added += n
    f = MANUAL / "disclosures.csv"
    if f.exists():
        df = pd.read_csv(f)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"]).dt.date
            df["loaded_at"] = now
            n = append_new(con, "disclosures", df, ["date", "company", "metric"])
            log(con, "disclosures", n); added += n
    return added
