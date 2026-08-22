from pyspark import pipelines as dp

from pyspark.sql.functions import (
    col,
    from_json,
    to_timestamp,
    hour,
    window,
    count,
    sum as spark_sum,
)


connection_string = dbutils.secrets.get(
    scope="kv-northmart-gmkng",
    key="eventhub-fraud-producer-connection-string"
)

jaas_config = (
    'kafkashaded.org.apache.kafka.common.security.plain.PlainLoginModule required '
    'username="$ConnectionString" '
    f'password="{connection_string}";'
)

@dp.table(
    name="northmart_dev.bronze.fraud_transactions",
    comment="Raw fraud transaction events ingested from Event Hubs via Kafka."
)
def fraud_transactions():

    kafka_stream = (
        spark.readStream
        .format("kafka")
        .option(
            "kafka.bootstrap.servers",
            spark.conf.get("fraud.kafka.bootstrap_servers")
        )
        .option(
            "subscribe",
            spark.conf.get("fraud.kafka.topic")
        )
        .option(
            "kafka.security.protocol",
            "SASL_SSL"
        )
        .option(
            "kafka.sasl.mechanism",
            "PLAIN"
        )
        .option(
            "kafka.sasl.jaas.config",
            jaas_config
        )
        .option("startingOffsets", "earliest")
        .load()
    )

    return (
        kafka_stream
        .select(
            col("key").cast("string").alias("kafka_key"),
            col("value").cast("string"),
            col("topic"),
            col("partition"),
            col("offset"),
            col("timestamp").alias("kafka_timestamp"),
        )
    )