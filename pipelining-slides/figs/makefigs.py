# -*- coding: utf-8 -*-
"""Generate the pipelining-deck figures as standalone SVG.

Three figures for Part I:
  fig-stations.svg       the five stations, their caches, and the register file
  fig-pipeline-regs.svg  the same chain, with the four pipeline registers
  fig-overlap.svg        six independent instructions, one per cycle
"""
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)))
INK, DARK, LIGHT = "#1a4f8b", "#12365f", "#e8eef7"
MID, ACCENT, GREEN, RED, GRAY = "#7ea2c8", "#c2410c", "#15803d", "#b91c1c", "#6b7280"
FONT = "Lato, 'Helvetica Neue', Helvetica, Arial, sans-serif"

# six instruction colours, all light enough for dark text
PAL = ["#dbe6f3", "#fbe0d3", "#dcf0e2", "#f6dde7", "#e6e1f4", "#f1ecd8"]


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def txt(x, y, s, size=15, anchor="start", fill=DARK, bold=False, italic=False, halo=False, op=1.0):
    st = f'font-family="{FONT}" font-size="{size}" fill="{fill}"'
    if op != 1.0:
        st += f' opacity="{op}"'
    if bold:
        st += ' font-weight="700"'
    if italic:
        st += ' font-style="italic"'
    if halo:
        st += ' paint-order="stroke" stroke="#ffffff" stroke-width="4.5" stroke-linejoin="round"'
    return f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" {st}>{esc(s)}</text>'


def line(x1, y1, x2, y2, stroke=INK, w=2, dash=None, op=1.0, arrow=False):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    a = f' marker-end="url(#arw_{stroke[1:]})"' if arrow else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{w}" stroke-linecap="round"{d}{a} opacity="{op}"/>')


def rect(x, y, w, h, fill="none", stroke=INK, sw=2, rx=0, dash=None, op=1.0):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d} opacity="{op}"/>')


def path(d, fill="none", stroke=INK, w=2, dash=None, op=1.0, arrow=False):
    ds = f' stroke-dasharray="{dash}"' if dash else ""
    a = f' marker-end="url(#arw_{stroke[1:]})"' if arrow else ""
    return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{w}"{ds}{a} opacity="{op}"/>'


DEFS = "".join(
    f'<marker id="arw_{c[1:]}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.5" '
    f'markerHeight="6.5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>'
    for c in (INK, ACCENT, MID, GRAY, DARK))


