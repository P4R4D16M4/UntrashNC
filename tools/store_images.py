#!/usr/bin/env python3
"""App store presentation images: a screenshot as a window on the UntrashOS wallpaper,
with a headline.

  tools/store_images.py RAW WALLPAPER OUT

RAW holds the 2880x1800 screenshots from tools/cdp_shot.py (photos, mounts, admin);
writes OUT/1-shares.png, 2-automatic.png, 3-mesh.png (1920x1080).
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080
GREEN, CYAN = (91, 227, 106), (25, 198, 198)
FONT_B = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
FONT_R = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"

SLIDES = [
    ("1-shares", "photos", (0, 0, 2880, 1000),
     ["Your NAS shares,", "right in Nextcloud"],
     "Every share an UntrashOS NAS offers appears as a folder, by itself."),
    ("2-automatic", "mounts", (620, 880, 2870, 1600),
     ["Pick the shares on the NAS.", "The storages follow."],
     "Made, updated and removed automatically. Each user signs in with their NAS account."),
    ("3-mesh", "admin", (620, 170, 2870, 800),
     ["Joins your UntrashMesh"],
     "Address book for the mesh, change feed instead of scans, optional tunnel: no port forwarding."),
]


def gradient_text(img, xy, text, font):
    """Text filled with the green -> cyan accent gradient."""
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=font, fill=255)
    box = mask.getbbox()
    grad = Image.new("RGB", img.size)
    gd = ImageDraw.Draw(grad)
    x0, x1 = box[0], max(box[2], box[0] + 1)
    for x in range(x0, x1 + 1):
        f = (x - x0) / (x1 - x0)
        gd.line([(x, 0), (x, img.size[1])], fill=tuple(int(GREEN[k] + (CYAN[k] - GREEN[k]) * f) for k in range(3)))
    img.paste(grad, (0, 0), mask)


def window(shot, width):
    """The screenshot with rounded corners, a thin accent border and a soft glow."""
    h = int(shot.height * width / shot.width)
    s = shot.resize((width, h), Image.LANCZOS)
    r = 18
    mask = Image.new("L", s.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s.width - 1, s.height - 1], r, fill=255)
    pad = 40
    layer = Image.new("RGBA", (s.width + 2 * pad, s.height + 2 * pad), (0, 0, 0, 0))
    glow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle([pad - 4, pad - 4, pad + s.width + 3, pad + s.height + 3], r + 4,
                                           fill=CYAN + (110,))
    layer = Image.alpha_composite(layer, glow.filter(ImageFilter.GaussianBlur(18)))
    body = Image.new("RGBA", s.size)
    body.paste(s.convert("RGBA"), (0, 0), mask)
    layer.alpha_composite(body, (pad, pad))
    ImageDraw.Draw(layer).rounded_rectangle([pad, pad, pad + s.width - 1, pad + s.height - 1], r,
                                            outline=GREEN + (200,), width=2)
    return layer, pad


def main():
    raw, wallpaper, out = sys.argv[1:4]
    os.makedirs(out, exist_ok=True)
    bg = Image.open(wallpaper).convert("RGB")
    scale = max(W / bg.width, H / bg.height)
    bg = bg.resize((int(bg.width * scale) + 1, int(bg.height * scale) + 1), Image.LANCZOS).crop((0, 0, W, H))
    shade = Image.new("L", (W, H))
    sd = ImageDraw.Draw(shade)
    for x in range(W):                       # darker on the left where the text and window sit
        sd.line([(x, 0), (x, H)], fill=int(205 - 120 * (x / W)))
    bg = Image.composite(Image.new("RGB", (W, H), (8, 10, 13)), bg, shade)
    fb, fr = ImageFont.truetype(FONT_B, 62), ImageFont.truetype(FONT_R, 30)
    for name, src, crop, title, sub in SLIDES:
        img = bg.copy().convert("RGBA")
        d = ImageDraw.Draw(img)
        y = 70
        for i, line in enumerate(title):
            if i == len(title) - 1:
                gradient_text(img, (96, y), line, fb)
            else:
                d.text((96, y), line, font=fb, fill=(236, 240, 242))
            y += 80
        d = ImageDraw.Draw(img)
        d.text((98, y + 6), sub, font=fr, fill=(170, 180, 186))
        shot = Image.open(os.path.join(raw, src + ".png")).convert("RGB").crop(crop)
        top = y + 80
        maxw, maxh = 1150, H - top - 50          # keeps the wallpaper logo on the right free
        width = min(maxw, int(shot.width * maxh / shot.height))
        layer, pad = window(shot, width)
        img.alpha_composite(layer, (96 - pad, top - pad))
        img.convert("RGB").save(os.path.join(out, name + ".png"), optimize=True)
        print(name)


if __name__ == "__main__":
    main()
