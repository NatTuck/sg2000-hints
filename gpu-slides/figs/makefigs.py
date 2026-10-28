# -*- coding: utf-8 -*-
"""Generate the seven Part I-III figures for the GPU deck as standalone SVG.

Helper block copied verbatim from memory-slides/figs/makefigs.py (house style).
"""
import math, os

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
# A1 — two bets: latency vs width
# =====================================================================
def fig_two_bets():
    W, H = 1140, 430
    b = [txt(24, 34, "Two bets: spend on latency, or spend on width", 21, "start", DARK, bold=True),
         txt(W - 24, 34, "same transistors, opposite bet", 15, "end", ACCENT, bold=True)]

    # --- left: one CPU core ---
    b.append(txt(60, 84, "One CPU core \u2014 spends on latency", 15, "start", DARK, bold=True))
    cpu = [  # x, y, w, h, label, sub
        (60, 100, 190, 120, "Branch predictor", ""),
        (250, 100, 180, 120, "Out-of-order window", ""),
        (430, 100, 90, 120, "Registers", ""),
        (60, 220, 360, 110, "L1 / L2 caches", ""),
        (420, 220, 100, 110, "ALUs", ""),
    ]
    for x, y, w, h, lab, sub in cpu:
        b.append(rect(x, y, w, h, LIGHT, INK, 2, rx=3))
        if lab == "ALUs":
            b.append(txt(x + w / 2, y + h / 2 - 4, lab, 13.5, "middle", DARK, bold=True))
            b.append(txt(x + w / 2, y + h / 2 + 16, "small", 11.5, "middle", ACCENT, italic=True))
        else:
            b.append(txt(x + w / 2, y + h / 2 + 5, lab, 13.5, "middle", DARK, bold=True))

    # --- right: one GPU compute unit ---
    b.append(txt(620, 84, "One GPU compute unit \u2014 spends on width", 15, "start", DARK, bold=True))
    b.append(rect(620, 100, 460, 100, LIGHT, INK, 2, rx=3))
    b.append(txt(850, 143, "VGPR file", 15, "middle", DARK, bold=True))
    b.append(txt(850, 165, "256 KB", 13.5, "middle", ACCENT, bold=True))
    gpu = [(620, 200, 250, 130, "64 lanes", "(4 \u00d7 SIMD16)"),
           (870, 200, 105, 130, "LDS", "64 KB"),
           (975, 200, 105, 130, "Scheduler", "")]
    for x, y, w, h, lab, sub in gpu:
        b.append(rect(x, y, w, h, LIGHT, INK, 2, rx=3))
        b.append(txt(x + w / 2, y + 40, lab, 13.5, "middle", DARK, bold=True))
        if sub:
            b.append(txt(x + w / 2, y + 60, sub, 11.5, "middle", GRAY))

    b.append(txt(60, 358, "\u22484-6 ALUs", 15, "start", ACCENT, bold=True))
    b.append(txt(620, 358, "64 lanes", 15, "start", ACCENT, bold=True))
    b.append(txt(24, H - 14, "boxes are proportional in area \u2014 both panels are the same total area.",
                 12.5, "start", GRAY, italic=True))
    save("fig-two-bets.svg", W, H, b)

# =====================================================================
# A2 — Little's law
# =====================================================================
def fig_littles_law():
    W, H = 900, 470
    L, R, T, B = 110, 760, 130, 380
    def X(t): return L + t / 800.0 * (R - L)
    def Y(v): return B - v / 800.0 * (B - T)
    b = [txt(24, 34, "Little's law: threads = latency \u00f7 work per thread", 21, "start", DARK, bold=True)]

    # the off-scale MI50 reference band
    b.append(rect(L, 86, R - L, 22, LIGHT, MID, 1.4, rx=3, dash="5,4"))
    b.append(txt(L + 10, 102, "MI50 holds 153,600 threads \u2014 off the top of this axis",
                 12.5, "start", DARK, bold=True))

    for v in (200, 400, 600, 800):
        b.append(line(L, Y(v), R, Y(v), MID, 1, op=0.35))
    b += [line(L, B, R, B, INK, 2), line(L, T, L, B, INK, 2)]
    for t in (0, 200, 400, 600, 800):
        b.append(line(X(t), B, X(t), B + 6, GRAY, 1.2))
        b.append(txt(X(t), B + 22, str(t), 12, "middle", GRAY))
    for v in (0, 200, 400, 600, 800):
        b.append(line(L - 5, Y(v), L, Y(v), GRAY, 1.2))
        b.append(txt(L - 9, Y(v) + 4, str(v), 12, "end", GRAY))
    b.append(txt(R, B + 46, "latency (cycles)", 14, "end", GRAY, italic=True))
    b.append(ylab(74, (T + B) / 2, "threads resident"))

    # three slopes
    for work, col in ((1, INK), (4, INK), (16, INK)):
        b.append(line(X(0), Y(0), X(800), Y(800.0 / work), col, 2.6))
    for work, ypos in ((1, 135), (4, 322), (16, 369)):
        b.append(txt(R + 8, ypos, f"{work} cycle" + ("s" if work > 1 else "") + "/thread",
                     13, "start", DARK, bold=True))

    # the worked point: 500 cycles / 4 = 125
    px, py = X(500), Y(125)
    b.append(circ(px, py, 5, ACCENT))
    b.append(txt(px - 10, 294, "500 cycles of latency,", 13.5, "end", DARK, bold=True, halo=True))
    b.append(txt(px - 10, 312, "4 cycles/thread", 13.5, "end", DARK, bold=True, halo=True))
    b.append(txt(px - 10, 330, "= 125 threads", 13.5, "end", ACCENT, bold=True, halo=True))

    b.append(txt(24, H - 14, "Straight lines through the origin: twice the work per thread, half the threads.",
                 12.5, "start", GRAY, italic=True))
    save("fig-littles-law.svg", W, H, b)

