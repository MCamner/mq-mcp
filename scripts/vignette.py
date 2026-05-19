"""Apply a soft vignette (edge fade to black) to assets/bridget.jpg."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "assets" / "bridget.jpg"
DST = REPO_ROOT / "assets" / "bridget.jpg"

STRENGTH = 0.82   # 0.0 = full black everywhere, 1.0 = no vignette
BLUR_RADIUS = 80  # how soft the fade is


def make_vignette_mask(size: tuple[int, int]) -> Image.Image:
    w, h = size
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)

    margin_x = int(w * 0.08)
    margin_y = int(h * 0.08)
    draw.ellipse(
        [margin_x, margin_y, w - margin_x, h - margin_y],
        fill=255,
    )

    mask = mask.filter(ImageFilter.GaussianBlur(radius=BLUR_RADIUS))

    # Scale brightness so centre stays at STRENGTH, not 1.0
    mask = mask.point(lambda p: int(p * STRENGTH))
    return mask


def apply_vignette(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(f"Image not found: {src}")

    img = Image.open(src).convert("RGB")
    black = Image.new("RGB", img.size, (0, 0, 0))
    mask = make_vignette_mask(img.size)

    result = Image.composite(img, black, mask)
    result.save(dst, quality=95)
    print(f"OK: vignette applied → {dst}")


if __name__ == "__main__":
    apply_vignette(SRC, DST)
