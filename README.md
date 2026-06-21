# 王道進行 Piano Video Transcription

Transcribe piano from [this 王道進行 tutorial video](https://www.youtube.com/watch?v=Fdx9fQv0qQU) to MIDI and sheet music.

**Output files in this repo:**
- [`output.mid`](output.mid) — MIDI transcription
- [`sheet.pdf`](sheet.pdf) — Sheet music (14 pages)
- [`playback.mp3`](playback.mp3) — Audio render of the MIDI

## Three Approaches

| Folder | How it works | When to use |
|--------|-------------|-------------|
| [`visual/`](visual/) | OpenCV color detection on video frames | Headless, no GPU, videos with lit-up keys |
| [`audio/`](audio/) | ByteDance neural net on audio track | Better rhythm accuracy, needs PyTorch |
| [`gui-local/`](gui-local/) | Interactive [video2midi](https://github.com/svsdval/video2midi) | Fine-tuning on a machine with a display |

## Visual Transcription (headless)

```bash
cd visual
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

pip install yt-dlp
yt-dlp -f "bestvideo[height<=720]+bestaudio/best[height<=720]" \
  --merge-output-format mp4 -o video.mp4 "https://www.youtube.com/watch?v=Fdx9fQv0qQU"
ffmpeg -i video.mp4 -c:v libx264 -crf 18 -c:a copy video_h264.mp4

python3 transcribe.py video_h264.mp4 -o output.mid --fps 30 --kb-top 0.78
```

Detects pressed keys by color:
- **White keys** — HSV saturation > 25 (pink tint vs pure white)
- **Black keys** — Red channel dominance (R > 80, R > 1.5× G and B)

## Audio Transcription (better rhythm)

```bash
cd audio
python3 -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

python3 transcribe.py <video_or_wav> -o output.mid
```

Uses [piano_transcription_inference](https://github.com/qiuqiangkong/piano_transcription_inference) (CRNN, F1=0.9677, trained on MAESTRO).

## Sheet Music from MIDI

```bash
sudo apt install lilypond   # or: brew install lilypond
midi2ly output.mid -o sheet.ly
lilypond --pdf -o sheet sheet.ly
```

## Audio Render from MIDI

```bash
sudo apt install fluidsynth fluid-soundfont-gm
fluidsynth -ni /usr/share/sounds/sf2/FluidR3_GM.sf2 output.mid -F playback.wav
ffmpeg -i playback.wav -c:a libmp3lame -q:a 2 playback.mp3
```

## What is 王道進行?

**Royal Road progression** (王道進行, *ōdō shinkō*): IV → V → iii → vi. The most common chord progression in J-pop, anime, and game music. In C major: F△ → G → Em7 → Am7.

The source video explores jazz reharmonizations: secondary dominants, tritone substitutions, passing diminished chords.
