#!/usr/bin/env python3
"""
mac-ascii — Image/video to ASCII art for terminal display.

Converts images and video to ASCII art, optimized for the Mac Plus
terminal (80x24 at 9600 baud) and macbridge right pane (41 cols).

Based on BEPb/image_to_ascii conversion logic.

Usage:
    mac-ascii input.jpg                      # ASCII to stdout (80 cols)
    mac-ascii input.jpg -w 40                # 40 cols (macbridge pane)
    mac-ascii input.jpg -o art.txt           # Save to file
    mac-ascii input.gif                      # Animated playback in terminal
    mac-ascii input.mp4 -w 60               # Video ASCII playback

Dependencies:
    pip install Pillow numpy
    pip install opencv-python   # only for video/GIF input
"""

import argparse
import sys

import numpy as np
from PIL import Image, ImageEnhance

# ---------------------------------------------------------------------------
# Character palettes — ordered dark to light
# ---------------------------------------------------------------------------

PALETTE_FULL = "@MWNHB8$06XFVYZ27>1jli!;:,. "
PALETTE_SPARSE = "@#W8X7l;:. "
PALETTE_BLOCK = "#=+:. "

# ---------------------------------------------------------------------------
# Core conversion
# ---------------------------------------------------------------------------


def load_image(path):
    """Load an image, handle transparency."""
    img = Image.open(path)
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        alpha = img.convert("RGBA").split()[-1]
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        bg.paste(img, mask=alpha)
        img = bg
    return img


def image_to_ascii(img, width=80, palette=PALETTE_FULL, contrast=1.0, sharpness=1.0):
    """Convert a PIL Image to ASCII art string."""
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)
    if sharpness != 1.0:
        img = ImageEnhance.Sharpness(img).enhance(sharpness)

    img = img.convert("L")
    w, h = img.size

    out_w = width
    out_h = max(1, int(width * (h / w) / 2.4))

    img = img.resize((out_w, out_h), Image.LANCZOS)
    pixels = np.array(img)

    scale = 256 / len(palette)
    lines = []
    for row in pixels:
        line = ""
        for pixel in row:
            idx = min(int(pixel / scale), len(palette) - 1)
            line += palette[idx]
        lines.append(line)

    return "\n".join(lines)


def video_frames(path):
    """Yield PIL Image frames from a video/GIF file."""
    import cv2
    cap = cv2.VideoCapture(path)
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        yield Image.fromarray(rgb)
    cap.release()


def get_video_fps(path):
    """Get FPS from a video file."""
    import cv2
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    cap.release()
    return fps


def is_video(path):
    """Check if file is a video/animated GIF."""
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    if ext in ("mp4", "avi", "mov", "mkv", "webm"):
        return True
    if ext == "gif":
        # Check if animated
        try:
            img = Image.open(path)
            img.seek(1)
            return True
        except EOFError:
            return False
    return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

PALETTES = {"full": PALETTE_FULL, "sparse": PALETTE_SPARSE, "block": PALETTE_BLOCK}


def main():
    parser = argparse.ArgumentParser(
        prog="mac-ascii",
        description="Image/video to ASCII art for Macintosh Plus",
    )
    parser.add_argument("input", help="Image or video file path")
    parser.add_argument("-w", "--width", type=int, default=80,
                        help="Output width in chars (default: 80)")
    parser.add_argument("-o", "--output", help="Save ASCII to file instead of stdout")
    parser.add_argument("-p", "--palette", choices=["full", "sparse", "block"],
                        default="full", help="Character palette (default: full)")
    parser.add_argument("-c", "--contrast", type=float, default=1.4,
                        help="Contrast enhancement (default: 1.4)")
    parser.add_argument("-s", "--sharpness", type=float, default=1.5,
                        help="Sharpness enhancement (default: 1.5)")

    args = parser.parse_args()
    palette = PALETTES[args.palette]

    if is_video(args.input):
        import time
        fps = get_video_fps(args.input)
        for frame_img in video_frames(args.input):
            ascii_art = image_to_ascii(
                frame_img, width=args.width, palette=palette,
                contrast=args.contrast, sharpness=args.sharpness,
            )
            print("\033[2J\033[H" + ascii_art, flush=True)
            time.sleep(1 / fps)
    else:
        img = load_image(args.input)
        ascii_art = image_to_ascii(
            img, width=args.width, palette=palette,
            contrast=args.contrast, sharpness=args.sharpness,
        )
        if args.output:
            with open(args.output, "w") as f:
                f.write(ascii_art)
            print(f"wrote {args.output}", file=sys.stderr)
        else:
            print(ascii_art)


if __name__ == "__main__":
    main()
