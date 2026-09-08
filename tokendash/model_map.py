"""permaslug -> (canonical_model, lab, open_weights). Built from the latest /models snapshot plus
every permaslug seen in or_daily, then hand overrides. Rebuilt fully each run (small, derived)."""
import re
import pandas as pd
from . import CONFIG
from .db import log

VERSION_SUFFIX = re.compile(r"-(\d{8}|\d{4}-\d{2}-\d{2}|\d{4}-\d{2})$")


def _split(permaslug: str):
    base, _, variant = permaslug.partition(":")
    author, _, model = base.partition("/")
    return author, model, variant


def canonical(permaslug: str) -> str:
    author, model, _ = _split(permaslug)
    return f"{author}/{VERSION_SUFFIX.sub('', model)}"


def build(con) -> int:
    labs = pd.read_csv(CONFIG / "lab_map.csv").set_index("author")
    ov = pd.read_csv(CONFIG / "model_map_overrides.csv")
    latest = con.execute("""
        SELECT model_id, canonical_slug, created, hugging_face_id
        FROM or_pricing WHERE snapshot_date = (SELECT max(snapshot_date) FROM or_pricing)""").df()
    seen = con.execute("SELECT DISTINCT permaslug FROM or_daily WHERE permaslug <> 'other'").df()
    slugs = set(latest.model_id) | set(latest.canonical_slug.dropna()) | set(seen.permaslug)
    info = {}
    for _, r in latest.iterrows():
        for s in (r.model_id, r.canonical_slug):
            if s:
                info[s] = r
    rows = []
    for s in sorted(slugs):
        author, model, variant = _split(s)
        a0 = author.lstrip("~")
        lab = labs.lab.get(author, labs.lab.get(a0, a0.title()))
        default_open = bool(labs.open_weights_default.get(author, labs.open_weights_default.get(a0, False)))
        r = info.get(s)
        if r is None:  # a :free variant or old permaslug: look up the base
            r = info.get(s.split(":")[0])
            if r is None:
                r = info.get(canonical(s))
        hf = bool(r is not None and isinstance(r.hugging_face_id, str) and r.hugging_face_id)
        rows.append(dict(permaslug=s, canonical_model=canonical(s), lab=lab, open_weights=(hf or default_open),
                         release_date=(pd.to_datetime(r.created).date() if r is not None and pd.notna(r.created) else None),
                         is_free_variant=(variant == "free"), source="auto"))
    df = pd.DataFrame(rows)
    if not ov.empty:
        ov = ov.set_index("permaslug")
        for s, o in ov.iterrows():
            m = df.permaslug == s
            if not m.any():
                df.loc[len(df)] = dict(permaslug=s, canonical_model=o.canonical_model, lab=o.lab,
                                       open_weights=bool(o.open_weights), release_date=None,
                                       is_free_variant=s.endswith(":free"), source="override")
                continue
            for c in ("canonical_model", "lab", "open_weights", "release_date"):
                if pd.notna(o.get(c)):
                    df.loc[m, c] = o[c]
            df.loc[m, "source"] = "override"
    con.execute("DELETE FROM model_map")
    con.register("_mm", df)
    con.execute("INSERT INTO model_map SELECT * FROM _mm")
    con.unregister("_mm")
    log(con, "model_map", len(df))
    return len(df)
