-- The article mart must account for every deduplicated pageview.
select
    (select count(*) from {{ ref('stg_pageviews') }})                as staged,
    (select sum(total_pageviews) from {{ ref('article_performance') }}) as in_mart
where staged != in_mart
