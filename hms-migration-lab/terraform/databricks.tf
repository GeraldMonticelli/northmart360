############################
# Databricks resources
############################

resource "databricks_external_location" "legacy_hms" {
  name = "el_legacy_hms_dev"

  url = "abfss://legacy-hms@stnorthmartdev.dfs.core.windows.net/"

  credential_name = data.databricks_storage_credential.northmart.name

  comment = "External location for legacy HMS federation lab"
}

resource "databricks_connection" "legacy_hms" {
  name            = "conn_legacy_hms_dev"
  connection_type = "HIVE_METASTORE"

  options = {
    host     = azurerm_postgresql_flexible_server.hms.fqdn
    port     = "5432"
    user     = "hmsadmin"
    password = data.azurerm_key_vault_secret.hms_postgres_password.value
    database = azurerm_postgresql_flexible_server_database.hms.name

    db_type = "POSTGRESQL"
    version = "3.1"
  }

  comment = "External Hive Metastore 3.1 - Northmart migration lab"
}

resource "databricks_catalog" "legacy_hms" {
  name            = "legacy_hms_dev"
  connection_name = databricks_connection.legacy_hms.name

  options = {
    authorized_paths = "abfss://legacy-hms@${data.azurerm_storage_account.northmart_dev.name}.dfs.core.windows.net/"
  }

  comment = "Federated external Hive Metastore - Northmart migration lab"
}

resource "databricks_mws_ncc_private_endpoint_rule" "northmart_postgresql_hms" {
  provider = databricks.account

  network_connectivity_config_id = (
    data.databricks_mws_network_connectivity_config.northmart
    .network_connectivity_config_id
  )

  resource_id = azurerm_postgresql_flexible_server.hms.id
  group_id    = "postgresqlServer"
}

resource "databricks_catalog" "migrated" {
  name = "northmart_migrated_dev"

  storage_root = "abfss://unity@${data.azurerm_storage_account.northmart_dev.name}.dfs.core.windows.net/hms-migration"

  comment = "Native Unity Catalog target for HMS migration lab"
}

resource "databricks_schema" "legacy_sales" {
  catalog_name = databricks_catalog.migrated.name
  name         = "legacy_sales"
  comment      = "Migrated legacy_sales schema"
}

resource "databricks_schema" "legacy_finance" {
  catalog_name = databricks_catalog.migrated.name
  name         = "legacy_finance"
  comment      = "Migrated legacy_finance schema"
}

resource "databricks_schema" "legacy_iot" {
  catalog_name = databricks_catalog.migrated.name
  name         = "legacy_iot"
  comment      = "Migrated legacy_iot schema"
}

resource "databricks_schema" "legacy_reference" {
  catalog_name = databricks_catalog.migrated.name
  name         = "legacy_reference"
  comment      = "Migrated legacy_reference schema"
}