{{ config(materialized='view') }}
-- The governed metric catalogue. The Copilot may ONLY answer with metrics listed here.
select *, now() as catalog_published_at from {{ ref('metric_catalog_seed') }} where certified
