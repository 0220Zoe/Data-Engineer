-- Grain: one row per article per day.
select
    article_id,
    cast(event_ts as date)        as view_date,
    count(*)                      as pageviews,
    count(distinct user_id)       as unique_readers
from {{ ref('stg_pageviews') }}
group by 1, 2
