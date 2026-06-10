from __future__ import annotations

import argparse
import hashlib
import html
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import DefaultDict, Iterable

from owlrl import DeductiveClosure, OWLRL_Semantics
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS, SKOS


@dataclass
class NodeInfo:
    uri: URIRef
    label: str
    sources: set[str] = field(default_factory=set)
    parents: set[URIRef] = field(default_factory=set)
    children: set[URIRef] = field(default_factory=set)
    alignment_targets: DefaultDict[str, set[URIRef]] = field(default_factory=lambda: defaultdict(set))
    outgoing_rules: DefaultDict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    incoming_rules: DefaultDict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    incoming_instances: DefaultDict[str, set[str]] = field(default_factory=lambda: defaultdict(set))


def local_name(term: URIRef | BNode | Literal) -> str:
    if isinstance(term, Literal):
        return str(term)
    text = str(term)
    for separator in ("#", "/", ":"):
        if separator in text:
            text = text.rsplit(separator, 1)[-1]
    return text


def label_for(graph: Graph, node: URIRef | BNode) -> str:
    for predicate in (RDFS.label, SKOS.prefLabel):
        for value in graph.objects(node, predicate):
            if isinstance(value, Literal):
                return str(value)
    return local_name(node)


MATERIAL_ENTITY_IRI = URIRef("http://purl.obolibrary.org/obo/BFO_0000040")
COSO_MATERIAL_SAMPLE_IRI = URIRef("http://w3id.org/coso/v1/contaminoso#MaterialSample")


def namespace_prefix_for_uri(uri: URIRef) -> str:
    text = str(uri).lower()
    if "foodon_" in text:
        return "FOODON"
    if "egad" in text:
        return "EGAD"
    if "wqp" in text:
        return "WQP"
    if "contaminoso" in text or "coso" in text:
        return "COSO"
    return local_name(uri).split("_")[0].upper() or "NS"


def namespace_class_for_uri(uri: URIRef) -> str:
    return namespace_prefix_for_uri(uri).lower()


def source_namespace_prefix(source: str) -> str:
    if source == "egad_alignment":
        return "EGAD"
    if source == "wqp_alignment":
        return "WQP"
    if source == "contaminoso_materialSample_ext":
        return "COSO"
    if source == "foodon_lite_updated":
        return "FOODON"
    return source.split("_")[0].upper() or "NS"


def source_namespace_for_uri(uri: URIRef) -> str:
    text = str(uri).lower()
    if "us-wqp" in text or "wqp" in text:
        return "WQP"
    if "egad" in text:
        return "EGAD"
    if "contaminoso" in text or "coso" in text:
        return "COSO"
    if "foodon" in text:
        return "FOODON"
    return "NS"


def namespace_prefixes_in_view(nodes: dict[URIRef, NodeInfo], selected: set[URIRef]) -> list[str]:
    prefixes: set[str] = set()
    visited: set[URIRef] = set()

    def visit(uri: URIRef) -> None:
        if uri in visited or uri not in nodes:
            return
        visited.add(uri)
        node = nodes[uri]
        prefixes.add(namespace_prefix_for_uri(uri))
        prefixes.update(source_namespace_prefix(source) for source in node.incoming_rules)
        prefixes.update(source_namespace_prefix(source) for source in node.incoming_instances)
        for child in node.children & selected:
            visit(child)

    for root in choose_roots(nodes, selected):
        visit(root)

    return sorted(prefixes)


def merge_graphs(graphs: Iterable[Graph]) -> Graph:
    merged = Graph()
    for graph in graphs:
        for triple in graph:
            merged.add(triple)
    return merged


def property_label(graph: Graph, predicate: URIRef | BNode | None) -> str:
    if isinstance(predicate, URIRef):
        return label_for(graph, predicate)
    return local_name(predicate) if predicate is not None else "related to"


