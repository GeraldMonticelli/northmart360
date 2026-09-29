variable "northmart_resource_group_name" {
  description = "Resource group containing the shared Northmart infrastructure"
  type        = string
  default     = "rg-dp750"
}

variable "northmart_location" {
  description = "Azure location for shared Northmart resources"
  type        = string
  default     = "Central India"
}
