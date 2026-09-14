"""
generate_synthetic_bins.py

Generates a small synthetic stand-in for the Amazon Bin Image Dataset (ABID)
so the audit tool has something to run against out of the box.

ABID (https://registry.opendata.aws/amazon-bin-imagery/) contains 500K+ real
images of storage bins from Amazon Fulfillment Centers, each with metadata
on the objects inside (count, ASIN, quantity). This sandbox has no network
access to S3, so this script draws simple synthetic "bin photos" (random
shapes on a shelf-colored background) with the SAME schema ABID uses:
one image per bin + a ground-truth object count.

To swap in real data: download a shard of ABID, and replace this script's
output (data/images/*.jpg + data/metadata.csv) with the real images and
their bin-metadata JSON object counts. app.py doesn't need to change.
"""

import csv
import os
import random

from PIL import Image, ImageDraw, ImageFilter

OUT_DIR = os.path.join(os.path.dirname(__file__), "data")
IMG_DIR = os.path.join(OUT_DIR, "images")
NUM_IMAGES = 60
IMG_SIZE = (400, 400)
BIN_BG = (222, 208, 184)  # cardboard color

SHAPE_COLORS = [
    (200, 60, 60), (60, 120, 200), (60, 170, 90),
    (230, 180, 40), (150, 90, 200), (90, 90, 90),
]


def draw_object(draw, cx, cy, size, color):
    shape = random.choice(["box", "circle", "poly"])
    if shape == "box":
        draw.rectangle([cx - size, cy - size, cx + size, cy + size], fill=color, outline=(0, 0, 0))
    elif shape == "circle":
        draw.ellipse([cx - size, cy - size, cx + size, cy + size], fill=color, outline=(0, 0, 0))
    else:
        pts = [
            (cx, cy - size), (cx + size, cy + size // 2),
            (cx - size, cy + size // 2),
        ]
        draw.polygon(pts, fill=color, outline=(0, 0, 0))


def make_bin_image(true_count, difficulty):
    img = Image.new("RGB", IMG_SIZE, BIN_BG)
    draw = ImageDraw.Draw(img)
    # shelf shading
    for y in range(0, IMG_SIZE[1], 40):
        draw.line([(0, y), (IMG_SIZE[0], y)], fill=(205, 190, 165), width=1)

    placed = 0
    attempts = 0
    occupied = []
    while placed < true_count and attempts < 200:
        attempts += 1
        size = random.randint(28, 45)
        cx = random.randint(size + 10, IMG_SIZE[0] - size - 10)
        cy = random.randint(size + 10, IMG_SIZE[1] - size - 10)
        # allow some overlap/occlusion on hard images, avoid it on easy ones
        overlap_ok = difficulty == "hard"
        collision = any(
            abs(cx - ox) < size + os_ - (15 if overlap_ok else 0)
            and abs(cy - oy) < size + os_ - (15 if overlap_ok else 0)
            for ox, oy, os_ in occupied
        )
        if collision:
            continue
        color = random.choice(SHAPE_COLORS)
        draw_object(draw, cx, cy, size, color)
        occupied.append((cx, cy, size))
        placed += 1

    if difficulty == "hard":
        img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(2.5, 4.5)))
        # dim / low-light look
        img = Image.eval(img, lambda p: int(p * random.uniform(0.55, 0.75)))

    return img


def main():
    os.makedirs(IMG_DIR, exist_ok=True)
    rows = []
    random.seed(42)
    for i in range(NUM_IMAGES):
        true_count = random.randint(1, 5)
        difficulty = "hard" if i % 3 == 0 else "easy"  # ~1/3 hard, matches JD's "blurry, less sharp" cases
        img = make_bin_image(true_count, difficulty)
        image_id = f"bin_{i:03d}"
        img.save(os.path.join(IMG_DIR, f"{image_id}.jpg"), quality=85)
        rows.append({"image_id": image_id, "true_count": true_count, "difficulty": difficulty})

    with open(os.path.join(OUT_DIR, "metadata.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["image_id", "true_count", "difficulty"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {NUM_IMAGES} synthetic bin images -> {IMG_DIR}")
    print(f"Ground truth metadata -> {os.path.join(OUT_DIR, 'metadata.csv')}")


if __name__ == "__main__":
    main()
