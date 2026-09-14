CREATE CONNECTION IF NOT EXISTS northmart_sql
TYPE SQLSERVER
OPTIONS (
  host 'sql-northmart-dev.database.windows.net',
  port '1433',
  user secret('kv-northmart-gmkng', 'northmart-sql-user'),
  password secret('kv-northmart-gmkng', 'northmart-sql-password')
);

CREATE FOREIGN CATALOG IF NOT EXISTS northmart_sql_federated
USING CONNECTION northmart_sql
OPTIONS (
  database 'sqldb-northmart-dev'
);