import datetime as dt
from tokendash import db, metrics


def test_prices_include_unbenchmarked_and_do_not_invent_cache_price(tmp_path):
    c=db.connect(tmp_path/'prices.duckdb')
    c.execute("INSERT INTO or_pricing (snapshot_date,model_id,name,prompt_price,completion_price,modality) VALUES ('2026-09-08','lab/a','A',0.000001,0.000003,'text->text'),('2026-09-08','lab/b','B',0,0,'text->text')")
    c.execute("INSERT INTO or_aa (snapshot_date,model_id,intelligence_idx) VALUES ('2026-09-01','lab/a',50)")
    p=metrics.pricing(c).set_index('model_id')
    assert len(p)==2
    assert p.loc['lab/a','p_in']==1
    assert p.loc['lab/a','intelligence_idx']==50
    assert p.loc['lab/b','p_in']==0
    assert p.p_cache.isna().all()
    assert 'blended' not in p
    assert metrics.price_changes(c).empty
    c.execute("INSERT INTO or_pricing (snapshot_date,model_id,prompt_price,completion_price) VALUES ('2026-09-15','lab/a',0.0000005,0.000002)")
    changes=metrics.price_changes(c)
    assert len(changes)==1
    assert changes.iloc[0].in_old==1
    assert changes.iloc[0].in_new==.5
    c.close()


def test_status_uses_latest_success_and_rows_not_lifetime_sum(tmp_path):
    c=db.connect(tmp_path/'status.duckdb')
    c.execute("INSERT INTO run_log VALUES ('2026-09-01','or_rankings_daily',0,'FAILED'),('2026-09-08','or_daily',25,''),('2026-09-07','or_daily',10,'')")
    status=metrics.source_status(c)
    assert len(status)==1
    assert status.iloc[0].rows_added==25
    assert status.iloc[0].last_note==''
    c.close()
