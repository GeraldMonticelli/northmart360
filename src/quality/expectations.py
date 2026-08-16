def load_expectations(spark, rule_set: str, action: str):
    rows = (
        spark.table("northmart_dev.reference.dq_rules")
        .where(
            f"rule_set = '{rule_set}' "
            f"AND action = '{action}' "
            f"AND enabled = true"
        )
        .collect()
    )

    return {
        row["rule_name"]: row["constraint_sql"]
        for row in rows
    }