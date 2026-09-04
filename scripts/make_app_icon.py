#!/usr/bin/env python3
"""Draw the shop mark as PNG + ICO for the Mac/Windows app."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

FOREST = (30, 77, 58, 255)
FOREST_DEEP = (22, 56, 43, 255)
CREAM = (247, 243, 234, 255)
GOLD = (196, 161, 90, 255)


def render_app_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = max(1, round(size * 0.04))
    radius = max(4, round(size * 0.22))
    box = [margin, margin, size - 1 - margin, size - 1 - margin]
    draw.rounded_rectangle(box, radius=radius, fill=FOREST)
    inner = max(2, round(size * 0.08))
    draw.rounded_rectangle(
        [margin + inner, margin + inner, size - 1 - margin - inner, size - 1 - margin - inner],
        radius=max(2, radius - inner),
        outline=FOREST_DEEP,
        width=max(1, size // 48),
    )
    stem_w = max(2, round(size * 0.14))
    bar_h = max(2, round(size * 0.12))
    top = round(size * 0.26)
    bottom = round(size * 0.74)
    left = round(size * 0.28)
    right = round(size * 0.72)
    cx = size // 2
    draw.rounded_rectangle([left, top, right, top + bar_h], radius=bar_h // 2, fill=CREAM)
    draw.rounded_rectangle(
        [cx - stem_w // 2, top, cx + stem_w // 2, bottom],
        radius=stem_w // 2,
        fill=CREAM,
    )
    gold_y = round(size * 0.80)
    gold_h = max(2, round(size * 0.045))
    draw.rounded_rectangle(
        [round(size * 0.32), gold_y, round(size * 0.68), gold_y + gold_h],
        radius=gold_h // 2,
        fill=GOLD,
    )
    return img


def write_icons(dest_dir: Path) -> tuple[Path, Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    png_path = dest_dir / "app-icon.png"
    ico_path = dest_dir / "app-icon.ico"
    hero = render_app_icon(1024)
    hero.save(png_path, format="PNG")
    hero.save(
        ico_path,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    return png_path, ico_path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    png, ico = write_icons(root / "assets")
    print(png)
    print(ico)


if __name__ == "__main__":
    main()
