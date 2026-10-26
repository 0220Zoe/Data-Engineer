-- Engagement counts are cumulative: a later snapshot must never be lower than an earlier one.
with ordered as (
    select
        post_id,
        snapshot_at,
        total_engagements,
        lag(total_engagements) over (partition by post_id order by snapshot_at) as previous_total
    from {{ ref('stg_social_post_snapshots') }}
)

select *
from ordered
where total_engagements < previous_total
