from pathlib import Path
import sys

from rdflib import Graph, RDF
from rdflib.namespace import SH


ROOT = Path(__file__).resolve().parent.parent
SHAPES_FILE = ROOT / "domains/crm/4_shapes.ttl"


# Contraintes qui pourront devenir des Lakeflow Expectations
EXPECTATION_CONSTRAINTS = {
    SH.minCount,
    SH.minLength,
    SH.maxLength,
    SH.minInclusive,
    SH.maxInclusive,
    SH.pattern,
    SH["in"],
}

# Contraintes garanties par le modèle physique / DDL
STRUCTURAL_CONSTRAINTS = {
    SH.datatype,
    SH.maxCount,
}

# Prédicats SHACL nécessaires pour décrire la shape,
# mais qui ne sont pas eux-mêmes des contraintes à traduire
SHAPE_METADATA = {
    RDF.type,
    SH.targetClass,
    SH.property,
    SH.path,
}


def short_name(uri) -> str:
    """Display the local name of a SHACL predicate."""
    text = str(uri)

    if "#" in text:
        return text.rsplit("#", 1)[1]

    return text.rsplit("/", 1)[-1]


def main() -> None:
    graph = Graph()
    graph.parse(SHAPES_FILE)

    unsupported = []

    print("\nRUNTIME SHACL ANALYSIS")
    print("=" * 70)

    node_shapes = list(
        graph.subjects(RDF.type, SH.NodeShape)
    )

    if not node_shapes:
        print("✗ No sh:NodeShape found")
        sys.exit(1)

    for node_shape in node_shapes:
        print(f"\nNodeShape: {node_shape}")

        for property_shape in graph.objects(node_shape, SH.property):

            path = graph.value(property_shape, SH.path)

            if path is None:
                print("  ✗ Property shape has no sh:path")
                unsupported.append((property_shape, SH.path))
                continue

            print(f"\n  Property: {path}")

            for predicate, value in graph.predicate_objects(property_shape):

                if predicate in SHAPE_METADATA:
                    continue

                name = short_name(predicate)

                if predicate in EXPECTATION_CONSTRAINTS:
                    print(
                        f"    ✓ sh:{name:<15} "
                        f"→ EXPECTATION ({value})"
                    )

                elif predicate in STRUCTURAL_CONSTRAINTS:
                    print(
                        f"    ✓ sh:{name:<15} "
                        f"→ STRUCTURAL ({value})"
                    )

                else:
                    print(
                        f"    ✗ sh:{name:<15} "
                        f"→ UNSUPPORTED ({value})"
                    )
                    unsupported.append(
                        (path, predicate, value)
                    )

    print("\n" + "=" * 70)

    if unsupported:
        print(
            f"✗ RUNTIME CONTRACT INVALID — "
            f"{len(unsupported)} unsupported constraint(s)"
        )
        sys.exit(1)

    print("✓ RUNTIME CONTRACT VALID")


if __name__ == "__main__":
    main()