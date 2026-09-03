from pyspark import pipelines as dp
from pyspark.sql.functions import (
    col,
    window,
    count,
    sum as spark_sum,
    avg,
)

@dp.table(
    name="northmart_dev.ml.fraud_features_300min",
    comment="Rolling fraud activity features over 300 minutes per card.",
    schema="""
         card_id STRING NOT NULL,
         window_start TIMESTAMP,
         feature_timestamp TIMESTAMP NOT NULL,
         tx_count_300min BIGINT,
         amount_sum_300min DOUBLE,
         avg_amount_300min DOUBLE,
         CONSTRAINT fraud_features_300min_pk
             PRIMARY KEY (card_id, feature_timestamp TIMESERIES)
    """
    )
def fraud_features_300min():

    transactions = (
        spark.readStream
        .table("northmart_dev.silver.fraud_transactions_silver")
        .withWatermark("event_time", "10 minutes")
    )

    return (
        transactions
        .groupBy(
            window(
                col("event_time"),
                "300 minutes",
                "5 minutes"
            ),
            col("card_id")
        )
        .agg(
            count("*").alias("tx_count_300min"),
            spark_sum("amount").alias("amount_sum_300min"),
            avg("amount").alias("avg_amount_300min")
        )
        .select(
            col("card_id"),
            col("window.start").alias("window_start"),
            col("window.end").alias("feature_timestamp"),
            col("tx_count_300min"),
            col("amount_sum_300min"),
            col("avg_amount_300min")
        )
    )