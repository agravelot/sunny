#!/usr/bin/env python3
"""Generate Sunny brand assets (SVG sources + Home Assistant brand PNGs).

Run from the repository root:

    python3 assets/generate_brand.py

Requires ``rsvg-convert`` (librsvg). See AGENTS.md for the project layout.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
BRAND = ROOT / "custom_components" / "sunny" / "brand"

FONT = "Inter, 'Fira Sans', 'Liberation Sans', sans-serif"

ICON_W = ICON_H = 512

ICON_LIGHT = dict(
    sky_top="#38BDF8",
    sky_bottom="#0284C7",
    frame="#FFFFFF",
    glass="#FFFFFF",
    glass_opacity="0.12",
    slat="#FFFFFF",
    slat_opacity="0.92",
    ray="#FDE68A",
)

ICON_DARK = dict(
    sky_top="#0F172A",
    sky_bottom="#1E3A8A",
    frame="#F8FAFC",
    glass="#93C5FD",
    glass_opacity="0.10",
    slat="#E2E8F0",
    slat_opacity="0.95",
    ray="#FCD34D",
)


def icon_svg(*, dark: bool) -> str:
    c = ICON_DARK if dark else ICON_LIGHT
    # Window frame geometry
    fx, fy, fw, fh, fr = 120, 120, 272, 272, 34
    stroke = 18
    ix, iy = fx + stroke / 2, fy + stroke / 2
    iw, ih = fw - stroke, fh - stroke
    ir = fr - stroke / 2

    # Blind slats (cover the upper part of the glass)
    slat_x, slat_w, slat_h, step = 138, 236, 15, 22
    slats = "".join(
        f'<rect x="{slat_x}" y="{141 + i * step}" width="{slat_w}" '
        f'height="{slat_h}" rx="6" fill="{c["slat"]}" '
        f'opacity="{c["slat_opacity"]}"/>'
        for i in range(4)
    )
    # Bottom rail of the blind
    rail = (
        f'<rect x="136" y="226" width="240" height="16" rx="8" '
        f'fill="{c["slat"]}" opacity="{c["slat_opacity"]}"/>'
    )

    # Sun sitting in the clear lower pane
    sun_cx, sun_cy, sun_r = 256, 316, 62
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{ICON_W}" height="{ICON_H}" viewBox="0 0 {ICON_W} {ICON_H}">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{c["sky_top"]}"/>
      <stop offset="1" stop-color="{c["sky_bottom"]}"/>
    </linearGradient>
    <radialGradient id="sun" cx="0.42" cy="0.38" r="0.75">
      <stop offset="0" stop-color="#FEF9C3"/>
      <stop offset="0.55" stop-color="#FACC15"/>
      <stop offset="1" stop-color="#F59E0B"/>
    </radialGradient>
    <filter id="glow" x="-80%" y="-80%" width="260%" height="260%">
      <feGaussianBlur stdDeviation="24"/>
    </filter>
    <clipPath id="window"><rect x="{ix}" y="{iy}" width="{iw}" height="{ih}" rx="{ir}"/></clipPath>
    <clipPath id="badge"><rect x="0" y="0" width="{ICON_W}" height="{ICON_H}" rx="112"/></clipPath>
  </defs>
  <g clip-path="url(#badge)">
    <rect width="{ICON_W}" height="{ICON_H}" fill="url(#sky)"/>
    <g clip-path="url(#window)">
      <circle cx="{sun_cx}" cy="{sun_cy}" r="{sun_r + 18}" fill="{c["ray"]}"
              opacity="0.9" filter="url(#glow)"/>
      <circle cx="{sun_cx}" cy="{sun_cy}" r="{sun_r}" fill="url(#sun)"/>
      <circle cx="{sun_cx}" cy="{sun_cy}" r="{sun_r}" fill="none"
              stroke="#FFFFFF" stroke-opacity="0.35" stroke-width="6"/>
      <rect x="{ix}" y="{iy}" width="{iw}" height="{ih}" fill="{c["glass"]}" opacity="{c["glass_opacity"]}"/>
      {slats}
      {rail}
    </g>
    <rect x="{fx}" y="{fy}" width="{fw}" height="{fh}" rx="{fr}" fill="none"
          stroke="{c["frame"]}" stroke-width="{stroke}"/>
  </g>
</svg>
"""


def logo_svg(*, dark: bool) -> str:
    width, height = 1200, 320
    badge = icon_svg(dark=dark)
    # Strip the outer <svg> wrapper of the icon so it can be embedded and scaled.
    inner = badge.split(">", 1)[1].rsplit("</svg>", 1)[0]
    title = "#F1F5F9" if dark else "#0F172A"
    subtitle = "#94A3B8" if dark else "#64748B"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <g transform="scale(0.625)">{inner}</g>
  <text x="372" y="178" font-family={FONT!r} font-size="140" font-weight="800"
        letter-spacing="-4" fill="{title}">Sunny</text>
  <text x="376" y="238" font-family={FONT!r} font-size="36" font-weight="500"
        fill="{subtitle}">Solar-driven blinds for Home Assistant</text>
</svg>
"""


def render(svg_path: Path, png_path: Path, width: int, height: int) -> None:
    subprocess.run(
        ["rsvg-convert", "-w", str(width), "-h", str(height), str(svg_path), "-o", str(png_path)],
        check=True,
    )
    print(f"  {png_path.relative_to(ROOT)}  ({width}x{height})")


def main() -> int:
    if shutil.which("rsvg-convert") is None:
        print("error: rsvg-convert not found (install librsvg2-bin)", file=sys.stderr)
        return 1

    ASSETS.mkdir(exist_ok=True)
    BRAND.mkdir(parents=True, exist_ok=True)

    sources = {
        "icon.svg": icon_svg(dark=False),
        "icon-dark.svg": icon_svg(dark=True),
        "logo.svg": logo_svg(dark=False),
        "logo-dark.svg": logo_svg(dark=True),
    }
    for name, svg in sources.items():
        (ASSETS / name).write_text(svg, encoding="utf-8")
        print(f"  assets/{name}")

    print("Rendering Home Assistant brand images:")
    render(ASSETS / "icon.svg", BRAND / "icon.png", 256, 256)
    render(ASSETS / "icon.svg", BRAND / "icon@2x.png", 512, 512)
    render(ASSETS / "icon-dark.svg", BRAND / "dark_icon.png", 256, 256)
    render(ASSETS / "icon-dark.svg", BRAND / "dark_icon@2x.png", 512, 512)
    render(ASSETS / "logo.svg", BRAND / "logo.png", 960, 256)
    render(ASSETS / "logo.svg", BRAND / "logo@2x.png", 1920, 512)
    render(ASSETS / "logo-dark.svg", BRAND / "dark_logo.png", 960, 256)
    render(ASSETS / "logo-dark.svg", BRAND / "dark_logo@2x.png", 1920, 512)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())