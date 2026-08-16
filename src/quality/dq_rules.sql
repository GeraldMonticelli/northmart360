CREATE TABLE IF NOT EXISTS northmart_dev.reference.dq_rules (
    rule_set        STRING,
    rule_name       STRING,
    constraint_sql  STRING,
    action          STRING,
    enabled         BOOLEAN,
    description     STRING
)
USING DELTA;

MERGE INTO northmart_dev.reference.dq_rules AS target
USING (
    SELECT * FROM VALUES
      (
        'orders_silver',
        'customer_not_null',
        'customer_id IS NOT NULL',
        'DROP',
        true,
        'Customer must be present'
      ),
      (
        'orders_silver',
        'positive_quantity',
        'quantity > 0',
        'DROP',
        true,
        'Quantity must be strictly positive'
      ),
      (
        'orders_silver',
        'valid_price',
        'unit_price >= 0',
        'DROP',
        true,
        'Unit price cannot be negative'
      )
    AS source(
        rule_set,
        rule_name,
        constraint_sql,
        action,
        enabled,
        description
    )
) AS source
ON  target.rule_set  = source.rule_set
AND target.rule_name = source.rule_name
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;