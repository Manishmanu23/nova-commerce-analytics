{# ---------- custom generic tests ---------- #}

{% test not_negative(model, column_name) %}
    select * from {{ model }} where {{ column_name }} < 0
{% endtest %}

{% test within_data_window(model, column_name) %}
    -- timestamps must fall inside the reporting window (+ a small grace period for late events)
    select * from {{ model }}
    where {{ column_name }} is not null
      and ({{ column_name }} < '{{ var("data_start_date") }}'::date - interval '1 day'
           or {{ column_name }} > '{{ var("data_end_date") }}'::date + interval '15 day')
{% endtest %}

{% test not_before(model, column_name, other_column) %}
    select * from {{ model }}
    where {{ column_name }} is not null and {{ other_column }} is not null
      and {{ column_name }} < {{ other_column }}
{% endtest %}

{% test max_null_rate(model, column_name, max_rate) %}
    -- fails only if the share of NULLs exceeds a tolerance (some nulls are expected in real data)
    select null_rate from (
        select avg(case when {{ column_name }} is null then 1.0 else 0 end) as null_rate from {{ model }}
    ) t where null_rate > {{ max_rate }}
{% endtest %}

{% test sum_reconciles(model, column_name, compare_model, compare_column, tolerance=0.01) %}
    -- the same governed number computed two ways must agree
    select a.total as left_total, b.total as right_total
    from (select coalesce(sum({{ column_name }}),0) as total from {{ model }}) a
    cross join (select coalesce(sum({{ compare_column }}),0) as total from {{ compare_model }}) b
    where abs(a.total - b.total) > {{ tolerance }}
{% endtest %}