def save(name, w, h, body):
    open(os.path.join(OUT, name), "w", encoding="utf-8").write(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">\n<defs>{DEFS}</defs>\n'
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>\n' + "\n".join(body) + "\n</svg>\n")
    print("wrote", name)


# =====================================================================
# FIG 1 — the five stations, the two caches, the register file
# =====================================================================
def fig_stations():
    W, H = 1140, 442
    b = [txt(24, 34, "Five stations, and the memory they talk to", 21, "start", DARK, bold=True)]

    x0, bw, gap, by, bh = 100, 168, 30, 196, 100
    stations = [
        ("IF", "IFU", "fetch"),
        ("ID", "IDU", "decode, read regs"),
        ("EX", "IU", "execute"),
        ("MEM", "LSU", "load / store"),
        ("WB", "RTU", "write back"),
    ]
    for i, (lab, unit, verb) in enumerate(stations):
        x = x0 + i * (bw + gap)
        b.append(rect(x, by, bw, bh, LIGHT, INK, 2.4, rx=6))
        b.append(txt(x + bw / 2, by + 34, lab, 19, "middle", DARK, bold=True))
        b.append(txt(x + bw / 2, by + 58, unit, 13, "middle", ACCENT, bold=True))
        b.append(txt(x + bw / 2, by + 80, verb, 12, "middle", GRAY, italic=True))
        # the arrow is where a pipeline register will go
        if i < len(stations) - 1:
            b.append(line(x + bw + 3, by + bh / 2, x + bw + gap - 1, by + bh / 2,
                          INK, 2.2, arrow=True))

    # PC
    b.append(rect(20, by + 24, 64, 52, "#ffffff", INK, 2, rx=4))
    b.append(txt(52, by + 56, "PC", 15, "middle", DARK, bold=True))
    b.append(line(84, by + 50, x0, by + 50, INK, 2, arrow=True))

    # the two caches, deliberately separate boxes
    b.append(rect(x0, 70, bw, 60, "#ffffff", INK, 2, rx=4))
    b.append(txt(x0 + bw / 2, 96, "L1 I-cache", 14, "middle", DARK, bold=True))
    b.append(txt(x0 + bw / 2, 116, "32 KB, 2-way", 11.5, "middle", GRAY, italic=True))
    b.append(line(x0 + bw / 2, 130, x0 + bw / 2, by, INK, 2, arrow=True))

    memx = x0 + 3 * (bw + gap)
    b.append(rect(memx, 70, bw, 60, "#ffffff", INK, 2, rx=4))
    b.append(txt(memx + bw / 2, 96, "L1 D-cache", 14, "middle", DARK, bold=True))
    b.append(txt(memx + bw / 2, 116, "64 KB, 4-way", 11.5, "middle", GRAY, italic=True))
    b.append(line(memx + bw / 2, 130, memx + bw / 2, by, INK, 2, arrow=True))

    # branch predictor, dashed: we come back to it in Part III
    px, pw = 340, 300
    b.append(rect(px, 70, pw, 60, "#ffffff", GRAY, 1.8, rx=4, dash="7,5"))
    b.append(txt(px + pw / 2, 94, "branch predictor", 13, "middle", GRAY, bold=True))
    b.append(txt(px + pw / 2, 114, "Gshare BHT \u00b7 16-entry BTB \u00b7 4-deep RAS", 10.5, "middle", GRAY, italic=True))
    b.append(path(f"M{px + 30},130 L{px + 30},160 L{x0 + bw - 20},160 L{x0 + bw - 20},{by}",
                  "none", GRAY, 1.6, dash="7,5", arrow=True))

    # register file, read in ID, written in WB
    rf_x, rf_w, rf_y, rf_h = 300, 360, 348, 72
    b.append(rect(rf_x, rf_y, rf_w, rf_h, "#ffffff", INK, 2.2, rx=6))
    b.append(txt(rf_x + rf_w / 2, rf_y + 30, "Register file", 15, "middle", DARK, bold=True))
    b.append(txt(rf_x + rf_w / 2, rf_y + 52, "32 \u00d7 64-bit, two read ports", 11.5, "middle", GRAY, italic=True))

    idx_x = x0 + 1 * (bw + gap) + bw / 2          # centre of ID
    wbx = x0 + 4 * (bw + gap) + bw / 2            # centre of WB
    b.append(line(idx_x, rf_y, idx_x, by + bh, INK, 2, arrow=True))
    b.append(txt(idx_x + 8, by + bh + 22, "read", 11.5, "start", GRAY, italic=True))
    b.append(path(f"M{wbx},{by + bh} L{wbx},{rf_y + 36} L{rf_x + rf_w},{rf_y + 36}",
                  "none", INK, 2, arrow=True))
    b.append(txt(wbx + 8, rf_y + 30, "write", 11.5, "start", GRAY, italic=True))

    save("fig-stations.svg", W, H, b)


# =====================================================================
# FIG 2 — the same chain with the four pipeline registers
# =====================================================================
def fig_regs():
    W, H = 1140, 228
    b = [txt(24, 34, "Four registers, and nothing else", 21, "start", DARK, bold=True)]

    x0, bw, gap, by, bh = 90, 150, 50, 100, 84
    names = ["IF/ID", "ID/EX", "EX/MEM", "MEM/WB"]
    for i, lab in enumerate(["IF", "ID", "EX", "MEM", "WB"]):
        x = x0 + i * (bw + gap)
        b.append(rect(x, by, bw, bh, LIGHT, INK, 2.2, rx=6))
        b.append(txt(x + bw / 2, by + bh / 2 + 7, lab, 19, "middle", DARK, bold=True))
        if i < 4:
            gx = x + bw + 18
            b.append(line(x + bw, by + bh / 2, gx - 4, by + bh / 2, INK, 1.8, arrow=True))
            b.append(rect(gx, by, 14, bh, ACCENT, ACCENT, 2, rx=2))
            b.append(line(gx + 18, by + bh / 2, x + bw + gap, by + bh / 2, INK, 1.8, arrow=True))
            b.append(txt(gx + 7, by + bh + 26, names[i], 12.5, "middle", ACCENT, bold=True))

    save("fig-pipeline-regs.svg", W, H, b)


# =====================================================================
# FIG 3 — six independent instructions, one per cycle
# =====================================================================
def fig_overlap():
    W, H = 1160, 404
    b = [txt(24, 34, "Six independent instructions, one per cycle", 21, "start", DARK, bold=True)]

    insts = ["ld x5", "add x6", "sub x7", "and x8", "or x9", "xor x19"]
    rows = ["IF", "ID", "EX", "MEM", "WB"]
    x0, colw, y0, rowh = 150, 100, 96, 58
    ncol = 10

    # grid
    for c in range(ncol + 1):
        b.append(line(x0 + c * colw, y0, x0 + c * colw, y0 + 5 * rowh, "#d7dee8", 1))
    for r in range(len(rows) + 1):
        b.append(line(x0, y0 + r * rowh, x0 + ncol * colw, y0 + r * rowh, "#d7dee8", 1))
    for c in range(ncol):
        b.append(txt(x0 + c * colw + colw / 2, y0 - 12, str(c + 1), 12.5, "middle", GRAY))
    for r, name in enumerate(rows):
        b.append(txt(x0 - 14, y0 + r * rowh + rowh / 2 + 5, name, 13.5, "end", DARK, bold=True))

    # cells
    band = x0 + 4 * colw
    b.append(f'<rect x="{band:.1f}" y="{y0:.1f}" width="{colw:.1f}" height="{5 * rowh:.1f}" '
             f'fill="{ACCENT}" opacity="0.09"/>')
    for i, inst in enumerate(insts):
        for k in range(5):
            c = i + k
            if c >= ncol:
                continue
            cx = x0 + c * colw + 3
            cy = y0 + k * rowh + 3
            b.append(rect(cx, cy, colw - 6, rowh - 6, PAL[i % len(PAL)], "#ffffff", 1, rx=4))
            b.append(txt(cx + (colw - 6) / 2, cy + (rowh - 6) / 2 + 4.5, inst, 12.5, "middle", DARK))

    # the snapshot column
    b.append(txt(band + colw / 2, y0 - 44, "cycle 5", 12.5, "middle", ACCENT, bold=True))
    b.append(txt(band + colw / 2, y0 - 28, "five instructions in flight", 11, "middle", ACCENT, italic=True))

    save("fig-overlap.svg", W, H, b)



# =====================================================================
# FIG 4 — one register, two instructions
# =====================================================================
def fig_hazard():
    W, H = 1160, 412
    b = [txt(24, 34, "Two accesses, two cycles apart", 21, "start", DARK, bold=True)]

    insts = ["ld x5", "add x6", "sub x7", "and x8", "or x9", "xor x19"]
    rows = ["IF", "ID", "EX", "MEM", "WB"]
    x0, colw, y0, rowh = 150, 100, 76, 58
    ncol = 10

    for c in range(ncol + 1):
        b.append(line(x0 + c * colw, y0, x0 + c * colw, y0 + 5 * rowh, "#d7dee8", 1))
    for r in range(len(rows) + 1):
        b.append(line(x0, y0 + r * rowh, x0 + ncol * colw, y0 + r * rowh, "#d7dee8", 1))
    for c in range(ncol):
        b.append(txt(x0 + c * colw + colw / 2, y0 - 12, str(c + 1), 12.5, "middle", GRAY))
    for r, name in enumerate(rows):
        b.append(txt(x0 - 14, y0 + r * rowh + rowh / 2 + 5, name, 13.5, "end", DARK, bold=True))

    for i, inst in enumerate(insts):
        for k in range(5):
            c = i + k
            if c >= ncol:
                continue
            cx = x0 + c * colw + 3
            cy = y0 + k * rowh + 3
            b.append(rect(cx, cy, colw - 6, rowh - 6, PAL[i % len(PAL)], "#ffffff", 1, rx=4))
            b.append(txt(cx + (colw - 6) / 2, cy + (rowh - 6) / 2 + 4.5, inst, 12.5, "middle", DARK))

    # the two cells that matter: sub reads x6 (instr 2, ID) and add writes x6 (instr 1, WB)
    for i, k in ((2, 1), (1, 4)):
        cx = x0 + (i + k) * colw + 3
        cy = y0 + k * rowh + 3
        b.append(rect(cx, cy, colw - 6, rowh - 6, "none", ACCENT, 3, rx=4))

    b.append(txt(x0 + 3.5 * colw, y0 - 34, "sub reads x6", 12.5, "middle", ACCENT, bold=True))
    b.append(txt(x0 + 5.5 * colw, y0 - 34, "add writes x6", 12.5, "middle", ACCENT, bold=True))

    yb = y0 + 5 * rowh + 24
    xa, xb = x0 + 3.5 * colw, x0 + 5.5 * colw
    mid = (xa + xb) / 2
    b.append(line(mid, yb, xa + 3, yb, ACCENT, 2, arrow=True))
    b.append(line(mid, yb, xb - 3, yb, ACCENT, 2, arrow=True))
    b.append(line(xa, yb - 7, xa, yb + 7, ACCENT, 2))
    b.append(line(xb, yb - 7, xb, yb + 7, ACCENT, 2))
    b.append(txt(mid, yb - 11, "2 cycles", 12, "middle", ACCENT, bold=True))

    save("fig-hazard.svg", W, H, b)


# =====================================================================
# FIG 5 — where the value actually is, cycle by cycle
# =====================================================================
def fig_value():
    W, H = 1140, 396
    b = [txt(24, 34, "The new x6, cycle by cycle", 21, "start", DARK, bold=True)]

    lanes = ["ALU output", "EX/MEM", "MEM/WB", "register file"]
    x0, colw, y0, rowh = 190, 118, 100, 56
    ncol = 8
    fills = {0: [3], 1: [4], 2: [5], 3: [6, 7]}      # 0-based cycle indices

    # the cycle in which sub reads
    band = x0 + 3 * colw
    b.append(f'<rect x="{band:.1f}" y="{y0 - 6:.1f}" width="{colw:.1f}" '
             f'height="{4 * rowh + 12:.1f}" fill="{ACCENT}" opacity="0.07"/>')

    for c in range(ncol + 1):
        b.append(line(x0 + c * colw, y0, x0 + c * colw, y0 + 4 * rowh, "#d7dee8", 1))
    for r in range(len(lanes) + 1):
        b.append(line(x0, y0 + r * rowh, x0 + ncol * colw, y0 + r * rowh, "#d7dee8", 1))
    for c in range(ncol):
        b.append(txt(x0 + c * colw + colw / 2, y0 - 14, str(c + 1), 12.5, "middle", GRAY))
    for r, name in enumerate(lanes):
        b.append(txt(x0 - 16, y0 + r * rowh + rowh / 2 + 5, name, 13, "end", DARK, bold=True))

    for r, cols in fills.items():
        for c in cols:
            cx = x0 + c * colw + 3
            cy = y0 + r * rowh + 3
            b.append(rect(cx, cy, colw - 6, rowh - 6, "#fdece4", ACCENT, 1.4, rx=4))
            b.append(txt(cx + (colw - 6) / 2, cy + (rowh - 6) / 2 + 4.5, "new x6", 12, "middle", DARK))

    # the read marker, below the grid
    yb = y0 + 4 * rowh
    b.append(txt(band + colw / 2, yb + 26, "sub reads x6 here", 12.5, "middle", ACCENT, bold=True))
    b.append(txt(band + colw / 2, yb + 46, "the register file still holds the old value", 11.5,
                 "middle", GRAY, italic=True))

    save("fig-value.svg", W, H, b)


fig_stations()
fig_regs()
fig_overlap()
fig_hazard()
fig_value()


# =====================================================================
# FIG 6 — bypass muxes on the ALU inputs
# =====================================================================
def fig_bypass():
    W, H = 1140, 430
    b = [txt(24, 34, "Bypassing: three sources into each ALU input", 21, "start", DARK, bold=True)]

    def mux(bx, by, bh, rows, out_lab, in_labels):
        # box
        b.append(rect(bx, by, 76, bh, LIGHT, INK, 2.2, rx=4))
        b.append(txt(bx + 38, by + bh / 2 - 4, "MUX", 12.5, "middle", DARK, bold=True))
        b.append(txt(bx + 38, by + bh / 2 + 13, out_lab, 12, "middle", ACCENT, bold=True))
        for ry, lab in zip(rows, in_labels):
            b.append(line(bx - 68, ry, bx - 3, ry, INK, 1.8, arrow=True))
            b.append(txt(bx - 76, ry + 5, lab, 12.5, "end", DARK))
        # select
        b.append(line(bx + 38, by + bh + 26, bx + 38, by + bh + 2, ACCENT, 1.6, dash="5,4", arrow=True))
        b.append(txt(bx + 48, by + bh + 22, "match", 10.5, "start", ACCENT, italic=True))

    srcs = ["EX/MEM \u00b7 Y", "MEM/WB \u00b7 Y or RD", "ID/EX \u00b7 A"]
    mux(322, 74, 136, [96, 142, 188], "A", srcs)
    srcs_b = ["EX/MEM \u00b7 Y", "MEM/WB \u00b7 Y or RD", "ID/EX \u00b7 B"]
    mux(322, 254, 136, [276, 322, 368], "B", srcs_b)

    # ALU
    b.append(rect(470, 110, 130, 244, "#ffffff", INK, 2.2, rx=6))
    b.append(txt(535, 226, "ALU", 17, "middle", DARK, bold=True))
    b.append(line(398, 142, 470, 142, INK, 2, arrow=True))
    b.append(line(398, 322, 470, 322, INK, 2, arrow=True))
    b.append(txt(434, 134, "A", 12, "middle", GRAY, italic=True))
    b.append(txt(434, 314, "B", 12, "middle", GRAY, italic=True))

    b.append(line(600, 232, 748, 232, INK, 2, arrow=True))
    b.append(txt(674, 222, "Y", 13, "middle", DARK, bold=True))
    b.append(rect(748, 202, 160, 60, LIGHT, INK, 2, rx=4))
    b.append(txt(828, 228, "EX/MEM", 12.5, "middle", DARK, bold=True))
    b.append(txt(828, 246, "next cycle", 10.5, "middle", GRAY, italic=True))

    save("fig-bypass.svg", W, H, b)


# =====================================================================
# FIG 7 — load-to-use: produced and needed in the same cycle
# =====================================================================
def fig_loaduse():
    W, H = 1160, 412
    b = [txt(24, 34, "A load is one stage too late", 21, "start", DARK, bold=True)]

    insts = ["ld x5", "add x6", "sub x7", "and x8", "or x9", "xor x19"]
    rows = ["IF", "ID", "EX", "MEM", "WB"]
    x0, colw, y0, rowh = 150, 100, 76, 58
    ncol = 10

    for c in range(ncol + 1):
        b.append(line(x0 + c * colw, y0, x0 + c * colw, y0 + 5 * rowh, "#d7dee8", 1))
    for r in range(len(rows) + 1):
        b.append(line(x0, y0 + r * rowh, x0 + ncol * colw, y0 + r * rowh, "#d7dee8", 1))
    for c in range(ncol):
        b.append(txt(x0 + c * colw + colw / 2, y0 - 12, str(c + 1), 12.5, "middle", GRAY))
    for r, name in enumerate(rows):
        b.append(txt(x0 - 14, y0 + r * rowh + rowh / 2 + 5, name, 13.5, "end", DARK, bold=True))

    for i, inst in enumerate(insts):
        for k in range(5):
            c = i + k
            if c >= ncol:
                continue
            cx = x0 + c * colw + 3
            cy = y0 + k * rowh + 3
            b.append(rect(cx, cy, colw - 6, rowh - 6, PAL[i % len(PAL)], "#ffffff", 1, rx=4))
            b.append(txt(cx + (colw - 6) / 2, cy + (rowh - 6) / 2 + 4.5, inst, 12.5, "middle", DARK))

    # ld produces x5 in MEM (instr 0, cycle 4); add needs it in EX (instr 1, cycle 4)
    for i, k in ((0, 3), (1, 2)):
        cx = x0 + (i + k) * colw + 3
        cy = y0 + k * rowh + 3
        b.append(rect(cx, cy, colw - 6, rowh - 6, "none", ACCENT, 3, rx=4))

    col = x0 + 3.5 * colw
    b.append(txt(col, y0 - 34, "both in cycle 4", 12.5, "middle", ACCENT, bold=True))
    b.append(line(col, y0 + 2 * rowh - 2, col, y0 + 3 * rowh + 2, ACCENT, 2, arrow=True))
    b.append(line(col, y0 + 3 * rowh + 2, col, y0 + 2 * rowh - 2, ACCENT, 2, arrow=True))

    save("fig-loaduse.svg", W, H, b)


fig_bypass()
fig_loaduse()

fig_stations()
fig_regs()
fig_overlap()
fig_hazard()
fig_value()
