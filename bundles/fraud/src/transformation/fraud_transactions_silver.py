from pyspark import pipelines as dp
from pyspark.sql.functions import (
    col,
    from_json,
    to_timestamp,
    hour,
    window,
    count,
    when,
    sum as spark_sum,
)

from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    DoubleType,
    TimestampType,
)

transaction_schema = StructType([
    StructField("transaction_id", StringType(), True),
    StructField("customer_id", StringType(), True),
    StructField("card_id", StringType(), True),
    StructField("event_time", TimestampType(), True),
    StructField("amount", DoubleType(), True),
    StructField("currency", StringType(), True),
    StructField("country", StringType(), True),
    StructField("merchant_id", StringType(), True),
    StructField("merchant_category", StringType(), True),
    StructField("channel", StringType(), True),
    StructField("device_id", StringType(), True),
    StructField("fraud_scenario", StringType(), True),
])

@dp.table(
    name="northmart_dev.silver.fraud_transactions_silver",
    comment="Validated and normalized fraud transactions."
)
@dp.expect(
    "valid_transaction_id",
    "transaction_id IS NOT NULL"
)
@dp.expect(
    "positive_amount",
    "amount > 0"
)
@dp.expect(
    "valid_event_time",
    "event_time IS NOT NULL"
)
def fraud_transactions_silver():

    bronze = spark.readStream.table(
        "northmart_dev.bronze.fraud_transactions"
    )

    parsed = (
        bronze
        .withColumn(
            "transaction",
            from_json(
                col("value"),
                transaction_schema
            )
        )
        .select(
            "transaction.*",
            "partition",
            "offset",
            "kafka_timestamp"
        )
    )

    return (
        parsed
        .withColumn(
            "is_fraud",
            when(col("fraud_scenario").isNotNull(), 1).otherwise(0)
        )
        .withColumn(
            "event_time",
            to_timestamp("event_time")
        )
        .withColumn(
            "transaction_hour",
            hour("event_time")
        )
    )