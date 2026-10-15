from hashlib import sha256
from math import cos, sin, pi
from pathlib import Path
import random
import re

from PIL import Image, ImageDraw, ImageFilter, ImageFont


def font(size: int, bold: bool = False):
    filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for folder in (Path("/usr/share/fonts/truetype/dejavu"), Path("/usr/share/fonts/dejavu-sans")):
        if (folder / filename).exists():
            return ImageFont.truetype(str(folder / filename), size)
    return ImageFont.truetype(filename, size)


def create_illustration(destination: Path, title: str, facts: list[str]) -> str:
    evidence = (title + " " + " ".join(facts)).lower()
    headline = title.lower()
    theme = "agents" if re.search(r"\b(?:ai|x402|artificial intelligence)\b", headline) else "bitcoin" if re.search(r"\b(?:bitcoin|btc)\b", headline) else "equities" if any(term in headline for term in ("tokeniz", "equities", "stocks")) else "network"
    colors = {"bitcoin": (245, 159, 66), "agents": (121, 159, 255), "equities": (102, 215, 177), "network": (182, 146, 244)}
    accent = colors[theme]
    canvas = Image.new("RGB", (1600, 900))
    draw = ImageDraw.Draw(canvas)
    for y in range(900):
        draw.line((0, y, 1600, y), fill=(12 + y // 180, 13 + y // 150, 24 + y // 60))
    glow = Image.new("RGBA", canvas.size)
    layer = ImageDraw.Draw(glow)
    layer.ellipse((390, -140, 1520, 1100), fill=accent + (75,))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(150)))
    draw = ImageDraw.Draw(canvas)
    for x in range(64, 1600, 64):
        for y in range(68, 900, 64):
            draw.ellipse((x, y, x + 2, y + 2), fill=(110, 117, 150, 90))
    draw.rounded_rectangle((60, 62, 247, 105), radius=20, outline=accent + (130,), width=1)
    draw.text((83, 70), "PRESENCE", font=font(22, True), fill=(222, 224, 236))
    label = {"bitcoin": "MARKETS / BITCOIN", "agents": "TECHNOLOGY / PAYMENTS", "equities": "FINANCE / TOKENIZATION", "network": "CRYPTO / NETWORKS"}[theme]
    draw.text((63, 783), label, font=font(25, True), fill=accent)
    draw.text((63, 825), "Independent reporting. Clear context.", font=font(20), fill=(158, 165, 190))
    if theme == "bitcoin":
        for offset in range(22, -1, -2):
            draw.ellipse((529 + offset, 164 + offset, 1071 + offset, 706 + offset), fill=(92, 53, 37))
        draw.ellipse((529, 164, 1071, 706), fill=(198, 113, 45), outline=(255, 209, 131), width=4)
        draw.ellipse((553, 188, 1047, 682), outline=(250, 184, 92), width=3)
        draw.ellipse((573, 208, 1027, 662), fill=(225, 145, 58), outline=(122, 68, 35), width=2)
        for x in (716, 744):
            draw.line((x, 286, x, 573), fill=(255, 229, 177), width=12)
        draw.text((688, 312), "B", font=font(320, True), fill=(255, 229, 177), anchor="lt", stroke_width=1)
        labels = ("CPI" if "cpi" in evidence or "inflation" in evidence else "BITCOIN", "LEVERAGE" if "leverage" in evidence or "liquidation" in evidence else "MARKETS")
        for position, text in zip(((1150, 270), (298, 510)), labels):
            x, y = position
            width = 220 if text == "CPI" else 270
            draw.rounded_rectangle((x - width // 2, y - 38, x + width // 2, y + 38), radius=18, fill=(22, 24, 38), outline=accent, width=1)
            draw.text((x, y), text, font=font(28, True), fill=(234, 231, 223), anchor="mm")
    elif theme == "agents":
        center = (810, 427)
        nodes = [(int(center[0] + cos(index * pi / 3) * 370), int(center[1] + sin(index * pi / 3) * 250)) for index in range(6)]
        for index, point in enumerate(nodes):
            draw.line((*center, *point), fill=(91, 126, 202), width=3)
            draw.line((*point, *nodes[(index + 1) % 6]), fill=(58, 78, 125), width=2)
        for point in nodes:
            x, y = point
            draw.rounded_rectangle((x - 78, y - 54, x + 78, y + 54), radius=26, fill=(27, 39, 70), outline=(136, 168, 246), width=2)
            draw.rounded_rectangle((x - 22, y - 24, x + 22, y + 24), radius=10, fill=accent)
        draw.rounded_rectangle((647, 310, 973, 544), radius=45, fill=(30, 42, 76), outline=(172, 194, 255), width=3)
        draw.text(center, "x402" if "x402" in evidence else "AI", font=font(86, True), fill=(225, 233, 255), anchor="mm")
    elif theme == "equities":
        for index, offset in enumerate((100, 50, 0)):
            x, y = 488 + offset, 170 + offset
            draw.rounded_rectangle((x, y, x + 510, y + 400), radius=30, fill=(25 + index * 4, 45 + index * 5, 47 + index * 5), outline=(78, 157, 133), width=2)
        draw.text((548, 225), "EQUITIES", font=font(40, True), fill=(214, 244, 229))
        for index in range(4):
            draw.rounded_rectangle((548, 314 + index * 48, 900 - index * 24, 325 + index * 48), radius=5, fill=(86, 139, 128))
        for x, y in ((1080, 330), (1140, 510), (1000, 665)):
            draw.line((900, 430, x, y), fill=accent, width=3)
            draw.rounded_rectangle((x - 58, y - 45, x + 58, y + 45), radius=22, fill=(41, 83, 76), outline=accent, width=2)
            draw.rectangle((x - 14, y - 14, x + 14, y + 14), fill=accent)
    else:
        rng = random.Random(sha256(title.encode()).hexdigest())
        points = [(rng.randrange(360, 1300), rng.randrange(170, 700)) for _ in range(18)]
        for index, point in enumerate(points):
            for target in points[index + 1:index + 4]:
                draw.line((*point, *target), fill=(76, 66, 120), width=2)
            radius = 18 + index % 4 * 5
            draw.ellipse((point[0] - radius, point[1] - radius, point[0] + radius, point[1] + radius), fill=(65, 49, 102), outline=accent, width=2)
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(destination, "WEBP", quality=92, method=6)
    return {"bitcoin": "Original Presence illustration of Bitcoin, leverage and the inflation reading.", "agents": "Original Presence illustration of software agents connected through a digital payment network.", "equities": "Original Presence illustration of equity certificates connected to digital tokens.", "network": "Original Presence illustration of connected digital asset networks."}[theme]
