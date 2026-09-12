import argparse
from pyspark.sql import SparkSession


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--catalog",
        required=True,
        help="Unity Catalog catalog, e.g. northmart_dev",
    )

    parser.add_argument(
        "--eventhub-namespace",
        required=True,
        help="Azure Event Hubs namespace without .servicebus.windows.net",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    spark = SparkSession.builder.getOrCreate()

    # dbutils is available when executed on Databricks
    from pyspark.dbutils import DBUtils

    dbutils = DBUtils(spark)

    scope = "kv-northmart-gmkng"
    secret_key = "eventhub-fraud-producer-connection-string"

    eventhub_name = "fraud-transactions"

    connection_string = dbutils.secrets.get(
        scope=scope,
        key=secret_key,
    )

    bootstrap_servers = (
        f"{args.eventhub_namespace}.servicebus.windows.net:9093"
    )

    jaas_config = (
        "kafkashaded.org.apache.kafka.common.security.plain."
        "PlainLoginModule required "
        'username="$ConnectionString" '
        f'password="{connection_string}";'
    )

    raw_stream = (
        spark.readStream
        .format("kafka")
        .option(
            "kafka.bootstrap.servers",
            bootstrap_servers,
        )
        .option("subscribe", eventhub_name)
        .option("kafka.security.protocol", "SASL_SSL")
        .option("kafka.sasl.mechanism", "PLAIN")
        .option("kafka.sasl.jaas.config", jaas_config)
        .option("startingOffsets", "earliest")
        .load()
    )

    bronze_stream = raw_stream.selectExpr(
        "CAST(key AS STRING) AS kafka_key",
        "CAST(value AS STRING) AS value",
        "topic",
        "partition",
        "offset",
        "timestamp AS kafka_timestamp",
    )

    spark.sql(
        f"""
        CREATE VOLUME IF NOT EXISTS
        {args.catalog}.bronze.checkpoints
        """
    )

    checkpoint_path = (
        f"/Volumes/{args.catalog}/bronze/checkpoints/"
        "fraud_transactions"
    )

    target_table = (
        f"{args.catalog}.bronze.fraud_transactions"
    )

    query = (
        bronze_stream.writeStream
        .format("delta")
        .option(
            "checkpointLocation",
            checkpoint_path,
        )
        .outputMode("append")
        .toTable(target_table)
    )

    query.awaitTermination()


if __name__ == "__main__":
    main()