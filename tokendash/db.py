"""DuckDB schema. Append-only: every loader inserts rows that are not already present."""
import duckdb
import pandas as pd
from . import DB_PATH, DATA

SCHEMA = """
CREATE TABLE IF NOT EXISTS or_daily (
    date DATE, permaslug VARCHAR, tokens HUGEINT, pulled_at TIMESTAMP,
    PRIMARY KEY (date, permaslug));
CREATE TABLE IF NOT EXISTS or_apps (
    window_start DATE, window_end DATE, sort VARCHAR, category VARCHAR,
    rank INTEGER, app_id BIGINT, app VARCHAR, tokens HUGEINT, requests BIGINT, pulled_at TIMESTAMP,
    PRIMARY KEY (window_start, window_end, sort, category, app_id));
CREATE TABLE IF NOT EXISTS or_pricing (
    snapshot_date DATE, model_id VARCHAR, canonical_slug VARCHAR, name VARCHAR, created TIMESTAMP,
    prompt_price DOUBLE, completion_price DOUBLE, cache_read_price DOUBLE, cache_write_price DOUBLE,
    context INTEGER, modality VARCHAR, hugging_face_id VARCHAR, pulled_at TIMESTAMP,
    PRIMARY KEY (snapshot_date, model_id));
CREATE TABLE IF NOT EXISTS or_aa (
    snapshot_date DATE, model_id VARCHAR, intelligence_idx DOUBLE, coding_idx DOUBLE, agentic_idx DOUBLE,
    prompt_price DOUBLE, completion_price DOUBLE, pulled_at TIMESTAMP,
    PRIMARY KEY (snapshot_date, model_id));
CREATE TABLE IF NOT EXISTS vercel_daily (
    date DATE, dataset VARCHAR, entity VARCHAR, metric VARCHAR, share DOUBLE, pulled_at TIMESTAMP,
    PRIMARY KEY (date, dataset, entity, metric));
CREATE TABLE IF NOT EXISTS vercel_rank (
    snapshot_date DATE, dataset VARCHAR, ranked_by VARCHAR, rank INTEGER, entity VARCHAR, url VARCHAR,
    pulled_at TIMESTAMP,
    PRIMARY KEY (snapshot_date, dataset, ranked_by, rank));
CREATE TABLE IF NOT EXISTS ramp_monthly (
    month DATE, vendor VARCHAR, metric VARCHAR, segment VARCHAR, value DOUBLE, loaded_at TIMESTAMP,
    PRIMARY KEY (month, vendor, metric, segment));
CREATE TABLE IF NOT EXISTS ramp_model_share (
    month DATE, provider VARCHAR, model_key VARCHAR, model_label VARCHAR, dimension_type VARCHAR, dimension_value VARCHAR,
    share DOUBLE, loaded_at TIMESTAMP,
    PRIMARY KEY (month, model_key, dimension_type, dimension_value));
CREATE TABLE IF NOT EXISTS cf_rank (
    date DATE, service VARCHAR, rank INTEGER, pulled_at TIMESTAMP,
    PRIMARY KEY (date, service));
CREATE TABLE IF NOT EXISTS disclosures (
    date DATE, company VARCHAR, metric VARCHAR, value DOUBLE, unit VARCHAR, definition VARCHAR,
    source_url VARCHAR, loaded_at TIMESTAMP,
    PRIMARY KEY (date, company, metric));
CREATE TABLE IF NOT EXISTS model_map (
    permaslug VARCHAR PRIMARY KEY, canonical_model VARCHAR, lab VARCHAR, open_weights BOOLEAN,
    release_date DATE, is_free_variant BOOLEAN, source VARCHAR);
CREATE TABLE IF NOT EXISTS run_log (
    run_at TIMESTAMP, source VARCHAR, rows_added INTEGER, note VARCHAR);
"""


def connect(path=DB_PATH):
    DATA.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute(SCHEMA)
    return con


def append_new(con, table: str, df: pd.DataFrame, keys: list[str]) -> int:
    """Insert rows whose key is not already in `table`. Returns the count inserted."""
    if df is None or df.empty:
        return 0
    cols = [r[1] for r in con.execute(f"PRAGMA table_info('{table}')").fetchall()]
    df = df.reindex(columns=cols)
    con.register("_incoming", df)
    on = " AND ".join(f"t.{k} IS NOT DISTINCT FROM i.{k}" for k in keys)
    before = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    con.execute(
        f"INSERT INTO {table} SELECT DISTINCT ON ({', '.join(keys)}) i.* FROM _incoming i "
        f"WHERE NOT EXISTS (SELECT 1 FROM {table} t WHERE {on})"
    )
    con.unregister("_incoming")
    return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0] - before


def log(con, source: str, rows: int, note: str = ""):
    con.execute("INSERT INTO run_log VALUES (now(), ?, ?, ?)", [source, rows, note])