# =====================================================================
# A3 — fabric share (Strix Halo saturation)
# =====================================================================
def fig_fabric_share():
    W, H = 900, 470
    L, R, T, B = 100, 820, 110, 370
    YMAX = 280.0
    def X(v): return L + 10 + (v - 1) / 15.0 * (R - L - 10)
    def Y(g): return B - g / YMAX * (B - T)
    thr = [1, 2, 4, 6, 8, 12, 16]
    gbs = [48.9, 83.5, 113.7, 123.9, 129.6, 137.9, 140.4]
    b = [txt(24, 34, "The fabric saturates well below its own interface", 21, "start", DARK, bold=True)]

    # shaded unreachable gap
    pts = [f"{X(v):.1f},{Y(g):.1f}" for v, g in zip(thr, gbs)]
    pts.append(f"{X(16):.1f},{Y(256):.1f}")
    pts.append(f"{X(1):.1f},{Y(256):.1f}")
    b.append(path("M" + " L".join(pts) + " Z", ACCENT, "none", 0, op=0.10))

    for g in (64, 128, 192):
        b.append(line(L, Y(g), R, Y(g), MID, 1, op=0.35))
    b += [line(L, B, R, B, INK, 2), line(L, T, L, B, INK, 2)]
    for v in thr:
        b.append(line(X(v), B, X(v), B + 6, GRAY, 1.2))
        b.append(txt(X(v), B + 22, str(v), 12, "middle", GRAY))
    for g in (0, 64, 128, 192, 256):
        b.append(line(L - 5, Y(g), L, Y(g), GRAY, 1.2))
        b.append(txt(L - 9, Y(g) + 4, str(g), 12, "end", GRAY))
    b.append(txt(R, B + 46, "concurrent threads", 14, "end", GRAY, italic=True))
    b.append(ylab(64, (T + B) / 2, "GB/s"))

    b.append(line(L, Y(256), R, Y(256), ACCENT, 2, dash="8,5"))
    b.append(txt(R - 4, Y(256) - 8, "memory interface (256 GB/s)", 13, "end", ACCENT, bold=True))
    b.append(line(L, Y(128), R, Y(128), GRAY, 1.6, dash="2,4"))
    b.append(txt(L + 8, Y(128) - 8, "half the interface (128 GB/s)", 12.5, "start", GRAY, italic=True))

    b.append(path("M" + " L".join(f"{X(v):.1f},{Y(g):.1f}" for v, g in zip(thr, gbs)), "none", INK, 3))
    for v, g in zip(thr, gbs):
        b.append(circ(X(v), Y(g), 4, INK))

    b.append(txt(480, 196, "unreachable by the CPU", 14, "middle", ACCENT, bold=True))
    b.append(txt(X(16) - 8, 224, "140.4 GB/s", 13, "end", ACCENT, bold=True, halo=True))
    b.append(txt(24, H - 14, "measured on vampire, copy kernel, 0.5 GiB/thread",
                 12.5, "start", GRAY, italic=True))
    save("fig-fabric-share.svg", W, H, b)

# =====================================================================
# B1 — SIMT
# =====================================================================
def fig_simt():
    W, H = 1100, 540
    b = [txt(24, 34, "SIMT: one PC, sixty-four lanes", 21, "start", DARK, bold=True)]

    # PC -> instruction
    b.append(rect(36, 96, 62, 36, LIGHT, INK, 2, rx=4))
    b.append(txt(67, 120, "PC", 15, "middle", DARK, bold=True))
    b.append(line(98, 114, 296, 114, INK, 2, arrow=True))
    b.append(rect(300, 96, 240, 36, LIGHT, INK, 2, rx=4))
    b.append(txt(420, 120, "V_ADD v1, v2, v3", 14.5, "middle", DARK, bold=True))
    b.append(txt(36, 152, "one PC \u2014", 12.5, "start", GRAY, italic=True))
    b.append(txt(36, 168, "all 64 lanes", 12.5, "start", GRAY, italic=True))

    # instruction fans out to every lane
    b.append(line(420, 132, 420, 152, INK, 2))
    b.append(line(180, 152, 660, 152, INK, 2))
    for bx in (180, 340, 500, 660):
        b.append(line(bx, 152, bx, 196, INK, 1.8, arrow=True))

    # 64 lanes, 2 rows of 32
    for i in range(64):
        row, col = divmod(i, 32)
        x, y = 150 + col * 17, 200 + row * 34
        hl = (i == 16)
        b.append(rect(x, y, 14, 26, ACCENT if hl else LIGHT, ACCENT if hl else INK, 1, rx=1))
    b.append(txt(429, 182, "lane 17", 13, "middle", ACCENT, bold=True))
    b.append(line(429, 186, 429, 198, ACCENT, 1.4, dash="3,3", arrow=True))
    b.append(txt(150, 296, "one wavefront = 64 lanes", 14, "start", DARK, bold=True))
    b.append(txt(150, 318, "the same instruction, 64 different data items",
                 12.5, "start", GRAY, italic=True))

    # what is shared, and what each lane owns
    b.append(rect(150, 348, 500, 80, "#f7fafd", MID, 1.2, rx=4))
    b.append(txt(164, 372, "shared by all 64 lanes", 12.5, "start", DARK, bold=True))
    b.append(txt(164, 392, "the PC, the instruction, the scalar values", 12.5, "start", GRAY, italic=True))
    b.append(txt(164, 412, "per lane: one VGPR column, one data element", 12.5, "start", GRAY, italic=True))

    # register file: one column per lane
    b.append(line(696, 230, 712, 230, INK, 1.8, arrow=True))
    b.append(rect(716, 96, 348, 210, LIGHT, INK, 2, rx=4))
    b.append(txt(730, 120, "VGPR file \u2014 64 columns", 12.5, "start", DARK, bold=True))
    for i in range(64):
        x = 724 + i * 5.3
        hl = (i == 16)
        b.append(rect(x, 132, 4, 164, ACCENT if hl else "#ffffff",
                      ACCENT if hl else MID, 0.6, rx=0.8))
    b.append(txt(720, 324, "one column per lane", 12, "start", GRAY, italic=True))

    # scalar unit
    b.append(rect(716, 344, 348, 82, LIGHT, INK, 2, rx=4))
    b.append(txt(730, 368, "scalar unit", 13.5, "start", DARK, bold=True))
    b.append(txt(730, 390, "base address \u00b7 stride \u00b7 loop counter", 12.5, "start", DARK))
    b.append(txt(730, 412, "one copy, shared", 12.5, "start", ACCENT, italic=True))

    b.append(txt(24, 476, "lane = thread, but no thread has its own PC", 15, "start", ACCENT, bold=True))
    b.append(txt(24, 500, "all 64 lanes run the same instruction; the scalar unit holds what is uniform.",
                 12.5, "start", GRAY, italic=True))
    save("fig-simt.svg", W, H, b)

