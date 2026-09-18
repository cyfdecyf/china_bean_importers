# Shared helpers to synthesize bill files for tests. Real exported bills are
# private data, so each importer is exercised against minimal synthetic
# fixtures that mimic the relevant parts of the real format.

import pymupdf


def text_width(text: str, fontsize: float) -> float:
    """Approximate rendered width: CJK glyphs are full width."""
    return sum(fontsize if ord(ch) > 0x2E80 else fontsize * 0.55 for ch in text)


def insert_text(page, pos, text, fontsize=8):
    """Insert text using a font that can render CJK glyphs."""
    fontname = "helv" if text.isascii() else "china-s"
    return page.insert_text(pos, text, fontname=fontname, fontsize=fontsize)


def header_lines(page, lines, x=50, y=40, fontsize=10, dy=14):
    for i, ln in enumerate(lines):
        insert_text(page, (x, y + i * dy), ln, fontsize)


def draw_table(page, x0, y0, rows, row_h=16, fontsize=8, pad=4, line_dy=10):
    """Draw a ruled table with auto column widths; returns total width.
    Cells containing newlines are drawn as multiple stacked lines and their
    row grows taller accordingly."""
    ncols = max(len(r) for r in rows)
    widths = [
        max(
            text_width(line, fontsize)
            for r in rows
            if len(r) > c
            for line in r[c].split("\n")
        )
        + pad * 2
        for c in range(ncols)
    ]
    total_w = sum(widths)
    heights = [
        max(row_h, max(cell.count("\n") for cell in r) * line_dy + fontsize + pad * 2)
        for r in rows
    ]
    ys = [y0]
    for h in heights:
        ys.append(ys[-1] + h)
    for y in ys:
        page.draw_line((x0, y), (x0 + total_w, y))
    for i in range(ncols + 1):
        x = x0 + sum(widths[:i])
        page.draw_line((x, y0), (x, ys[-1]))
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            x = x0 + sum(widths[:c]) + pad
            for li, line in enumerate(text.split("\n")):
                insert_text(page, (x, ys[r] + pad + fontsize + li * line_dy), line, fontsize)
    return total_w


def new_pdf(path, width=1200, height=842):
    doc = pymupdf.open()
    doc.new_page(width=width, height=height)
    doc.save(path)
    doc.close()
    return path


def open_and_insert(path):
    doc = pymupdf.open(path)
    return doc, doc[0]
