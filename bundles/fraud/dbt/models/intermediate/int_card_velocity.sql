with base as (
    select
        transaction_id,
        card_id,
        customer_id,
        event_time,
        amount,

        count(*) over (
            partition by card_id
            order by unix_timestamp(event_time)
            range between 1800 preceding and 1 preceding
        ) as previous_tx_count_30m,

        sum(amount) over (
            partition by card_id
            order by unix_timestamp(event_time)
            range between 1800 preceding and 1 preceding
        ) as previous_amount_30m,

        avg(amount) over (
            partition by card_id
            order by unix_timestamp(event_time)
            range between 86400 preceding and 1 preceding
        ) as previous_avg_amount_24h

    from {{ ref('stg_transactions') }}
)

select
    *,
    case
        when previous_tx_count_30m >= 3 then 1
        else 0
    end as high_velocity_flag
from base