# -*- coding: utf-8 -*-
"""Generate the six figures for the memory-hierarchy deck as standalone SVG."""
import math, os
import numpy as np

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)))
INK, DARK, LIGHT = "#1a4f8b", "#12365f", "#e8eef7"
MID, ACCENT, GREEN, RED, GRAY = "#7ea2c8", "#c2410c", "#15803d", "#b91c1c", "#6b7280"
FONT = "Lato, 'Helvetica Neue', Helvetica, Arial, sans-serif"

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def txt(x, y, s, size=15, anchor="start", fill=DARK, bold=False, italic=False, halo=False, op=1.0):
    st = f'font-family="{FONT}" font-size="{size}" fill="{fill}"'
    if op != 1.0: st += f' opacity="{op}"'
    if bold:   st += ' font-weight="700"'
    if italic: st += ' font-style="italic"'
    if halo:   st += ' paint-order="stroke" stroke="#ffffff" stroke-width="4.5" stroke-linejoin="round"'
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

def circ(x, y, r, fill=INK, op=1.0):
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" opacity="{op}"/>'

def path(d, fill="none", stroke=INK, w=2, dash=None, op=1.0):
    ds = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{w}"{ds} opacity="{op}"/>'

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

def ylab(x, y, s, size=13):
    return (f'<text transform="translate({x:.1f},{y:.1f}) rotate(-90)" text-anchor="middle" '
            f'font-family="{FONT}" font-size="{size}" fill="{GRAY}" font-style="italic">{esc(s)}</text>')

