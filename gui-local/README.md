# GUI-Based Piano Video Transcription (Local)

Interactive GUI tool using [video2midi](https://github.com/svsdval/video2midi) — requires a display (can't run headless).

## Prerequisites

- Python 3.9+
- A display (cannot run headless)
- MuseScore 4 (for sheet music export): `brew install --cask musescore`

## Setup

```bash
# Clone video2midi
git clone https://github.com/svsdval/video2midi.git
cd video2midi

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies (use pygame-ce for Python 3.14+ compatibility)
pip install pygame-ce opencv-python midiutil PyOpenGL mido

# Copy the saved settings and video
cp ../v2m-settings.ini video.mp4.ini
cp ../oudou-shinkou-video.mp4 video.mp4
```

## Step 1: Generate Raw MIDI (video2midi GUI)

```bash
source .venv/bin/activate
python v2m.py video.mp4
```

### In the GUI:
1. Press **F3** to load saved settings (keyboard alignment, colors, sensitivity)
2. Verify the overlay aligns with the video piano keys
3. Press **Q** to process all frames → raw MIDI is generated

### Key controls:
- **Right-click drag** — move all keys together
- **Mouse wheel** — resize keyboard overlay
- **`[` / `]`** — change base octave
- **CTRL + left-click** — pick a color from the video for detection
- **`p`** — set left/right hand split point (hover over a key first)
- **`o`** — toggle overlap detection
- **`i`** — handle very short notes
- **`F2` / `F3`** — save / load settings
- **Roll check** — resolve adjacent key conflicts (color bleed)

### Color map tips:
- Multiple colors on the same channel is correct (white keys in shadow, black keys have different shades)
- The `+`/`-` buttons change the MIDI **channel number**, not add/remove colors
- The `X` button disables a color
- To pick a color: click the color square to select it, then **CTRL + left-click** on a highlighted key in the video

## Step 2: Merge & Split MIDI

The raw video2midi output has notes on multiple channels. Use `midi_split.py` to merge and split into right hand / left hand:

```bash
source .venv/bin/activate
python ../midi_split.py video.mp4_6_output.mid 65 3
```

This produces:
- `*-merged.mid` — all channels merged to channel 0 (baseline, no notes lost)
- `*-split.mid` — split into RH/LH tracks (Type 1 MIDI for MuseScore grand staff)

Split parameters:
- `65` = F4 (F above middle C). Notes ≤ F4 → left hand, > F4 → right hand.
- `3` = max 3 notes per right hand chord. If 4+, lowest moves to left hand.

## Step 3: Sheet Music (MuseScore 4)

```bash
open -a "MuseScore 4" video.mp4_6_output-split.mid
```

- If the bass clef keeps switching to treble clef: click each auto-inserted treble clef in the bass staff and press Delete
- Export PDF: File → Export → PDF
- The `.mscz` file preserves your MuseScore edits

## Files in this directory

| File | Description |
|------|-------------|
| `midi_split.py` | Pipeline: merge channels → split RH/LH tracks |
| `v2m-settings.ini` | video2midi calibration (copy to `video.mp4.ini`) |
| `oudou-shinkou-video.mp4` | Source piano video (720p) |
| `oudou-shinkou-raw.mid` | Raw video2midi output |
| `oudou-shinkou-merged.mid` | All channels merged (1776 notes) |
| `oudou-shinkou-split.mid` | RH/LH split (Type 1 MIDI, 1776 notes) |
| `oudou-shinkou-split.mscz` | MuseScore project (editable) |
| `oudou-shinkou-split.pdf` | Final PDF sheet music |
