#!/usr/bin/env python3
"""
mac-flim — Convert images and video to MacFlim format for Macintosh Plus.

Handles the full pipeline: resize to 512x342, preprocess for 1-bit display,
and run flimmaker with the correct Mac Plus settings.

Wraps the hard-won knowledge from previous conversions:
  - --profile plus (byterate 1500, fps-ratio 2)
  - --filters "" for crisp 1-bit (no gamma/blur)
  - --fps-ratio 2 default (safe for Mac Plus SCSI), 1 for short clips
  - PGM must be P5 binary, 512x342, 8-bit, no comments

Usage:
    mac-flim image input.jpg output.flim              # Still image (5s loop)
    mac-flim image input.jpg output.flim -d 10        # Still image (10s)
    mac-flim video input.mp4 output.flim              # Video
    mac-flim video input.gif output.flim              # GIF
    mac-flim video input.mp4 output.flim -a music.wav # Video with audio
    mac-flim preview input.jpg -o preview.png         # 1-bit preview

Dependencies:
    pip install Pillow numpy
    pip install opencv-python       # for video input
    brew install ffmpeg             # for frame→video assembly
    brew install fstark/macflim/flimmaker
"""

import argparse
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageEnhance

# Mac Plus screen
MAC_W = 512
MAC_H = 342


# ---------------------------------------------------------------------------
# Image processing
# ---------------------------------------------------------------------------


def load_and_prepare(path, contrast=1.4, sharpness=1.5, invert=False):
    """Load image, resize to 512x342, apply preprocessing.

    Returns grayscale PIL Image at Mac Plus resolution.
    """
    img = Image.open(path)

    # Handle transparency
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        alpha = img.convert("RGBA").split()[-1]
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        bg.paste(img, mask=alpha)
        img = bg

    img = img.convert("L")

    # Fit to 512x342 — fill and center-crop
    w, h = img.size
    ratio = max(MAC_W / w, MAC_H / h)
    img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    w, h = img.size
    left = (w - MAC_W) // 2
    top = (h - MAC_H) // 2
    img = img.crop((left, top, left + MAC_W, top + MAC_H))

    # Enhance
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)
    if sharpness != 1.0:
        img = ImageEnhance.Sharpness(img).enhance(sharpness)

    if invert:
        img = Image.eval(img, lambda x: 255 - x)

    return img


def to_1bit(img, dither=True):
    """Convert grayscale image to 1-bit.

    With dithering (default), uses Floyd-Steinberg error diffusion —
    preserves mid-tone detail like skin, fabric, gradients.
    Without dithering, hard threshold at 128 — crisp but loses detail.
    """
    if dither:
        return img.convert("1")  # Pillow default = Floyd-Steinberg
    return img.point(lambda x: 0 if x < 128 else 255, "1")


def save_pgm(img, path):
    """Save as P5 PGM — flimmaker's preferred input.

    P5 binary, exactly 512x342, maxval 255, no comments.
    """
    if img.mode != "L":
        img = img.convert("L")
    if img.size != (MAC_W, MAC_H):
        img = img.resize((MAC_W, MAC_H), Image.LANCZOS)

    pixels = np.array(img)
    header = f"P5\n{MAC_W} {MAC_H}\n255\n".encode("ascii")
    with open(path, "wb") as f:
        f.write(header)
        f.write(pixels.tobytes())


# ---------------------------------------------------------------------------
# Video helpers
# ---------------------------------------------------------------------------


def video_frames(path):
    """Yield PIL Image frames from a video/GIF."""
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


def get_frame_count(path):
    """Get total frame count."""
    import cv2
    cap = cv2.VideoCapture(path)
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return count


# ---------------------------------------------------------------------------
# Flimmaker pipeline
# ---------------------------------------------------------------------------


def frames_to_flim(frames_dir, output_path, fps=12, audio=None, fps_ratio=2):
    """Assemble PGM frames into a .flim via ffmpeg + flimmaker."""
    tmp_mp4 = os.path.join(frames_dir, "_tmp.mp4")

    # PGM frames → MP4
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", os.path.join(frames_dir, "frame_%06d.pgm"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-vf", f"scale={MAC_W}:{MAC_H}",
    ]
    if audio:
        ffmpeg_cmd.extend(["-i", audio, "-c:a", "aac", "-shortest"])
    ffmpeg_cmd.append(tmp_mp4)

    result = subprocess.run(ffmpeg_cmd, capture_output=True)
    if result.returncode != 0:
        print(f"ffmpeg error: {result.stderr.decode()[:200]}", file=sys.stderr)
        sys.exit(1)

    # MP4 → flim
    flim_cmd = [
        "flimmaker", tmp_mp4,
        "--profile", "plus",
        "--filters", "",
        "--fps-ratio", str(fps_ratio),
        "--flim", output_path,
    ]
    result = subprocess.run(flim_cmd, capture_output=True)
    if result.returncode != 0:
        print(f"flimmaker error: {result.stderr.decode()[:200]}", file=sys.stderr)
        sys.exit(1)

    os.remove(tmp_mp4)


