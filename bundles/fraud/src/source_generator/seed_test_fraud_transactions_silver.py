import uuid
from datetime import UTC, datetime, timedelta

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

spark = SparkSession.builder.getOrCreate()

CATALOG = "northmart_test"
SCHEMA = "silver"
TABLE = "fraud_transactions_silver"

assert CATALOG == "northmart_test", "Seed is allowed only in TEST"

schema = StructType([
    StructField("transaction_id", StringType(), False),
    StructField("customer_id", StringType(), False),
    StructField("card_id", StringType(), False),
    StructField("event_time", TimestampType(), False),
    StructField("amount", DoubleType(), False),
    StructField("currency", StringType(), False),
    StructField("country", StringType(), False),
    StructField("merchant_id", StringType(), False),
    StructField("merchant_category", StringType(), False),
    StructField("channel", StringType(), False),
    StructField("device_id", StringType(), False),
    StructField("fraud_scenario", StringType(), True),
    StructField("partition", IntegerType(), False),
    StructField("offset", LongType(), False),
    StructField("kafka_timestamp", TimestampType(), False),
    StructField("is_fraud", IntegerType(), False),
    StructField("transaction_hour", IntegerType(), False),
])

base_time = datetime(2026, 9, 16, 10, 0, tzinfo=UTC)

rows = []

for i in range(100):
    event_time = base_time + timedelta(minutes=i)

    # deterministic mix: roughly 10% fraudulent transactions
    is_fraud = 1 if i % 10 == 0 else 0

    rows.append((
        str(uuid.uuid5(uuid.NAMESPACE_DNS, f"northmart-test-{i}")),
        f"C-{(i % 25) + 1:06d}",
        f"CARD-{(i % 40) + 1:06d}",
        event_time,
        float(25 + (i * 17) % 2000),
        "EUR",
        ["BE", "FR", "NL", "DE"][i % 4],
        f"M-{(i % 20) + 1:05d}",
        ["retail", "travel", "restaurant", "electronics"][i % 4],
        ["web", "mobile", "pos"][i % 3],
        f"DEV-{(i % 30) + 1:05d}",
        "test_fraud" if is_fraud else None,
        i % 4,
        i,
        event_time,
        is_fraud,
        event_time.hour,
    ))

df = spark.createDataFrame(rows, schema)

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")

(
    df.write
      .format("delta")
      .mode("overwrite")
      .saveAsTable(f"{CATALOG}.{SCHEMA}.{TABLE}")
)

print(
    f"Seeded {df.count()} rows into "
    f"{CATALOG}.{SCHEMA}.{TABLE}"
)