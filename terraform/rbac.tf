resource "azurerm_role_assignment" "northmart_blob_data_contributor" {
  scope                = azurerm_storage_account.northmart.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_databricks_access_connector.northmart.identity[0].principal_id
}

resource "azurerm_role_assignment" "northmart_queue_data_contributor" {
  scope                = azurerm_storage_account.northmart.id
  role_definition_name = "Storage Queue Data Contributor"
  principal_id         = azurerm_databricks_access_connector.northmart.identity[0].principal_id
}

resource "azurerm_role_assignment" "northmart_storage_account_contributor" {
  scope                = azurerm_storage_account.northmart.id
  role_definition_name = "Storage Account Contributor"
  principal_id         = azurerm_databricks_access_connector.northmart.identity[0].principal_id
}

resource "azurerm_role_assignment" "northmart_eventgrid_contributor" {
  scope                = azurerm_storage_account.northmart.id
  role_definition_name = "EventGrid EventSubscription Contributor"
  principal_id         = azurerm_databricks_access_connector.northmart.identity[0].principal_id
}