resource "databricks_group" "northmart_data_engineers" {
  provider = databricks.account

  display_name = azuread_group.northmart_data_engineers.display_name
  external_id  = azuread_group.northmart_data_engineers.object_id
}

resource "databricks_group" "northmart_data_analysts" {
  provider = databricks.account

  display_name = azuread_group.northmart_data_analysts.display_name
  external_id  = azuread_group.northmart_data_analysts.object_id
}

resource "databricks_group" "northmart_data_readers" {
  provider = databricks.account

  display_name = azuread_group.northmart_data_readers.display_name
  external_id  = azuread_group.northmart_data_readers.object_id
}