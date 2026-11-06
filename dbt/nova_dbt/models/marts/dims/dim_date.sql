-- grain: one row per calendar date. Generated (not sourced) so there are no gaps; festival flags joined from business calendar.
with spine as (
    select d::date as date_day
    from generate_series('2023-12-01'::date, '2026-02-28'::date, interval '1 day') d
)
select
    to_char(s.date_day, 'YYYYMMDD')::int                    as date_key,
    s.date_day,
    extract(year from s.date_day)::int                      as year,
    extract(quarter from s.date_day)::int                   as quarter,
    extract(month from s.date_day)::int                     as month,
    to_char(s.date_day, 'Mon YYYY')                         as month_label,
    date_trunc('month', s.date_day)::date                   as month_start,
    date_trunc('week', s.date_day)::date                    as week_start,          -- ISO week (Monday)
    extract(isodow from s.date_day)::int                    as iso_day_of_week,
    to_char(s.date_day, 'Dy')                               as day_name,
    extract(isodow from s.date_day) in (6, 7)               as is_weekend,
    coalesce(c.fiscal_year,
             'FY' || (extract(year from s.date_day) + case when extract(month from s.date_day) >= 4 then 1 else 0 end)::int) as fiscal_year,
    c.fiscal_quarter,
    c.festival_name,
    coalesce(c.is_sale_period, false)                       as is_sale_period,
    s.date_day between '{{ var("data_start_date") }}' and '{{ var("data_end_date") }}' as is_in_reporting_window
from spine s
left join {{ ref('stg_dates') }} c on c.date_day = s.date_day
