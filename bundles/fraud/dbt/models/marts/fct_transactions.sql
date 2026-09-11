with transactions as (

    select *
    from {{ ref('stg_transactions') }}

),

card_velocity as (

    select *
    from {{ ref('int_card_velocity') }}

),

customer_behavior as (

    select *
    from {{ ref('int_customer_behavior') }}

)

select
    t.transaction_id,
    t.customer_id,
    t.card_id,
    t.event_time,
    t.amount,
    t.currency,
    t.country,
    t.merchant_id,
    t.merchant_category,
    t.channel,
    t.device_id,
    t.fraud_scenario,
    t.is_fraud,
    t.transaction_hour,
    t.kafka_partition,
    t.kafka_offset,
    t.kafka_timestamp,

    cv.previous_tx_count_30m,
    cv.previous_amount_30m,
    cv.previous_avg_amount_24h,

    cb.previous_tx_count_24h,
    cb.previous_amount_24h,
    cb.previous_avg_amount_7d

from transactions t

left join card_velocity cv
    on t.transaction_id = cv.transaction_id

left join customer_behavior cb
    on t.transaction_id = cb.transaction_id