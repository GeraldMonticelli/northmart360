#!/usr/bin/env python3
"""Convert a CyFun/OSCAL catalog to RDF/Turtle while preserving its hierarchy.

Preserved for the supplied CyFun 2025 catalog:
- Catalog + metadata (uuid, title, version, dates, OSCAL version, document IDs)
- Recursive group hierarchy (Function -> Category -> Subcategory)
- Controls/requirements and their parent group
- Parts (overview, statement) including id/name/prose
- Properties including name/value/ns (assurance-level, key-measures, governance-measures, labels, sort-id)
- Source order through oscal:index

No semantic classification is invented: this is a structural projection of OSCAL JSON to RDF.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import quote

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS, XSD

OSCAL = Namespace("https://example.org/oscal#")
CYFUN = Namespace("https://cyfun.eu/resource/")
CYFUN_ONTO = Namespace("https://cyfun.eu/ontology#")


def uri(kind: str, identifier: str) -> URIRef:
    return URIRef(f"{CYFUN}{kind}/{quote(str(identifier), safe='.-_')}")


def add_literal(g: Graph, subject: URIRef, predicate: URIRef, value, datatype=None) -> None:
    if value is not None:
        g.add((subject, predicate, Literal(value, datatype=datatype)))


def add_props(g: Graph, owner: URIRef, props: list[dict], owner_key: str) -> None:
    for i, prop in enumerate(props or [], 1):
        p = uri("property", f"{owner_key}-{i}")
        g.add((p, RDF.type, OSCAL.Property))
        g.add((owner, OSCAL.prop, p))
        add_literal(g, p, OSCAL["index"], i, XSD.integer)
        add_literal(g, p, OSCAL.name, prop.get("name"))
        if "value" in prop:
            add_literal(g, p, OSCAL.value, str(prop["value"]))
        if prop.get("ns"):
            g.add((p, OSCAL.ns, URIRef(prop["ns"])))


def add_parts(g: Graph, owner: URIRef, parts: list[dict], owner_key: str) -> None:
    for i, part in enumerate(parts or [], 1):
        pid = part.get("id") or f"{owner_key}-part-{i}"
        p = uri("part", pid)
        g.add((p, RDF.type, OSCAL.Part))
        g.add((owner, OSCAL.part, p))
        add_literal(g, p, OSCAL["index"], i, XSD.integer)
        add_literal(g, p, OSCAL.id, part.get("id"))
        add_literal(g, p, OSCAL.name, part.get("name"))
        add_literal(g, p, OSCAL.prose, part.get("prose"))
        # Future-proof for nested OSCAL parts/props.
        add_props(g, p, part.get("props", []), f"{pid}-prop")
        add_parts(g, p, part.get("parts", []), f"{pid}-part")


def add_control(g: Graph, control: dict, parent: URIRef, index: int) -> URIRef:
    cid = control["id"]
    c = uri("control", cid)
    g.add((c, RDF.type, OSCAL.Control))
    g.add((c, RDF.type, CYFUN_ONTO.Requirement))
    g.add((parent, OSCAL.control, c))
    g.add((c, OSCAL.parent, parent))
    add_literal(g, c, OSCAL["index"], index, XSD.integer)
    add_literal(g, c, OSCAL.id, cid)
    add_literal(g, c, OSCAL.title, control.get("title"))
    if control.get("title"):
        g.add((c, RDFS.label, Literal(control["title"])))
    add_props(g, c, control.get("props", []), cid)
    for prop in control.get("props", []):
        if prop.get("name") == "assurance-level":
            level = str(prop.get("value", "")).strip().lower()
            level_uri = {
                "basic": CYFUN_ONTO.Basic,
                "important": CYFUN_ONTO.Important,
                "essential": CYFUN_ONTO.Essential,
            }.get(level)
            if level_uri is not None:
                g.add((c, CYFUN_ONTO.assuranceLevel, level_uri))
    add_parts(g, c, control.get("parts", []), cid)
    # OSCAL permits nested controls; preserve them if encountered.
    for j, child in enumerate(control.get("controls", []), 1):
        add_control(g, child, c, j)
    return c


def add_group(g: Graph, group: dict, parent: URIRef, index: int, depth: int) -> URIRef:
    gid = group["id"]
    u = uri("group", gid)
    g.add((u, RDF.type, OSCAL.Group))
    if depth == 1:
        g.add((u, RDF.type, CYFUN_ONTO.Function))
    elif depth == 2:
        g.add((u, RDF.type, CYFUN_ONTO.Category))
    elif depth == 3:
        g.add((u, RDF.type, CYFUN_ONTO.Subcategory))
    g.add((parent, OSCAL.group, u))
    g.add((u, OSCAL.parent, parent))
    add_literal(g, u, OSCAL["index"], index, XSD.integer)
    add_literal(g, u, OSCAL.depth, depth, XSD.integer)
    add_literal(g, u, OSCAL.id, gid)
    add_literal(g, u, OSCAL.title, group.get("title"))
    if group.get("title"):
        g.add((u, RDFS.label, Literal(group["title"])))
    add_props(g, u, group.get("props", []), gid)
    add_parts(g, u, group.get("parts", []), gid)

    for j, child in enumerate(group.get("groups", []), 1):
        add_group(g, child, u, j, depth + 1)
    for j, control in enumerate(group.get("controls", []), 1):
        add_control(g, control, u, j)
    return u


def convert(catalog_json: dict) -> Graph:
    catalog = catalog_json["catalog"]
    g = Graph()
    g.bind("oscal", OSCAL)
    g.bind("cyfunres", CYFUN)
    g.bind("cyfun", CYFUN_ONTO)
    g.bind("dcterms", DCTERMS)

    catalog_uuid = catalog.get("uuid", "cyfun-2025")
    root = uri("catalog", catalog_uuid)
    g.add((root, RDF.type, OSCAL.Catalog))
    g.add((root, RDF.type, CYFUN_ONTO.CyFunFramework))
    add_literal(g, root, OSCAL.uuid, catalog.get("uuid"))

    metadata = catalog.get("metadata", {})
    m = uri("metadata", catalog_uuid)
    g.add((m, RDF.type, OSCAL.Metadata))
    g.add((root, OSCAL.metadata, m))
    add_literal(g, m, OSCAL.title, metadata.get("title"))
    add_literal(g, m, OSCAL.version, metadata.get("version"))
    add_literal(g, m, OSCAL.published, metadata.get("published"))
    add_literal(g, m, OSCAL.lastModified, metadata.get("last-modified"))
    add_literal(g, m, OSCAL.oscalVersion, metadata.get("oscal-version"))
    if metadata.get("title"):
        g.add((root, RDFS.label, Literal(metadata["title"])))
        g.add((root, DCTERMS.title, Literal(metadata["title"])))

    for i, doc in enumerate(metadata.get("document-ids", []), 1):
        d = uri("document-id", f"{catalog_uuid}-{i}")
        g.add((d, RDF.type, OSCAL.DocumentId))
        g.add((m, OSCAL.documentId, d))
        add_literal(g, d, OSCAL["index"], i, XSD.integer)
        if doc.get("scheme"):
            g.add((d, OSCAL.scheme, URIRef(doc["scheme"])))
        add_literal(g, d, OSCAL.identifier, doc.get("identifier"))

    for i, group in enumerate(catalog.get("groups", []), 1):
        add_group(g, group, root, i, 1)

    return g


def stats(catalog_json: dict) -> dict[str, int]:
    counts = {"groups": 0, "controls": 0, "parts": 0, "props": 0}
    def walk(node):
        if isinstance(node, dict):
            if "id" in node and ("groups" in node or "controls" in node) and "title" in node:
                counts["groups"] += 1
            for c in node.get("controls", []):
                counts["controls"] += 1
            counts["parts"] += len(node.get("parts", []))
            counts["props"] += len(node.get("props", []))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(catalog_json["catalog"])
    # controls get seen through parent controls arrays only once; groups heuristic above
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("catalog", help="OSCAL catalog JSON")
    ap.add_argument("-o", "--output", required=True, help="Output Turtle file")
    args = ap.parse_args()

    data = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    g = convert(data)
    g.serialize(args.output, format="turtle")

    # Validate by parsing our own output.
    check = Graph()
    check.parse(args.output, format="turtle")
    s = stats(data)
    print(f"Catalog: {data['catalog'].get('metadata', {}).get('title', '')}")
    print(f"Groups: {s['groups']} | Controls: {s['controls']} | Parts: {s['parts']} | Props: {s['props']}")
    print(f"RDF triples: {len(check)}")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
