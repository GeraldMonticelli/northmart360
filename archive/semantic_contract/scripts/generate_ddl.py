from pathlib import Path

from rdflib import Graph, Namespace, RDF


ROOT = Path(__file__).resolve().parents[1]

SOURCE = ROOT / "domains" / "crm" / "3_physical-model.jsonld"
OUTPUT = ROOT / "generated" / "crm_customer.sql"

DP = Namespace("https://northmart.example/ontology/dataproduct#")


# ---------------------------------------------------------------------------
# Load physical contract
# ---------------------------------------------------------------------------

g = Graph().parse(SOURCE, format="json-ld")

table = next(g.subjects(RDF.type, DP.Table))

catalog = str(g.value(table, DP.catalog))
schema = str(g.value(table, DP.schema))
table_name = str(g.value(table, DP.tableName))
table_binding = str(g.value(table, DP.semanticBinding))


# ---------------------------------------------------------------------------
# Generate physical columns and semantic tags
# ---------------------------------------------------------------------------

columns = []
column_tag_statements = []

for column in g.objects(table, DP.hasColumn):

    name = str(g.value(column, DP.columnName))
    sql_type = str(g.value(column, DP.sqlType))
    nullable_literal = g.value(column, DP.nullable)
    semantic_binding = str(g.value(column, DP.semanticBinding))

    nullable = (
        True
        if nullable_literal is None
        else bool(nullable_literal.toPython())
    )

    # Physical column definition
    definition = f"  {name} {sql_type}"

    if not nullable:
        definition += " NOT NULL"

    columns.append(definition)

    # Semantic property tag on the Unity Catalog column
    column_tag_statements.append(
        f"SET TAG ON COLUMN "
        f"{catalog}.{schema}.{table_name}.{name} "
        f"`semantic_property` = `{semantic_binding}`;"
    )


# ---------------------------------------------------------------------------
# Generate Databricks SQL
# ---------------------------------------------------------------------------

sql = (
    f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema};\n\n"

    f"CREATE TABLE IF NOT EXISTS {catalog}.{schema}.{table_name} (\n"
    + ",\n".join(columns)
    + "\n) USING DELTA;\n\n"

    + f"SET TAG ON TABLE {catalog}.{schema}.{table_name} "
      f"`semantic_class` = `{table_binding}`;\n\n"

    + "\n\n".join(column_tag_statements)
    + "\n"
)


# ---------------------------------------------------------------------------
# Write generated SQL artifact
# ---------------------------------------------------------------------------

OUTPUT.parent.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT.write_text(
    sql,
    encoding="utf-8",
)

print(f"Generated: {OUTPUT}")