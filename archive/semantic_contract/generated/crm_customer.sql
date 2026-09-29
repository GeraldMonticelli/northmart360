CREATE SCHEMA IF NOT EXISTS northmart_dev.crm;

CREATE TABLE IF NOT EXISTS northmart_dev.crm.customer (
  customer_id STRING NOT NULL,
  first_name STRING NOT NULL,
  birth_date DATE
) USING DELTA;

SET TAG ON TABLE northmart_dev.crm.customer `semantic_class` = `https://northmart.example/crm/Customer`;

SET TAG ON COLUMN northmart_dev.crm.customer.customer_id `semantic_property` = `https://northmart.example/crm/customerId`;

SET TAG ON COLUMN northmart_dev.crm.customer.first_name `semantic_property` = `https://northmart.example/crm/givenName`;

SET TAG ON COLUMN northmart_dev.crm.customer.birth_date `semantic_property` = `https://northmart.example/crm/birthDate`;
