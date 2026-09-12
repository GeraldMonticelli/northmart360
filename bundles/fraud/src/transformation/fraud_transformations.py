from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    col,
    from_json,
    to_timestamp,
    hour,
    when,
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


def transform_fraud_transactions(bronze: DataFrame) -> DataFrame:
    """
    Transform raw Kafka Bronze transactions into Silver transactions.
    """

    parsed = (
        bronze
        .withColumn(
            "transaction",
            from_json(
                col("value"),
                transaction_schema,
            ),
        )
        .select(
            "transaction.*",
            "partition",
            "offset",
            "kafka_timestamp",
        )
    )

    return (
        parsed
        .withColumn(
            "is_fraud",
            when(
                col("fraud_scenario").isNotNull(),
                1,
            ).otherwise(0),
        )
        .withColumn(
            "event_time",
            to_timestamp("event_time"),
        )
        .withColumn(
            "transaction_hour",
            hour("event_time"),
        )
    )