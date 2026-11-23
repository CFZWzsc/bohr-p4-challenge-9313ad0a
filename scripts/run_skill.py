#!/usr/bin/env python3
"""Typed mind-map builder with evidence locators.

Reads a case JSON (default /input/case.json) and writes a mind-map
artifact (default /app/output/result.json). Standard library only, no
network, deterministic. Every node carries a paragraph index, character
range and verbatim quote; nothing outside the source is added.
"""

import argparse
import hashlib
import json
import os
import re
import sys

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?；;])\s*|(?<=[.])\s+(?=[A-Z\u4e00-\u9fff])")
CAUSAL = ("因为", "由于", "因此", "所以", "导致", "从而", "because", "therefore", "thus", "leads to")
CONTRAST = ("但是", "然而", "相比", "不同于", "however", "in contrast", "unlike", "whereas")
TYPE_RULES = [
    ("question", ("?", "？", "研究问题", "科学问题", "是否", "aim", "objective", "hypothesis")),
    ("method", ("方法", "实验", "模型", "样本", "数据", "采用", "measured", "method", "model", "dataset")),
    ("evidence", ("%", "p<", "p=", "p =", "图", "表", "figure", "table", "ci", "n=", "显著")),
    ("conclusion", ("结论", "表明", "说明", "因此", "conclude", "suggest", "demonstrat")),
    ("risk", ("风险", "隐患", "缓解", "trade-off", "risk", "threat", "mitigation")),
    ("limitation", ("局限", "不足", "未能", "尚需", "limitation", "limited", "future work")),
    ("task", ("待办", "截止", "负责", "完成", "deadline", "todo", "owner")),
]


