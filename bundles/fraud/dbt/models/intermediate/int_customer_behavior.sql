select
    transaction_id,
    customer_id,
    event_time,
    amount,
    country,
    device_id,

    count(*) over (
        partition by customer_id
        order by unix_timestamp(event_time)
        range between 86400 preceding and 1 preceding
    ) as previous_tx_count_24h,

    sum(amount) over (
        partition by customer_id
        order by unix_timestamp(event_time)
        range between 86400 preceding and 1 preceding
    ) as previous_amount_24h,

    avg(amount) over (
        partition by customer_id
        order by unix_timestamp(event_time)
        range between 604800 preceding and 1 preceding
    ) as previous_avg_amount_7d

from {{ ref('stg_transactions') }}