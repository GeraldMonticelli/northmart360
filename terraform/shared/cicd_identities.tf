resource "databricks_service_principal" "github_cicd" {
  provider     = databricks.account
  display_name = "northmart-github-cicd"
}

resource "databricks_service_principal" "platform_cicd" {
  provider       = databricks.account
  application_id = "080dc876-6182-44a4-a5dd-3e85292d302a"
  display_name   = "northmart-platform-cicd"
}

resource "databricks_service_principal_federation_policy" "github_cicd" {
  provider = databricks.account

  service_principal_id = databricks_service_principal.github_cicd.id

  oidc_policy = {
    issuer        = "https://token.actions.githubusercontent.com"
    subject_claim = "job_workflow_ref"
    subject       = "GeraldMonticelli/northmart360/.github/workflows/databricks-auth.yml@refs/heads/main"

    audiences = [
      "72b31e8d-b148-4abf-bce7-a803d20310c5"
    ]
  }
}