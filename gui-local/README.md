# GUI-Based Piano Video Transcription (Local)

Interactive GUI tool using [video2midi](https://github.com/svsdval/video2midi) — best for fine-tuning key alignment and color selection visually.

## Prerequisites

- Python 3.9+
- A display (cannot run headless)
- The video file downloaded locally

## Setup

```bash
# Clone video2midi
git clone https://github.com/svsdval/video2midi.git
cd video2midi

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install pygame opencv-python midiutil PyOpenGL
```

## Usage

```bash
source .venv/bin/activate
python v2m.py
```

### Steps for 王道進行 video:

1. **Load video**: Open the downloaded video file (720p recommended)
2. **Align keyboard**: Use mouse wheel + arrow keys to position the virtual keyboard overlay over the video's piano
   - Left-click to drag a selected key
   - Right-click to drag all keys
   - `[` / `]` to change base octave
3. **Select colors**: Click on the red/pink key highlight color in the color map
   - The pressed keys in this video use a salmon/pink overlay
   - Each color maps to a MIDI channel
4. **Process**: Press `Q` to start processing
5. **Export**: A MIDI file is generated automatically

### Tips

- Use `o` toggle if keys overlap (notes ending/starting simultaneously)
- Use `i` toggle to handle very short notes
- Use `p` to force 2-channel split by key position (left/right hand)
- Save settings with `F2`, load with `F3`

## Download the video first

```bash
pip install yt-dlp
yt-dlp -f "bestvideo[height<=720]+bestaudio/best[height<=720]" --merge-output-format mp4 -o "video.mp4" "https://www.youtube.com/watch?v=Fdx9fQv0qQU"
```
