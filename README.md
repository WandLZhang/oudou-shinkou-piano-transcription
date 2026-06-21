# 王道進行 Visual Piano Transcription

Visual piano transcription using computer vision — detects which keys are pressed by analyzing color highlights in piano tutorial videos frame-by-frame. Outputs MIDI files.

Built for videos like [this 王道進行 (Royal Road chord progression) tutorial](https://www.youtube.com/watch?v=Fdx9fQv0qQU) where keys light up when pressed.

## How It Works

1. **Detect keyboard region** — finds the piano keyboard in the bottom portion of each video frame
2. **Map key boundaries** — identifies all 88 keys by detecting the black key pattern (groups of 2 and 3)
3. **Frame-by-frame color detection**:
   - **White keys**: HSV saturation thresholding (pressed keys show a pink/salmon tint vs pure white)
   - **Black keys**: Red channel dominance detection (R > 80, R > G×1.5, R > B×1.5)
4. **Track note events** — detects onset (key goes from unpressed → pressed) and offset (pressed → released)
5. **Generate MIDI** — maps pixel positions to MIDI note numbers and writes a standard MIDI file

## Two Approaches

### [`headless/`](headless/) — Scriptable CV Pipeline (No GUI)

Runs anywhere including cloud/SSH. Pure Python with OpenCV.

```bash
cd headless
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Download video
pip install yt-dlp
yt-dlp -f "bestvideo[height<=720]+bestaudio/best[height<=720]" --merge-output-format mp4 -o video.mp4 "https://www.youtube.com/watch?v=Fdx9fQv0qQU"

# If video is AV1 encoded (OpenCV may not decode it), re-encode to H.264:
ffmpeg -i video.mp4 -c:v libx264 -crf 18 -c:a copy video_h264.mp4

# Transcribe
python3 src/transcribe.py video_h264.mp4 -o output.mid --json output.json --fps 30 --kb-top 0.78
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `-o` | `output.mid` | Output MIDI file path |
| `--json` | — | Also save note events as JSON |
| `--fps` | 30 | Sampling rate (higher = more accurate timing, slower) |
| `--kb-top` | 0.75 | Where the keyboard starts (0 = top, 1 = bottom of frame) |
| `--kb-bottom` | 1.0 | Where the keyboard ends |
| `--velocity` | 80 | MIDI note velocity |

### [`gui-local/`](gui-local/) — Interactive GUI (Local Machine)

Uses [video2midi](https://github.com/svsdval/video2midi) for interactive keyboard alignment and color picking. Requires a display. See [gui-local/README.md](gui-local/README.md) for setup instructions.

## What is 王道進行?

The **Royal Road progression** (王道進行, *ōdō shinkō*) is IV→V→iii→vi in Japanese pop music — the "royal road" because it's the most common chord progression in J-pop, anime, and game music. In C major: FΔ → G → E-7 → A-7, often extended to IV→V→iii→vi→ii→V→I.

This video explores jazz variations on the progression: secondary dominants, tritone substitutions, passing diminished chords, and other reharmonizations.

## Limitations

- Detection accuracy depends on video quality and the distinctness of the key highlight color
- Very fast repeated notes on the same key may merge if no frame captures the key in released state between presses
- The keyboard region parameters (`--kb-top`, `--kb-bottom`) may need adjustment for different video layouts
- Works best with videos that have clear, solid-color key highlights (not gradients or particle effects)
