select
    article_id,
    lower(trim(section))            as section,
    headline,
    cast(published_at as timestamp) as published_at
from {{ ref('raw_articles') }}
