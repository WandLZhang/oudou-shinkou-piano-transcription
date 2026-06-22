# 王道進行 Piano Video Transcription

Transcribe piano from [this 王道進行 tutorial video](https://www.youtube.com/watch?v=Fdx9fQv0qQU) to MIDI and sheet music using video-based key detection.

## Output Files

All artifacts are in [`gui-local/`](gui-local/):

| File | Description |
|------|-------------|
| `oudou-shinkou-split.pdf` | Final sheet music (RH/LH split) |
| `oudou-shinkou-split.mscz` | MuseScore 4 project (editable) |
| `oudou-shinkou-split.mid` | MIDI with RH/LH tracks (Type 1, 1776 notes) |
| `oudou-shinkou-merged.mid` | All notes merged to single channel |
| `oudou-shinkou-raw.mid` | Raw video2midi output (multi-channel) |
| `oudou-shinkou-video.mp4` | Source piano video (720p) |
| `v2m-settings.ini` | video2midi calibration settings |
| `midi_split.py` | Pipeline script: merge → split RH/LH |

## How It Works

### 1. Video → MIDI (video2midi GUI)

Uses [video2midi](https://github.com/svsdval/video2midi) to detect pressed piano keys by color in each video frame.

```bash
cd gui-local
git clone https://github.com/svsdval/video2midi.git
cd video2midi
python3 -m venv .venv && source .venv/bin/activate
pip install pygame-ce opencv-python midiutil PyOpenGL

# Copy settings and video
cp ../v2m-settings.ini video.mp4.ini
cp ../oudou-shinkou-video.mp4 video.mp4

# Run GUI, press F3 to load settings, then Q to process
python v2m.py video.mp4
```

### 2. MIDI Processing (merge + split)

The raw video2midi output has notes on multiple MIDI channels (due to multi-color detection). The `midi_split.py` script:
1. **Merges** all channels to channel 0 (no notes lost)
2. **Splits** into right hand / left hand tracks based on pitch

```bash
pip install mido
python ../midi_split.py video.mp4_6_output.mid 65 3
```

Arguments: `<input.mid> [split_point] [max_rh_chord]`
- `split_point`: MIDI note boundary (default 65 = F4, F above middle C). Notes ≤ F4 → LH, notes > F4 → RH.
- `max_rh_chord`: Max simultaneous RH notes (default 3). Excess lowest notes move to LH.

### 3. Sheet Music (MuseScore 4)

```bash
open -a "MuseScore 4" video.mp4_6_output-split.mid
```

Export as PDF from MuseScore: File → Export → PDF.

## What is 王道進行?

**Royal Road progression** (王道進行, *ōdō shinkō*): IV → V → iii → vi. The most common chord progression in J-pop, anime, and game music. In C major: F△ → G → Em7 → Am7.

The source video explores jazz reharmonizations: secondary dominants, tritone substitutions, passing diminished chords.