# =====================================================================
# FIG 1 — reference patterns + working set
# =====================================================================
def fig1():
    W, H = 1140, 520
    b = [txt(24, 34, "Memory reference patterns", 21, "start", DARK, bold=True)]
    L, R, T, B = 120, 560, 66, 430
    def X(t): return L + t * (R - L)
    def Y(a): return B - a * (B - T)
    b += [line(L - 6, B, R, B, INK, 2), line(L, T - 6, L, B, INK, 2),
          txt(L - 8, T - 16, "address", 14, "start", GRAY, italic=True),
          txt(R, B + 30, "time →", 14, "end", GRAY, italic=True)]
    b.append(rect(X(0.285), T, X(0.375) - X(0.285), B - T, "#e9edf2", "#9aa7b4", 1.2, op=0.9))

    CODE, STACK, DATA = INK, "#7ea2c8", ACCENT
    rng = np.random.default_rng(5)

    # --- code: ascending ramps (straight-line execution) that loop back ---
    for it in range(7):
        t0 = 0.02 + it * 0.138
        n = 11
        for j in range(n):
            t = t0 + j * 0.0095
            a = 0.055 + j * 0.0098 + rng.normal(0, 0.0015)
            if t <= 1 and 0 <= a <= 1:
                b.append(circ(X(t), Y(a), 2.6, CODE, 0.85))
        if it < 6:   # the branch back
            b.append(line(X(t0 + (n - 1) * 0.0095), Y(0.055 + (n - 1) * 0.0098),
                          X(t0 + 0.138), Y(0.055), CODE, 1.0, dash="3,4", op=0.45))

    # --- stack: slow drift with small call/return clusters ---
    for i in range(90):
        t = 0.015 + i * 0.0110
        a = 0.395 + 0.075 * t + rng.normal(0, 0.004)
        b.append(circ(X(t), Y(a), 2.5, STACK, 0.85))
        if rng.random() < 0.16:          # a call: a couple of frames pushed
            for k in range(1, 3):
                b.append(circ(X(t + 0.002 * k), Y(a + 0.010 * k), 2.5, STACK, 0.85))

    # --- data: small blobs of a few addresses, wandering ---
    a0 = 0.78
    for k in range(11):
        t0 = 0.035 + k * 0.086
        a0 = float(np.clip(a0 + rng.normal(0, 0.055), 0.60, 0.92))
        rows, cols = 3, 3
        for i in range(rows):
            for j in range(cols):
                if rng.random() < 0.22: continue
                b.append(circ(X(t0 + j * 0.0055), Y(a0 + i * 0.0115), 2.6, DATA, 0.85))

    # --- the window bracket (the shading itself is drawn behind the dots) ---
    xa, xb = 0.285, 0.375
    b.append(line(X(xa), B + 8, X(xb), B + 8, GRAY, 1.6))
    b.append(line(X(xa), B + 4, X(xa), B + 12, GRAY, 1.6))
    b.append(line(X(xb), B + 4, X(xb), B + 12, GRAY, 1.6))
    b.append(txt((X(xa) + X(xb)) / 2, B + 30, "Δt", 15, "middle", DARK, bold=True))

    b.append(txt(X(0.40), Y(0.30), "S = the set of locations", 13.5, "start", DARK, bold=True, halo=True))
    b.append(txt(X(0.40), Y(0.265), "accessed during Δt", 13.5, "start", DARK, bold=True, halo=True))

    b.append(txt(L - 14, Y(0.11) + 4, "code", 14, "end", CODE, italic=True))
    b.append(txt(L - 14, Y(0.46) + 4, "stack", 14, "end", STACK, italic=True))
    b.append(txt(L - 14, Y(0.80) + 4, "data", 14, "end", DATA, italic=True))
    b.append(txt(L - 14, Y(0.11) + 22, "sequential,", 10.5, "end", GRAY, italic=True))
    b.append(txt(L - 14, Y(0.11) + 34, "then loops back", 10.5, "end", GRAY, italic=True))

    # ---- right panel: |S| vs delta-t ----
    L2, R2, T2, B2 = 700, 1100, 66, 430
    def X2(t): return L2 + t * (R2 - L2)
    ymax = 260.0
    def Y2(v): return B2 - (v / ymax) * (B2 - T2)
    b += [line(L2, B2, R2, B2, INK, 2), line(L2, T2, L2, B2, INK, 2),
          txt(R2, B2 + 30, "Δt  (window size) →", 14, "end", GRAY, italic=True),
          ylab(L2 - 36, (T2 + B2) / 2, "|S|  (KB)")]
    for v in (0, 100, 200):
        b.append(line(L2 - 5, Y2(v), L2, Y2(v), GRAY, 1.2))
        b.append(txt(L2 - 9, Y2(v) + 4, str(v), 12, "end", GRAY))
    pts = [f"{X2(t):.1f},{Y2(220 * (1 - math.exp(-t / 0.30))):.1f}"
           for t in np.linspace(0.001, 1, 200)]
    b.append(path("M" + " L".join(pts), "none", INK, 3))
    b.append(line(L2, Y2(220), R2 - 4, Y2(220), INK, 1.2, dash="3,4", op=0.5))
    for kb, lab, col in ((32, "L1 I  32 KB", MID), (64, "L1 D  64 KB", "#4a7fb0"),
                         (128, "L2  128 KB  (A53 only)", ACCENT)):
        b.append(line(L2, Y2(kb), R2 - 4, Y2(kb), col, 1.6, dash="6,4"))
        b.append(txt(R2 - 8, Y2(kb) - 7, lab, 12.5, "end", col, bold=(col == ACCENT), halo=True))
    b.append(txt(L2 + 16, Y2(250), "working set saturates", 14, "start", DARK, bold=True, halo=True))
    b.append(txt(L2 + 16, Y2(234), "— the program's real footprint", 13, "start", GRAY, italic=True, halo=True))
    b.append(txt(L2 + 16, Y2(16), "DRAM is 512 MB — three orders of", 12.5, "start", GRAY, italic=True, halo=True))
    b.append(txt(L2 + 16, Y2(6), "magnitude above the top of this chart", 12.5, "start", GRAY, italic=True, halo=True))
    b.append(txt(24, H - 14, "Illustrative — the shape is the lesson, not the numbers.",
                 12.5, "start", GRAY, italic=True))
    save("fig-access-pattern.svg", W, H, b)

