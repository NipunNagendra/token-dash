import json, time, datetime as dt
import requests
from . import RAW

UA = "token-dash/0.1 (weekly public-dataset pull)"


def get_json(url, params=None, headers=None, retries=4, timeout=60):
    h = {"User-Agent": UA, **(headers or {})}
    for i in range(retries):
        r = requests.get(url, params=params, headers=h, timeout=timeout)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 ** i * 2)
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()


def snapshot(source: str, name: str, payload) -> None:
    """Keep the raw response on disk so the DB can always be rebuilt."""
    d = RAW / source
    d.mkdir(parents=True, exist_ok=True)
    stamp = dt.date.today().isoformat()
    (d / f"{stamp}_{name}.json").write_text(json.dumps(payload, separators=(",", ":")))
