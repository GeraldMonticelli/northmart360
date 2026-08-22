from pyspark import pipelines as dp
from pyspark.sql.functions import (
    col,
    from_json,
    to_timestamp,
    hour,
    window,
    count,
    sum as spark_sum,
    max as spark_max
)



@dp.table(
    name="northmart_dev.silver.fraud_features_5min",
    comment="Five-minute fraud activity features per card."
)
def fraud_features_5min():

    transactions = (
        spark.readStream
        .table("northmart_dev.silver.fraud_transactions_silver")
        .withWatermark("event_time", "2 minutes")
    )

    return (
        transactions
        .groupBy(
            window(
                col("event_time"),
                "5 minutes"
            ),
            col("card_id")
        )
        .agg(
            count("*").alias("transaction_count_5min"),
            spark_sum("amount").alias("amount_sum_5min"),
            spark_max("is_fraud").alias("is_fraud")
        )
    )