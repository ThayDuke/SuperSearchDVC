"""
HTML Builder for SuperSearch
Converts Markdown and OCR output to clean, styled HTML documents.
Supports:
- MathJax LaTeX formulas
- Tables, headers, lists, blockquotes, code blocks
- Responsive, dark/light glassmorphic modern layout
Uses Python standard library only (zero external dependencies).
"""

import re
import html

CSS_STYLES = """
:root {
    --bg-primary: #0b1329;
    --bg-surface: rgba(18, 26, 51, 0.85);
    --border-color: rgba(255, 255, 255, 0.12);
    --text-main: #e2e8f0;
    --text-muted: #94a3b8;
    --accent: #3b82f6;
    --accent-glow: rgba(59, 130, 246, 0.25);
    --code-bg: rgba(15, 23, 42, 0.7);
    --table-header: rgba(59, 130, 246, 0.18);
    --table-stripe: rgba(255, 255, 255, 0.02);
}

@media (prefers-color-scheme: light) {
    :root {
        --bg-primary: #f8fafc;
        --bg-surface: #ffffff;
        --border-color: rgba(0, 0, 0, 0.1);
        --text-main: #1e293b;
        --text-muted: #64748b;
        --accent: #2563eb;
        --accent-glow: rgba(37, 99, 235, 0.15);
        --code-bg: #f1f5f9;
        --table-header: rgba(37, 99, 235, 0.08);
        --table-stripe: rgba(0, 0, 0, 0.02);
    }
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    background-color: var(--bg-primary);
    color: var(--text-main);
    line-height: 1.7;
    font-size: 15px;
    padding: 2rem 1rem;
}

.container {
    max-width: 900px;
    margin: 0 auto;
    background: var(--bg-surface);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    box-shadow: 0 8px 32px var(--accent-glow);
    padding: 2.5rem 3rem;
}

.doc-header {
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 1.5rem;
    margin-bottom: 2rem;
}

.doc-title {
    font-size: 1.85rem;
    font-weight: 700;
    color: var(--text-main);
    margin-bottom: 0.5rem;
}

.doc-meta {
    font-size: 0.85rem;
    color: var(--text-muted);
}

h1, h2, h3, h4, h5, h6 {
    color: var(--text-main);
    margin-top: 1.5rem;
    margin-bottom: 0.75rem;
    font-weight: 600;
    line-height: 1.3;
}

h1 { font-size: 1.75rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.4rem; }
h2 { font-size: 1.45rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.3rem; }
h3 { font-size: 1.25rem; }
h4 { font-size: 1.1rem; }

p {
    margin-bottom: 1rem;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 1.25rem 0;
    font-size: 0.95rem;
    overflow-x: auto;
    display: table;
}

th, td {
    padding: 10px 14px;
    border: 1px solid var(--border-color);
    text-align: left;
}

th {
    background-color: var(--table-header);
    font-weight: 600;
    color: var(--text-main);
}

tr:nth-child(even) {
    background-color: var(--table-stripe);
}

pre {
    background: var(--code-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1rem;
    overflow-x: auto;
    margin: 1.25rem 0;
    font-family: ui-monospace, SFMono-Regular, Consolas, "Courier New", monospace;
    font-size: 0.9rem;
    line-height: 1.5;
}

code {
    background: var(--code-bg);
    border-radius: 4px;
    padding: 0.15rem 0.4rem;
    font-family: ui-monospace, SFMono-Regular, Consolas, "Courier New", monospace;
    font-size: 0.88em;
}

pre code {
    background: transparent;
    padding: 0;
}

blockquote {
    border-left: 4px solid var(--accent);
    padding-left: 1rem;
    margin: 1.25rem 0;
    color: var(--text-muted);
    font-style: italic;
}

ul, ol {
    margin-left: 1.75rem;
    margin-bottom: 1rem;
}

li {
    margin-bottom: 0.35rem;
}

a {
    color: var(--accent);
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

hr {
    border: 0;
    border-top: 1px solid var(--border-color);
    margin: 2rem 0;
}
"""