# =====================================================================
# B2 — divergence
# =====================================================================
def fig_divergence():
    W, H = 1100, 470
    b = [txt(24, 34, "Divergence: the wavefront pays for both paths", 21, "start", DARK, bold=True),
         txt(24, 66, "if (a[i] > 0)", 15, "start", ACCENT, bold=True),
         txt(24, 88, "one wavefront, one branch, 64 lanes", 12.5, "start", GRAY, italic=True)]

    SQ0, PITCH, SW = 230, 9.8, 8.5
    taken = [((i * 37) % 100) < 62 for i in range(64)]

    bands = [(116, "phase 1", "both paths predicated"),
             (196, "phase 2", "then-branch executes"),
             (276, "phase 3", "else-branch executes")]
    for ytop, name, sub in bands:
        b.append(rect(SQ0 - 6, ytop, 638, 26, "#f5f8fc", "none", 0, rx=3))
        b.append(txt(24, ytop + 12, name, 14, "start", DARK, bold=True))
        b.append(txt(24, ytop + 30, sub, 12, "start", GRAY, italic=True))

    OFF = [8, 88, 168]          # square y-offset inside each band (124, 204, 284)
    for i in range(64):
        x = SQ0 + i * PITCH
        live = taken[i]
        # phase 1: both paths predicated, mask shown
        b.append(rect(x, 124, SW, 12, GREEN if live else GRAY, "none", 0, rx=1,
                      op=0.95 if live else 0.75))
        # phase 2: only the taken lanes are active
        b.append(rect(x, 204, SW, 12, GREEN if live else "#eef1f5", "none", 0, rx=1))
        if not live:
            b.append(rect(x, 204, SW, 12, "none", "#d5dbe3", 0.7, rx=1))
        # phase 3: only the masked lanes are active
        b.append(rect(x, 284, SW, 12, "#eef1f5" if live else GRAY, "none", 0, rx=1,
                      op=1.0 if not live else 1.0))
        if live:
            b.append(rect(x, 284, SW, 12, "none", "#d5dbe3", 0.7, rx=1))

    bits = "".join("1" if t else "0" for t in taken)
    groups = " ".join(bits[i:i + 8] for i in range(0, 64, 8))
    b.append(txt(230, 160, "mask", 11, "start", GRAY, bold=True))
    b.append(txt(268, 160, groups, 10.5, "start", GRAY))

    # total time on the right
    b.append(txt(880, 108, "time", 12, "start", GRAY, italic=True))
    b.append(rect(880, 116, 64, 94, GREEN, "none", 0, rx=2))
    b.append(rect(880, 210, 64, 90, GRAY, "none", 0, rx=2))
    b.append(txt(912, 168, "tA", 14, "middle", "#ffffff", bold=True))
    b.append(txt(912, 262, "tB", 14, "middle", "#ffffff", bold=True))
    b.append(line(954, 116, 954, 300, MID, 1.6))
    b.append(line(954, 116, 962, 116, MID, 1.6))
    b.append(line(954, 300, 962, 300, MID, 1.6))
    b.append(txt(972, 198, "tA + tB,", 15, "start", ACCENT, bold=True))
    b.append(txt(972, 222, "not max(tA, tB)", 15, "start", ACCENT, bold=True))
    b.append(txt(880, 316, "one wavefront's time", 11.5, "start", GRAY, italic=True))

    b.append(txt(24, 346, "the wavefront runs both paths one after the other", 14, "start", DARK, bold=True))
    b.append(txt(24, 370, "the mask decides which lanes are live in each pass; the others idle.",
                 12.5, "start", GRAY, italic=True))
    b.append(txt(24, H - 14, "the cost is the sum of both paths \u2014 the SIMT tax on branchy code.",
                 12.5, "start", GRAY, italic=True))
    save("fig-divergence.svg", W, H, b)

# =====================================================================
# B3 — one compute unit
# =====================================================================
def fig_cu():
    W, H = 1100, 580
    b = [txt(24, 34, "One Vega-20 compute unit", 21, "start", DARK, bold=True)]

    b.append(rect(24, 60, 800, 434, "none", MID, 1.6, dash="7,5"))
    b.append(txt(812, 484, "one compute unit", 13, "end", GRAY, bold=True))

    # scalar unit across the top
    b.append(rect(60, 80, 715, 30, LIGHT, INK, 2, rx=4))
    b.append(txt(72, 100, "scalar unit", 13.5, "start", DARK, bold=True))
    b.append(txt(180, 100, "uniform values: base address, stride, loop counter \u2014 one copy, shared",
                 12, "start", GRAY))

    cols = [60, 245, 430, 615]
    for x in cols:
        b.append(rect(x, 130, 160, 34, LIGHT, INK, 2, rx=4))
        b.append(txt(x + 80, 152, "scheduler", 13.5, "middle", DARK, bold=True))
        b.append(line(x + 80, 164, x + 80, 186, INK, 2, arrow=True))
        b.append(rect(x, 190, 160, 62, "#f7fafd", INK, 2, rx=4))
        b.append(txt(x + 80, 218, "SIMD16", 14.5, "middle", DARK, bold=True))
        b.append(txt(x + 80, 238, "16 lanes", 12, "middle", GRAY))
        b.append(line(x + 80, 252, x + 80, 268, INK, 1.6, arrow=True))
        b.append(rect(x, 272, 160, 48, LIGHT, INK, 2, rx=4))
        b.append(txt(x + 80, 300, "64 KB", 13.5, "middle", DARK, bold=True))

    b.append(txt(417, 342, "VGPR file \u2014 256 KB (4 \u00d7 64 KB)", 13.5, "middle", DARK, bold=True))

    b.append(rect(60, 358, 220, 52, LIGHT, INK, 2, rx=4))
    b.append(txt(170, 382, "LDS", 13.5, "middle", DARK, bold=True))
    b.append(txt(170, 400, "64 KB", 12, "middle", GRAY))
    b.append(rect(300, 358, 220, 52, LIGHT, INK, 2, rx=4))
    b.append(txt(410, 382, "L1 vector cache", 13.5, "middle", DARK, bold=True))
    b.append(txt(410, 400, "16 KB", 12, "middle", GRAY))
    b.append(rect(540, 358, 235, 52, "#ffffff", ACCENT, 2, rx=4))
    b.append(txt(657, 382, "64 lanes total", 15, "middle", ACCENT, bold=True))
    b.append(txt(657, 400, "4 \u00d7 SIMD16", 12, "middle", GRAY))

    b.append(line(170, 410, 170, 426, INK, 1.6, arrow=True))
    b.append(line(410, 410, 410, 426, INK, 1.6, arrow=True))
    b.append(rect(60, 428, 715, 36, LIGHT, INK, 2, rx=4))
    b.append(txt(417, 452, "crossbar", 14, "middle", DARK, bold=True))

    b.append(line(779, 446, 876, 446, INK, 2, arrow=True))
    b.append(rect(880, 428, 160, 36, "#f7fafd", INK, 2, rx=4))
    b.append(txt(960, 452, "L2 (4 MB)", 14, "middle", DARK, bold=True))

    b.append(txt(24, 524, "every SIMD16 has its own scheduler; all four share this register file and this LDS.",
                 12.5, "start", GRAY, italic=True))
    save("fig-cu.svg", W, H, b)

