"""Apply a soft vignette (edge fade to black) to assets/bridget.jpg."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "assets" / "bridget.jpg"
DST = REPO_ROOT / "assets" / "bridget.jpg"

# How far from each edge the fade starts (0.0–0.5, larger = more fading)
FEATHER = 0.28
# How soft the transition is (larger = smoother but wider fade)
BLUR_RADIUS = 120


def make_vignette_mask(size: tuple[int, int]) -> Image.Image:
    w, h = size
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)

    mx = int(w * FEATHER)
    my = int(h * FEATHER)
    draw.ellipse([mx, my, w - mx, h - my], fill=255)

    mask = mask.filter(ImageFilter.GaussianBlur(radius=BLUR_RADIUS))
    return mask


def apply_vignette(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(f"Image not found: {src}")

    img = Image.open(src).convert("RGB")
    black = Image.new("RGB", img.size, (0, 0, 0))
    mask = make_vignette_mask(img.size)

    result = Image.composite(img, black, mask)
    result.save(dst, quality=95)

    w, h = img.size
    print(f"OK: vignette applied → {dst}  ({w}x{h})")


if __name__ == "__main__":
    apply_vignette(SRC, DST)
