from pyspark import pipelines as dp
import pyspark.sql.functions as F

HISTORY_PATH = (
    "abfss://unity@stnorthmartdev.dfs.core.windows.net/"
    "source/orders/history/"
)

INCOMING_PATH = (
    "abfss://unity@stnorthmartdev.dfs.core.windows.net/"
    "source/orders/incoming/"
)

SCHEMA_HINTS = """
    order_id STRING,
    customer_id LONG,
    product_id LONG,
    store_id LONG,
    quantity LONG,
    unit_price DOUBLE,
    discount DOUBLE,
    order_timestamp TIMESTAMP
"""

def read_history(path):
    return (
        spark.read
        .format("parquet")
        .load(path)
        .withColumn(
            "order_timestamp",
            F.col("order_timestamp").cast("timestamp")
        )
    )


def read_live(path):
    return (
        spark.readStream
        .format("cloudFiles")
        .option("cloudFiles.format", "parquet")
        .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
        .option("cloudFiles.schemaHints", SCHEMA_HINTS)
        .option("rescuedDataColumn", "_rescued_data")
        .load(path)
        .withColumn(
            "order_timestamp",
            F.col("order_timestamp").cast("timestamp")
        )
    )


dp.create_streaming_table(
    name="northmart_dev.bronze.orders",
    comment="Raw NorthMart orders with schema evolution",
    table_properties={
        "delta.feature.timestampNtz": "supported"
    }
)


@dp.append_flow(
    target="northmart_dev.bronze.orders",
    name="orders_history",
    once=True,
)
def orders_history():
    return read_history(HISTORY_PATH)


@dp.append_flow(
    target="northmart_dev.bronze.orders",
    name="orders_live",
)
def orders_live():
    return read_live(INCOMING_PATH)