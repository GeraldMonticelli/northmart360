from pathlib import Path
import sys

from rdflib import Graph, Namespace, RDF


ROOT = Path(__file__).resolve().parents[1]

CONTRACT = ROOT / "domains" / "crm" / "3_physical-model.jsonld"
R2RML_FILE = ROOT / "generated" / "crm_customer.r2rml.ttl"

DP = Namespace("https://northmart.example/ontology/dataproduct#")
RR = Namespace("http://www.w3.org/ns/r2rml#")


# ---------------------------------------------------------------------------
# Load contract
# ---------------------------------------------------------------------------

contract = Graph().parse(CONTRACT, format="json-ld")

table = next(contract.subjects(RDF.type, DP.Table))

catalog = str(contract.value(table, DP.catalog))
schema = str(contract.value(table, DP.schema))
table_name = str(contract.value(table, DP.tableName))
expected_logical_table = f"{catalog}.{schema}.{table_name}"

expected_class = contract.value(table, DP.semanticBinding)

expected_mappings = set()

for column in contract.objects(table, DP.hasColumn):
    column_name = str(contract.value(column, DP.columnName))
    semantic_property = contract.value(column, DP.semanticBinding)

    expected_mappings.add(
        (column_name, semantic_property)
    )


# ---------------------------------------------------------------------------
# Load generated R2RML
# ---------------------------------------------------------------------------

r2rml = Graph()

try:
    r2rml.parse(R2RML_FILE, format="turtle")
except Exception as exc:
    print("R2RML INVALID")
    print(f"Turtle parsing failed: {exc}")
    sys.exit(1)


errors = []


# ---------------------------------------------------------------------------
# Find TriplesMap
# ---------------------------------------------------------------------------

triples_maps = list(
    r2rml.subjects(RDF.type, RR.TriplesMap)
)

if len(triples_maps) != 1:
    errors.append(
        f"Expected exactly 1 rr:TriplesMap, found {len(triples_maps)}"
    )
else:
    triples_map = triples_maps[0]


# ---------------------------------------------------------------------------
# Validate logical table
# ---------------------------------------------------------------------------

if not errors:

    logical_table = r2rml.value(
        triples_map,
        RR.logicalTable
    )

    actual_table = (
        r2rml.value(logical_table, RR.tableName)
        if logical_table is not None
        else None
    )

    if actual_table is None:
        errors.append("Missing rr:tableName")

    elif str(actual_table) != expected_logical_table:
        errors.append(
            "Logical table mismatch: "
            f"expected {expected_logical_table}, "
            f"found {actual_table}"
        )


# ---------------------------------------------------------------------------
# Validate semantic class
# ---------------------------------------------------------------------------

if not errors:

    subject_map = r2rml.value(
        triples_map,
        RR.subjectMap
    )

    actual_class = (
        r2rml.value(subject_map, RR["class"])
        if subject_map is not None
        else None
    )

    if actual_class is None:
        errors.append("Missing rr:class")

    elif actual_class != expected_class:
        errors.append(
            "Semantic class mismatch: "
            f"expected {expected_class}, "
            f"found {actual_class}"
        )


# ---------------------------------------------------------------------------
# Validate column → semantic property mappings
# ---------------------------------------------------------------------------

actual_mappings = set()

if not errors:

    for pom in r2rml.objects(
        triples_map,
        RR.predicateObjectMap
    ):

        predicate = r2rml.value(
            pom,
            RR.predicate
        )

        object_map = r2rml.value(
            pom,
            RR.objectMap
        )

        column = (
            r2rml.value(object_map, RR.column)
            if object_map is not None
            else None
        )

        if predicate is None or column is None:
            errors.append(
                "Invalid rr:predicateObjectMap: "
                "rr:predicate or rr:column missing"
            )
            continue

        actual_mappings.add(
            (str(column), predicate)
        )


missing = expected_mappings - actual_mappings
unexpected = actual_mappings - expected_mappings

for column, predicate in sorted(
    missing,
    key=lambda x: x[0]
):
    errors.append(
        f"Missing mapping: "
        f"{column} -> {predicate}"
    )

for column, predicate in sorted(
    unexpected,
    key=lambda x: x[0]
):
    errors.append(
        f"Unexpected mapping: "
        f"{column} -> {predicate}"
    )


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

if errors:

    print("R2RML VALIDATION FAILED")

    for error in errors:
        print(f" - {error}")

    sys.exit(1)


print("R2RML syntax: OK")
print(f"Logical table: {expected_logical_table} -> OK")
print(f"Semantic class: {expected_class} -> OK")

for column, predicate in sorted(
    expected_mappings,
    key=lambda x: x[0]
):
    print(
        f"Mapping: {column} -> {predicate} -> OK"
    )

print()
print("R2RML CONTRACT VALID")
