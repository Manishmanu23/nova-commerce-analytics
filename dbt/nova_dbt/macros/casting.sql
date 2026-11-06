{#-
  Casting helpers. Raw columns are TEXT; these macros cast defensively so that one bad value
  becomes NULL (and is caught by a test) instead of failing the whole model.
-#}

{# UTC text timestamp -> IST local timestamp. Source systems emit UTC; the business reports in IST. #}
{% macro to_ist(col) -%}
    (case when {{ col }} ~ '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$'
          then ({{ col }}::timestamp at time zone 'UTC') at time zone 'Asia/Kolkata' end)
{%- endmacro %}

{% macro safe_date(col) -%}
    (case when {{ col }} ~ '^\d{4}-\d{2}-\d{2}' then left({{ col }}, 10)::date end)
{%- endmacro %}

{% macro safe_numeric(col) -%}
    (case when trim({{ col }}) ~ '^-?\d+(\.\d+)?$' then trim({{ col }})::numeric end)
{%- endmacro %}

{% macro safe_int(col) -%}
    (case when trim({{ col }}) ~ '^-?\d+(\.0+)?$' then trim({{ col }})::numeric::bigint end)
{%- endmacro %}

{# normalise free-text labels before mapping through a seed #}
{% macro norm(col) -%}
    lower(trim({{ col }}))
{%- endmacro %}

{# latest-record-wins de-duplication #}
{% macro dedupe(relation, partition_by, order_by, rn='_rn') -%}
    select * from (
        select *, row_number() over (partition by {{ partition_by }} order by {{ order_by }}) as {{ rn }}
        from {{ relation }}
    ) _d where {{ rn }} = 1
{%- endmacro %}
