-- Engagement is cumulative, so the latest snapshot per post is the current total.
with ranked as (
    select
        *,
        row_number() over (partition by post_id order by snapshot_at desc) as snapshot_rank
    from {{ ref('stg_social_post_snapshots') }}
)

select post_id, article_id, platform, posted_at, snapshot_at,
       likes, shares, comments, total_engagements
from ranked
where snapshot_rank = 1