# =====================================================================
# C1 — the inverted hierarchy
# =====================================================================
def fig_hierarchy_inverted():
    W, H = 1100, 540
    b = [txt(24, 34, "The hierarchy, inverted", 21, "start", DARK, bold=True)]

    b.append(line(56, 100, 56, 404, MID, 1.6, arrow=True))
    b.append(ylab(36, 252, "latency"))
    b.append(txt(80, 78, "CPU", 15, "start", DARK, bold=True))
    b.append(txt(490, 78, "GPU (MI50)", 15, "start", DARK, bold=True))
    b.append(txt(880, 78, "bandwidth", 12, "start", GRAY, bold=True))

    rows = [100, 180, 260, 340]
    cpu = [(26, "Registers (tiny)", False), (80, "L1 32 KB", True),
           (175, "L2 512 KB", True), (350, "DRAM 32 GB", True)]
    gpu = [(290, "Registers 15.0 MiB", True), (55, "L1 16 KB/CU", False),
           (215, "L2 4 MB", True), (350, "HBM2 32 GB", True)]
    for i, y in enumerate(rows):
        w, lab, inside = cpu[i]
        b.append(rect(80, y, w, 64, LIGHT, INK, 2, rx=3))
        b.append(txt(88, y + 37, lab, 13, "start", DARK, bold=True) if inside
                 else txt(114, y + 37, lab, 13, "start", DARK, bold=True))
        w, lab, inside = gpu[i]
        b.append(rect(490, y, w, 64, LIGHT, INK, 2, rx=3))
        b.append(txt(498, y + 37, lab, 13, "start", DARK, bold=True) if inside
                 else txt(553, y + 37, lab, 13, "start", DARK, bold=True))

    # the punchline: the GPU register block runs past the L2's edge
    b.append(line(705, 96, 705, 332, ACCENT, 1.6, dash="5,4", op=0.75))
    b.append(txt(710, 90, "register file > L2", 13.5, "start", ACCENT, bold=True))

    b.append(line(858, 92, 858, 404, MID, 1, op=0.5))
    b.append(txt(880, 216, "LDS ~20 TB/s", 14, "start", DARK, bold=True))
    b.append(txt(880, 296, "L2 ~5 TB/s", 14, "start", DARK, bold=True))
    b.append(txt(880, 376, "HBM2 1 TB/s", 14, "start", DARK, bold=True))

    b.append(txt(24, 442, "Same four levels, opposite balance.", 14.5, "start", DARK, bold=True))
    b.append(txt(24, 466, "rows line up by level; block width is capacity.",
                 12.5, "start", GRAY, italic=True))
    save("fig-hierarchy-inverted.svg", W, H, b)


# ====================================================================
# Figures from makefigs_b (Part IV-V): card anatomy, PCIe, BARs, the wall
# ====================================================================

def fig_coalescing():
    W, H = 1100, 420
    b = [txt(24, 34, "Coalescing: 64 lanes, how many transactions", 21, "start", DARK, bold=True)]
    x0, pitch, cw, N = 110, 13.0, 10.4, 64
    def LX(i): return x0 + i * pitch
    split = (LX(31) + cw + LX(32)) / 2.0
    gL, gR = x0 - 2, LX(63) + cw + 2

    # ---------------- panel A: coalesced ----------------
    b.append(txt(x0, 82, "coalesced \u2014 addresses 0, 4, 8, \u2026 consecutive", 15, "start", INK, bold=True))
    b.append(txt(x0 - 12, 112, "64 lanes", 13.5, "end", DARK, bold=True))
    for i in range(N):
        b.append(rect(LX(i), 96, cw, 18, LIGHT, INK, 1.0, rx=2))
    for i in range(N):
        b.append(line(LX(i) + cw / 2, 114, LX(i) + cw / 2, 128, MID, 1.0, op=0.8))
    for i in range(N):
        b.append(rect(LX(i), 128, cw, 22, "#ffffff", INK, 1.1, rx=2))
    b.append(rect(gL, 122, split - 1.3 - gL, 34, "none", INK, 2.4, rx=4))
    b.append(rect(split + 1.3, 122, gR - (split + 1.3), 34, "none", INK, 2.4, rx=4))
    for i in (0, 1, 2):
        b.append(txt(LX(i) + cw / 2, 172, str(4 * i), 12.5, "middle", GRAY))
    b.append(txt(x0 - 8, 172, "addr", 11.5, "end", GRAY, italic=True))
    b.append(txt((gL + split - 1.3) / 2, 172, "128 B \u00b7 transaction 0", 13, "middle", DARK, bold=True))
    b.append(txt((split + 1.3 + gR) / 2, 172, "128 B \u00b7 transaction 1", 13, "middle", DARK, bold=True))

    # ---------------- panel B: strided ----------------
    b.append(txt(x0, 222, "strided by 32 \u2014 addresses 0, 32, 64, \u2026", 15, "start", INK, bold=True))
    b.append(txt(x0 - 12, 250, "same 64", 13.5, "end", DARK, bold=True))
    b.append(txt(x0 - 12, 266, "lanes", 13.5, "end", DARK, bold=True))
    for i in range(N):
        b.append(rect(LX(i), 236, cw, 18, LIGHT, INK, 1.0, rx=2))
    for i in range(N):
        b.append(line(LX(i) + cw / 2, 254, LX(i) + cw / 2, 268, MID, 1.0, op=0.8))
    for i in range(N):
        b.append(rect(LX(i), 268, cw, 22, "#ffffff", ACCENT, 1.4, rx=2))
    for k in range(0, 64, 8):
        b.append(txt(LX(k) + cw / 2, 308, str(k), 12.5, "middle", GRAY))
    b.append(txt(x0 - 8, 308, "lane", 11.5, "end", GRAY, italic=True))

    # ---------------- verdicts ----------------
    b.append(txt(1090, 140, "2 transactions", 15, "end", GREEN, bold=True))
    b.append(txt(1090, 282, "64 transactions", 15, "end", ACCENT, bold=True))
    b.append(txt(1090, 356, "16× more traffic", 18, "end", ACCENT, bold=True))
    b.append(txt(24, 396, "each lane reads one 4 B word \u00b7 a transaction is a 128 B cache line",
                 12.5, "start", GRAY, italic=True))
    save("fig-coalescing.svg", W, H, b)