# =====================================================================
# FIG 2 — block size
# =====================================================================
def fig2():
    W, H = 1140, 505
    b = [txt(24, 34, "Block size: two effects, one minimum", 21, "start", DARK, bold=True),
         txt(24, 58, "dashed line = our 64 B line size, on all four cores", 12.5, "start", ACCENT, italic=True)]
    blocks = [8, 16, 32, 64, 128, 256, 512]
    miss = {8: .160, 16: .085, 32: .050, 64: .030, 128: .026, 256: .028, 512: .036}
    pen  = {8: 32, 16: 44, 32: 68, 64: 116, 128: 212, 256: 404, 512: 788}
    amat = {k: 3 + miss[k] * pen[k] for k in blocks}
    PW, PH, T = 270, 285, 110
    panels = [(100, "miss rate", miss, MID, "falls — more spatial reuse per fetch", "{:.3f}"),
              (440, "miss penalty (cycles)", pen, ACCENT, "rises — a longer fill before any is usable", "{:.0f}"),
              (780, "AMAT (cycles)", amat, INK, "the sum: U-shaped", "{:.1f}")]
    for x0, title, data, col, note, fmt in panels:
        def X(v, x0=x0): return x0 + (math.log2(v) - 3) / 6.0 * PW
        vs = [data[k] for k in blocks]
        vlo, vhi = min(vs), max(vs); pad = (vhi - vlo) * 0.22 or 1
        def Y(v, vlo=vlo, pad=pad): return T + PH - (v - (vlo - pad)) / ((vhi + pad) - (vlo - pad)) * PH
        b.append(txt(x0, T - 16, title, 14.5, "start", DARK, bold=True))
        b += [line(x0, T + PH, x0 + PW, T + PH, INK, 1.8), line(x0, T, x0, T + PH, INK, 1.8)]
        b.append(path("M" + " L".join(f"{X(k):.1f},{Y(data[k]):.1f}" for k in blocks), "none", col, 3))
        for k in blocks: b.append(circ(X(k), Y(data[k]), 4.0, col))
        for k in (8, 32, 128, 512):
            b.append(line(X(k), T + PH, X(k), T + PH + 6, GRAY, 1.2))
            b.append(txt(X(k), T + PH + 22, str(k), 12, "middle", GRAY))
        b.append(txt(x0 + PW / 2, T + PH + 46, "block size (bytes)", 12.5, "middle", GRAY, italic=True))
        b.append(txt(x0, T + PH + 72, note, 12, "start", GRAY, italic=True))
        b.append(txt(X(64) + 11, Y(data[64]) - 11, fmt.format(data[64]), 13, "start", col, bold=True, halo=True))
        b.append(line(X(64), T - 6, X(64), T + PH, ACCENT, 1.8, dash="6,5", op=0.85))
    b.append(txt(24, H - 14, "Illustrative curves — the tradeoff is the point, not the calibration.",
                 12.5, "start", GRAY, italic=True))
    save("fig-block-size.svg", W, H, b)

