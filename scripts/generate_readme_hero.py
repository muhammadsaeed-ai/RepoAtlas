"""Generate the animated README hero for RepoAtlas."""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1000, 430
OUTPUT = Path("assets/readme/readme-hero.gif")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


def font(size: int, *, bold: bool = False, mono: bool = False) -> ImageFont.ImageFont:
    path = MONO if mono else (BOLD if bold else FONT)
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def rounded(draw: ImageDraw.ImageDraw, coords: tuple[int, int, int, int], radius: int, fill: tuple[int, ...], outline: tuple[int, ...] | None = None, width: int = 1) -> None:
    draw.rounded_rectangle(coords, radius=radius, fill=fill, outline=outline, width=width)


def create_frame(frame: int) -> Image.Image:
    phase = frame / 9
    image = Image.new("RGB", (WIDTH, HEIGHT), (5, 10, 22))
    pixels = image.load()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            glow = max(0.0, 1.0 - math.sqrt(((x - 840) / 520) ** 2 + ((y - 40) / 350) ** 2))
            glow2 = max(0.0, 1.0 - math.sqrt(((x - 260) / 420) ** 2 + ((y - 430) / 350) ** 2))
            pixels[x, y] = (
                int(5 + 6 * glow + 3 * glow2),
                int(10 + 15 * glow + 4 * glow2),
                int(22 + 26 * glow + 18 * glow2),
            )
    draw = ImageDraw.Draw(image, "RGBA")
    for x in range(0, WIDTH, 28):
        draw.line((x, 0, x, HEIGHT), fill=(65, 110, 160, 18), width=1)
    for y in range(0, HEIGHT, 28):
        draw.line((0, y, WIDTH, y), fill=(65, 110, 160, 18), width=1)

    rounded(draw, (28, 22, 72, 66), 12, (8, 37, 61, 255), (41, 217, 247, 210), 2)
    for y, x2 in ((36, 59), (44, 60), (52, 54)):
        draw.line((39, y, x2, y), fill=(81, 226, 255, 255), width=3)
    draw.text((87, 22), "Repo", font=font(28, bold=True), fill=(242, 248, 255, 255))
    draw.text((153, 22), "Atlas", font=font(28, bold=True), fill=(57, 220, 250, 255))
    draw.text((89, 52), "PYTHON REPOSITORY INTELLIGENCE", font=font(10, bold=True), fill=(130, 172, 210, 255))
    rounded(draw, (805, 28, 970, 58), 15, (12, 37, 54, 240), (45, 180, 199, 200), 1)
    draw.ellipse((820, 39, 828, 47), fill=(56, 224, 177, 255))
    draw.text((838, 35), "LOCAL-FIRST ANALYSIS", font=font(10, bold=True), fill=(196, 235, 246, 255))

    draw.text((30, 91), "See how your codebase", font=font(29, bold=True), fill=(244, 248, 255, 255))
    draw.text((30, 126), "actually connects.", font=font(29, bold=True), fill=(65, 219, 250, 255))
    draw.text((32, 166), "Scan modules  /  Trace imports  /  Find cycles  /  Export maps", font=font(13), fill=(150, 177, 207, 255))

    rounded(draw, (30, 207, 475, 385), 15, (6, 16, 31, 250), (41, 77, 112, 240), 1)
    rounded(draw, (30, 207, 475, 238), 15, (14, 33, 55, 255), (41, 77, 112, 240), 1)
    draw.rectangle((30, 224, 475, 238), fill=(14, 33, 55, 255))
    for x, color in ((48, (255, 113, 133, 255)), (63, (255, 207, 105, 255)), (78, (69, 226, 177, 255))):
        draw.ellipse((x, 218, x + 7, 225), fill=color)
    draw.text((98, 214), "repoatlas  /  scan .", font=font(11, bold=True, mono=True), fill=(187, 211, 234, 255))
    logs = [
        ("> repoatlas scan . --output atlas.json", (106, 221, 255, 255)),
        ("✓  Repository indexed", (75, 231, 189, 255)),
        ("✓  Python AST parsed", (75, 231, 189, 255)),
        ("✓  Import graph assembled", (75, 231, 189, 255)),
        ("✓  Cycle analysis complete", (75, 231, 189, 255)),
    ]
    show = max(1, min(5, math.ceil(phase * 5)))
    for index, (label, color) in enumerate(logs[:show]):
        draw.text((48, 253 + index * 23), label, font=font(11, mono=True), fill=color)

    progress = frame / 9
    bar_x, bar_y, bar_w = 48, 368, 409
    rounded(draw, (bar_x, bar_y, bar_x + bar_w, bar_y + 5), 3, (26, 48, 69, 255))
    rounded(draw, (bar_x, bar_y, bar_x + max(5, int(bar_w * progress)), bar_y + 5), 3, (54, 220, 249, 255))
    if frame < 8:
        scan_x = bar_x + int(bar_w * progress)
        draw.line((scan_x, bar_y - 5, scan_x, bar_y + 10), fill=(120, 245, 255, 220), width=2)

    rounded(draw, (495, 91, 970, 385), 17, (7, 17, 32, 250), (40, 79, 116, 245), 1)
    rounded(draw, (495, 91, 970, 126), 17, (13, 31, 52, 255), (40, 79, 116, 245), 1)
    draw.rectangle((495, 111, 970, 126), fill=(13, 31, 52, 255))
    draw.text((516, 102), "EXAMPLE DEPENDENCY MAP", font=font(11, bold=True), fill=(197, 224, 242, 255))
    draw.text((947, 102), "SVG PREVIEW", font=font(9, bold=True), fill=(103, 211, 242, 255), anchor="ra")

    nodes = {
        "app.py": (555, 179, (36, 212, 244)),
        "core.py": (725, 166, (49, 220, 245)),
        "render.py": (878, 210, (159, 131, 255)),
        "users.py": (590, 285, (72, 222, 187)),
        "billing.py": (770, 303, (255, 151, 126)),
        "atlas.json": (879, 320, (82, 197, 255)),
    }
    edges = [
        ("app.py", "core.py"), ("app.py", "users.py"), ("core.py", "render.py"),
        ("users.py", "billing.py"), ("billing.py", "users.py"), ("core.py", "atlas.json"),
        ("render.py", "atlas.json"), ("billing.py", "atlas.json"),
    ]
    for index, (source, target) in enumerate(edges):
        ax, ay, _ = nodes[source]
        bx, by, _ = nodes[target]
        draw.line((ax, ay, bx, by), fill=(61, 164, 208, 150), width=2)
        progress_t = (phase * 1.6 + index * 0.127) % 1.0
        dot_x, dot_y = ax + (bx - ax) * progress_t, ay + (by - ay) * progress_t
        draw.ellipse((dot_x - 3, dot_y - 3, dot_x + 3, dot_y + 3), fill=(105, 244, 255, 245))

    for name, (cx, cy, color) in nodes.items():
        pulse = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(frame * 0.55 + cx))
        alpha = int(70 * pulse)
        draw.ellipse((cx - 22, cy - 22, cx + 22, cy + 22), fill=(*color, alpha))
        rounded(draw, (cx - 43, cy - 16, cx + 43, cy + 16), 8, (10, 31, 51, 255), (*color, 230), 2 if pulse > 0.8 else 1)
        draw.text((cx, cy), name, font=font(10, bold=True, mono=True), fill=(234, 245, 255, 255), anchor="mm")

    if frame >= 4:
        rounded(draw, (515, 340, 663, 367), 13, (54, 27, 39, 240), (255, 137, 155, 220), 1)
        draw.ellipse((527, 349, 536, 358), fill=(255, 137, 155, 255))
        draw.text((543, 347), "CYCLE SIGNAL", font=font(9, bold=True), fill=(255, 207, 215, 255))

    status = "MAPPING RELATIONSHIPS" if frame < 4 else ("CHECKING CYCLES" if frame < 6 else "EXPORTS READY")
    status_color = (96, 217, 245, 255) if frame < 6 else (83, 232, 186, 255)
    rounded(draw, (692, 340, 952, 367), 13, (11, 34, 48, 245), (50, 111, 131, 230), 1)
    if frame >= 6:
        draw.ellipse((706, 349, 716, 359), fill=(75, 229, 183, 255))
    else:
        draw.ellipse((706, 349, 716, 359), outline=(96, 217, 245, 255), width=2)
    draw.text((725, 347), status, font=font(9, bold=True), fill=status_color)

    draw.text((31, 402), "STATIC ANALYSIS  ·  NO TARGET CODE EXECUTION  ·  NO NETWORK UPLOADS", font=font(10, bold=True), fill=(104, 140, 174, 255))
    draw.text((969, 402), "JSON  /  MD  /  MMD  /  SVG", font=font(10, bold=True, mono=True), fill=(92, 207, 231, 255), anchor="ra")
    return image.resize((800, 344), Image.Resampling.LANCZOS)


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frames = [create_frame(index) for index in range(10)]
    palette = frames[0].quantize(colors=32, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    optimized = [palette] + [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames[1:]]
    optimized[0].save(OUTPUT, save_all=True, append_images=optimized[1:], duration=[170] * len(optimized), loop=0, optimize=True, disposal=2)
    print(f"Generated {OUTPUT} ({OUTPUT.stat().st_size:,} bytes, {len(frames)} frames).")


if __name__ == "__main__":
    main()
