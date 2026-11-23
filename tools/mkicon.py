#!/usr/bin/env python3
"""App icon: two circular arrows (as in the UntrashOS logo) around the three nodes of a mesh.

  tools/mkicon.py untrash/img   writes app.svg (white, header) and app-dark.svg (dark, settings)
"""
import math, sys
def icon(color):
    c, r, w = 16.0, 12.6, 2.6
    def pt(a, rad=r): return (c + rad*math.cos(math.radians(a)), c + rad*math.sin(math.radians(a)))
    parts = []
    for a0, a1 in ((165, 290), (345, 110)):            # two arcs, clockwise, gaps for the heads
        x0, y0 = pt(a0); x1, y1 = pt(a1)
        parts.append('<path d="M%.2f %.2fA%.1f %.1f 0 0 1 %.2f %.2f" fill="none" stroke="%s" stroke-width="%.1f" stroke-linecap="round"/>'
                     % (x0, y0, r, r, x1, y1, color, w))
        t = math.radians(a1 + 14)                       # arrow tip a bit further along the circle
        tip = pt(a1 + 16)
        n = (math.cos(math.radians(a1)), math.sin(math.radians(a1)))
        b1 = (x1 + n[0]*3.6, y1 + n[1]*3.6); b2 = (x1 - n[0]*3.6, y1 - n[1]*3.6)
        parts.append('<path d="M%.2f %.2fL%.2f %.2fL%.2f %.2fZ" fill="%s"/>' % (tip[0], tip[1], b1[0], b1[1], b2[0], b2[1], color))
    nodes = [(16, 10.2), (11.0, 19.0), (21.0, 19.0)]
    parts.append('<path d="M16 10.2L11 19L21 19Z" fill="none" stroke="%s" stroke-width="1.6" stroke-linejoin="round"/>' % color)
    for x, y in nodes:
        parts.append('<circle cx="%.1f" cy="%.1f" r="2.7" fill="%s"/>' % (x, y, color))
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">' + ''.join(parts) + '</svg>\n'
if __name__ == "__main__":
    out = sys.argv[1]
    open(out + "/app.svg", "w").write(icon("#fff"))
    open(out + "/app-dark.svg", "w").write(icon("#000"))
