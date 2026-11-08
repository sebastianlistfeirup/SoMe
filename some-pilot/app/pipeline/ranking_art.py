from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.pipeline.media import run
from app.pipeline.ranking import RankingPlan

BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    ratio = max(size[0] / image.width, size[1] / image.height)
    scaled = image.resize((round(image.width * ratio), round(image.height * ratio)), Image.Resampling.LANCZOS)
    left = (scaled.width - size[0]) // 2
    top = (scaled.height - size[1]) // 2
    return scaled.crop((left, top, left + size[0], top + size[1]))


def _centered(draw: ImageDraw.ImageDraw, text: str, y: int, font: ImageFont.FreeTypeFont, fill: str, stroke: int = 0) -> None:
    box = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
    draw.text(((1080 - (box[2] - box[0])) / 2, y), text, font=font, fill=fill, stroke_width=stroke, stroke_fill="#07101f")


def make_thumbnail(plan_path: Path, output: Path) -> Path:
    plan = RankingPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    work = output / "thumbnail-frames"
    work.mkdir(parents=True, exist_ok=True)
    top = sorted(plan.scenes, key=lambda scene: scene.rank)[:3]
    canvas = Image.new("RGB", (1080, 1920), "#07101f")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 1080, 14), fill="#58efff")
    _centered(draw, "THE ULTIMATE", 92, ImageFont.truetype(BOLD, 45), "#58efff")
    _centered(draw, "TOP 10", 155, ImageFont.truetype(BOLD, 176), "#ffffff", 4)
    _centered(draw, "LEGION GO 2", 353, ImageFont.truetype(BOLD, 84), "#ffd54f", 3)
    _centered(draw, "GAMES", 455, ImageFont.truetype(BOLD, 112), "#ffffff", 3)
    for index, scene in enumerate(top):
        frame = work / f"rank-{scene.rank}.jpg"
        run(["ffmpeg", "-y", "-ss", f"{scene.start_seconds + 1:.3f}", "-i", str(plan_path.parent / scene.source_path), "-frames:v", "1", "-q:v", "2", str(frame)])
        image = _cover(Image.open(frame).convert("RGB"), (986, 338))
        y = 650 + index * 360
        canvas.paste(image, (47, y))
        draw.rectangle((47, y, 1033, y + 338), outline="#58efff" if index == 0 else "#263b59", width=5)
        draw.rounded_rectangle((66, y + 18, 184, y + 102), radius=18, fill="#07101fe8")
        draw.text((82, y + 23), f"#{scene.rank}", font=ImageFont.truetype(BOLD, 51), fill="#ffd54f")
        draw.rounded_rectangle((65, y + 260, 1015, y + 327), radius=15, fill="#07101fe8")
        font_size = 37 if len(scene.game) < 25 else 30
        draw.text((87, y + 273), scene.game.upper(), font=ImageFont.truetype(BOLD, font_size), fill="#ffffff")
    _centered(draw, "REAL GAMES. ZERO FILLER.", 1775, ImageFont.truetype(BOLD, 35), "#58efff")
    target = output / "thumbnail.jpg"
    canvas.save(target, quality=94, subsampling=0)
    return target


def make_storyboard(video: Path, output: Path, duration: float) -> Path:
    interval = max(duration / 7, 0.1)
    target = output / "storyboard.jpg"
    run(["ffmpeg", "-y", "-i", str(video), "-vf", f"fps=1/{interval:.6f},scale=270:480,tile=7x1", "-frames:v", "1", "-q:v", "2", str(target)])
    return target
