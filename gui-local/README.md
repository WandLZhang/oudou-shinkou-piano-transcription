# GUI-Based Transcription (Local Machine)

Interactive tool using [video2midi](https://github.com/svsdval/video2midi) — requires a display (can't run headless).

## Setup

```bash
git clone https://github.com/svsdval/video2midi.git
cd video2midi
python3 -m venv .venv && source .venv/bin/activate
pip install pygame opencv-python midiutil PyOpenGL
```

## Usage

```bash
python v2m.py
```

1. Load the video (720p recommended)
2. Align the virtual keyboard overlay to the video piano (mouse wheel + arrows)
3. Pick the red/pink key highlight color from the color map
4. Press `Q` to process → MIDI file is generated

### Useful controls
- `o` — toggle overlap detection (simultaneous note end/start)
- `i` — handle very short notes
- `p` — force left/right hand split by key position
- `F2`/`F3` — save/load settings
