from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rdflib import (
    BNode,
    Graph,
    Literal,
    Namespace,
    RDF,
    RDFS,
    URIRef,
)
from rdflib.namespace import OWL, SH, XSD


# ============================================================
# Configuration
# ============================================================

ROOT = Path(__file__).resolve().parent.parent

ONTOUML_FILE = ROOT / "generated/semantic_poc.ttl"
GUFO_FILE = ROOT / "generated/semantic_poc_gufo.ttl"
OUTPUT_FILE = ROOT / "generated/semantic_poc_shapes.ttl"

ONTOUML = Namespace("https://w3id.org/ontouml#")


# ============================================================
# Logging / reporting
# ============================================================

@dataclass
class PatternStats:
    discovered: int = 0
    generated: int = 0
    skipped: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class GenerationReport:
    patterns: dict[str, PatternStats] = field(default_factory=dict)

    def stats(self, pattern: str) -> PatternStats:
        if pattern not in self.patterns:
            self.patterns[pattern] = PatternStats()
        return self.patterns[pattern]

    def print_summary(self) -> None:
        print()
        print("=" * 70)
        print("SHACL GENERATION REPORT")
        print("=" * 70)

        for name, stats in self.patterns.items():
            status = (
                "✓"
                if stats.generated == stats.discovered
                and not stats.warnings
                else "⚠"
            )

            print(
                f"{name:<24} "
                f"{stats.generated:>3}/{stats.discovered:<3} "
                f"{status}"
            )

            if stats.skipped:
                print(f"  skipped: {stats.skipped}")

            for warning in stats.warnings:
                print(f"  ⚠ {warning}")

        print("=" * 70)


# ============================================================
# Transformation context
# ============================================================

@dataclass
class Context:
    ontouml: Graph
    gufo: Graph
    shapes: Graph
    report: GenerationReport

    class_map: dict[URIRef, URIRef] = field(default_factory=dict)

    def shape_for_class(self, class_uri: URIRef) -> URIRef:
        return URIRef(f"{class_uri}Shape")


# ============================================================
# Utility functions
# ============================================================

def literal_text(value) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def read_cardinality(
    graph: Graph,
    property_uri: URIRef,
) -> tuple[Optional[int], Optional[int]]:

    cardinality = graph.value(
        property_uri,
        ONTOUML.cardinality,
    )

    if cardinality is None:
        return None, None

    lower_value = graph.value(
        cardinality,
        ONTOUML.lowerBound,
    )

    upper_value = graph.value(
        cardinality,
        ONTOUML.upperBound,
    )

    lower = (
        int(lower_value)
        if lower_value is not None
        else None
    )

    upper = None

    if upper_value is not None:
        value = str(upper_value)

        if value != "*":
            upper = int(value)

    return lower, upper


def find_gufo_class_by_label(
    ctx: Context,
    label: str,
) -> Optional[URIRef]:

    candidates = []

    for subject in ctx.gufo.subjects(
        RDF.type,
        OWL.Class,
    ):
        gufo_label = ctx.gufo.value(
            subject,
            RDFS.label,
        )

        if literal_text(gufo_label) == label:
            candidates.append(subject)

    if len(candidates) == 1:
        return candidates[0]

    return None


def find_gufo_property_by_label(
    ctx: Context,
    label: str,
) -> Optional[URIRef]:

    candidates = []

    for subject in ctx.gufo.subjects(
        RDF.type,
        OWL.ObjectProperty,
    ):
        property_label = ctx.gufo.value(
            subject,
            RDFS.label,
        )

        if literal_text(property_label) == label:
            candidates.append(subject)

    if len(candidates) == 1:
        return candidates[0]

    return None


# ============================================================
# Base transformation pattern
# ============================================================

class ShapePattern(ABC):

    name: str

    @abstractmethod
    def generate(self, ctx: Context) -> None:
        pass


# ============================================================
# Pattern 1
#
# OntoUML Class
#       ↓
# SHACL NodeShape
# ============================================================

class ClassShapePattern(ShapePattern):

    name = "Classes"

    def generate(self, ctx: Context) -> None:

        stats = ctx.report.stats(self.name)

        classes = list(
            ctx.ontouml.subjects(
                RDF.type,
                ONTOUML.Class,
            )
        )

        stats.discovered = len(classes)

        for ontouml_class in classes:

            class_name = literal_text(
                ctx.ontouml.value(
                    ontouml_class,
                    ONTOUML.name,
                )
            )

            if not class_name:
                stats.skipped += 1
                stats.warnings.append(
                    f"{ontouml_class}: missing name"
                )
                continue

            gufo_class = find_gufo_class_by_label(
                ctx,
                class_name,
            )

            if gufo_class is None:
                stats.skipped += 1
                stats.warnings.append(
                    f"{class_name}: no unique OWL class mapping"
                )
                continue

            ctx.class_map[ontouml_class] = gufo_class

            shape = ctx.shape_for_class(gufo_class)

            ctx.shapes.add(
                (
                    shape,
                    RDF.type,
                    SH.NodeShape,
                )
            )

            ctx.shapes.add(
                (
                    shape,
                    SH.targetClass,
                    gufo_class,
                )
            )

            stats.generated += 1


# ============================================================
# Pattern 2
#
# OntoUML mediation
#       +
# OntoUML cardinality
#       +
# gUFO ObjectProperty/domain/range
#
#       ↓
#
# SHACL PropertyShape
# ============================================================

