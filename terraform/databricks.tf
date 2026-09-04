resource "databricks_storage_credential" "northmart" {
  name = "sc_${local.catalog_name}"
  azure_managed_identity {
    access_connector_id = azurerm_databricks_access_connector.northmart.id
  }
  comment = local.access_connector_name
}

resource "databricks_external_location" "northmart" {
  name               = "el_${local.catalog_name}"
  url                = "abfss://unity@${var.storage_account_name}.dfs.core.windows.net/"
  credential_name    = databricks_storage_credential.northmart.name
  enable_file_events = true
  file_event_queue {
    managed_aqs {
      resource_group  = var.resource_group_name
      subscription_id = "60b97edd-4189-44b0-92bd-5ba7c24dadc5"
    }
  }
}

resource "databricks_catalog" "northmart_dev" {
  name                       = local.catalog_name
  comment                    = "NorthMart development catalog"
  custom_max_retention_hours = 0
  properties = {
    "collation" = "UTF8_BINARY"
  }
  storage_root = "abfss://unity@${var.storage_account_name}.dfs.core.windows.net/catalogs/${local.catalog_name}"
  effective_predictive_optimization_flag {
    inherited_from_name = "metastore_azure_centralindia"
    inherited_from_type = "METASTORE"
    value               = "ENABLE"
  }
  provider_config {
    workspace_id = "7405613337187597"
  }
}

resource "databricks_schema" "bronze" {
  catalog_name = databricks_catalog.northmart_dev.name
  name         = "bronze"
  storage_root = "abfss://unity@${var.storage_account_name}.dfs.core.windows.net/catalogs/${local.catalog_name}/bronze"
  properties = {
    "collation" = "UTF8_BINARY"
    "owner"     = "root"
  }
}

resource "databricks_schema" "silver" {
  catalog_name = databricks_catalog.northmart_dev.name
  name         = "silver"
  storage_root = "abfss://unity@${var.storage_account_name}.dfs.core.windows.net/catalogs/${local.catalog_name}/silver"
  properties = {
    "collation" = "UTF8_BINARY"
    "owner"     = "root"
  }
}

resource "databricks_schema" "ml" {
  catalog_name = databricks_catalog.northmart_dev.name
  name         = "ml"
  storage_root = "abfss://unity@${var.storage_account_name}.dfs.core.windows.net/catalogs/${local.catalog_name}/ml"
  properties = {
    "collation" = "UTF8_BINARY"
    "owner"     = "root"
  }
}

resource "databricks_schema" "gold" {
  catalog_name = databricks_catalog.northmart_dev.name
  name         = "gold"
  storage_root = "abfss://unity@${var.storage_account_name}.dfs.core.windows.net/catalogs/${local.catalog_name}/gold"
  properties = {
    "collation" = "UTF8_BINARY"
    "owner"     = "root"
  }
}

resource "databricks_schema" "reference" {
  catalog_name = databricks_catalog.northmart_dev.name
  name         = "reference"
  storage_root = "abfss://unity@${var.storage_account_name}.dfs.core.windows.net/catalogs/${local.catalog_name}/reference"
  properties = {
    "collation" = "UTF8_BINARY"
    "owner"     = "root"
  }
}

resource "databricks_schema" "sandbox" {
  catalog_name = databricks_catalog.northmart_dev.name
  name         = "sandbox"
  properties = {
    "collation" = "UTF8_BINARY"
    "owner"     = "root"
  }
  provider_config {
    workspace_id = "7405613337187597"
  }
}

data "databricks_group" "northmart_data_engineers" {
  provider     = databricks.account
  display_name = "grp-northmart-data-engineers"
}

data "databricks_group" "northmart_data_analysts" {
  provider     = databricks.account
  display_name = "grp-northmart-data-analysts"
}

data "databricks_group" "northmart_data_readers" {
  provider     = databricks.account
  display_name = "grp-northmart-data-readers"
}

data "databricks_service_principal" "github_cicd" {
  provider       = databricks.account
  application_id = "818c9a7a-b711-4ebf-909a-a0be7c379c3f"
}

data "databricks_service_principal" "platform_cicd" {
  provider       = databricks.account
  application_id = "080dc876-6182-44a4-a5dd-3e85292d302a"
}

resource "databricks_grants" "northmart_catalog" {
  catalog = databricks_catalog.northmart_dev.name

  grant {
    principal = data.databricks_group.northmart_data_engineers.display_name
    privileges = [
      "ALL_PRIVILEGES",
      "MANAGE"
    ]
  }

  grant {
    principal = data.databricks_group.northmart_data_analysts.display_name
    privileges = [
      "ALL_PRIVILEGES",
      "MANAGE"
    ]
  }

  grant {
    principal = data.databricks_group.northmart_data_readers.display_name
    privileges = [
      "ALL_PRIVILEGES",
      "MANAGE"
    ]
  }

  grant {
    principal = data.databricks_service_principal.github_cicd.application_id
    privileges = [
      "ALL_PRIVILEGES",
      "MANAGE"
    ]
  }

  grant {
    principal = data.databricks_service_principal.platform_cicd.application_id
    privileges = [
      "ALL_PRIVILEGES",
      "MANAGE"
    ]
  }
}

resource "databricks_grants" "bronze" {
  schema = "${databricks_catalog.northmart_dev.name}.${databricks_schema.bronze.name}"

  grant {
    principal = data.databricks_group.northmart_data_engineers.display_name

    privileges = [
      "USE_SCHEMA",
      "CREATE_TABLE",
      "CREATE_FUNCTION"
    ]
  }
}

