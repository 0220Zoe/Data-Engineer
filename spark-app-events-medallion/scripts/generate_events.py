"""Generate synthetic nested JSON app events from two regional systems."""
import hashlib
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

random.seed(7)
OUT = Path(__file__).resolve().parent.parent / "data"
START = datetime(2026, 9, 1, tzinfo=timezone.utc)
EVENTS = ["app_open", "article_view", "push_open", "share"]
people = [f"reader{i}@example.com" for i in range(1, 151)]
# Some people use the app in both regions (e.g. travelers), so their IDs must be stitched.
us_people = people[:100]
eu_people = people[80:]


def sha256(text):
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()


def sessions(n_sessions):
    for _ in range(n_sessions):
        t = START + timedelta(days=random.randint(0, 44), minutes=random.randint(0, 1439))
        for _ in range(random.randint(1, 6)):
            yield t
            t += timedelta(minutes=random.randint(1, 12))


us, eu, n = [], [], 0
for email in us_people:
    account = f"US-{sha256(email)[:8]}"
    for ts in sessions(random.randint(2, 12)):
        n += 1
        us.append({
            "event_id": f"us-{n}",
            "user": {"us_account_id": account, "email": email.upper() if n % 9 == 0 else email},
            "event": {"name": random.choice(EVENTS), "ts": ts.isoformat()},
            "device": {"platform": random.choice(["ios", "android"])},
        })
for email in eu_people:
    member = f"EU{random.randint(100000, 999999)}"
    for ts in sessions(random.randint(2, 12)):
        n += 1
        eu.append({
            "id": f"eu-{n}",
            "account": {"eu_member_id": member, "email_sha256": sha256(email)},
            "event_name": random.choice(EVENTS),
            "event_time_ms": int(ts.timestamp() * 1000),
            "platform": random.choice(["IOS", "ANDROID"]),
        })
# At-least-once delivery: replay some events.
us += random.sample(us, 25)
eu += random.sample(eu, 25)

for name, rows in [("us_events.jsonl", us), ("eu_events.jsonl", eu)]:
    with open(OUT / name, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
print(len(us), "US events,", len(eu), "EU events")