class MediationShapePattern(ShapePattern):

    name = "Mediations"

    def generate(self, ctx: Context) -> None:

        stats = ctx.report.stats(self.name)

        relations = list(
            ctx.ontouml.subjects(
                ONTOUML.stereotype,
                ONTOUML.mediation,
            )
        )

        stats.discovered = len(relations)

        for relation in relations:

            relation_name = literal_text(
                ctx.ontouml.value(
                    relation,
                    ONTOUML.name,
                )
            )

            if not relation_name:
                stats.skipped += 1
                stats.warnings.append(
                    f"{relation}: missing relation name"
                )
                continue

            gufo_property = find_gufo_property_by_label(
                ctx,
                relation_name,
            )

            if gufo_property is None:
                stats.skipped += 1
                stats.warnings.append(
                    f"{relation_name}: "
                    "no unique OWL ObjectProperty mapping"
                )
                continue

            domain = ctx.gufo.value(
                gufo_property,
                RDFS.domain,
            )

            range_ = ctx.gufo.value(
                gufo_property,
                RDFS.range,
            )

            if domain is None or range_ is None:
                stats.skipped += 1
                stats.warnings.append(
                    f"{relation_name}: "
                    "ObjectProperty has no domain/range"
                )
                continue

            #
            # Current OntoUML→gUFO transformation represents
            # mediation as:
            #
            # participant --property--> relator
            #
            participant_class = domain
            relator_class = range_

            matching_end = None

            for relation_end in ctx.ontouml.objects(
                relation,
                ONTOUML.relationEnd,
            ):

                property_type = ctx.ontouml.value(
                    relation_end,
                    ONTOUML.propertyType,
                )

                mapped_class = ctx.class_map.get(
                    property_type
                )

                if mapped_class == participant_class:
                    matching_end = relation_end
                    break

            if matching_end is None:
                stats.skipped += 1
                stats.warnings.append(
                    f"{relation_name}: "
                    "cannot identify participant relation end"
                )
                continue

            min_count, max_count = read_cardinality(
                ctx.ontouml,
                matching_end,
            )

            relator_shape = ctx.shape_for_class(
                relator_class
            )

            property_shape = BNode()
            inverse_path = BNode()

            ctx.shapes.add(
                (
                    relator_shape,
                    SH.property,
                    property_shape,
                )
            )

            ctx.shapes.add(
                (
                    property_shape,
                    SH.path,
                    inverse_path,
                )
            )

            ctx.shapes.add(
                (
                    inverse_path,
                    SH.inversePath,
                    gufo_property,
                )
            )

            ctx.shapes.add(
                (
                    property_shape,
                    SH["class"],
                    participant_class,
                )
            )

            if min_count is not None:
                ctx.shapes.add(
                    (
                        property_shape,
                        SH.minCount,
                        Literal(
                            min_count,
                            datatype=XSD.integer,
                        ),
                    )
                )

            if max_count is not None:
                ctx.shapes.add(
                    (
                        property_shape,
                        SH.maxCount,
                        Literal(
                            max_count,
                            datatype=XSD.integer,
                        ),
                    )
                )

            message = (
                f"{relator_class.split('#')[-1]} "
                f"must mediate "
                f"{participant_class.split('#')[-1]} "
                f"with cardinality "
                f"{min_count if min_count is not None else 0}"
                ".."
                f"{max_count if max_count is not None else '*'}."
            )

            ctx.shapes.add(
                (
                    property_shape,
                    SH.message,
                    Literal(message),
                )
            )

            stats.generated += 1


# ============================================================
# Pattern registry
#
# ADD NEW GENERATORS HERE.
#
# Existing generators never need to be modified.
# ============================================================

PATTERNS: list[type[ShapePattern]] = [
    ClassShapePattern,
    MediationShapePattern,

    # Future:
    # GeneralizationSetPattern,
    # DisjointnessPattern,
    # CompleteGeneralizationSetPattern,
    # MaterialRelationPattern,
    # CharacterizationPattern,
    # ComparativeRelationPattern,
    # DerivationPattern,
]


# ============================================================
# Coverage diagnostics
# ============================================================

def report_model_features(ctx: Context) -> None:

    stats = ctx.report.stats("Model features")

    stereotypes = set(
        ctx.ontouml.objects(
            None,
            ONTOUML.stereotype,
        )
    )

    stats.discovered = len(stereotypes)
    stats.generated = len(stereotypes)

    print()
    print("OntoUML stereotypes discovered:")

    for stereotype in sorted(
        stereotypes,
        key=str,
    ):
        print(
            f"  - {str(stereotype).split('#')[-1]}"
        )


# ============================================================
# Main
# ============================================================

def main() -> None:

    print()
    print("OntoUML → SHACL generator")
    print("=" * 70)

    ontouml = Graph()
    ontouml.parse(
        ONTOUML_FILE,
        format="turtle",
    )

    gufo = Graph()
    gufo.parse(
        GUFO_FILE,
        format="turtle",
    )

    shapes = Graph()

    shapes.bind("sh", SH)
    shapes.bind("xsd", XSD)

    #
    # Preserve namespaces from gUFO graph.
    #
    for prefix, namespace in gufo.namespaces():
        shapes.bind(prefix, namespace)

    report = GenerationReport()

    ctx = Context(
        ontouml=ontouml,
        gufo=gufo,
        shapes=shapes,
        report=report,
    )

    print(
        f"OntoUML triples : {len(ontouml)}"
    )
    print(
        f"gUFO triples    : {len(gufo)}"
    )

    print()
    print("Running transformation patterns:")

    for pattern_class in PATTERNS:

        pattern = pattern_class()

        print(
            f"  → {pattern.name}"
        )

        pattern.generate(ctx)

    report_model_features(ctx)

    shapes.serialize(
        destination=OUTPUT_FILE,
        format="turtle",
    )

    report.print_summary()

    print()
    print(
        f"SHACL triples generated: {len(shapes)}"
    )

    print(
        f"Output: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()