def render_restriction_rules(label_graph: Graph, graph: Graph, subject: URIRef, expression: URIRef | BNode) -> list[tuple[URIRef, str]]:
    rules: list[tuple[URIRef, str]] = []

    if isinstance(expression, URIRef) and (expression, RDF.type, OWL.Restriction) not in graph:
        return rules

    prop = graph.value(expression, OWL.onProperty)
    prop_text = property_label(label_graph, prop)
    operator = "some"
    target = graph.value(expression, OWL.someValuesFrom)
    if target is None:
        target = graph.value(expression, OWL.hasValue)
        if target is not None:
            operator = "hasValue"
    if target is None:
        target = graph.value(expression, OWL.onClass)
        if target is not None:
            operator = "onClass"
    if isinstance(target, URIRef):
        subject_text = label_for(label_graph, subject)
        target_text = label_for(label_graph, target)
        rule_text = f"{subject_text}: {prop_text} {operator} {target_text}"
        rules.append((target, rule_text))

    nested = graph.value(expression, OWL.intersectionOf) or graph.value(expression, OWL.unionOf)
    if isinstance(nested, BNode):
        for item in Collection(graph, nested):
            rules.extend(render_restriction_rules(label_graph, graph, subject, item))

    return rules


def node_dom_id(uri: URIRef) -> str:
    digest = hashlib.sha1(str(uri).encode("utf-8")).hexdigest()[:10]
    return f"node-{digest}"