# =====================================================================
# FIG 3 — associativity
# =====================================================================
def fig3():
    W, H = 1140, 560
    b = [txt(24, 34, "Associativity: conflict misses fall, hit time rises", 21, "start", DARK, bold=True)]
    ways = [1, 2, 4, 8, 16]
    conf = {1: 1.00, 2: .52, 4: .30, 8: .20, 16: .155}
    hit  = {1: 1.00, 2: 1.16, 4: 1.34, 8: 1.55, 16: 1.80}
    amat = {w: 0.62 * hit[w] + 0.72 * conf[w] for w in ways}
    PX, PW = 140, 660
    def X(w): return PX + (math.log2(w) / 4.0) * PW

    T1, PH1 = 96, 145
    b.append(txt(PX, T1 - 16, "the two components (relative)", 14.5, "start", DARK, bold=True))
    b += [line(PX, T1 + PH1, PX + PW, T1 + PH1, INK, 1.8), line(PX, T1, PX, T1 + PH1, INK, 1.8)]
    def YC(v): return T1 + PH1 - (v / 2.0) * PH1
    b.append(path("M" + " L".join(f"{X(w):.1f},{YC(conf[w]):.1f}" for w in ways), "none", MID, 3))
    b.append(path("M" + " L".join(f"{X(w):.1f},{YC(hit[w]):.1f}" for w in ways), "none", ACCENT, 3))
    for w in ways:
        b.append(circ(X(w), YC(conf[w]), 3.8, MID)); b.append(circ(X(w), YC(hit[w]), 3.8, ACCENT))
    b.append(txt(X(16) - 6, YC(1.80) - 12, "hit time ↑", 13, "end", ACCENT, bold=True, halo=True))
    b.append(txt(X(16) - 6, YC(0.155) + 24, "conflict misses ↓", 13, "end", MID, bold=True, halo=True))

    T2, PH2 = 330, 120
    b.append(txt(PX, T2 - 16, "AMAT", 14.5, "start", DARK, bold=True))
    b += [line(PX, T2 + PH2, PX + PW, T2 + PH2, INK, 1.8), line(PX, T2, PX, T2 + PH2, INK, 1.8)]
    vlo, vhi = min(amat.values()), max(amat.values())
    def YA(v): return T2 + PH2 - (v - vlo * 0.94) / (vhi * 1.06 - vlo * 0.94) * PH2
    b.append(path("M" + " L".join(f"{X(w):.1f},{YA(amat[w]):.1f}" for w in ways), "none", INK, 3.4))
    for w in ways:
        b.append(circ(X(w), YA(amat[w]), 4.4, INK))
        b.append(txt(X(w), T2 + PH2 + 22, str(w), 13, "middle", GRAY))
    b.append(txt(PX + PW / 2, T2 + PH2 + 46, "ways per set", 12.5, "middle", GRAY, italic=True))
    for w in (2, 4, 8, 12):
        b.append(line(X(w), T2 - 4, X(w), T2 + PH2, ACCENT, 1.3, dash="4,4", op=0.7))
    b.append(txt(PX + PW / 2, T2 + PH2 + 74,
                 "2 = C906 I, A53 I   |   4 = C906 D, A53 D   |   8 = Zen 5 I   |   12 = Zen 5 D",
                 12.5, "middle", ACCENT, bold=True))
    b.append(txt(24, H - 14, "Illustrative curves. Markers show where our four cores actually sit.",
                 12.5, "start", GRAY, italic=True))
    b.append(txt(W - 24, H - 14, "little benefit beyond 4–8 ways", 13.5, "end", DARK, bold=True, italic=True))
    save("fig-associativity.svg", W, H, b)

# =====================================================================
# FIG 4 — hierarchy pyramid
# =====================================================================
def fig4():
    W, H = 1180, 560
    b = [txt(24, 34, "Our hierarchy", 21, "start", DARK, bold=True)]
    levels = [
        ("Registers", "1 KB", "0 cycles", "#12365f", False),
        ("L1 I / D", "96 KB total", "1-4 cycles", "#1a4f8b", False),
        ("L2  (A53 only)", "128 KB", "~10 cycles", "#2f6ba8", False),
        ("DRAM", "512 MB DDR3", "60-100 cycles", "#4a7fb0", False),
        ("NAND flash", "16-64 GB", "50-100 us", "#7ea2c8", True),
        ("eMMC / disk", "up to 2 TB", "100 us - 10 ms", "#a8c3de", True),
    ]
    widths = [200, 330, 410, 570, 700, 810, 890]
    cx, SZX, LATX = 440, 950, 1010
    b.append(txt(SZX, 62, "size", 12.5, "end", GRAY, bold=True))
    b.append(txt(LATX, 62, "latency", 12.5, "start", GRAY, bold=True))
    y, hh, gap = 78, 64, 5
    for i, (name, size, lat, col, light) in enumerate(levels):
        wt, wb = widths[i], widths[i + 1]
        d = (f"M{cx-wt/2:.1f},{y:.1f} L{cx+wt/2:.1f},{y:.1f} "
             f"L{cx+wb/2:.1f},{y+hh:.1f} L{cx-wb/2:.1f},{y+hh:.1f} Z")
        b.append(path(d, col, "none", 0))
        fg = DARK if light else "#ffffff"
        b.append(txt(cx, y + hh / 2 + 6, name, 15, "middle", fg, bold=True))
        b.append(txt(SZX, y + hh / 2 + 6, size, 13, "end", DARK))
        b.append(txt(LATX, y + hh / 2 + 6, lat, 13, "start", GRAY, italic=True))
        b.append(line(cx + wb / 2 + 6, y + hh / 2, SZX - 74, y + hh / 2, GRAY, 0.8, op=0.5))
        y += hh + gap
    b.append(txt(24, H - 34, "No L3: an L1 miss on our core goes straight to DRAM.",
                 13, "start", ACCENT, bold=True))
    b.append(txt(24, H - 14, "The A53's 128 KB L2 is the only second level anywhere on the die.",
                 12.5, "start", GRAY, italic=True))
    save("fig-hierarchy.svg", W, H, b)

