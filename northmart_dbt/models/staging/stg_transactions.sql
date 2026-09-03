select
    transaction_id,
    customer_id,
    card_id,
    event_time,
    amount,
    upper(currency) as currency,
    upper(country) as country,
    merchant_id,
    merchant_category,
    lower(channel) as channel,
    device_id,
    fraud_scenario,
    is_fraud,
    transaction_hour,
    -- metadata d'ingestion
    partition as kafka_partition,
    offset as kafka_offset,
    kafka_timestamp

from {{ source('northmart', 'fraud_transactions_silver') }}

where transaction_id is not null
  and event_time is not null