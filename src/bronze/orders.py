from pyspark import pipelines as dp

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

def read_orders(path):
    return (
        spark.readStream
        .format("cloudFiles")
        .option("cloudFiles.format", "parquet")
        .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
        .option("cloudFiles.schemaHints", SCHEMA_HINTS)
        .option("rescuedDataColumn", "_rescued_data")
        .load(path)
    )


dp.create_streaming_table(
    name="northmart_dev.bronze.orders",
    comment="Raw NorthMart orders with schema evolution"
)


@dp.append_flow(
    target="northmart_dev.bronze.orders",
    name="orders_history",
    once=True,
)
def orders_history():
    return read_orders(HISTORY_PATH)


@dp.append_flow(
    target="northmart_dev.bronze.orders",
    name="orders_live",
)
def orders_live():
    return read_orders(INCOMING_PATH)