# =====================================================================
# FIG — occupancy
# =====================================================================
def fig_occupancy():
    W, H = 900, 480
    b = [txt(24, 34, "Occupancy is a VGPR budget", 21, "start", DARK, bold=True),
         txt(24, 58, "resident threads against registers per thread", 13, "start", GRAY, italic=True)]
    L, R, T, B = 120, 860, 92, 390
    def X(r): return L + (r - 16) / 112.0 * (R - L)
    def Y(t): return B - t / 160000.0 * (B - T)

    b += [line(L, B, R, B, INK, 2), line(L, T, L, B, INK, 2)]
    for t in (0, 40000, 80000, 120000, 160000):
        b.append(line(L - 5, Y(t), L, Y(t), GRAY, 1.2))
        b.append(txt(L - 9, Y(t) + 4, f"{t // 1000}k" if t else "0", 12, "end", GRAY))
        b.append(line(L, Y(t), R, Y(t), GRAY, 0.8, op=0.22))
    for r in (16, 25, 50, 100, 128):
        b.append(line(X(r), B, X(r), B + 6, GRAY, 1.2))
        b.append(txt(X(r), B + 22, str(r), 12.5, "middle", GRAY))
    b.append(txt((L + R) / 2, B + 46, "VGPRs per thread", 13, "middle", GRAY, italic=True))
    b.append(ylab(L - 40, (T + B) / 2, "resident threads"))

    # staircase: 40 waves per CU cap, 60 CUs x 64 lanes, 1000 = 40 waves x 25 regs
    def thr(r):
        return min(40, int(1024 / r)) * 60 * 64
    pts = [f"M{X(16):.1f},{Y(thr(16)):.1f}"]
    for r in range(16, 128):
        pts.append(f"L{X(r + 1):.1f},{Y(thr(r)):.1f}")
        pts.append(f"L{X(r + 1):.1f},{Y(thr(r + 1)):.1f}")
    b.append(path(" ".join(pts), "none", INK, 2.6))

    for r, val in ((25, "153,600"), (50, "76,800"), (100, "38,400")):
        b.append(line(X(r), B, X(r), Y(thr(r)), ACCENT, 1.6, dash="6,5", op=0.9))
        b.append(circ(X(r), Y(thr(r)), 4.6, ACCENT))
        b.append(txt(X(r) - 8, Y(thr(r)) + 22, val, 13, "end", ACCENT, bold=True, halo=True))
        b.append(txt(X(r) - 8, Y(thr(r)) + 37, f"{r} regs", 11.5, "end", GRAY, italic=True, halo=True))

    b.append(txt(R, 140, "256 KB VGPR / (64 lanes x 4 B x regs)", 13, "end", GRAY, italic=True))
    b.append(txt(R, 160, "one CU's budget sets its waves", 12.5, "end", GRAY, italic=True))
    b.append(txt(24, H - 14, "the steps are wave quantisation \u2014 threads arrive 64 at a time",
                 12.5, "start", GRAY, italic=True))
    save("fig-occupancy.svg", W, H, b)

# =====================================================================
# FIG — VRAM vs GTT
# =====================================================================
def fig_vram_gtt():
    W, H = 1100, 470
    b = [txt(24, 34, "the gap is the bus", 21, "start", DARK, bold=True),
         txt(24, 58, "VRAM bandwidth vs the GTT path, GB/s", 13, "start", GRAY, italic=True)]
    X0, XW, VMAX = 170, 700, 2500.0
    def X(v): return X0 + v / VMAX * XW
    b.append(rect(X0, 74, 26, 12, INK, INK, 1, rx=2))
    b.append(txt(X0 + 32, 85, "VRAM", 12.5, "start", DARK, bold=True))
    b.append(rect(X0 + 96, 76, 26, 8, MID, MID, 1, rx=2))
    b.append(txt(X0 + 128, 85, "GTT path", 12.5, "start", DARK, bold=True))
    b.append(txt(1090, 92, "gap", 12, "end", GRAY, italic=True))

    rows = [("celedyr", 256, 8, "32x", ACCENT),
            ("kraken", 1024, 31.5, "33x", ACCENT),
            ("vampire", 200, 200, "1x", GREEN),
            ("typhon", 2450, 31.5, "78x", ACCENT)]
    for i, (name, vram, gtt, gap, col) in enumerate(rows):
        y = 110 + i * 80
        b.append(txt(X0 - 16, y + 30, name, 14.5, "end", DARK, bold=True))
        w1 = max(5.0, X(vram) - X0)
        w2 = max(5.0, X(gtt) - X0)
        fill1 = GREEN if name == "vampire" else INK
        b.append(rect(X0, y + 6, w1, 18, fill1, fill1, 1, rx=3))
        b.append(rect(X0, y + 30, w2, 12, MID, MID, 1, rx=3))
        b.append(txt(X0 + w1 + 8, y + 20, str(vram), 13.5, "start", fill1, bold=True))
        b.append(txt(X0 + w2 + 8, y + 41, str(gtt), 12.5, "start", GRAY))
        b.append(txt(1090, y + 32, gap, 19, "end", col, bold=True))

    b.append(line(X0, 430, X0 + XW, 430, INK, 2))
    for v in (0, 500, 1000, 1500, 2000, 2500):
        b.append(line(X(v), 430, X(v), 436, GRAY, 1.2))
        b.append(txt(X(v), 450, str(v), 11.5, "middle", GRAY))
    b.append(txt((X0 + X0 + XW) / 2, 466, "GB/s", 13, "middle", GRAY, italic=True))
    b.append(txt(1090, 466, "celedyr is PCIe 2.0 x16; kraken and typhon are PCIe 4.0 x16", 12, "end", GRAY, italic=True))
    save("fig-vram-gtt.svg", W, H, b)

