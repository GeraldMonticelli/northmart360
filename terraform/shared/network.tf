resource "azurerm_resource_group" "northmart" {
  name     = var.northmart_resource_group_name
  location = var.northmart_location
}

resource "azurerm_virtual_network" "northmart" {
  name                = "vnet-northmart-dev"
  resource_group_name = azurerm_resource_group.northmart.name
  location            = azurerm_resource_group.northmart.location

  address_space = ["10.20.0.0/16"]
}
