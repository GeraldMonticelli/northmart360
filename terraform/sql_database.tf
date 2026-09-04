resource "azurerm_mssql_server" "northmart" {
  name                = local.sql_server_name
  resource_group_name = var.resource_group_name
  location            = var.location
  version             = "12.0"

  administrator_login          = var.sql_admin_login
  administrator_login_password = var.sql_admin_password

  minimum_tls_version = "1.2"
}

resource "azurerm_mssql_database" "northmart" {
  name      = local.sql_database_name
  server_id = azurerm_mssql_server.northmart.id

  sku_name = "GP_S_Gen5_1"

  min_capacity                = 0.5
  auto_pause_delay_in_minutes = 60

  max_size_gb = 32

  zone_redundant = false
}

resource "azurerm_mssql_firewall_rule" "gerald" {
  for_each = toset(var.dev_public_ips)

  name      = "gerald-${var.environment}-${replace(each.value, ".", "-")}"
  server_id = azurerm_mssql_server.northmart.id

  start_ip_address = each.value
  end_ip_address   = each.value
}

resource "azurerm_mssql_firewall_rule" "allow_azure_services" {
  name = "AllowAzureServices"

  server_id = azurerm_mssql_server.northmart.id

  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"

}