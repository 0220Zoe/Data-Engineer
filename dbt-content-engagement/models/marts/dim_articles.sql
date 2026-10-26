select article_id, section, headline, published_at
from {{ ref('stg_articles') }}
