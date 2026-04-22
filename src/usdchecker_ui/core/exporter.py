"""Exporter — render diagnostics as JSON / Markdown / HTML."""

from __future__ import annotations

import html
import json
from collections import defaultdict
from collections.abc import Iterable

from usdchecker_ui.core.enricher import EnrichedDiagnostic


def to_json(diags: Iterable[EnrichedDiagnostic], meta: dict) -> str:
    payload = {
        "meta": meta,
        "diagnostics": [d.to_dict() for d in diags],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _group_by_rule(diags: Iterable[EnrichedDiagnostic]) -> dict[str, list[EnrichedDiagnostic]]:
    grouped: dict[str, list[EnrichedDiagnostic]] = defaultdict(list)
    for d in diags:
        grouped[d.diagnostic.rule].append(d)
    return grouped


def to_markdown(diags: Iterable[EnrichedDiagnostic], meta: dict) -> str:
    diags_list = list(diags)
    grouped = _group_by_rule(diags_list)
    file_path = meta.get("file_path", "?")
    lines: list[str] = []
    lines.append(f"# USDChecker UI — report: {file_path}")
    lines.append("")
    lines.append("| Key | Value |")
    lines.append("| --- | --- |")
    for key in ("file_path", "date", "duration_seconds", "total"):
        if key in meta:
            lines.append(f"| {key} | {meta[key]} |")
    lines.append("")

    for rule, entries in sorted(grouped.items()):
        lines.append(f"## {rule} ({len(entries)})")
        lines.append("")
        for e in entries:
            prim = e.diagnostic.prim_path or "—"
            lines.append(f"- `{prim}` — {e.diagnostic.message}")
        lines.append("")

    return "\n".join(lines)


_HTML_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       margin: 2em; color: #222; }
h1 { border-bottom: 2px solid #333; padding-bottom: .3em; }
h2 { background: #f4f4f4; padding: .4em .6em; border-left: 4px solid #c33; }
.warning { border-left-color: #d99;}
table.meta { border-collapse: collapse; margin-bottom: 1.5em; }
table.meta td { border: 1px solid #ccc; padding: .3em .6em; }
ul { margin: 0 0 1.5em 0; }
code { background: #eee; padding: 1px 5px; border-radius: 3px; }
"""


def to_html(diags: Iterable[EnrichedDiagnostic], meta: dict) -> str:
    diags_list = list(diags)
    grouped = _group_by_rule(diags_list)
    file_path = html.escape(str(meta.get("file_path", "?")))

    parts: list[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append("<html lang='en'><head><meta charset='utf-8'>")
    parts.append(f"<title>USDChecker UI — {file_path}</title>")
    parts.append(f"<style>{_HTML_CSS}</style>")
    parts.append("</head><body>")
    parts.append(f"<h1>USDChecker UI — report: {file_path}</h1>")

    parts.append("<table class='meta'>")
    for key in ("file_path", "date", "duration_seconds", "total"):
        if key in meta:
            parts.append(
                f"<tr><td>{key}</td><td>{html.escape(str(meta[key]))}</td></tr>"
            )
    parts.append("</table>")

    for rule, entries in sorted(grouped.items()):
        parts.append(f"<h2>{html.escape(rule)} ({len(entries)})</h2>")
        parts.append("<ul>")
        for e in entries:
            prim = html.escape(e.diagnostic.prim_path or "—")
            msg = html.escape(e.diagnostic.message)
            parts.append(f"<li><code>{prim}</code> — {msg}</li>")
        parts.append("</ul>")

    parts.append("</body></html>")
    return "\n".join(parts)
