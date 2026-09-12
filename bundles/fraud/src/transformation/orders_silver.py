from pyspark import pipelines as dp
import pyspark.sql.functions as F
from quality.expectations import load_expectations

DROP_RULES = load_expectations(
    spark,
    "orders_silver",
    "DROP"
)

# Toutes les règles doivent être vraies pour qu'une ligne soit valide
VALID_CONDITION = " AND ".join(
    f"COALESCE(({constraint}), FALSE)"
    for constraint in DROP_RULES.values()
)

FAILED_RULE_COLUMNS = [
    F.when(
        ~F.coalesce(F.expr(constraint), F.lit(False)),
        F.lit(rule_name)
    )
    for rule_name, constraint in DROP_RULES.items()
]

def silver_source():
    return (
        spark.readStream.table("northmart_dev.bronze.orders")
        .withColumn(
            "order_timestamp",
            F.col("order_timestamp").cast("timestamp")
        )
    )

@dp.table(
    name="northmart_dev.silver.orders",
    comment="Validated NorthMart orders",
    table_properties={
        "delta.feature.timestampNtz": "supported"
    }
)
@dp.expect_all_or_drop(DROP_RULES)
def orders_silver():
    return silver_source()

@dp.table(
    name="northmart_dev.silver.orders_quarantine",
    comment="Orders rejected by Silver data quality rules",
    table_properties={
        "delta.feature.timestampNtz": "supported"
    }
)
def orders_quarantine():
    return (
        silver_source()
        .filter(F.expr(f"NOT ({VALID_CONDITION})"))
        .withColumn(
            "dq_failed_rules",
            F.array_compact(F.array(*FAILED_RULE_COLUMNS))
        )
        .withColumn(
            "quarantine_timestamp", 
            F.current_timestamp())
    )