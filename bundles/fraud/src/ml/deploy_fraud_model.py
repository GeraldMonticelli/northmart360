import sys
import mlflow
from mlflow import MlflowClient

model_name = sys.argv[1]
model_version = sys.argv[2]

mlflow.set_registry_uri("databricks-uc")

client = MlflowClient()

print("Model:", model_name)
print("Candidate version:", model_version)

try:
    champion = client.get_model_version_by_alias(
        name=model_name,
        alias="Champion"
    )

    print("Current Champion:", champion.version)

    client.set_registered_model_alias(
        name=model_name,
        alias="Challenger",
        version=model_version
    )

    print(f"Version {model_version} → @Challenger")

except Exception:

    client.set_registered_model_alias(
        name=model_name,
        alias="Champion",
        version=model_version
    )

    print(f"Version {model_version} → @Champion")