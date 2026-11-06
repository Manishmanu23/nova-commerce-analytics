-- grain: one row per standardised marketing channel (conformed across orders, sessions, spend)
select channel, channel_name, channel_group, is_paid, is_acquisition_channel from {{ ref('dim_channel_seed') }}
