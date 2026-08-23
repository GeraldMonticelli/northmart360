import mlflow
import mlflow.spark


from pyspark.sql import SparkSession
from pyspark.ml import Pipeline
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.classification import RandomForestClassifier
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from mlflow.models import infer_signature


spark = SparkSession.builder.getOrCreate()

# ---------------------------------------------------------
# 1. Load ML dataset
# ---------------------------------------------------------

df = (
    spark.table("northmart_dev.silver.fraud_features_5min")
    .select(
        "transaction_count_5min",
        "amount_sum_5min",
        "is_fraud"
    )
    .dropna()
)

# ---------------------------------------------------------
# 2. Train / test split
# ---------------------------------------------------------

train_df, test_df = df.randomSplit(
    [0.8, 0.2],
    seed=42
)

# ---------------------------------------------------------
# 3. ML pipeline
# ---------------------------------------------------------

assembler = VectorAssembler(
    inputCols=[
        "transaction_count_5min",
        "amount_sum_5min",
    ],
    outputCol="features"
)

classifier = RandomForestClassifier(
    featuresCol="features",
    labelCol="is_fraud",
    numTrees=100,
    maxDepth=6,
    seed=42
)

pipeline = Pipeline(
    stages=[
        assembler,
        classifier,
    ]
)



# ---------------------------------------------------------
# 4. MLflow experiment
# ---------------------------------------------------------

mlflow.set_experiment(
    "/Shared/northmart_fraud_detection"
)

with mlflow.start_run() as run:

    mlflow.log_param("algorithm", "RandomForestClassifier")
    mlflow.log_param("numTrees", 100)
    mlflow.log_param("maxDepth", 6)

    model = pipeline.fit(train_df)

    predictions = model.transform(test_df)

    evaluator_roc = BinaryClassificationEvaluator(
        labelCol="is_fraud",
        rawPredictionCol="rawPrediction",
        metricName="areaUnderROC"
    )

    evaluator_pr = BinaryClassificationEvaluator(
        labelCol="is_fraud",
        rawPredictionCol="rawPrediction",
        metricName="areaUnderPR"
    )

    roc_auc = evaluator_roc.evaluate(predictions)
    pr_auc = evaluator_pr.evaluate(predictions)

    mlflow.log_metric("roc_auc", roc_auc)
    mlflow.log_metric("pr_auc", pr_auc)

    signature = infer_signature(
        test_df.select(
            "transaction_count_5min",
            "amount_sum_5min"
        ),
        predictions.select(
            "prediction"
            )
    )
    mlflow.spark.log_model(
        model,
        artifact_path="model",
        signature=signature
    )

    print(f"MLflow run_id = {run.info.run_id}")
    print(f"ROC-AUC = {roc_auc}")
    print(f"PR-AUC = {pr_auc}")