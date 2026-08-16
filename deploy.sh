#!/bin/bash

set -e

WAREHOUSE_ID=$(terraform -chdir=terraform output -raw northmart_sql_warehouse_id)

export BUNDLE_VAR_sql_warehouse_id="$WAREHOUSE_ID"

databricks bundle validate -t dev
databricks bundle deploy -t dev