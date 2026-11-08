import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1080
HEIGHT = 1920
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
NAVY = (10, 18, 38)
CARD = (20, 34, 64)
CYAN = (56, 225, 255)
YELLOW = (255, 205, 77)
WHITE = (245, 248, 255)
MUTED = (169, 188, 216)
GREEN = (75, 222, 146)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size)


def base() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), NAVY)
    pixels = image.load()
    for y in range(HEIGHT):
        progress = y / HEIGHT
        color = (int(10 + 8 * progress), int(18 + 30 * progress), int(38 + 55 * progress))
        for x in range(WIDTH):
            pixels[x, y] = color
    draw = ImageDraw.Draw(image)
    draw.ellipse((760, -180, 1260, 320), fill=(20, 70, 100))
    draw.ellipse((-260, 1480, 360, 2100), fill=(24, 52, 93))
    return image, draw


def centered(draw: ImageDraw.ImageDraw, text: str, y: int, size: int, color=WHITE, bold: bool = False) -> None:
    face = font(size, bold)
    box = draw.textbbox((0, 0), text, font=face)
    draw.text(((WIDTH - (box[2] - box[0])) / 2, y), text, font=face, fill=color)


def label(draw: ImageDraw.ImageDraw, text: str, x: int, y: int, size: int = 34, color=MUTED, bold: bool = False) -> None:
    draw.text((x, y), text, font=font(size, bold), fill=color)


def rounded(draw: ImageDraw.ImageDraw, box, fill=CARD, outline=None, radius: int = 30, width: int = 3) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def check(draw: ImageDraw.ImageDraw, x: int, y: int, scale: float = 1.0, color=GREEN) -> None:
    draw.ellipse((x, y, x + 64 * scale, y + 64 * scale), fill=color)
    draw.line((x + 16 * scale, y + 33 * scale, x + 28 * scale, y + 46 * scale, x + 50 * scale, y + 19 * scale), fill=NAVY, width=max(3, int(7 * scale)), joint="curve")


def device(draw: ImageDraw.ImageDraw, x: int, y: int, w: int = 620, h: int = 330) -> None:
    rounded(draw, (x, y, x + w, y + h), fill=(8, 12, 24), outline=CYAN, radius=48, width=6)
    rounded(draw, (x + 28, y + 28, x + w - 28, y + h - 28), fill=(22, 52, 80), outline=None, radius=26)
    draw.ellipse((x - 38, y + h / 2 - 42, x + 8, y + h / 2 + 42), fill=(30, 42, 62))
    draw.ellipse((x + w - 8, y + h / 2 - 42, x + w + 38, y + h / 2 + 42), fill=(30, 42, 62))
    draw.rectangle((x + w / 2 - 45, y + h, x + w / 2 + 45, y + h + 22), fill=(10, 15, 28))


def scene_title() -> Image.Image:
    image, draw = base()
    centered(draw, "YOUR NEXT HANDHELD", 170, 32, CYAN, True)
    centered(draw, "Start with a checklist", 225, 60, WHITE, True)
    device(draw, 230, 440)
    for index, text in enumerate(("GAMES", "BUDGET", "PLAY TIME")):
        x = 160 + index * 270
        rounded(draw, (x, 920, x + 220, 1100), fill=CARD, outline=CYAN)
        check(draw, x + 78, 950, 1)
        centered_text(draw, text, x + 110, 1040, 28, WHITE, True)
    centered(draw, "A better decision starts with your habits", 1280, 38, MUTED)
    return image


def centered_text(draw: ImageDraw.ImageDraw, text: str, x: int, y: int, size: int, color, bold: bool = False) -> None:
    face = font(size, bold)
    box = draw.textbbox((0, 0), text, font=face)
    draw.text((x - (box[2] - box[0]) / 2, y), text, font=face, fill=color)


