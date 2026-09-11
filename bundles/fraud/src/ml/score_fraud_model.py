import mlflow
from pyspark.sql import SparkSession
from pyspark.sql.functions import struct, current_timestamp

spark = SparkSession.builder.getOrCreate()

mlflow.set_registry_uri("databricks-uc")

model_uri = "models:/northmart_dev.ml.fraud_detection_model/1"

features = (
    spark.table("northmart_dev.silver.fraud_features_5min")
    .select(
        "window",
        "card_id",
        "transaction_count_5min",
        "amount_sum_5min",
        "is_fraud"
    )
)

predict_udf = mlflow.pyfunc.spark_udf(
    spark,
    model_uri=model_uri,
    result_type="double"
)

result = (
    features
    .withColumn(
        "prediction",
        predict_udf(
            struct(
                "transaction_count_5min",
                "amount_sum_5min"
            )
        )
    )
    .withColumn("scored_at", current_timestamp())
)

result.write.mode("append").saveAsTable(
    "northmart_dev.gold.fraud_predictions"
)