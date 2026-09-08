"""Weekly job: pull every source (each isolated), rebuild model_map, build the static site.
Usage: python run.py [pull|site|all]  (default all)"""
import sys, os, traceback
from pathlib import Path
try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass
from tokendash import db, pull_openrouter, pull_vercel, pull_cloudflare, pull_ramp, load_manual, model_map


def pull(con):
    steps = [
        ("or_models", lambda: pull_openrouter.pull_models(con)),
        ("or_rankings_daily", lambda: pull_openrouter.pull_rankings_daily(con)),
        ("or_app_rankings", lambda: pull_openrouter.pull_app_rankings(con)),
        ("vercel", lambda: pull_vercel.pull(con)),
        ("cloudflare", lambda: pull_cloudflare.pull(con)),
        ("ramp", lambda: pull_ramp.pull(con)),
        ("manual", lambda: load_manual.load(con)),
    ]
    failures = []
    for name, fn in steps:
        try:
            n = fn(); print(f"[pull] {name}: +{n} rows")
        except Exception as e:
            print(f"[pull] {name}: FAILED {type(e).__name__}: {e}")
            db.log(con, name, 0, f"FAILED {type(e).__name__}: {str(e)[:200]}")
            failures.append(name)
            if os.environ.get("TOKENDASH_DEBUG"):
                traceback.print_exc()
    model_map.build(con)
    return failures


def site(con):
    from tokendash import build_site
    out = build_site.build(con)
    print(f"[site] wrote {out} ({out.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    con = db.connect()
    fails = []
    if mode in ("pull", "all"):
        fails = pull(con)
    if mode in ("site", "all"):
        site(con)
    con.close()
    if fails:
        print("sources failed:", ", ".join(fails))
        # keep exit 0 so the job still commits what it got; failures are visible in run_log + page footer
