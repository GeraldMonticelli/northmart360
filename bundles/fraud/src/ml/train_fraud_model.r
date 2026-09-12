library(SparkR)
library(mlflow)

# Initialiser SparkR
sparkR.session()

# Lire les données depuis Unity Catalog
df <- sql("
    SELECT
        amount,
        transaction_hour,
        is_fraud
    FROM northmart_dev.silver.transactions
    WHERE amount IS NOT NULL
      AND transaction_hour IS NOT NULL
      AND is_fraud IS NOT NULL
")

# Conversion en dataframe R pour ce petit exercice
training_data <- collect(df)

training_data$is_fraud <- as.factor(training_data$is_fraud)

# MLflow
mlflow_set_experiment("/Shared/northmart360-r-fraud")

mlflow_start_run()

# Modèle R très simple
model <- glm(
    is_fraud ~ amount + transaction_hour,
    data = training_data,
    family = binomial()
)

# Quelques paramètres
mlflow_log_param("model_type", "R glm logistic regression")
mlflow_log_param("features", "amount,transaction_hour")

# Sauvegarder le modèle
saveRDS(model, "/tmp/fraud_model_r.rds")

mlflow_log_artifact("/tmp/fraud_model_r.rds")

mlflow_end_run()

print(summary(model))