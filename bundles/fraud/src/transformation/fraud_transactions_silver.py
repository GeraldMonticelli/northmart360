from pyspark import pipelines as dp

from src.transformation.fraud_transformations import (
    transform_fraud_transactions,
)


@dp.table(
    name="northmart_dev.silver.fraud_transactions_silver",
    comment="Validated and normalized fraud transactions.",
)
@dp.expect(
    "valid_transaction_id",
    "transaction_id IS NOT NULL",
)
@dp.expect(
    "positive_amount",
    "amount > 0",
)
@dp.expect(
    "valid_event_time",
    "event_time IS NOT NULL",
)
def fraud_transactions_silver():

    bronze = spark.readStream.table(
        "northmart_dev.bronze.fraud_transactions"
    )

    return transform_fraud_transactions(bronze)