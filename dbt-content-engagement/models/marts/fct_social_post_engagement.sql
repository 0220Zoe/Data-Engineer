-- Recent posts are still collecting engagement. Instead of silently excluding them,
-- flag them, so dashboards can filter and post counts still reconcile.
{% set as_of = "cast('" ~ var('as_of_date') ~ "' as timestamp)" %}

select
    post_id,
    article_id,
    platform,
    posted_at,
    snapshot_at,
    likes,
    shares,
    comments,
    total_engagements,
    date_diff('day', posted_at, {{ as_of }})                              as post_age_days,
    date_diff('day', posted_at, {{ as_of }}) >= {{ var('maturity_days') }} as is_mature
from {{ ref('int_social_posts_latest') }}
