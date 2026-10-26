import hashlib
from datetime import datetime, timezone

from src import transforms as t


def sha(email):
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


def us_events(spark):
    rows = [
        {"event_id": "us-1", "user": {"us_account_id": "US-1", "email": " Reader@Example.com "},
         "event": {"name": "app_open", "ts": "2026-09-01T10:00:00+00:00"}, "device": {"platform": "IOS"}},
        {"event_id": "us-2", "user": {"us_account_id": "US-1", "email": "reader@example.com"},
         "event": {"name": "article_view", "ts": "2026-09-01T10:10:00+00:00"}, "device": {"platform": "ios"}},
        {"event_id": "us-2", "user": {"us_account_id": "US-1", "email": "reader@example.com"},
         "event": {"name": "article_view", "ts": "2026-09-01T10:10:00+00:00"}, "device": {"platform": "ios"}},
    ]
    return spark.read.json(spark.sparkContext.parallelize([__import__("json").dumps(r) for r in rows]))


def eu_events(spark):
    import json
    rows = [
        {"id": "eu-1", "account": {"eu_member_id": "EU9", "email_sha256": sha("reader@example.com")},
         "event_name": "push_open", "event_time_ms": int(datetime(2026, 9, 1, 11, 0, tzinfo=timezone.utc).timestamp() * 1000),
         "platform": "ANDROID"},
        {"id": "eu-2", "account": {"eu_member_id": "EU9", "email_sha256": None},
         "event_name": "share", "event_time_ms": int(datetime(2026, 9, 1, 11, 5, tzinfo=timezone.utc).timestamp() * 1000),
         "platform": "ANDROID"},
    ]
    return spark.read.json(spark.sparkContext.parallelize([json.dumps(r) for r in rows]))


def silver(spark):
    return t.unify_and_dedupe(t.silver_us(us_events(spark)), t.silver_eu(eu_events(spark)))


def test_dedupe_keeps_one_row_per_event(spark):
    assert silver(spark).count() == 4  # 3 US rows with one replay + 2 EU rows


def test_identity_stitching_across_regions(spark):
    valid, _ = t.quarantine_invalid(silver(spark))
    people = valid.select("person_id").distinct().collect()
    assert len(people) == 1  # US account and EU member resolve to the same person
    assert people[0].person_id == sha("reader@example.com")


def test_missing_identity_is_quarantined_not_dropped(spark):
    valid, quarantined = t.quarantine_invalid(silver(spark))
    assert valid.count() == 3
    assert [r.event_id for r in quarantined.collect()] == ["eu-2"]


def test_sessions_split_after_30_minutes_of_inactivity(spark):
    valid, _ = t.quarantine_invalid(silver(spark))
    sessions = t.gold_sessions(t.sessionize(valid)).orderBy("session_start").collect()
    # 10:00 and 10:10 form one session; 11:00 starts a new one after a 50-minute gap.
    assert [s.events for s in sessions] == [2, 1]


def test_monthly_active_counts_people_not_accounts(spark):
    valid, _ = t.quarantine_invalid(silver(spark))
    row = t.gold_monthly_active(valid).collect()[0]
    assert row.mau == 1
    assert row.unstitched_accounts == 2