// grant permissions
resource "databricks_grants" "silver" {
  schema = "${databricks_catalog.northmart_dev.name}.${databricks_schema.silver.name}"

  grant {
    principal = data.databricks_group.northmart_data_engineers.display_name

    privileges = [
      "USE_SCHEMA",
      "CREATE_TABLE",
      "CREATE_FUNCTION"
    ]
  }

  grant {
    principal  = data.databricks_group.northmart_data_analysts.display_name
    privileges = ["USE_SCHEMA"]
  }
}

//grant gold access permissions to groups 
resource "databricks_grants" "gold" {
  schema = "${databricks_catalog.northmart_dev.name}.${databricks_schema.gold.name}"

  grant {
    principal = data.databricks_group.northmart_data_engineers.display_name

    privileges = [
      "USE_SCHEMA",
      "CREATE_TABLE"
    ]
  }

  grant {
    principal  = data.databricks_group.northmart_data_analysts.display_name
    privileges = ["USE_SCHEMA"]
  }

  grant {
    principal  = data.databricks_group.northmart_data_readers.display_name
    privileges = ["USE_SCHEMA"]
  }
}

// create the sql warhouse pro serverless to execute SQL to create rule tables in UC
resource "databricks_sql_endpoint" "northmart" {
  name = local.sql_server_name

  cluster_size = "2X-Small"

  min_num_clusters = 1
  max_num_clusters = 1

  auto_stop_mins = 10

  warehouse_type            = "PRO"
  enable_serverless_compute = true
}

// import entra account-imported groups in workspace 
resource "databricks_mws_permission_assignment" "northmart_data_engineers" {
  provider = databricks.account

  workspace_id = 7405613337187597
  principal_id = data.databricks_group.northmart_data_engineers.id

  permissions = ["USER"]
}

resource "databricks_mws_permission_assignment" "northmart_data_analysts" {
  provider = databricks.account

  workspace_id = 7405613337187597
  principal_id = data.databricks_group.northmart_data_analysts.id

  permissions = ["USER"]
}

resource "databricks_mws_permission_assignment" "northmart_data_readers" {
  provider = databricks.account

  workspace_id = 7405613337187597
  principal_id = data.databricks_group.northmart_data_readers.id

  permissions = ["USER"]
}


//assign permission on sql compute 
resource "databricks_permissions" "northmart_sql_warehouse" {
  sql_endpoint_id = databricks_sql_endpoint.northmart.id

  depends_on = [
    databricks_mws_permission_assignment.northmart_data_engineers,
    databricks_mws_permission_assignment.northmart_data_analysts
  ]

  access_control {
    group_name       = data.databricks_group.northmart_data_engineers.display_name
    permission_level = "CAN_USE"
  }

  access_control {
    group_name       = data.databricks_group.northmart_data_analysts.display_name
    permission_level = "CAN_USE"
  }

  access_control {
    service_principal_name = data.databricks_service_principal.github_cicd.application_id
    permission_level       = "CAN_MANAGE"

  }

}

//create the scope in databricks for the SQL database login password

resource "databricks_secret_scope" "northmart" {
  name = var.key_vault_name
  keyvault_metadata {
    resource_id = azurerm_key_vault.northmart.id
    dns_name    = azurerm_key_vault.northmart.vault_uri
  }

}


// create the NCC for the serverless compute with pricate access to ALDS
# ============================================================
# NorthMart - Serverless Network Connectivity
# Network Connectivity Configuration for serverless workloads
# ============================================================

resource "databricks_mws_network_connectivity_config" "northmart" {
  provider = databricks.account

  name   = local.ncc_name
  region = "centralindia"
}

# Attach the NCC to the existing NorthMart Databricks workspace.
#
# A workspace can only be attached to one NCC at a time.
resource "databricks_mws_ncc_binding" "northmart" {
  provider = databricks.account

  network_connectivity_config_id = (
    databricks_mws_network_connectivity_config.northmart
    .network_connectivity_config_id
  )

  workspace_id = 7405613337187597
}

# ------------------------------------------------------------
# 3. Private endpoint rule - ADLS DFS endpoint
#
# Used for ADLS Gen2 hierarchical namespace access.
# ------------------------------------------------------------
resource "databricks_mws_ncc_private_endpoint_rule" "northmart_adls_dfs" {
  provider = databricks.account

  network_connectivity_config_id = (
    databricks_mws_network_connectivity_config.northmart
    .network_connectivity_config_id
  )

  resource_id = azurerm_storage_account.northmart.id
  group_id    = "dfs"
}

# ------------------------------------------------------------
# 4. Private endpoint rule - ADLS Blob endpoint
#
# Some Databricks/storage operations use the blob endpoint
# even when the account has hierarchical namespace enabled.
# ------------------------------------------------------------
resource "databricks_mws_ncc_private_endpoint_rule" "northmart_adls_blob" {
  provider = databricks.account

  network_connectivity_config_id = (
    databricks_mws_network_connectivity_config.northmart
    .network_connectivity_config_id
  )
  resource_id = azurerm_storage_account.northmart.id
  group_id    = "blob"
}

resource "databricks_mws_ncc_private_endpoint_rule" "northmart_sql" {
  provider = databricks.account

  network_connectivity_config_id = (
    databricks_mws_network_connectivity_config.northmart
    .network_connectivity_config_id
  )

  resource_id = azurerm_mssql_server.northmart.id
  group_id    = "sqlServer"
}