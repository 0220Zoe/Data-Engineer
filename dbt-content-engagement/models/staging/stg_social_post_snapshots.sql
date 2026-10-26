select
    post_id,
    article_id,
    lower(platform)                as platform,
    cast(posted_at as timestamp)   as posted_at,
    cast(snapshot_at as timestamp) as snapshot_at,
    likes,
    shares,
    comments,
    likes + shares + comments      as total_engagements
from {{ ref('raw_social_post_snapshots') }}