def direct_flim(input_path, output_path, fps_ratio=2):
    """Pass video directly to flimmaker (simpler, uses flimmaker's own processing)."""
    flim_cmd = [
        "flimmaker", input_path,
        "--profile", "plus",
        "--filters", "",
        "--fps-ratio", str(fps_ratio),
        "--flim", output_path,
    ]
    result = subprocess.run(flim_cmd, capture_output=True)
    if result.returncode != 0:
        print(f"flimmaker error: {result.stderr.decode()[:200]}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


def cmd_image(args):
    """Convert a still image to .flim."""
    print(f"loading {args.input}...", file=sys.stderr)
    img = load_and_prepare(
        args.input, contrast=args.contrast,
        sharpness=args.sharpness, invert=args.invert,
    )

    with tempfile.TemporaryDirectory(prefix="mac-flim-") as tmpdir:
        fps = 12
        total_frames = fps * args.duration
        print(f"generating {total_frames} frames ({args.duration}s)...", file=sys.stderr)
        for i in range(total_frames):
            save_pgm(img, os.path.join(tmpdir, f"frame_{i:06d}.pgm"))
        print("building flim...", file=sys.stderr)
        frames_to_flim(tmpdir, args.output, fps=fps, fps_ratio=args.fps_ratio)

    size = os.path.getsize(args.output)
    print(f"wrote {args.output} ({size // 1024}KB, {args.duration}s)")


def cmd_video(args):
    """Convert video/GIF to .flim."""
    if args.direct:
        # Skip our preprocessing, let flimmaker handle everything
        print(f"passing {args.input} directly to flimmaker...", file=sys.stderr)
        direct_flim(args.input, args.output, fps_ratio=args.fps_ratio)
    else:
        # Our pipeline: preprocess each frame for best 1-bit results
        fps = get_video_fps(args.input)
        frame_count = get_frame_count(args.input)
        print(f"processing {frame_count} frames at {fps:.1f} fps...", file=sys.stderr)

        with tempfile.TemporaryDirectory(prefix="mac-flim-") as tmpdir:
            frame_num = 0
            for frame_img in video_frames(args.input):
                # Prepare frame at Mac Plus resolution
                frame_l = frame_img.convert("L")
                w, h = frame_l.size
                ratio = max(MAC_W / w, MAC_H / h)
                frame_l = frame_l.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
                w, h = frame_l.size
                left = (w - MAC_W) // 2
                top = (h - MAC_H) // 2
                frame_l = frame_l.crop((left, top, left + MAC_W, top + MAC_H))

                if args.contrast != 1.0:
                    frame_l = ImageEnhance.Contrast(frame_l).enhance(args.contrast)
                if args.sharpness != 1.0:
                    frame_l = ImageEnhance.Sharpness(frame_l).enhance(args.sharpness)
                if args.invert:
                    frame_l = Image.eval(frame_l, lambda x: 255 - x)

                save_pgm(frame_l, os.path.join(tmpdir, f"frame_{frame_num:06d}.pgm"))
                frame_num += 1
                if frame_num % 100 == 0:
                    print(f"  frame {frame_num}/{frame_count}...", file=sys.stderr)

            print(f"building flim from {frame_num} frames...", file=sys.stderr)
            frames_to_flim(tmpdir, args.output, fps=int(fps), audio=args.audio,
                           fps_ratio=args.fps_ratio)

    size = os.path.getsize(args.output)
    print(f"wrote {args.output} ({size // 1024}KB)")


def cmd_preview(args):
    """Generate a 1-bit preview PNG of what the Mac Plus would show."""
    img = load_and_prepare(
        args.input, contrast=args.contrast,
        sharpness=args.sharpness, invert=args.invert,
    )
    preview = to_1bit(img, dither=not args.no_dither)
    output = args.output or args.input.rsplit(".", 1)[0] + "_preview.png"
    preview.save(output)
    mode = "1-bit dithered" if not args.no_dither else "1-bit"
    print(f"wrote {output} ({MAC_W}x{MAC_H}, {mode})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        prog="mac-flim",
        description="Convert images/video to MacFlim for Macintosh Plus",
    )
    parser.add_argument("-c", "--contrast", type=float, default=1.4,
                        help="Contrast enhancement (default: 1.4)")
    parser.add_argument("-s", "--sharpness", type=float, default=1.5,
                        help="Sharpness enhancement (default: 1.5)")
    parser.add_argument("--invert", action="store_true",
                        help="Invert image (white on black)")

    sub = parser.add_subparsers(dest="command")

    # image
    img_p = sub.add_parser("image", help="Convert a still image to .flim")
    img_p.add_argument("input", help="Image file path")
    img_p.add_argument("output", help="Output .flim path")
    img_p.add_argument("-d", "--duration", type=int, default=5,
                        help="Duration in seconds (default: 5)")
    img_p.add_argument("--fps-ratio", type=int, default=2,
                        help="flimmaker fps-ratio (default: 2, use 1 for short clips)")

    # video
    vid_p = sub.add_parser("video", help="Convert video/GIF to .flim")
    vid_p.add_argument("input", help="Video/GIF file path")
    vid_p.add_argument("output", help="Output .flim path")
    vid_p.add_argument("-a", "--audio", help="Audio file to include")
    vid_p.add_argument("--direct", action="store_true",
                        help="Pass directly to flimmaker (skip preprocessing)")
    vid_p.add_argument("--fps-ratio", type=int, default=2,
                        help="flimmaker fps-ratio (default: 2, use 1 for short clips)")

    # preview
    pre_p = sub.add_parser("preview", help="1-bit preview of what Mac Plus shows")
    pre_p.add_argument("input", help="Image file path")
    pre_p.add_argument("-o", "--output", help="Output PNG path")
    pre_p.add_argument("--no-dither", action="store_true",
                        help="Hard threshold instead of Floyd-Steinberg dithering")

    args = parser.parse_args()

    if args.command == "image":
        cmd_image(args)
    elif args.command == "video":
        cmd_video(args)
    elif args.command == "preview":
        cmd_preview(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