# =====================================================================
# FIG 5 — 6T SRAM cell
# =====================================================================
def fig5():
    W, H = 940, 560
    b = [txt(24, 34, "The 6T SRAM cell", 21, "start", DARK, bold=True)]
    WL_Y = 88
    BL, BLB = 150, 770
    QL, QR = 350, 620          # Q̄ rail (left), Q rail (right)
    b.append(line(BL, WL_Y + 20, BL, 500, INK, 2.4))
    b.append(line(BLB, WL_Y + 20, BLB, 500, INK, 2.4))
    b.append(line(BL, WL_Y, BLB, WL_Y, INK, 2.6))
    b.append(txt(BL, WL_Y - 14, "wordline (WL)", 13.5, "start", DARK, bold=True))
    b.append(txt(BL - 10, 520, "BL", 13.5, "end", DARK, bold=True))
    b.append(txt(BLB + 10, 520, "BL̄", 13.5, "start", DARK, bold=True))

    # access transistors
    for x0, lab in ((186, "M1"), (634, "M2")):
        b.append(rect(x0, 160, 116, 54, LIGHT, INK, 2.2, rx=6))
        b.append(txt(x0 + 58, 194, lab, 13, "middle", DARK, bold=True))
        b.append(line(x0 + 58, 160, x0 + 58, WL_Y + 3, INK, 1.8, arrow=True))
        b.append(txt(x0 + 66, 140, "gate", 11, "start", GRAY, italic=True))
    b.append(line(BL, 187, 186, 187, INK, 2.2))
    b.append(line(302, 187, QL, 187, INK, 2.2))
    b.append(line(QR, 187, 634, 187, INK, 2.2))
    b.append(line(750, 187, BLB, 187, INK, 2.2))

    # rails
    b.append(line(QL, 187, QL, 470, INK, 2.2))
    b.append(line(QR, 187, QR, 470, INK, 2.2))
    b.append(txt(QL - 10, 330, "Q̄", 15, "end", ACCENT, bold=True))
    b.append(txt(QR + 10, 330, "Q", 15, "start", ACCENT, bold=True))

    # inverter 1 (points right, top)
    b.append(path(f"M390,250 L390,330 L560,290 Z", LIGHT, INK, 2.2))
    b.append(txt(452, 296, "INV", 12.5, "middle", DARK, bold=True))
    b.append(line(QL, 290, 390, 290, INK, 2.2))
    b.append(line(560, 290, QR, 290, INK, 2.2))
    # inverter 2 (points left, bottom)
    b.append(path(f"M550,400 L550,480 L380,440 Z", LIGHT, INK, 2.2))
    b.append(txt(488, 446, "INV", 12.5, "middle", DARK, bold=True))
    b.append(line(QR, 440, 550, 440, INK, 2.2))
    b.append(line(380, 440, QL, 440, INK, 2.2))

    b.append(txt(BL - 6, 372, "bitline", 12, "end", GRAY, italic=True))
    b.append(txt(BLB + 6, 372, "bitline", 12, "start", GRAY, italic=True))
    b.append(txt(470, H - 46, "6 transistors: 2 cross-coupled inverters + 2 access FETs",
                 14, "middle", DARK, bold=True))
    b.append(txt(470, H - 24, "The loop has two stable states — that is the bit. Reading does not disturb it.",
                 13, "middle", GRAY, italic=True))
    save("fig-sram-cell.svg", W, H, b)

