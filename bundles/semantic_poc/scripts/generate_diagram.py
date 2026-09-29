import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

INPUT = ROOT / "src/ontology/semantic_poc.json"
OUTPUT = ROOT / "generated/semantic_poc.puml"

with INPUT.open(encoding="utf-8") as f:
    project = json.load(f)

contents = project["model"]["contents"]

classes = {
    element["id"]: element
    for element in contents
    if element.get("type") == "Class"
}

generalizations = [
    element
    for element in contents
    if element.get("type") == "Generalization"
]

relations = [
    element
    for element in contents
    if element.get("type") == "Relation"
]


def class_name(class_id):
    return classes[class_id]["name"]


lines = [
    "@startuml",
    "",
    "hide empty members",
    "skinparam classAttributeIconSize 0",
    "",
]

# Classes OntoUML
for class_id, element in classes.items():
    name = element["name"]
    stereotype = element.get("stereotype", "")

    lines.append(
        f'class "{name}" as {class_id.replace("-", "_")} <<{stereotype}>>'
    )

lines.append("")

# Generalizations
for gen in generalizations:
    specific = gen["specific"]["id"]
    general = gen["general"]["id"]

    lines.append(
        f'{specific.replace("-", "_")} --|> {general.replace("-", "_")}'
    )

lines.append("")

# OntoUML relations
for relation in relations:
    properties = relation.get("properties", [])

    if len(properties) != 2:
        continue

    left = properties[0]
    right = properties[1]

    left_id = left["propertyType"]["id"]
    right_id = right["propertyType"]["id"]

    left_card = left.get("cardinality", "")
    right_card = right.get("cardinality", "")

    stereotype = relation.get("stereotype", "")
    name = relation.get("name", "")

    lines.append(
        f'{left_id.replace("-", "_")} "{right_card}" '
        f'-- "{left_card}" {right_id.replace("-", "_")} '
        f': <<{stereotype}>>\\n{name}'
    )

lines.extend([
    "",
    "@enduml",
])

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text("\n".join(lines), encoding="utf-8")

print(f"Generated: {OUTPUT}")