def scene_games() -> Image.Image:
    image, draw = base()
    centered(draw, "1 · YOUR GAME LIBRARY", 150, 34, CYAN, True)
    centered(draw, "Check what you actually play", 215, 52, WHITE, True)
    names = ("ACTION", "INDIE", "RETRO")
    for index, name in enumerate(names):
        y = 390 + index * 300
        rounded(draw, (120, y, 960, y + 240), fill=CARD)
        rounded(draw, (155, y + 35, 365, y + 205), fill=(35 + index * 12, 75 + index * 15, 105 + index * 18), outline=CYAN)
        centered_text(draw, "PLAY", 260, y + 95, 30, YELLOW, True)
        label(draw, name, 410, y + 55, 38, WHITE, True)
        label(draw, "Compatibility first", 410, y + 115, 30, MUTED)
        check(draw, 835, y + 85, 1.1)
    centered(draw, "Not every game works the same way", 1390, 36, MUTED)
    return image


def scene_compare() -> Image.Image:
    image, draw = base()
    centered(draw, "2 · COMPARE YOUR NEEDS", 145, 34, CYAN, True)
    centered(draw, "Three practical trade-offs", 210, 54, WHITE, True)
    cards = (("BUDGET", "What can you spend?", "DKK"), ("SYSTEM", "Which OS fits?", "OS"), ("PLAY TIME", "How long per session?", "TIME"))
    for index, (title, subtitle, icon) in enumerate(cards):
        x = 75 + index * 330
        rounded(draw, (x, 400, x + 300, 1080), fill=CARD)
        rounded(draw, (x + 60, 460, x + 240, 650), fill=(25, 75, 105), outline=CYAN)
        centered_text(draw, icon, x + 150, 525, 34, YELLOW, True)
        centered_text(draw, title, x + 150, 730, 28, WHITE, True)
        for line_index, line in enumerate(subtitle.split(" ")):
            centered_text(draw, line, x + 150, 800 + line_index * 44, 26, MUTED)
    centered(draw, "Price alone is not the whole decision", 1250, 36, MUTED)
    return image


def scene_verify() -> Image.Image:
    image, draw = base()
    centered(draw, "3 · VERIFY BEFORE BUYING", 145, 34, CYAN, True)
    centered(draw, "Current facts beat old reviews", 215, 52, WHITE, True)
    rows = (("SPECIFICATIONS", "Check the exact model"), ("COMPATIBILITY", "Check your actual games"), ("CURRENT PRICE", "Check today's seller and total"))
    for index, (title, subtitle) in enumerate(rows):
        y = 410 + index * 260
        rounded(draw, (110, y, 970, y + 210), fill=CARD)
        check(draw, 155, y + 65, 1.2)
        label(draw, title, 275, y + 52, 32, WHITE, True)
        label(draw, subtitle, 275, y + 112, 29, MUTED)
    centered(draw, "Specifications and prices can change", 1340, 36, MUTED)
    return image


def scene_save() -> Image.Image:
    image, draw = base()
    centered(draw, "SAVE THIS CHECKLIST", 160, 36, CYAN, True)
    centered(draw, "Use it for your next upgrade", 225, 54, WHITE, True)
    device(draw, 230, 410)
    for index, text in enumerate(("1 · Games", "2 · Budget + OS", "3 · Play time", "4 · Verify")):
        y = 870 + index * 145
        check(draw, 220, y, 0.9)
        label(draw, text, 330, y + 5, 38, WHITE, True)
    rounded(draw, (230, 1510, 850, 1640), fill=(20, 105, 120), outline=CYAN)
    centered_text(draw, "MAKE A BETTER CHOICE", 540, 1550, 32, WHITE, True)
    return image


def make_scene_assets(output: Path) -> list[Path]:
    scenes = (scene_title, scene_games, scene_compare, scene_verify, scene_save)
    paths = []
    for index, factory in enumerate(scenes, 1):
        path = output / f"scene-{index}.png"
        factory().save(path, format="PNG", optimize=True)
        paths.append(path)
    return paths
