"""Generate deterministic synthetic seed data for the dbt project."""
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)
SEEDS = Path(__file__).resolve().parent.parent / "seeds"
SECTIONS = ["politics", "economy", "tech", "health", "energy"]
PLATFORMS = ["web", "ios", "android"]
SOCIAL = ["x", "linkedin", "facebook"]
START = datetime(2026, 9, 21)
AS_OF = datetime(2026, 10, 20)

articles = []
for i in range(1, 41):
    published = START + timedelta(days=random.randint(0, 28), hours=random.randint(6, 20))
    articles.append({
        "article_id": f"A{i:03d}",
        "section": random.choice(SECTIONS),
        "headline": f"Sample headline {i}",
        "published_at": published.strftime("%Y-%m-%d %H:%M:%S"),
    })

pageviews, event_id = [], 0
for a in articles:
    published = datetime.strptime(a["published_at"], "%Y-%m-%d %H:%M:%S")
    for _ in range(random.randint(20, 120)):
        event_id += 1
        ts = published + timedelta(minutes=random.randint(1, 60 * 24 * 7))
        if ts > AS_OF:
            continue
        row = {
            "event_id": f"E{event_id:06d}",
            "user_id": f"U{random.randint(1, 400):04d}",
            "article_id": a["article_id"],
            "event_ts": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "platform": random.choice(PLATFORMS),
        }
        pageviews.append(row)
        if random.random() < 0.03:  # duplicate deliveries, as real event streams have
            pageviews.append(dict(row))

posts, post_id = [], 0
for a in articles:
    published = datetime.strptime(a["published_at"], "%Y-%m-%d %H:%M:%S")
    for platform in random.sample(SOCIAL, 2):
        post_id += 1
        posted = published + timedelta(minutes=random.randint(5, 120))
        likes = shares = comments = 0
        for day in range(0, 10):  # daily engagement snapshots that keep growing
            snap = posted + timedelta(days=day, hours=1)
            if snap > AS_OF:
                break
            likes += random.randint(0, 40)
            shares += random.randint(0, 10)
            comments += random.randint(0, 6)
            posts.append({
                "post_id": f"P{post_id:04d}",
                "article_id": a["article_id"],
                "platform": platform,
                "posted_at": posted.strftime("%Y-%m-%d %H:%M:%S"),
                "snapshot_at": snap.strftime("%Y-%m-%d %H:%M:%S"),
                "likes": likes,
                "shares": shares,
                "comments": comments,
            })


def write(name, rows):
    with open(SEEDS / f"{name}.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


write("raw_articles", articles)
write("raw_pageviews", pageviews)
write("raw_social_post_snapshots", posts)
print(len(articles), "articles,", len(pageviews), "pageviews,", len(posts), "snapshots")
