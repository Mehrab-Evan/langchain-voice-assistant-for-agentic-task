import re
import html


def split_message(text: str, max_length: int = 4096) -> list[str]:
    if len(text) <= max_length:
        return [text]
    chunks = []
    while len(text) > max_length:
        split_at = text.rfind("\n", 0, max_length)
        if split_at == -1:
            split_at = max_length
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    if text:
        chunks.append(text)
    return chunks


def clean_markdown(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text.strip()


def escape_html_outside_tags(text: str) -> str:
    return re.sub(
        r"(<[^>]+>)|([^<]+)",
        lambda m: m.group(1) if m.group(1) else html.escape(m.group(2)),
        text
    )


def render_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    rows = [[clean_markdown(cell) for cell in row] for row in rows]
    col_widths = [
        max(len(row[i]) for row in rows if i < len(row))
        for i in range(len(rows[0]))
    ]
    lines = []
    for i, row in enumerate(rows):
        padded = "  ".join(cell.ljust(col_widths[j]) for j, cell in enumerate(row))
        lines.append(padded)
        if i == 0:
            lines.append("─" * (sum(col_widths) + 2 * (len(col_widths) - 1)))
    return "<pre>" + "\n".join(lines) + "</pre>"


def try_parse_kv_table(block_lines: list[str]) -> str | None:
    """
    Detects and reformats a plain-text two-column table like:

        Item             What the sheet shows
        ────────────────────────────────────
        Column name      LAB MID TERM ...
        Typical score    The overwhelming ...

    Into clean Telegram-friendly key-value cards.
    """
    if len(block_lines) < 3:
        return None

    header_line = block_lines[0]

    # Find the ─── divider
    divider_idx = next(
        (i for i, l in enumerate(block_lines[1:], 1) if re.match(r"^\s*[─━—\-]{10,}\s*$", l)),
        None
    )
    if divider_idx is None:
        return None

    # Find column split position from header spacing
    m = re.match(r"^(.+?)\s{2,}(\S.*)$", header_line)
    if not m:
        return None

    col2_start = header_line.index(m.group(2), len(m.group(1).rstrip()))
    h1 = m.group(1).strip()
    h2 = m.group(2).strip()

    rows = []
    for line in block_lines[divider_idx + 1:]:
        if not line.strip():
            continue
        key = line[:col2_start].strip() if len(line) > col2_start else line.strip()
        val = line[col2_start:].strip() if len(line) > col2_start else ""
        if key:
            rows.append((key, val))

    if not rows:
        return None

    # Render as card-style key → value blocks
    parts = [f"<b>📋 {h1}</b>  │  <i>{h2}</i>", ""]
    for key, value in rows:
        parts.append(f"<b>▸ {key}</b>")
        if value:
            parts.append(value)
        parts.append("")  # blank line between cards

    return "\n".join(parts)


def apply_inline_formatting(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = re.sub(r"^###\s+(.+)", r"<b>🔹 \1</b>", text)
    text = re.sub(r"^##\s+(.+)",  r"<b>📌 \1</b>", text)
    text = re.sub(r"^#\s+(.+)",   r"<b>🔷 \1</b>", text)
    return text


def format_for_telegram(text: str) -> str:
    lines = text.strip().split("\n")
    output = []
    table_rows = []
    in_table = False
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        next_stripped = lines[i + 1].strip() if i + 1 < len(lines) else ""

        # ── Plain-text KV table: current line is header, next is ─── divider ──
        if stripped and re.match(r"^[─━—]{10,}$", next_stripped):
            if in_table and table_rows:
                output.append(render_table(table_rows))
                table_rows, in_table = [], False

            block = [line, lines[i + 1]]
            i += 2
            while i < len(lines) and lines[i].strip():
                block.append(lines[i])
                i += 1

            result = try_parse_kv_table(block)
            output.append(result if result else "\n".join(block))
            continue

        # ── Markdown pipe table ──
        if stripped.startswith("|") and stripped.endswith("|"):
            if not re.match(r"^\|[-| :]+\|$", stripped):
                in_table = True
                table_rows.append([c.strip() for c in stripped.strip("|").split("|")])
            i += 1
            continue

        if in_table and table_rows:
            output.append(render_table(table_rows))
            table_rows, in_table = [], False

        # ── Regular line ──
        output.append(apply_inline_formatting(stripped))
        i += 1

    if table_rows:
        output.append(render_table(table_rows))

    return "\n".join(output)