# =====================================================================
# FIG — GPU anatomy
# =====================================================================
def fig_gpu_anatomy():
    W, H = 1140, 550
    b = [txt(24, 34, "Anatomy: one CU, a shader array, the card", 21, "start", DARK, bold=True)]
    PY, PH = 62, 440
    P1X, P1W = 28, 310
    P2X, P2W = 388, 330
    P3X, P3W = 768, 344
    for px, pw in ((P1X, P1W), (P2X, P2W), (P3X, P3W)):
        b.append(rect(px, PY, pw, PH, "#ffffff", INK, 2, rx=8))
    b.append(line(P1X + P1W + 4, PY + 240, P2X - 4, PY + 240, ACCENT, 2.4, arrow=True))
    b.append(txt((P1X + P1W + P2X) / 2, PY + 226, "\u00d716", 15, "middle", ACCENT, bold=True))
    b.append(line(P2X + P2W + 4, PY + 240, P3X - 4, PY + 240, ACCENT, 2.4, arrow=True))
    b.append(txt((P2X + P2W + P3X) / 2, PY + 226, "\u00d74", 15, "middle", ACCENT, bold=True))

    # ---- panel 1: one CU ----
    b.append(txt(P1X + 16, PY + 30, "1 CU", 16, "start", DARK, bold=True))
    for i in range(4):
        y = PY + 52 + i * 46
        b.append(rect(P1X + 12, y, 54, 32, LIGHT, INK, 1.6, rx=3))
        b.append(txt(P1X + 39, y + 21, "sched", 11.5, "middle", DARK))
        b.append(rect(P1X + 72, y, 226, 32, "#ffffff", INK, 1.6, rx=3))
        b.append(txt(P1X + 185, y + 21, "SIMD16 \u00b7 16 lanes", 12.5, "middle", DARK, bold=True))
        b.append(line(P1X + 68, y + 16, P1X + 70, y + 16, INK, 1.4, arrow=True))
    b.append(rect(P1X + 12, PY + 246, 286, 38, LIGHT, INK, 1.8, rx=3))
    b.append(txt(P1X + 155, PY + 271, "VGPR file 256 KB", 13, "middle", DARK, bold=True))
    b.append(rect(P1X + 12, PY + 292, 138, 34, "#ffffff", INK, 1.6, rx=3))
    b.append(txt(P1X + 81, PY + 314, "LDS 64 KB", 12.5, "middle", DARK))
    b.append(rect(P1X + 160, PY + 292, 138, 34, "#ffffff", INK, 1.6, rx=3))
    b.append(txt(P1X + 229, PY + 314, "L1 16 KB", 12.5, "middle", DARK))
    b.append(rect(P1X + 12, PY + 334, 286, 32, "#ffffff", INK, 1.6, rx=3))
    b.append(txt(P1X + 155, PY + 356, "scalar unit", 12.5, "middle", DARK))
    b.append(txt(P1X + 155, PY + 396, "64 lanes total", 13, "middle", ACCENT, bold=True))
    b.append(txt(P1X + 155, PY + 418, "4 SIMD16, one scheduler each", 12, "middle", GRAY, italic=True))

    # ---- panel 2: one shader array ----
    b.append(txt(P2X + 16, PY + 30, "one shader array", 16, "start", DARK, bold=True))
    b.append(txt(P2X + 16, PY + 48, "16 CUs", 12.5, "start", GRAY, italic=True))
    gx, gy = P2X + 16, PY + 58
    for r in range(2):
        for c in range(8):
            b.append(rect(gx + c * 29, gy + r * 24, 26, 20, LIGHT, INK, 1.0, rx=2))
    b.append(line(gx + 143, gy + 64, gx + 143, PY + 224, INK, 1.6, arrow=True))
    b.append(rect(gx, PY + 226, 287, 44, "#ffffff", INK, 2, rx=4))
    b.append(txt(gx + 143, PY + 254, "L2  4 MB", 14, "middle", DARK, bold=True))
    b.append(txt(P2X + 16, PY + 300, "16 CUs, all sharing one L2", 12, "start", GRAY, italic=True))
    b.append(txt(P2X + 16, PY + 318, "and one path to HBM2", 12, "start", GRAY, italic=True))
    b.append(txt(P2X + 16, PY + 348, "1,024 lanes", 13, "start", ACCENT, bold=True))

    # ---- panel 3: the card ----
    b.append(txt(P3X + 16, PY + 30, "the card", 16, "start", DARK, bold=True))
    for r in range(2):
        for c in range(2):
            b.append(rect(P3X + 14 + c * 158, PY + 42 + r * 68, 150, 60, LIGHT, INK, 1.8, rx=4))
            b.append(txt(P3X + 89 + c * 158, PY + 78 + r * 68, "shader array", 12.5, "middle", DARK, bold=True))
    for c in range(8):
        b.append(rect(P3X + 14 + c * 40, PY + 188, 36, 32, "#ffffff", INK, 1.4, rx=2))
    b.append(txt(P3X + 172, PY + 240, "8 HBM2 controllers", 12.5, "middle", DARK, bold=True))
    b.append(rect(P3X + 14, PY + 252, 160, 32, "#ffffff", INK, 1.6, rx=3))
    b.append(txt(P3X + 94, PY + 273, "command processor", 11.5, "middle", DARK))
    b.append(rect(P3X + 184, PY + 252, 70, 32, "#ffffff", INK, 1.6, rx=3))
    b.append(txt(P3X + 219, PY + 273, "copy engine", 10.5, "middle", DARK))
    b.append(rect(P3X + 260, PY + 252, 70, 32, "#ffffff", INK, 1.6, rx=3))
    b.append(txt(P3X + 295, PY + 273, "copy engine", 10.5, "middle", DARK))
    b.append(rect(P3X + 14, PY + 292, 148, 30, "#ffffff", INK, 1.6, rx=3))
    b.append(txt(P3X + 88, PY + 312, "display", 12, "middle", DARK))
    b.append(rect(P3X + 172, PY + 292, 158, 30, "#ffffff", INK, 1.6, rx=3))
    b.append(txt(P3X + 251, PY + 312, "video engine", 12, "middle", DARK))
    b.append(txt(P3X + 172, PY + 352, "4 arrays \u00b7 60 CUs of 64", 12, "middle", ACCENT, bold=True))
    b.append(txt(P3X + 172, PY + 372, "one die, one memory system", 12, "middle", GRAY, italic=True))
    b.append(txt(P3X + 172, PY + 390, "and two copies of the bus", 12, "middle", GRAY, italic=True))

    b.append(txt(W / 2, 530, "a GPU is a SoC, not a big ALU", 18, "middle", ACCENT, bold=True))
    save("fig-gpu-anatomy.svg", W, H, b)

