from pathlib import Path
import hashlib
import sys
import yaml

from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, XSD


# Usage:
# python build_knowledge_graph.py <ontouml-language> <output.ttl>

if len(sys.argv) != 3:
    raise SystemExit(
        "Usage: python build_knowledge_graph.py "
        "<ontouml-language-dir> <output.ttl>"
    )

ROOT = Path(sys.argv[1])
OUTPUT = Path(sys.argv[2])

ONTOUML = Namespace("https://w3id.org/ontouml#")
KNOW = Namespace("https://w3id.org/ontouml/knowledge#")

g = Graph()

g.bind("ontouml", ONTOUML)
g.bind("ok", KNOW)
g.bind("rdfs", RDFS)


def slug(value: str) -> str:
    return (
        value.strip()
        .replace(" ", "-")
        .replace("_", "-")
        .lower()
    )


def literal(value):
    if isinstance(value, bool):
        return Literal(value, datatype=XSD.boolean)

    return Literal(str(value))


def deterministic_node(subject, predicate, value):
    """
    Generate a stable URI for nested YAML structures.
    Unlike Python hash(), SHA-256 is reproducible across executions.
    """
    raw = f"{subject}|{predicate}|{repr(value)}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]

    return URIRef(f"{KNOW}node/{digest}")


def add_value(subject, predicate, value):
    """Generic recursive YAML -> RDF conversion."""

    if value is None:
        return

    if isinstance(value, dict):
        node = deterministic_node(subject, predicate, value)

        g.add((subject, predicate, node))

        for key, child_value in value.items():
            add_value(
                node,
                KNOW[slug(key)],
                child_value,
            )

    elif isinstance(value, list):
        for item in value:
            add_value(subject, predicate, item)

    else:
        g.add((subject, predicate, literal(value)))


def process_meta(path: Path):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    if not data:
        return

    for category, content in data.items():

        if not isinstance(content, dict):
            continue

        name = content.get("name")

        if not name:
            continue

        subject = KNOW[f"element/{slug(name)}"]

        g.add((subject, RDF.type, KNOW.LanguageElement))
        g.add((subject, RDFS.label, Literal(name)))
        g.add((subject, KNOW.category, Literal(category)))

        # Link to the official OntoUML vocabulary.
        official = ONTOUML[name[0].lower() + name[1:]]

        g.add((subject, KNOW.describes, official))

        relative_path = path.relative_to(ROOT)

        g.add(
            (
                subject,
                KNOW.source,
                Literal(str(relative_path)),
            )
        )

        # Completely generic conversion of every property in meta.yml
        for key, value in content.items():

            if key == "name":
                continue

            add_value(
                subject,
                KNOW[slug(key)],
                value,
            )


def find_element_subject(directory: Path):
    """
    Find the LanguageElement corresponding to an OntoUML-language
    stereotype directory by reading its meta.yml.

    No stereotype name is hard-coded.
    """

    meta_path = directory / "meta.yml"

    if not meta_path.exists():
        return None

    data = yaml.safe_load(meta_path.read_text(encoding="utf-8"))

    if not data:
        return None

    for _, content in data.items():

        if not isinstance(content, dict):
            continue

        name = content.get("name")

        if name:
            return KNOW[f"element/{slug(name)}"]

    return None


def process_rst(path: Path, document_type: str):
    """
    Attach an official RST document to the corresponding
    OntoUML language element.

    The text is stored as-is. We deliberately do not ask an LLM
    to interpret or rewrite the official source during ingestion.
    """

    subject = find_element_subject(path.parent)

    if subject is None:
        return False

    text = path.read_text(encoding="utf-8").strip()

    if not text:
        return False

    relative_path = path.relative_to(ROOT)

    # Deterministic document URI based on its source path.
    digest = hashlib.sha256(
        str(relative_path).encode("utf-8")
    ).hexdigest()[:20]

    document = URIRef(f"{KNOW}document/{digest}")

    g.add((document, RDF.type, KNOW.DocumentationFragment))
    g.add((document, KNOW.documentType, Literal(document_type)))
    g.add((document, KNOW.text, Literal(text)))
    g.add((document, KNOW.source, Literal(str(relative_path))))

    # Connect the documentation to the language element.
    g.add((subject, KNOW[document_type], document))

    return True

def process_validator_rules(validator_root: Path):
    import ast

    path = (
        validator_root
        / "validator"
        / "validations"
        / "rules_definitions.py"
    )

    tree = ast.parse(path.read_text(encoding="utf-8"))

    rules = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "RULES_DEFINITIONS"
                ):
                    rules = ast.literal_eval(node.value)

    for code, description in rules.items():
        rule = KNOW[f"rule/{code.lower()}"]

        g.add((rule, RDF.type, KNOW.ValidationRule))
        g.add((rule, RDFS.label, Literal(code)))
        g.add((rule, KNOW.description, Literal(description)))
        g.add((rule, KNOW.sourceType, Literal("ontouml-validator")))
        g.add((
            rule,
            KNOW.source,
            Literal("validator/validations/rules_definitions.py")
        ))

    return len(rules)

# ------------------------------------------------------------------
# 1. Structured stereotype metadata
# ------------------------------------------------------------------

meta_files = sorted(ROOT.glob("classes/**/meta.yml"))
meta_files += sorted(ROOT.glob("relationships/**/meta.yml"))

for path in meta_files:
    process_meta(path)


# ------------------------------------------------------------------
# 2. Official definitions
# ------------------------------------------------------------------

definition_files = sorted(ROOT.glob("classes/**/definition.rst"))
definition_files += sorted(ROOT.glob("relationships/**/definition.rst"))

definitions_processed = 0

for path in definition_files:
    if process_rst(path, "definition"):
        definitions_processed += 1


# ------------------------------------------------------------------
# 3. Official constraints
# ------------------------------------------------------------------

constraint_files = sorted(ROOT.glob("classes/**/constraints.rst"))
constraint_files += sorted(ROOT.glob("relationships/**/constraints.rst"))

constraints_processed = 0

for path in constraint_files:
    if process_rst(path, "constraint"):
        constraints_processed += 1

# ------------------------------------------------------------------

validator_root = ROOT.parent / "ontouml-validator"

validator_rules = 0

if validator_root.exists():
    validator_rules = process_validator_rules(validator_root)

# ------------------------------------------------------------------
# Serialize
# ------------------------------------------------------------------

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

g.serialize(
    destination=str(OUTPUT),
    format="turtle",
)

print(f"Meta files processed       : {len(meta_files)}")
print(f"Definitions processed      : {definitions_processed}")
print(f"Constraint files processed : {constraints_processed}")
print(f"RDF triples generated      : {len(g)}")
print(f"Output                     : {OUTPUT}")
print(f"Validator rules processed : {validator_rules}")