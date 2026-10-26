-- Event streams deliver some events more than once; keep one row per event_id.
with source as (
    select
        event_id,
        user_id,
        article_id,
        cast(event_ts as timestamp) as event_ts,
        lower(platform)             as platform,
        row_number() over (partition by event_id order by event_ts) as delivery_rank
    from {{ ref('raw_pageviews') }}
)

select event_id, user_id, article_id, event_ts, platform
from source
where delivery_rank = 1