MATHJAX_SCRIPT = """
<script>
    window.MathJax = {
        tex: {
            inlineMath: [['\\\\(', '\\\\)'], ['$', '$']],
            displayMath: [['\\\\[', '\\\\]'], ['$$', '$$']],
            processEscapes: true
        },
        options: {
            skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code']
        }
    };
</script>
"""

def _format_inline(text):
    if not text:
        return ""

    math_placeholders = []
    def _save_math(match):
        idx = len(math_placeholders)
        math_placeholders.append(match.group(0))
        return f"___MATH_PLACEHOLDER_{idx}___"

    # Save block math \\[ ... \\] and $$ ... $$
    text = re.sub(r"\\\[[\s\S]*?\\\]", _save_math, text)
    text = re.sub(r"\$\$[\s\S]*?\$\$", _save_math, text)
    # Save inline math \\( ... \\) and $ ... $
    text = re.sub(r"\\\([\s\S]*?\\\)", _save_math, text)
    text = re.sub(r"(?<!\\)\$(?!\$)([^\$\n]+?)(?<!\\)\$", _save_math, text)

    # Save code spans `code`
    code_placeholders = []
    def _save_code(match):
        idx = len(code_placeholders)
        code_placeholders.append(html.escape(match.group(1)))
        return f"___CODE_PLACEHOLDER_{idx}___"

    text = re.sub(r"`([^`]+)`", _save_code, text)

    # HTML Escape regular text
    text = html.escape(text)

    # Restore code spans
    for idx, c in enumerate(code_placeholders):
        text = text.replace(f"___CODE_PLACEHOLDER_{idx}___", f"<code>{c}</code>")

    # Restore math placeholders
    for idx, m in enumerate(math_placeholders):
        text = text.replace(f"___MATH_PLACEHOLDER_{idx}___", m)

    # Format bold, italic, links, del
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\g<1></strong>", text)
    text = re.sub(r"__([^_]+)__", r"<strong>\g<1></strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\g<1></em>", text)
    text = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"<em>\g<1></em>", text)
    text = re.sub(r"~~([^~]+)~~", r"<del>\g<1></del>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\g<2>" target="_blank" rel="noopener">\g<1></a>', text)

    return text

def markdown_to_html_body(markdown_text):
    if not markdown_text:
        return ""

    lines = markdown_text.splitlines()
    html_out = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Fenced code blocks
        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            code_lines = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < n:
                i += 1
            code_content = html.escape("\n".join(code_lines))
            lang_class = f' class="language-{html.escape(lang)}"' if lang else ""
            html_out.append(f'<pre><code{lang_class}>{code_content}</code></pre>')
            continue

        # Headers (# H1 to ###### H6)
        header_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if header_match:
            level = len(header_match.group(1))
            header_text = _format_inline(header_match.group(2).strip())
            html_out.append(f"<h{level}>{header_text}</h{level}>")
            i += 1
            continue

        # Horizontal Rule
        if re.match(r"^(\-{3,}|\*{3,}|_{3,})$", stripped):
            html_out.append("<hr>")
            i += 1
            continue

        # Table detection
        if "|" in line and i + 1 < n and re.match(r"^\s*\|?[\s\-:|]+\|?\s*$", lines[i + 1]):
            table_lines = []
            while i < n and "|" in lines[i]:
                table_lines.append(lines[i].strip())
                i += 1

            if len(table_lines) >= 2:
                headers = [c.strip() for c in table_lines[0].strip("|").split("|")]
                rows = []
                for row_line in table_lines[2:]:
                    cols = [c.strip() for c in row_line.strip("|").split("|")]
                    rows.append(cols)

                tbl = ['<div style="overflow-x: auto;"><table><thead><tr>']
                for h in headers:
                    tbl.append(f"<th>{_format_inline(h)}</th>")
                tbl.append("</tr></thead><tbody>")
                for r in rows:
                    tbl.append("<tr>")
                    for c in r:
                        tbl.append(f"<td>{_format_inline(c)}</td>")
                    tbl.append("</tr>")
                tbl.append("</tbody></table></div>")
                html_out.append("".join(tbl))
                continue
            else:
                for tl in table_lines:
                    html_out.append(f"<p>{_format_inline(tl)}</p>")
                continue

        # Blockquote (> quote)
        if stripped.startswith(">"):
            quote_lines = []
            while i < n and (lines[i].strip().startswith(">") or (lines[i].strip() and quote_lines)):
                if lines[i].strip().startswith(">"):
                    quote_lines.append(re.sub(r"^\s*>\s?", "", lines[i]))
                else:
                    quote_lines.append(lines[i])
                i += 1
            quote_body = "<br>".join([_format_inline(ql.strip()) for ql in quote_lines if ql.strip()])
            html_out.append(f"<blockquote>{quote_body}</blockquote>")
            continue

        # Lists (unordered - * + or ordered 1. 2.)
        ul_match = re.match(r"^[\*\-\+]\s+(.*)$", stripped)
        ol_match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if ul_match or ol_match:
            is_ol = bool(ol_match)
            tag = "ol" if is_ol else "ul"
            html_out.append(f"<{tag}>")
            while i < n:
                cur_line = lines[i].strip()
                if not cur_line:
                    break
                m = re.match(r"^\d+\.\s+(.*)$" if is_ol else r"^[\*\-\+]\s+(.*)$", cur_line)
                if m:
                    item_text = _format_inline(m.group(1).strip())
                    html_out.append(f"<li>{item_text}</li>")
                    i += 1
                else:
                    if re.match(r"^[\*\-\+\d]", cur_line):
                        break
                    if html_out and html_out[-1].endswith("</li>"):
                        html_out[-1] = html_out[-1][:-5] + " " + _format_inline(cur_line) + "</li>"
                    i += 1
            html_out.append(f"</{tag}>")
            continue

        # Regular Paragraph - always consumes at least 1 line to guarantee termination
        p_lines = [stripped]
        i += 1
        while i < n:
            next_line = lines[i]
            next_stripped = next_line.strip()
            if not next_stripped:
                break
            if next_stripped.startswith("```"):
                break
            if re.match(r"^#{1,6}\s+", next_stripped):
                break
            if re.match(r"^(\-{3,}|\*{3,}|_{3,})$", next_stripped):
                break
            if next_stripped.startswith(">"):
                break
            if re.match(r"^[\*\-\+]\s+", next_stripped) or re.match(r"^\d+\.\s+", next_stripped):
                break
            if "|" in next_line and i + 1 < n and re.match(r"^\s*\|?[\s\-:|]+\|?\s*$", lines[i + 1]):
                break
            p_lines.append(next_stripped)
            i += 1
        p_content = "<br>".join([_format_inline(pl) for pl in p_lines])
        html_out.append(f"<p>{p_content}</p>")

    return "\n".join(html_out)

def build_html_document(markdown_text, title="", original_path=""):
    safe_title = html.escape(title or "Tài liệu")
    safe_path = html.escape(original_path or "")
    body_content = markdown_to_html_body(markdown_text)

    header_meta = f'<div class="doc-meta">Đường dẫn: {safe_path}</div>' if safe_path else ""

    doc = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{safe_title}</title>
    {MATHJAX_SCRIPT}
    <style>
        {CSS_STYLES}
    </style>
</head>
<body>
    <div class="container">
        <header class="doc-header">
            <h1 class="doc-title">{safe_title}</h1>
            {header_meta}
        </header>
        <main class="doc-body">
            {body_content}
        </main>
    </div>
</body>
</html>"""
    return doc
