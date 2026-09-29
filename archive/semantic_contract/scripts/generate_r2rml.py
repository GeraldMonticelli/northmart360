from pathlib import Path

from rdflib import Graph, Namespace, RDF

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "domains" / "crm" / "3_physical-model.jsonld"
OUTPUT = ROOT / "generated" / "crm_customer.r2rml.ttl"

DP = Namespace("https://northmart.example/ontology/dataproduct#")

g = Graph().parse(SOURCE, format="json-ld")
table = next(g.subjects(RDF.type, DP.Table))

catalog = str(g.value(table, DP.catalog))
schema = str(g.value(table, DP.schema))
table_name = str(g.value(table, DP.tableName))
semantic_class = str(g.value(table, DP.semanticBinding))

primary_key = None
mappings = []

for column in g.objects(table, DP.hasColumn):
    name = str(g.value(column, DP.columnName))
    predicate = str(g.value(column, DP.semanticBinding))
    mappings.append((name, predicate))

    pk_literal = g.value(column, DP.primaryKey)
    if pk_literal is not None and bool(pk_literal.toPython()):
        primary_key = name

if primary_key is None:
    raise RuntimeError(
        "No primary-key column declared in the physical model; "
        "cannot generate a stable subject IRI template."
    )

logical_table = f"{catalog}.{schema}.{table_name}"

blocks = []
for column, predicate in mappings:
    blocks.append(
        "    rr:predicateObjectMap [\n"
        f"        rr:predicate <{predicate}> ;\n"
        f'        rr:objectMap [ rr:column "{column}" ]\n'
        "    ]"
    )

ttl = (
    "@prefix rr: <http://www.w3.org/ns/r2rml#> .\n\n"
    "<#CustomerMap>\n"
    "    a rr:TriplesMap ;\n"
    f'    rr:logicalTable [ rr:tableName "{logical_table}" ] ;\n'
    "    rr:subjectMap [\n"
    f'        rr:template "https://northmart.example/resource/crm/customer/'
    f'{{{primary_key}}}" ;\n'
    f"        rr:class <{semantic_class}>\n"
    "    ] ;\n"
    + " ;\n".join(blocks)
    + " .\n"
)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(ttl, encoding="utf-8")
print(f"Generated: {OUTPUT}")