def existing_path(candidates: Iterable[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def ensure_node(nodes: dict[URIRef, NodeInfo], graph: Graph, uri: URIRef, source: str) -> NodeInfo:
    node = nodes.get(uri)
    if node is None:
        node = NodeInfo(uri=uri, label=label_for(graph, uri))
        nodes[uri] = node
    node.sources.add(source)
    if node.label == local_name(uri):
        node.label = label_for(graph, uri)
    return node


def class_terms(graph: Graph) -> set[URIRef]:
    terms: set[URIRef] = {subject for subject in graph.subjects(RDF.type, OWL.Class) if isinstance(subject, URIRef)}
    terms.update(subject for subject in graph.subjects(RDF.type, OWL.Restriction) if isinstance(subject, URIRef))
    terms.update(subject for subject in graph.subjects(RDFS.subClassOf, None) if isinstance(subject, URIRef))
    terms.update(subject for subject in graph.subjects(OWL.equivalentClass, None) if isinstance(subject, URIRef))
    terms.update(subject for subject in graph.subjects(OWL.intersectionOf, None) if isinstance(subject, URIRef))
    terms.update(subject for subject in graph.subjects(OWL.unionOf, None) if isinstance(subject, URIRef))
    return terms


def collect_restriction_targets(graph: Graph, node: URIRef | BNode, seen: set[URIRef | BNode] | None = None) -> set[URIRef]:
    seen = seen or set()
    if node in seen:
        return set()
    seen.add(node)

    targets: set[URIRef] = set()
    for predicate, obj in graph.predicate_objects(node):
        if predicate in {OWL.someValuesFrom, OWL.hasValue, OWL.onClass} and isinstance(obj, URIRef):
            targets.add(obj)
        elif predicate in {OWL.intersectionOf, OWL.unionOf} and isinstance(obj, BNode):
            for item in Collection(graph, obj):
                if isinstance(item, URIRef):
                    targets.add(item)
                elif isinstance(item, BNode):
                    targets.update(collect_restriction_targets(graph, item, seen))
        elif isinstance(obj, BNode):
            targets.update(collect_restriction_targets(graph, obj, seen))
    return targets


def build_structure(graph: Graph, label_graph: Graph, source: str, nodes: dict[URIRef, NodeInfo]) -> None:
    for subject in class_terms(graph):
        ensure_node(nodes, graph, subject, source)

    for subject in {s for s in graph.subjects(RDF.type, OWL.Restriction) if isinstance(s, URIRef)}:
        ensure_node(nodes, graph, subject, source)
        for target, rule_text in render_restriction_rules(label_graph, graph, subject, subject):
            ensure_node(nodes, graph, target, source)
            nodes[subject].outgoing_rules[source].append(rule_text)
            nodes[target].incoming_rules[source].append(rule_text)

    for subject, parent in graph.subject_objects(RDFS.subClassOf):
        if not isinstance(subject, URIRef) or not isinstance(parent, URIRef):
            continue
        ensure_node(nodes, graph, subject, source)
        ensure_node(nodes, graph, parent, source)
        nodes[subject].parents.add(parent)
        nodes[parent].children.add(subject)

    for subject, expression in graph.subject_objects(OWL.equivalentClass):
        if not isinstance(subject, URIRef):
            continue
        ensure_node(nodes, graph, subject, source)
        if isinstance(expression, URIRef):
            ensure_node(nodes, graph, expression, source)
            nodes[subject].alignment_targets[source].add(expression)
        elif isinstance(expression, BNode):
            targets = collect_restriction_targets(graph, expression)
            nodes[subject].alignment_targets[source].update(targets)
            for target, rule_text in render_restriction_rules(label_graph, graph, subject, expression):
                ensure_node(nodes, graph, target, source)
                nodes[subject].outgoing_rules[source].append(rule_text)
                nodes[target].incoming_rules[source].append(rule_text)

    for subject in class_terms(graph):
        for expression in graph.objects(subject, OWL.intersectionOf):
            if not isinstance(expression, BNode):
                continue
            for item in Collection(graph, expression):
                if isinstance(item, URIRef):
                    ensure_node(nodes, graph, item, source)
                    nodes[subject].parents.add(item)
                    nodes[item].children.add(subject)
                elif isinstance(item, BNode):
                    targets = collect_restriction_targets(graph, item)
                    nodes[subject].alignment_targets[source].update(targets)
                    for target, rule_text in render_restriction_rules(label_graph, graph, subject, item):
                        ensure_node(nodes, graph, target, source)
                        nodes[subject].outgoing_rules[source].append(rule_text)
                        nodes[target].incoming_rules[source].append(rule_text)

        for expression in graph.objects(subject, OWL.unionOf):
            if not isinstance(expression, BNode):
                continue
            for item in Collection(graph, expression):
                if isinstance(item, URIRef):
                    ensure_node(nodes, graph, item, source)
                elif isinstance(item, BNode):
                    targets = collect_restriction_targets(graph, item)
                    nodes[subject].alignment_targets[source].update(targets)
                    for target, rule_text in render_restriction_rules(label_graph, graph, subject, item):
                        ensure_node(nodes, graph, target, source)
                        nodes[subject].outgoing_rules[source].append(rule_text)
                        nodes[target].incoming_rules[source].append(rule_text)


def add_inferred_instances(graph: Graph, label_graph: Graph, nodes: dict[URIRef, NodeInfo]) -> None:
    class_like_targets = {target for target in graph.subjects(RDF.type, OWL.Class) if isinstance(target, URIRef)}
    type_sets: dict[URIRef, set[URIRef]] = defaultdict(set)

    for subject, target in graph.subject_objects(RDF.type):
        if not isinstance(subject, URIRef) or not isinstance(target, URIRef):
            continue
        if target in {OWL.Class, OWL.Restriction, OWL.Ontology}:
            continue
        if subject in class_like_targets:
            continue
        type_sets[subject].add(target)

    for subject, targets in type_sets.items():
        minimal_targets: set[URIRef] = set()
        for candidate in targets:
            if not any(
                other != candidate and candidate in set(graph.transitive_objects(other, RDFS.subClassOf))
                for other in targets
            ):
                minimal_targets.add(candidate)

        source = source_namespace_for_uri(subject).lower()
        ensure_node(nodes, label_graph, subject, source)
        subject_label = label_for(label_graph, subject)

        for target in minimal_targets:
            ensure_node(nodes, label_graph, target, source)
            nodes[target].incoming_instances[source].add(subject_label)


def collect_alignment_targets(graph: Graph) -> dict[URIRef, set[URIRef]]:
    targets_by_subject: dict[URIRef, set[URIRef]] = {}
    for subject in {s for s in graph.subjects(RDF.type, OWL.Class) if isinstance(s, URIRef)}:
        targets: set[URIRef] = set()
        for expression in graph.objects(subject, OWL.equivalentClass):
            if isinstance(expression, URIRef):
                targets.add(expression)
            elif isinstance(expression, BNode):
                targets.update(collect_restriction_targets(graph, expression))
        for expression in graph.objects(subject, OWL.intersectionOf):
            if isinstance(expression, BNode):
                for item in Collection(graph, expression):
                    if isinstance(item, URIRef):
                        targets.add(item)
                    elif isinstance(item, BNode):
                        targets.update(collect_restriction_targets(graph, item))
        for expression in graph.objects(subject, OWL.unionOf):
            if isinstance(expression, BNode):
                for item in Collection(graph, expression):
                    if isinstance(item, URIRef):
                        targets.add(item)
                    elif isinstance(item, BNode):
                        targets.update(collect_restriction_targets(graph, item))
        if targets:
            targets_by_subject[subject] = targets
    return targets_by_subject


def choose_roots(nodes: dict[URIRef, NodeInfo], selected: set[URIRef]) -> list[URIRef]:
    roots: list[URIRef] = []
    for candidate in (MATERIAL_ENTITY_IRI, COSO_MATERIAL_SAMPLE_IRI):
        if candidate in selected:
            roots.append(candidate)
    if roots:
        return roots
    roots = [uri for uri in selected if not (nodes[uri].parents & selected)]
    return sorted(roots, key=lambda uri: nodes[uri].label.lower())


def render_tree(nodes: dict[URIRef, NodeInfo], selected: set[URIRef], shared_targets: set[URIRef]) -> str:
    def render_node(uri: URIRef, path: set[URIRef]) -> str:
        node = nodes[uri]
        next_path = set(path)
        next_path.add(uri)
        prefix = namespace_prefix_for_uri(uri)
        prefix_class = namespace_class_for_uri(uri)
        overlap_tag = " <span class='tag overlap'>shared</span>" if uri in shared_targets else ""
        incoming_summary = ""
        if node.incoming_rules:
            lines = []
            for source, rules in sorted(node.incoming_rules.items()):
                source_prefix = source_namespace_prefix(source)
                rule_markup = " ".join(
                    f"<span class='rule-pill'>{html.escape(rule)}</span>"
                    for rule in sorted(rules)
                )
                lines.append(f"<div class='mapping-line'><span class='ns-box ns-{source_prefix.lower()}'>{html.escape(source_prefix)}</span>{rule_markup}</div>")
            incoming_summary = f"<div class='alignment-lines'>{''.join(lines)}</div>"

        outgoing_summary = ""
        if node.outgoing_rules:
            lines = []
            for source, rules in sorted(node.outgoing_rules.items()):
                source_prefix = source_namespace_prefix(source)
                rule_markup = " ".join(
                    f"<span class='rule-pill'>{html.escape(rule)}</span>"
                    for rule in sorted(set(rules))
                )
                lines.append(f"<div class='mapping-line'><span class='ns-box ns-{source_prefix.lower()}'>{html.escape(source_prefix)}</span>{rule_markup}</div>")
            outgoing_summary = f"<div class='alignment-lines'>{''.join(lines)}</div>"

        instance_summary = ""
        if node.incoming_instances:
            lines = []
            for source, instances in sorted(node.incoming_instances.items()):
                source_prefix = source_namespace_prefix(source)
                instance_markup = " ".join(
                    f"<span class='instance-pill'>{html.escape(instance)}</span>"
                    for instance in sorted(instances)
                )
                lines.append(f"<div class='mapping-line'><span class='ns-box ns-{source_prefix.lower()}'>{html.escape(source_prefix)}</span>{instance_markup}</div>")
            instance_summary = f"<div class='alignment-lines'>{''.join(lines)}</div>"

        child_markup = []
        for child in sorted(node.children & selected, key=lambda item: nodes[item].label.lower()):
            if child not in next_path:
                child_markup.append(render_node(child, next_path))

        child_id = node_dom_id(uri) + "-children"
        toggle_button = (
            f"<span class='toggle-marker' aria-hidden='true'></span>"
            if child_markup
            else "<span class='toggle-marker hidden' aria-hidden='true'></span>"
        )
        if child_markup:
            return (
                "<li>"
                f"<details class='node ns-{prefix_class}' open>"
                f"<summary class='node-header'>{toggle_button}<span class='ns-box ns-{prefix_class}'>{html.escape(prefix)}</span>"
                f"<span class='label'>{html.escape(node.label)}</span>"
                f"<span class='uri'>{html.escape(str(uri))}</span>{overlap_tag}</summary>"
                f"{outgoing_summary}{incoming_summary}{instance_summary}"
                f"<div class='children'><ul>{''.join(child_markup)}</ul></div>"
                "</details>"
                "</li>"
            )

        return (
            "<li>"
            f"<div class='node ns-{prefix_class}'>"
            f"<div class='node-header'>{toggle_button}<span class='ns-box ns-{prefix_class}'>{html.escape(prefix)}</span>"
            f"<span class='label'>{html.escape(node.label)}</span>"
            f"<span class='uri'>{html.escape(str(uri))}</span>{overlap_tag}</div>"
            f"{outgoing_summary}{incoming_summary}{instance_summary}</div>"
            "</li>"
        )

    return "".join(render_node(root, set()) for root in choose_roots(nodes, selected))


def build_html(nodes: dict[URIRef, NodeInfo], selected: set[URIRef], shared_targets: set[URIRef], title: str) -> str:
    tree_markup = render_tree(nodes, selected, shared_targets)
    namespaces = namespace_prefixes_in_view(nodes, selected)

    return f"""<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
            --bg: #fafafa;
            --panel: #ffffff;
            --panel-soft: #f4f6f8;
            --text: #20242a;
            --muted: #5d6773;
            --accent: #2b5b84;
            --border: #d8dee6;
            --chip: #e9edf2;
    }}
    body {{
      margin: 0;
            font-family: "Segoe UI", Arial, sans-serif;
            background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
      color: var(--text);
    }}
    main {{
            max-width: 1180px;
      margin: 0 auto;
            padding: 20px 18px 28px;
    }}
    h1 {{
            margin: 0 0 6px;
            font-size: 1.45rem;
            letter-spacing: -0.02em;
    }}
    p {{
      color: var(--muted);
            line-height: 1.35;
            margin: 6px 0 0;
    }}
    .legend, .summary {{
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 10px 12px;
            margin: 12px 0;
    }}
    .tags {{
      display: flex;
      flex-wrap: wrap;
            gap: 6px;
            margin-top: 8px;
    }}
    .tag {{
      display: inline-block;
            padding: 2px 8px;
      border-radius: 999px;
            font-size: 0.72rem;
            line-height: 1.25;
            border: 1px solid var(--border);
      background: var(--chip);
            color: #334155;
    }}
        .ns-box {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 3.4rem;
            padding: 0.15rem 0.45rem;
            border-radius: 2px;
            border: 1px solid var(--border);
            font-weight: 700;
            letter-spacing: 0.04em;
        }}
        .instance-pill {{
            display: inline-flex;
            align-items: center;
            padding: 0.18rem 0.55rem;
            border-radius: 999px;
            border: 1px solid var(--border);
            background: #fff;
            color: #111827;
        }}
        .rule-pill {{
            display: inline-flex;
            align-items: center;
            padding: 0.18rem 0.55rem;
            border-radius: 2px;
            border: 1px solid #c7cfd8;
            background: #fff7dd;
            color: #5b4a14;
            font-style: italic;
        }}
        .ns-foodon {{ background: #e7f0fa; color: #284766; }}
        .ns-egad {{ background: #f7e7f0; color: #7a284e; }}
        .ns-wqp {{ background: #e3f4ee; color: #1e6651; }}
        .ns-coso {{ background: #f2ece4; color: #6a4e2f; }}
        .node.ns-foodon {{ border-color: #c8d9ea; }}
        .node.ns-egad {{ border-color: #e1bfd2; }}
        .node.ns-wqp {{ border-color: #bfded5; }}
        .node.ns-coso {{ border-color: #dfd1be; }}
        .overlap {{ background: #f8e3c0; }}
        .uri {{ color: var(--muted); font-size: 0.72rem; margin-left: 8px; word-break: break-all; }}
    .node {{
            padding: 6px 8px;
            border-radius: 10px;
            border: 1px solid var(--border);
            background: var(--panel-soft);
            margin: 4px 0;
    }}
        details.node {{ padding: 0; }}
        details.node > summary {{
            list-style: none;
            cursor: pointer;
            margin: 0;
        }}
        details.node > summary::-webkit-details-marker {{ display: none; }}
        .label {{ font-weight: 600; color: #111827; }}
        ul {{ list-style: none; margin: 0; padding-left: 18px; border-left: 1px solid #e2e8f0; }}
        li {{ margin: 4px 0; }}
        .tree {{ margin-top: 10px; }}
    .tree > ul {{ border-left: 0; padding-left: 0; }}
        .summary-list {{ padding-left: 16px; }}
    .summary-list li {{ margin: 4px 0; }}
        .node-header {{ display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }}
        .toggle-marker {{
            display: inline-flex;
            width: 1rem;
            justify-content: center;
            color: #64748b;
            font-size: 0.95rem;
            flex: 0 0 auto;
        }}
        details[open] > summary .toggle-marker::before {{ content: "▾"; }}
        details:not([open]) > summary .toggle-marker::before {{ content: "▸"; }}
        .toggle-marker.hidden {{ visibility: hidden; }}
        details.node > .children {{ margin-top: 2px; }}
        .alignment-lines {{ margin-top: 4px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }}
        .mapping-line {{ display: inline-flex; flex-wrap: wrap; gap: 4px; align-items: center; }}
        @media print {{
            body {{ background: #fff; }}
            main {{ max-width: none; padding: 0; }}
            .legend, .summary, .node {{ break-inside: avoid; }}
            .tag.overlap {{ background: #ead2a8; }}
        }}
  </style>
</head>
<body>
  <main>
    <h1>{html.escape(title)}</h1>
        <p>Hierarchy extracted from the ontology sources, with EGAD and WQP highlights shown inline where they map onto FOODON and COSO classes.</p>
    <section class='legend'>
            <strong>Namespaces</strong>
      <div class='tags'>
                {''.join(f"<span class='ns-box ns-{ns.lower()}'>{html.escape(ns)}</span>" for ns in namespaces)}
      </div>
    </section>
    <section class='tree'>
      <ul>{tree_markup}</ul>
    </section>
  </main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a hierarchy visualization from ContaminOSO, FOODON, and alignment TTL files.")
    parser.add_argument(
        "--foodon",
        type=Path,
        default=Path(__file__).resolve().parent / "reuse" / "foodon_lite_updated.ttl",
        help="Path to the FOODON lite TTL file.",
    )
    parser.add_argument(
        "--contaminoso",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "v1" / "contaminoso_materialSample_ext.ttl",
        help="Path to the ContaminOSO material sample extension TTL file.",
    )
    parser.add_argument(
        "--egad-alignment",
        type=Path,
        default=Path(__file__).resolve().parent / "example_data" / "egad-controlledVocab-alignment.ttl",
        help="Path to the EGAD controlled vocabulary alignment TTL file.",
    )
    parser.add_argument(
        "--wqp-alignment",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "pfas-kg" / "datasets" / "federal" / "us-wqp" / "ontology" / "wqp_alignment.ttl",
        help="Path to the WQP alignment TTL file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "hierarchy_visualization.html",
        help="Output HTML file.",
    )
    args = parser.parse_args()

    foodon_path = existing_path([args.foodon])
    contaminoso_path = existing_path([
        args.contaminoso,
        args.contaminoso.with_name("contaminoso_matrialSample_ext.ttl"),
    ])
    egad_path = existing_path([args.egad_alignment])
    wqp_path = existing_path([args.wqp_alignment])

    missing: list[str] = []
    if foodon_path is None:
        missing.append(str(args.foodon))
    if contaminoso_path is None:
        missing.append(str(args.contaminoso))
    if egad_path is None:
        missing.append(str(args.egad_alignment))
    if missing:
        raise FileNotFoundError(f"Required input file(s) not found: {', '.join(missing)}")

    sources: list[tuple[str, Graph]] = []
    for source, path in (
        ("foodon_lite_updated", foodon_path),
        ("contaminoso_materialSample_ext", contaminoso_path),
        ("egad_alignment", egad_path),
    ):
        graph = Graph()
        graph.parse(path)
        sources.append((source, graph))

    if wqp_path is not None:
        graph = Graph()
        graph.parse(wqp_path)
        sources.append(("wqp_alignment", graph))

    merged_graph = merge_graphs(graph for _, graph in sources)
    reasoned_graph = Graph()
    for triple in merged_graph:
        reasoned_graph.add(triple)
    DeductiveClosure(OWLRL_Semantics, axiomatic_triples=False, datatype_axioms=False).expand(reasoned_graph)

    nodes: dict[URIRef, NodeInfo] = {}
    for source, graph in sources:
        build_structure(graph, reasoned_graph, source, nodes)

    add_inferred_instances(reasoned_graph, reasoned_graph, nodes)

    alignment_targets: dict[str, dict[URIRef, set[URIRef]]] = {
        source: collect_alignment_targets(graph)
        for source, graph in sources
        if source in {"egad_alignment", "wqp_alignment"}
    }

    shared_targets: set[URIRef] = set()
    if {"egad_alignment", "wqp_alignment"}.issubset(alignment_targets):
        egad_targets = {target for targets in alignment_targets["egad_alignment"].values() for target in targets}
        wqp_targets = {target for targets in alignment_targets["wqp_alignment"].values() for target in targets}
        shared_targets = egad_targets & wqp_targets
    elif "wqp_alignment" not in alignment_targets:
        print("WQP alignment file not found; overlap highlighting will be omitted.")

    selected: set[URIRef] = set(nodes)
    if shared_targets:
        selected.update(shared_targets)

    html_output = build_html(nodes, selected, shared_targets, "ContaminOSO hierarchy visualization")
    args.output.write_text(html_output, encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())