# =====================================================================
# FIG 6 — N-way structure
# =====================================================================
def fig6():
    W, H = 1120, 560
    b = [txt(24, 34, "N-way set associative: what one lookup costs", 21, "start", DARK, bold=True)]
    ax, ay, ah = 60, 66, 42
    fields = [("tag", 150, INK), ("index", 96, ACCENT), ("offset", 78, GRAY)]
    x = ax
    for name, w, col in fields:
        b.append(rect(x, ay, w, ah, "#fdece4" if col == ACCENT else LIGHT, col, 2))
        b.append(txt(x + w / 2, ay + ah / 2 + 5, name, 13, "middle", DARK, bold=True))
        x += w
    b.append(txt(ax, ay - 10, "address", 12.5, "start", GRAY, italic=True))

    # index -> set select -> row bracket
    b.append(line(ax + 198, ay + ah, ax + 198, 150, ACCENT, 2, arrow=True))
    b.append(rect(152, 150, 190, 42, "#fdece4", ACCENT, 2, rx=4))
    b.append(txt(247, 177, "set select", 13, "middle", DARK, bold=True))
    b.append(line(247, 192, 247, 210, ACCENT, 2))
    b.append(line(330, 210, 690, 210, ACCENT, 2, dash="6,4"))
    b.append(txt(340, 204, "index picks one row (set)", 11.5, "start", ACCENT, italic=True))

    # tag bus
    TAGY = 232
    b.append(line(ax + 75, ay + ah, ax + 75, TAGY, INK, 2))
    b.append(line(ax + 75, TAGY, 690, TAGY, INK, 2))
    b.append(txt(ax + 8, TAGY + 16, "tag to every comparator", 11.5, "start", GRAY, italic=True))

    ways = [(300, "0"), (470, "1"), (640, "2")]
    for xw, lab in ways:
        b.append(line(xw + 50, TAGY, xw + 50, 248, INK, 1.8, arrow=True))
        b.append(rect(xw, 248, 100, 42, LIGHT, INK, 2, rx=4))
        b.append(txt(xw + 50, 274, "tag", 12.5, "middle", DARK, bold=True))
        b.append(line(xw + 50, 290, xw + 50, 302, INK, 1.8, arrow=True))
        b.append(rect(xw, 302, 100, 42, "#ffffff", INK, 2, rx=4))
        b.append(txt(xw + 50, 329, "=", 20, "middle", ACCENT, bold=True))
        b.append(line(xw + 50, 344, xw + 50, 360, INK, 1.8))

    # OR bus below comparators
    b.append(line(350, 360, 830, 360, ACCENT, 2))
    b.append(txt(760, 352, "\u22ef", 20, "middle", GRAY))
    b.append(rect(830, 338, 96, 44, "#fdece4", ACCENT, 2, rx=4))
    b.append(txt(878, 366, "OR", 15, "middle", DARK, bold=True))
    b.append(line(926, 360, 986, 360, ACCENT, 2, arrow=True))
    b.append(txt(992, 366, "HIT", 15, "start", ACCENT, bold=True))

    # data arrays, staggered so the mux inputs never cross a box
    dys = [410, 446, 482]
    for (xw, lab), dy in zip(ways, dys):
        b.append(rect(xw, dy, 100, 30, LIGHT, INK, 2, rx=4))
        b.append(txt(xw + 50, dy + 20, f"data {lab}", 12, "middle", DARK, bold=True))
        b.append(line(xw + 100, dy + 15, 800, dy + 15, INK, 1.8, arrow=True))
    b.append(rect(800, 404, 96, 100, LIGHT, INK, 2, rx=4))
    b.append(txt(848, 448, "N:1", 13, "middle", DARK, bold=True))
    b.append(txt(848, 466, "mux", 13, "middle", DARK, bold=True))
    b.append(line(896, 454, 986, 454, INK, 2, arrow=True))
    b.append(txt(992, 460, "data out", 14, "start", DARK, bold=True))

    b.append(txt(24, H - 16,
                 "N tag comparators and an N:1 mux sit on every access \u2014 that is why hit time rises with N.",
                 12.5, "start", GRAY, italic=True))
    save("fig-nway.svg", W, H, b)

fig1(); fig2(); fig3(); fig4(); fig5(); fig6()