# =====================================================================
# FIG — PCIe topology (2x2)
# =====================================================================
def fig_pcie_topology():
    W, H = 1140, 620
    b = [txt(24, 34, "PCIe topology: four machines, four shapes", 21, "start", DARK, bold=True)]
    PW, PH = 540, 240
    spots = [(28, 72), (572, 72), (28, 326), (572, 326)]
    for px, py in spots:
        b.append(rect(px, py, PW, PH, "#ffffff", INK, 2, rx=8))

    # ---- 1. sg2000: one die, one bus ----
    px, py = spots[0]
    b.append(txt(px + 16, py + 30, "sg2000", 16, "start", DARK, bold=True))
    b.append(txt(px + PW - 16, py + 30, "one die", 12, "end", GRAY, italic=True))
    b.append(rect(px + 14, py + 42, 512, 170, LIGHT, INK, 2, rx=6, op=0.55))
    BUSY = py + 150
    b.append(line(px + 30, BUSY, px + 510, BUSY, INK, 3))
    b.append(txt(px + 34, BUSY + 20, "memory-mapped bus", 12, "start", GRAY, italic=True))
    for i, lab in enumerate(("CPU", "TPU", "VPU", "ISP")):
        bx = px + 36 + i * 120
        b.append(rect(bx, py + 58, 104, 36, "#ffffff", INK, 1.8, rx=4))
        b.append(txt(bx + 52, py + 81, lab, 13, "middle", DARK, bold=True))
        b.append(line(bx + 52, py + 94, bx + 52, BUSY - 2, INK, 1.6))
    b.append(txt(px + 16, py + 228, "no bus \u2014 everything on-die", 12.5, "start", GRAY, italic=True))

    # ---- 2. celedyr: one slot ----
    px, py = spots[1]
    b.append(txt(px + 16, py + 30, "celedyr", 16, "start", DARK, bold=True))
    cy = py + 92
    for i, lab in enumerate(("root complex", "PCIe slot", "Polaris 10")):
        bx = px + 26 + i * 170
        b.append(rect(bx, cy, 136, 56, LIGHT if i == 0 else "#ffffff", INK, 2, rx=5))
        b.append(txt(bx + 68, cy + 34, lab, 12.5, "middle", DARK, bold=(i == 2)))
    b.append(line(px + 164, cy + 28, px + 192, cy + 28, ACCENT, 2, arrow=True))
    b.append(line(px + 334, cy + 28, px + 362, cy + 28, ACCENT, 2, arrow=True))
    b.append(txt(px + 270, cy + 78, "one card, one link", 12, "middle", GRAY, italic=True))
    b.append(txt(px + 16, py + 228, "1 slot", 12.5, "start", GRAY, italic=True))

    # ---- 3. kraken: four root complexes ----
    px, py = spots[2]
    b.append(txt(px + 16, py + 30, "kraken", 16, "start", DARK, bold=True))
    for i in range(4):
        cx = px + 19 + i * 130
        b.append(rect(cx, py + 52, 112, 44, LIGHT, INK, 1.8, rx=4))
        b.append(txt(cx + 56, py + 70, "root", 11.5, "middle", DARK))
        b.append(txt(cx + 56, py + 85, "complex", 11.5, "middle", DARK))
        b.append(line(cx + 56, py + 96, cx + 56, py + 146, INK, 1.8, arrow=True))
        b.append(rect(cx, py + 150, 112, 44, "#ffffff", INK, 2, rx=4))
        b.append(txt(cx + 56, py + 177, "GPU", 13, "middle", DARK, bold=True))
    b.append(txt(px + 16, py + 228, "4 root complexes \u2014 no switches", 12.5, "start", GRAY, italic=True))

    # ---- 4. typhon: 2 sockets x 2 switches x 2 cards ----
    px, py = spots[3]
    b.append(txt(px + 16, py + 30, "typhon", 16, "start", DARK, bold=True))
    for s in range(2):
        sx = px + 16 + s * 256
        fill = LIGHT if s == 0 else "#fdece4"
        b.append(rect(sx, py + 42, 252, 168, fill, INK, 2, rx=6, op=0.75))
        b.append(txt(sx + 10, py + 62, f"NUMA {s}", 13, "start", DARK, bold=True))
        for k in range(2):
            wx = sx + 8 + k * 118
            b.append(rect(wx, py + 72, 118, 118, "#ffffff", INK, 1.8, rx=4))
            b.append(txt(wx + 59, py + 90, "PMC-Sierra", 11, "middle", DARK, bold=True))
            b.append(txt(wx + 59, py + 103, "switch", 11, "middle", DARK))
            for c in range(2):
                b.append(rect(wx + 8, py + 112 + c * 32, 102, 26, "#ffffff", ACCENT, 1.4, rx=3))
                b.append(txt(wx + 59, py + 129 + c * 32, "Gaudi2", 11.5, "middle", DARK, bold=True))
    b.append(txt(px + 16, py + 228, "2 sockets x 2 switches x 2 cards", 12.5, "start", GRAY, italic=True))

    b.append(txt(W / 2, 604, "a shared bus cannot be a tree", 18, "middle", ACCENT, bold=True))
    save("fig-pcie-topology.svg", W, H, b)

