from datetime import datetime

from src.transformation.fraud_transformations import (
    transform_fraud_transactions,
)


def test_transform_fraud_transactions(spark):

    input_data = [
        (
            """
            {
              "transaction_id": "tx001",
              "customer_id": "cust001",
              "card_id": "card001",
              "event_time": "2026-09-12T10:15:00",
              "amount": 125.0,
              "currency": "EUR",
              "country": "BE",
              "merchant_id": "merchant001",
              "merchant_category": "grocery",
              "channel": "POS",
              "device_id": "device001",
              "fraud_scenario": null
            }
            """,
            0,
            100,
            datetime(2026, 9, 12, 10, 15),
        ),
        (
            """
            {
              "transaction_id": "tx002",
              "customer_id": "cust002",
              "card_id": "card002",
              "event_time": "2026-09-12T23:42:00",
              "amount": 6200.0,
              "currency": "EUR",
              "country": "FR",
              "merchant_id": "merchant002",
              "merchant_category": "electronics",
              "channel": "WEB",
              "device_id": "device002",
              "fraud_scenario": "high_amount"
            }
            """,
            0,
            101,
            datetime(2026, 9, 12, 23, 42),
        ),
    ]

    bronze = spark.createDataFrame(
        input_data,
        [
            "value",
            "partition",
            "offset",
            "kafka_timestamp",
        ],
    )

    result = transform_fraud_transactions(bronze)

    rows = {
        row.transaction_id: row
        for row in result.collect()
    }

    assert len(rows) == 2

    # Transaction normale
    assert rows["tx001"].amount == 125.0
    assert rows["tx001"].is_fraud == 0
    assert rows["tx001"].transaction_hour == 10

    # Transaction frauduleuse
    assert rows["tx002"].amount == 6200.0
    assert rows["tx002"].is_fraud == 1
    assert rows["tx002"].transaction_hour == 23