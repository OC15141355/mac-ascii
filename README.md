# mac-ascii

Image and video conversion tools for the **Macintosh Plus** (512x342, 1-bit display).

Two scripts:
- **`mac-ascii.py`** — image/video to ASCII art for terminal display
- **`mac-flim.py`** — image/video to [MacFlim](https://github.com/fstark/macflim) format for Mac Plus playback

## Examples

Floyd-Steinberg dithered 1-bit conversion (grayscale → Mac Plus):

| Porco Rosso (1992) | The Little Mermaid (1989) |
|---|---|
| ![Porco Rosso](examples/porco_rosso.gif) | ![Mermaid](examples/mermaid.gif) |

## mac-ascii.py

Converts images and video to ASCII art, optimized for 80x24 terminals at 9600 baud.

```bash
mac-ascii input.jpg                    # ASCII to stdout (80 cols)
mac-ascii input.jpg -w 40             # 40 columns (macbridge pane)
mac-ascii input.jpg -o art.txt        # Save to file
mac-ascii input.gif                    # Animated playback
mac-ascii input.mp4 -w 60            # Video ASCII playback
```

Three character palettes: `full` (default), `sparse`, `block`. Contrast and sharpness tuned for Mac Plus defaults (`-c 1.4 -s 1.5`).

## mac-flim.py

Converts images and video to `.flim` files for playback on a real Mac Plus via [MacFlim](https://github.com/fstark/macflim).

```bash
# 1-bit preview (Floyd-Steinberg dithered)
mac-flim preview input.jpg
mac-flim preview input.jpg --no-dither    # hard threshold

# Still image → .flim (5 second loop)
mac-flim image input.jpg output.flim
mac-flim image input.jpg output.flim -d 10    # 10 seconds

# Video → .flim
mac-flim video input.mp4 output.flim
mac-flim video input.mp4 output.flim --fps-ratio 1    # short clips only
mac-flim video input.mp4 output.flim --direct          # skip preprocessing
```

### Key settings

- `--profile plus` — byterate 1500, sized for Mac Plus SCSI throughput
- `--filters ""` — no gamma/blur, preserves crisp 1-bit pixels
- `--fps-ratio 2` (default) — safe for long content; use `1` only for short clips
- Floyd-Steinberg dithering by default — essential for photographic/gradient content

### Tips

- **flimmaker can't read MKV** — convert to MP4 first via ffmpeg
- **fps-ratio 1 can overwhelm Mac Plus SCSI** — stick with 2 for anything over ~30 seconds
- Set Mac Plus Memory Control Panel: Disk Cache → 32K, Virtual Memory → Off

## Dependencies

```bash
pip install Pillow numpy
pip install opencv-python          # video/GIF input
brew install ffmpeg                # frame assembly
brew install fstark/macflim/flimmaker
```

## License

MIT
