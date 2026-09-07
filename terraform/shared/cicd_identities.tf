# ============================================================
# WORKLOAD CI/CD IDENTITY
# Databricks-managed service principal
# ============================================================

resource "databricks_service_principal" "github_cicd" {
  provider     = databricks.account
  display_name = "northmart-github-cicd"
}


# ------------------------------------------------------------
# GitHub OIDC federation - DEV workload
# ------------------------------------------------------------

resource "databricks_service_principal_federation_policy" "github_cicd_dev" {
  provider = databricks.account

  service_principal_id = databricks_service_principal.github_cicd.id

  oidc_policy = {
    issuer        = "https://token.actions.githubusercontent.com"
    subject_claim = "job_workflow_ref"
    subject       = "GeraldMonticelli/northmart360/.github/workflows/workload-dev.yml@refs/heads/main"

    audiences = [
      "72b31e8d-b148-4abf-bce7-a803d20310c5"
    ]
  }
}


# ------------------------------------------------------------
# GitHub OIDC federation - TEST workload
# ------------------------------------------------------------

resource "databricks_service_principal_federation_policy" "github_cicd_test" {
  provider = databricks.account

  service_principal_id = databricks_service_principal.github_cicd.id

  oidc_policy = {
    issuer        = "https://token.actions.githubusercontent.com"
    subject_claim = "job_workflow_ref"
    subject       = "GeraldMonticelli/northmart360/.github/workflows/workload-test.yml@refs/heads/main"

    audiences = [
      "72b31e8d-b148-4abf-bce7-a803d20310c5"
    ]
  }
}


# ============================================================
# PLATFORM CI/CD IDENTITY
# Entra-managed service principal
# ============================================================

resource "databricks_service_principal" "platform_cicd" {
  provider = databricks.account

  application_id = "080dc876-6182-44a4-a5dd-3e85292d302a"
  display_name   = "northmart-platform-cicd"
}


# ============================================================
# Terraform resource address migration
# ============================================================

moved {
  from = databricks_service_principal_federation_policy.github_cicd
  to   = databricks_service_principal_federation_policy.github_cicd_dev
}