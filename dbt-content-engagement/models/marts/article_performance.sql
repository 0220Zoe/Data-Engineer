-- Grain: one row per article. Aggregate each fact before joining to avoid fan-out.
with views as (
    select
        article_id,
        sum(pageviews)       as total_pageviews,
        sum(unique_readers)  as reader_days
    from {{ ref('fct_article_daily_views') }}
    group by 1
),

readers as (
    select article_id, count(distinct user_id) as unique_readers
    from {{ ref('stg_pageviews') }}
    group by 1
),

social as (
    select
        article_id,
        count(*)                                                  as social_posts,
        count(*) filter (where is_mature)                         as mature_social_posts,
        sum(total_engagements) filter (where is_mature)           as mature_engagements,
        sum(total_engagements) filter (where not is_mature)       as immature_engagements
    from {{ ref('fct_social_post_engagement') }}
    group by 1
)

select
    a.article_id,
    a.section,
    a.published_at,
    coalesce(v.total_pageviews, 0)        as total_pageviews,
    coalesce(r.unique_readers, 0)         as unique_readers,
    coalesce(s.social_posts, 0)           as social_posts,
    coalesce(s.mature_social_posts, 0)    as mature_social_posts,
    coalesce(s.mature_engagements, 0)     as mature_engagements,
    coalesce(s.immature_engagements, 0)   as immature_engagements
from {{ ref('dim_articles') }} a
left join views   v on v.article_id = a.article_id
left join readers r on r.article_id = a.article_id
left join social  s on s.article_id = a.article_id
