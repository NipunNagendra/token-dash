"""python -m pytest tests/  (or python tests/test_smoke.py). Builds a fixture DB in a temp dir and renders the page."""
import sys, tempfile, subprocess, shutil, os
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_fixture_builds_page(monkeypatch):
    from tokendash import db, build_site, DB_PATH
    assert DB_PATH.exists(), "run `python run.py pull` (or at least pull_models) first"
    with tempfile.TemporaryDirectory() as d:
        fx = Path(d) / "fx.duckdb"
        shutil.copy(DB_PATH, fx)
        subprocess.run([sys.executable, "tests/make_fixture.py", str(fx)], cwd=ROOT, check=True)
        con = db.connect(fx)
        monkeypatch.setattr(build_site, "SITE", Path(d) / "site")
        out = build_site.build(con)
        con.close()
        html = out.read_text()
        for must in ("Token desk", "Weekly tokens", "Price against quality", "Observed DNS rank", "Methodology", "{{DATA}}"):
            if must == "{{DATA}}":
                assert must not in html
            else:
                assert must in html
