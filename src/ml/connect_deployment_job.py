import sys
import mlflow
from databricks.sdk import WorkspaceClient
from mlflow import MlflowClient

model_name = sys.argv[1]
deployment_job_name = sys.argv[2]

w = WorkspaceClient()

matching_jobs = [
    job
    for job in w.jobs.list()
    if job.settings and job.settings.name == deployment_job_name
]

if not matching_jobs:
    raise RuntimeError(
        f"Deployment job not found: {deployment_job_name}"
    )

if len(matching_jobs) > 1:
    raise RuntimeError(
        f"Several jobs found with name: {deployment_job_name}"
    )

deployment_job_id = matching_jobs[0].job_id

print("Deployment job:", deployment_job_name)
print("Deployment job ID:", deployment_job_id)

mlflow.set_registry_uri("databricks-uc")

client = MlflowClient()

client.update_registered_model(
    name=model_name,
    deployment_job_id=deployment_job_id,
)

print(
    f"{model_name} connected to deployment job "
    f"{deployment_job_id}"
)