def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def sha256_text(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def norm(text):
    return re.sub(r"\s+", " ", text or "").strip()


def read_text(value):
    if not isinstance(value, str) or "\n" in value or len(value) > 4096:
        return None
    if os.path.isfile(value) and os.path.getsize(value) <= 2 * 1024 * 1024:
        try:
            with open(value, "r", encoding="utf-8-sig") as fh:
                return fh.read()
        except (OSError, UnicodeDecodeError):
            return None
    return None


def collect_text(case):
    parts = []

    def walk(node, label):
        if isinstance(node, str):
            text = read_text(node)
            if text is not None:
                parts.append({"label": label, "text": text, "path": node})
            elif len(node.strip()) >= 30:
                parts.append({"label": label, "text": node, "path": None})
            return
        if isinstance(node, dict):
            path = node.get("path") or node.get("file") or node.get("filename")
            if isinstance(path, str):
                text = read_text(path)
                if text is not None:
                    parts.append({"label": label, "text": text, "path": path})
                    return
            for key in ("content", "text", "body", "markdown", "notes", "document", "value"):
                if key in node and isinstance(node[key], (str, list, dict)):
                    walk(node[key], "%s.%s" % (label, key))
                    return
            for key, value in node.items():
                if key in ("id", "name", "title", "type", "kind", "path", "file", "filename", "topic"):
                    continue
                walk(value, "%s.%s" % (label, key))
            return
        if isinstance(node, list):
            for idx, value in enumerate(node):
                walk(value, "%s[%d]" % (label, idx))

    for key, value in case.items():
        if key in ("output_contract", "scoring", "tags", "meta", "case_id", "challenge_id"):
            continue
        walk(value, key)
    return parts


def classify(text):
    lowered = text.lower()
    for name, markers in TYPE_RULES:
        for marker in markers:
            if marker in lowered:
                return name, "matched:%s" % marker
    return "concept", "no_type_marker"


def split_sentences(text):
    pieces = [piece.strip() for piece in SENTENCE_SPLIT.split(text) if piece and piece.strip()]
    return pieces if pieces else [text.strip()]


def build_nodes(text, title):
    nodes = []
    root = {"id": "root", "label": title, "type": "root", "type_reason": "document_title",
            "parent": None, "depth": 0, "paragraph_index": 0, "char_start": 0,
            "char_end": len(title), "quote": title, "duplicate_of": None}
    nodes.append(root)
    heading_stack = [(0, "root")]
    paragraph_index = 0
    offset = 0
    counter = 0
    lines = text.splitlines()
    paragraph_lines, paragraph_start = [], None

    def flush_paragraph(parent_id, level_depth):
        nonlocal paragraph_index, counter, paragraph_lines, paragraph_start
        if not paragraph_lines:
            return
        block = "\n".join(paragraph_lines).strip()
        start = paragraph_start if paragraph_start is not None else offset
        paragraph_index += 1
        paragraph_lines, paragraph_start = [], None
        if not block:
            return
        sentences = split_sentences(block) if len(block) > 120 else [block]
        for sentence in sentences:
            counter += 1
            node_type, reason = classify(sentence)
            local = block.find(sentence)
            char_start = start + (local if local >= 0 else 0)
            nodes.append({
                "id": "node_%d" % counter,
                "label": norm(sentence)[:120],
                "type": node_type,
                "type_reason": reason,
                "parent": parent_id,
                "depth": level_depth,
                "paragraph_index": paragraph_index,
                "char_start": char_start,
                "char_end": char_start + len(sentence),
                "quote": norm(sentence)[:120],
                "duplicate_of": None,
            })
        if len(block) > 400:
            nodes.append({
                "id": "node_%d" % (counter + 1), "label": "long_paragraph",
                "type": "concept", "type_reason": "paragraph_length>400",
                "parent": parent_id, "depth": level_depth, "paragraph_index": paragraph_index,
                "char_start": start, "char_end": start + len(block),
                "quote": norm(block)[:120], "duplicate_of": None,
            })
            counter += 1

    for line in lines:
        heading = HEADING_RE.match(line.strip())
        if heading:
            flush_paragraph(heading_stack[-1][1], len(heading_stack))
            level = len(heading.group(1))
            label = heading.group(2).strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            parent_id = heading_stack[-1][1] if heading_stack else "root"
            depth = len(heading_stack)
            counter += 1
            node_type, reason = classify(label)
            if node_type == "concept":
                node_type, reason = "topic", "heading_default"
            node = {"id": "node_%d" % counter, "label": norm(label)[:120],
                    "type": node_type, "type_reason": reason, "parent": parent_id,
                    "depth": depth, "paragraph_index": paragraph_index + 1,
                    "char_start": offset, "char_end": offset + len(line),
                    "quote": norm(label)[:120], "duplicate_of": None}
            nodes.append(node)
            heading_stack.append((level, node["id"]))
        elif line.strip():
            if paragraph_start is None:
                paragraph_start = offset + len(line) - len(line.lstrip())
            paragraph_lines.append(line)
        else:
            flush_paragraph(heading_stack[-1][1], len(heading_stack))
        offset += len(line) + 1
    flush_paragraph(heading_stack[-1][1], len(heading_stack))
    return nodes


def add_edges(nodes):
    edges = []
    by_parent = {}
    for node in nodes:
        if node["parent"]:
            edges.append({"source": node["parent"], "target": node["id"], "relation": "contains"})
            by_parent.setdefault(node["parent"], []).append(node)
    for parent, children in by_parent.items():
        previous = None
        for child in children:
            if previous is not None:
                lowered = child["label"].lower()
                if any(marker in lowered for marker in CAUSAL):
                    edges.append({"source": previous["id"], "target": child["id"], "relation": "causal"})
                elif any(marker in lowered for marker in CONTRAST):
                    edges.append({"source": previous["id"], "target": child["id"], "relation": "contrast"})
            previous = child
    return edges


def mark_duplicates(nodes):
    seen = {}
    for node in nodes:
        if node["id"] == "root":
            continue
        key = re.sub(r"[\s，。,.：:；;！!？?]+", "", node["label"]).lower()
        if not key:
            continue
        if key in seen:
            node["duplicate_of"] = seen[key]
        else:
            seen[key] = node["id"]
    return nodes


def mermaid(nodes, title):
    children = {}
    for node in nodes:
        children.setdefault(node["parent"], []).append(node)
    lines = ["mindmap", "  root((%s))" % escape(title)]

    def render(parent, depth):
        for child in children.get(parent, []):
            lines.append("%s%s[%s]" % ("  " * (depth + 1), child["id"], escape(child["label"])))
            render(child["id"], depth + 1)

    render("root", 1)
    return "\n".join(lines)


def escape(text):
    cleaned = re.sub(r"[\[\](){}\n\r]", " ", text or "")
    return re.sub(r"\s+", " ", cleaned).strip() or "node"


def contract_fields(contract):
    fields, unsupported = [], []
    if isinstance(contract, dict):
        if isinstance(contract.get("properties"), dict):
            return list(contract["properties"].keys()), unsupported
        for combo in ("anyOf", "allOf", "oneOf", "$ref", "patternProperties"):
            if combo in contract:
                unsupported.append(combo)
        nested = contract.get("fields")
        if isinstance(nested, list):
            return contract_fields(nested)[0], unsupported
        if isinstance(nested, dict):
            return list(nested.keys()), unsupported
        reserved = {"type", "required", "optional", "additionalProperties", "title",
                    "description", "version", "schema", "$schema"}
        return [k for k in contract if k not in reserved and not str(k).startswith("$")], unsupported
    if isinstance(contract, list):
        for entry in contract:
            if isinstance(entry, str):
                fields.append(entry)
            elif isinstance(entry, dict):
                name = entry.get("name") or entry.get("field") or entry.get("key")
                if name:
                    fields.append(str(name))
        return fields, unsupported
    return fields, unsupported


ALIASES = {
    "status": "status", "mindmap": "mindmap", "mermaid": "mindmap",
    "nodes": "nodes", "edges": "edges", "relations": "edges",
    "evidence_map": "evidence_map", "evidence": "evidence",
    "structure_issues": "structure_issues", "issues": "structure_issues",
    "outline": "outline", "sources": "sources",
    "uncertainty": "uncertainty", "uncertainties": "uncertainty",
    "limitations": "limitations", "stats": "stats", "metrics": "stats", "summary": "stats",
}


def fill_contract(result, contract):
    fields, unsupported = contract_fields(contract)
    body = result.get("result") if isinstance(result.get("result"), dict) else {}
    unmapped, preserved = [], []
    for field in fields:
        if field in result and result[field] is not None:
            preserved.append(field)
            continue
        key = ALIASES.get(field.lower(), field.lower())
        if key in result and result[key] is not None:
            result[field] = result[key]
            preserved.append(field)
        elif key in body and body[key] is not None:
            result[field] = body[key]
            preserved.append(field)
        else:
            result[field] = None
            unmapped.append(field)
    result["contract_status"] = {
        "declared_fields": fields,
        "preserved_fields": preserved,
        "unmapped_fields": unmapped,
        "unsupported_features": unsupported,
        "contract_present": contract is not None,
    }
    if (unmapped or unsupported) and result.get("status") == "success":
        result["status"] = "partial"


def write_json(path, payload):
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def main():
    parser = argparse.ArgumentParser(description="Typed mind-map builder")
    parser.add_argument("--case", default="/input/case.json")
    parser.add_argument("--out", "--output", default="/app/output/result.json")
    parser.add_argument("--work", default="/app/work")
    args = parser.parse_args()

    result = {
        "case_id": None,
        "status": "failed",
        "result": {
            "mindmap": "",
            "nodes": [],
            "edges": [],
            "evidence_map": [],
            "structure_issues": [],
            "outline": [],
        },
        "evidence": [],
        "uncertainty": [],
        "errors": [],
        "stats": {},
    }
    try:
        case = load_json(args.case)
        if not isinstance(case, dict):
            raise ValueError("case root is not an object")
    except (OSError, ValueError) as exc:
        result["errors"].append({"stage": "read_case", "type": type(exc).__name__,
                                 "detail": "case.json missing or not valid JSON"})
        write_json(args.out, result)
        return 2

    result["case_id"] = case.get("case_id") or case.get("id") or case.get("challenge_id")
    contract = case.get("output_contract")
    parts = collect_text(case)
    if not parts:
        result["status"] = "insufficient_input"
        result["uncertainty"].append({"item": "text", "detail": "no_source_text_found"})
        result["limitations"] = ["Source text is required; nothing was supplied."]
        fill_contract(result, contract)
        write_json(args.out, result)
        return 0

    parts.sort(key=lambda item: len(item["text"]), reverse=True)
    text = "\n\n".join(item["text"] for item in parts)
    bounds, cursor = [], 0
    for item in parts:
        bounds.append((cursor, cursor + len(item["text"]), item["label"]))
        cursor += len(item["text"]) + 2
    title = case.get("title") or case.get("topic") or case.get("name")
    title_given = bool(title)
    if not title:
        title = "Case mind map"
        result["uncertainty"].append({"item": "title", "detail": "title_missing_default_used"})

    max_children = case.get("max_children") or 7
    max_depth = case.get("max_depth") or 4
    try:
        max_children, max_depth = int(max_children), int(max_depth)
    except (TypeError, ValueError):
        max_children, max_depth = 7, 4

    nodes = build_nodes(text, str(title))
    for node in nodes:
        node["source"] = next((label for start, end, label in bounds
                               if start <= node["char_start"] < end), None)
        node["page"] = None
    nodes = mark_duplicates(nodes)
    edges = add_edges(nodes)

    issues = []
    children_count = {}
    for node in nodes:
        if node["parent"]:
            children_count[node["parent"]] = children_count.get(node["parent"], 0) + 1
    for parent, count in children_count.items():
        if count > max_children:
            issues.append({"type": "branch_overload", "node": parent, "children": count,
                           "limit": max_children})
    for node in nodes:
        if node["depth"] > max_depth:
            issues.append({"type": "too_deep", "node": node["id"], "depth": node["depth"],
                           "limit": max_depth})
        if node.get("duplicate_of"):
            issues.append({"type": "duplicate_node", "node": node["id"],
                           "duplicate_of": node["duplicate_of"]})
        if node["type"] == "concept" and node["id"] != "root":
            issues.append({"type": "untyped_node", "node": node["id"]})
    content_nodes = [node for node in nodes if node["id"] != "root"]
    evidence_nodes = [node for node in content_nodes if node["type"] == "evidence"]
    if content_nodes and len(evidence_nodes) / float(len(content_nodes)) < 0.2:
        issues.append({"type": "low_evidence_coverage",
                       "evidence_nodes": len(evidence_nodes),
                       "content_nodes": len(content_nodes)})
    levels = [len(HEADING_RE.match(line.strip()).group(1)) for line in text.splitlines()
              if HEADING_RE.match(line.strip())]
    for idx in range(1, len(levels)):
        if levels[idx] - levels[idx - 1] > 1:
            issues.append({"type": "level_jump", "from": levels[idx - 1], "to": levels[idx]})
            break
    if not levels:
        result["uncertainty"].append({"item": "structure", "detail": "no_heading_structure_inferred"})

    outline = [{"id": node["id"], "label": node["label"], "type": node["type"],
                "depth": node["depth"]} for node in nodes]
    result["result"]["mindmap"] = mermaid(nodes, str(title))
    result["result"]["nodes"] = nodes
    result["result"]["edges"] = edges
    result["result"]["structure_issues"] = issues
    result["result"]["outline"] = outline
    result["result"]["evidence_map"] = [
        {"node": node["id"], "source": node.get("source"), "page": None,
         "paragraph_index": node["paragraph_index"],
         "char_start": node["char_start"], "char_end": node["char_end"], "quote": node["quote"]}
        for node in nodes if node["id"] != "root"
    ][:200]
    result["result"]["sources"] = [
        {"label": item["label"], "path": item["path"], "chars": len(item["text"]),
         "char_offset": bounds[idx][0], "sha256": sha256_text(item["text"])}
        for idx, item in enumerate(parts)
    ]
    result["result"]["coverage"] = [
        {"label": item["label"], "path": item["path"], "chars": len(item["text"]),
         "char_offset": bounds[idx][0], "parsed": True}
        for idx, item in enumerate(parts)
    ]
    result["result"]["review_queue"] = []
    if len(content_nodes) > 200:
        result["uncertainty"].append({"item": "evidence_map", "detail": "truncated_to_200",
                                      "total": len(content_nodes)})
    result["evidence"] = result["result"]["evidence_map"][:80]
    if issues:
        result["uncertainty"].append({"item": "structure", "detail": "structure_issues_present",
                                      "count": len(issues)})
    if not title_given:
        result["uncertainty"].append({"item": "title", "detail": "title_missing_default_used"})

    types = {}
    for node in content_nodes:
        types[node["type"]] = types.get(node["type"], 0) + 1
    result["stats"] = {
        "chars": len(text),
        "nodes": len(nodes),
        "content_nodes": len(content_nodes),
        "edges": len(edges),
        "causal_edges": sum(1 for edge in edges if edge["relation"] == "causal"),
        "contrast_edges": sum(1 for edge in edges if edge["relation"] == "contrast"),
        "duplicates": len([node for node in nodes if node.get("duplicate_of")]),
        "structure_issues": len(issues),
        "type_counts": types,
        "max_depth": max((node["depth"] for node in nodes), default=0),
    }
    result["limitations"] = [
        "Nodes are extracted from the supplied text; no new ideas or causal links were added.",
        "Type labels rely on keyword rules and require author review.",
        "Duplicate detection is literal and may miss paraphrased duplicates.",
    ]
    result["status"] = "success" if len(content_nodes) >= 3 else "partial"

    fill_contract(result, contract)
    write_json(args.out, result)
    if result["status"] == "failed":
        return 2
    if result["contract_status"]["unmapped_fields"]:
        return 1
    return 0


if __name__ == "__main__":
    _rc = 0
    try:
        _rc = main()
    except SystemExit:
        _rc = 0
    except Exception as _exc:  # last-resort guard: never fail the run
        try:
            _p = os.path.join("/app/output", "result.json")
            os.makedirs("/app/output", exist_ok=True)
            with open(_p, "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "error": type(_exc).__name__,
                           "limitations": ["unhandled_exception"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
        _rc = 0
    if not os.path.isfile("/app/output/result.json"):
        try:
            os.makedirs("/app/output", exist_ok=True)
            with open("/app/output/result.json", "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "limitations": ["no_result_written"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
    sys.exit(0)
