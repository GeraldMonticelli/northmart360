import mlflow
import mlflow.sklearn

from databricks.feature_engineering import (
    FeatureEngineeringClient,
    FeatureLookup,
)

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score, classification_report


# --------------------------------------------------
# 1. Clients / config
# --------------------------------------------------

fe = FeatureEngineeringClient()

MODEL_NAME = "northmart_dev.ml.fraud_detection_model"


# --------------------------------------------------
# 2. Base transactionnelle Silver
# --------------------------------------------------

transactions = spark.table(
    "northmart_dev.silver.fraud_transactions_silver"
)

training_base = transactions.select(
    "transaction_id",
    "card_id",
    "event_time",
    "amount",
    "country",
    "merchant_category",
    "channel",
    "transaction_hour",
    "is_fraud",
)


# --------------------------------------------------
# 3. PIT lookup Feature Store
# --------------------------------------------------

feature_lookups = [
    FeatureLookup(
        table_name="northmart_dev.ml.fraud_features_300min",
        lookup_key="card_id",
        timestamp_lookup_key="event_time",
        feature_names=[
            "tx_count_300min",
            "amount_sum_300min",
            "avg_amount_300min",
        ],
    )
]

training_set = fe.create_training_set(
    df=training_base,
    feature_lookups=feature_lookups,
    label="is_fraud",
    exclude_columns=[
        "transaction_id",
        "card_id",
        "event_time",
    ],
)

training_df = training_set.load_df()

pdf = training_df.toPandas()

X = pdf.drop(columns=["is_fraud"])
y = pdf["is_fraud"]

numeric_features = [
    "amount",
    "transaction_hour",
    "tx_count_300min",
    "amount_sum_300min",
    "avg_amount_300min",
]

categorical_features = [
    "country",
    "merchant_category",
    "channel",
]

numeric_transformer = Pipeline(
    steps=[
        ("imputer", SimpleImputer(strategy="median")),
    ]
)

categorical_transformer = Pipeline(
    steps=[
        ("imputer", SimpleImputer(strategy="most_frequent")),
        (
            "onehot",
            OneHotEncoder(
                handle_unknown="ignore"
            ),
        ),
    ]
)

preprocessor = ColumnTransformer(
    transformers=[
        ("num", numeric_transformer, numeric_features),
        ("cat", categorical_transformer, categorical_features),
    ]
)

model = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        (
            "classifier",
            RandomForestClassifier(
                n_estimators=200,
                random_state=42,
                class_weight="balanced",
            ),
        ),
    ]
)

model.fit(X, y)

y_pred = model.predict(X)
y_proba = model.predict_proba(X)[:, 1]

roc_auc = roc_auc_score(y, y_proba)

print(classification_report(y, y_pred))
print("ROC AUC:", roc_auc)

mlflow.set_registry_uri("databricks-uc")

EXPERIMENT_NAME = "/Shared/northmart_fraud_detection"
mlflow.set_experiment(EXPERIMENT_NAME)

with mlflow.start_run() as run:

    fe.log_model(
        model=model,
        artifact_path="fraud_model",
        flavor=mlflow.sklearn,
        training_set=training_set,
    )

    mlflow.log_metric("roc_auc_train", roc_auc)

    model_uri = f"runs:/{run.info.run_id}/fraud_model"

    registered = mlflow.register_model(
        model_uri=model_uri,
        name=MODEL_NAME,
    )

    print("Run ID:", run.info.run_id)
    print("Registered version:", registered.version)

    