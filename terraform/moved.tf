moved {
  from = azurerm_resource_group.northmart
  to   = azurerm_resource_group.northmart[0]
}

moved {
  from = azurerm_virtual_network.northmart_databricks
  to   = azurerm_virtual_network.northmart[0]
}
