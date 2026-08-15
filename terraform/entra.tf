resource "azuread_group" "northmart_data_engineers" {
  display_name     = "grp-northmart-data-engineers"
  security_enabled = true
}

resource "azuread_group" "northmart_data_analysts" {
  display_name     = "grp-northmart-data-analysts"
  security_enabled = true
}

resource "azuread_group" "northmart_data_readers" {
  display_name     = "grp-northmart-data-readers"
  security_enabled = true
}