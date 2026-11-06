select * from (values
    ('mobile_app', 'App', true), ('mobile_web', 'Web', true), ('desktop', 'Web', false), ('unknown', 'Marketplace', null)
) v(device_type, platform, is_mobile)