# =====================================================================
# FIG — BAR windows
# =====================================================================
def fig_bar_windows():
    W, H = 1100, 580
    b = [txt(24, 34, "What the host can actually see", 21, "start", DARK, bold=True),
         txt(24, 58, "card memory against the window the host can map", 13, "start", GRAY, italic=True)]
    X0, BW = 150, 500
    rows = [("celedyr", "4 GiB", 4.0, "256 MiB", 0.25, ACCENT, "6%", GRAY, "you page through it"),
            ("unicorn", "8 GiB", 8.0, "256 MiB", 0.25, ACCENT, "3%", ACCENT, "same window, seven years later"),
            ("pegasus", "32 GiB", 32.0, "32 GiB", 32.0, GREEN, "100%", GREEN, "resizable BAR on"),
            ("kraken", "32 GiB", 32.0, "32 GiB", 32.0, GREEN, "100%", GREEN, "point straight at it"),
            ("typhon", "96 GiB", 96.0, "128 GiB", 128.0, ACCENT, "133%", ACCENT,
             "the BAR maps a computer, not a memory"),
            ("vampire", "16 GiB", 16.0, "16 GiB", 16.0, GREEN, "100%", GREEN, "carveout + GTT")]
    for i, (name, mlab, mem, wlab, win, col, pct, pcol, note) in enumerate(rows):
        y = 84 + i * 78
        b.append(txt(X0 - 10, y + 30, name, 14.5, "end", DARK, bold=True))
        scale = max(mem, win)
        wm = max(4.0, mem / scale * BW)
        ww = max(14.0, win / scale * BW)
        b.append(rect(X0, y + 6, wm, 20, LIGHT, INK, 1.6, rx=3))
        b.append(rect(X0, y + 34, ww, 16, col, col, 1.4, rx=3, op=0.85))
        b.append(txt(X0 + wm + 8, y + 21, mlab, 13, "start", DARK, bold=True))
        b.append(txt(X0 + ww + 8, y + 47, f"{wlab} \u00b7 {pct}", 13, "start", pcol,
                     bold=(pcol == ACCENT)))
        b.append(txt(790, y + 30, note, 13, "start", col, bold=True))
    b.append(txt(24, 550, "upper bar: card memory  \u00b7  lower bar: the window the host can map"
                          "  \u00b7  % = window / memory", 12.5, "start", GRAY, italic=True))
    b.append(txt(24, 570, "each row is scaled to its own larger bar \u2014 read each pair, not across rows",
                 12.5, "start", GRAY, italic=True))
    save("fig-bar-windows.svg", W, H, b)

# =====================================================================
# FIG — bandwidth wall
# =====================================================================
def fig_bandwidth_wall():
    W, H = 1100, 540
    b = [txt(24, 34, "The bandwidth wall", 21, "start", DARK, bold=True),
         txt(24, 58, "everything a GPU can reach, GB/s, on a log scale", 13, "start", GRAY, italic=True)]
    X0, BW, DEC = 300, 660, 7.0      # axis covers 0.01 .. 100,000 GB/s
    def X(v): return X0 + (math.log10(v) + 2) / DEC * BW
    rows = [("LDS", 20000, "~20,000", INK),
            ("L2", 5000, "~5,000", INK),
            ("HBM2 (MI50)", 1024, "1,024", INK),
            ("LPDDR5X fabric (vampire)", 256, "256", MID),
            ("CPU's share of that fabric", 140, "140", ACCENT),
            ("PCIe 4.0 x16", 31.5, "31.5", RED),
            ("PCIe 3.0 x16", 15.75, "15.75", RED),
            ("USB 2.0", 0.06, "0.06", GRAY)]
    for v in (0.1, 1, 10, 100, 1000, 10000):
        b.append(line(X(v), 80, X(v), 456, GRAY, 1.0, op=0.25))
    for i, (lab, v, vs, col) in enumerate(rows):
        y = 84 + i * 47
        w = max(3.0, X(v) - X0)
        b.append(txt(X0 - 10, y + 25, lab, 13.5, "end", DARK, bold=(col in (INK, ACCENT, RED))))
        b.append(rect(X0, y + 8, w, 26, col, col, 1.2, rx=3, op=0.9))
        b.append(txt(X0 + w + 8, y + 27, vs, 13.5, "start", col, bold=True))
    b.append(line(X0, 80, X0, 456, INK, 2))
    b.append(line(X0, 456, X0 + BW, 456, INK, 2))
    for v, lab in ((0.1, "0.1"), (1, "1"), (10, "10"), (100, "100"), (1000, "1k"), (10000, "10k")):
        b.append(line(X(v), 456, X(v), 462, GRAY, 1.2))
        b.append(txt(X(v), 478, lab, 12, "middle", GRAY))
    b.append(txt(X0 + BW, 500, "GB/s \u2014 each tick is 10x", 12.5, "end", GRAY, italic=True))
    b.append(txt(24, 500, "HBM2 : PCIe3 x16 = 64x", 14, "start", ACCENT, bold=True))
    b.append(txt(24, 522, "PCIe3 x16 : USB2 = 262x", 14, "start", ACCENT, bold=True))
    save("fig-bandwidth-wall.svg", W, H, b)


if __name__ == "__main__":
    fig_two_bets()
    fig_littles_law()
    fig_fabric_share()
    fig_simt()
    fig_divergence()
    fig_cu()
    fig_hierarchy_inverted()
    fig_coalescing()
    fig_occupancy()
    fig_vram_gtt()
    fig_gpu_anatomy()
    fig_pcie_topology()
    fig_bar_windows()
    fig_bandwidth_wall()
