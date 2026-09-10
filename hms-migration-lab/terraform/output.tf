output "hms_postgres_fqdn" {
  value = azurerm_postgresql_flexible_server.hms.fqdn
}

output "hms_database" {
  value = azurerm_postgresql_flexible_server_database.hms.name
}

output "legacy_hms_container" {
  value = azurerm_storage_container.legacy_hms.name
}