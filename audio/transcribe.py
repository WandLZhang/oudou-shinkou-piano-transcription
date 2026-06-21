"""
Audio-based piano transcription using ByteDance's piano_transcription_inference.
Produces cleaner rhythmic output than visual detection.
"""

import argparse
import subprocess
import sys
from pathlib import Path

from piano_transcription_inference import PianoTranscription, sample_rate, load_audio


def extract_audio(video_path, audio_path):
    """Extract audio from video file."""
    subprocess.run([
        'ffmpeg', '-y', '-i', str(video_path),
        '-vn', '-acodec', 'pcm_s16le', '-ar', str(sample_rate), '-ac', '1',
        str(audio_path)
    ], capture_output=True, check=True)


def transcribe(input_path, output_midi, device='cpu'):
    audio_path = input_path

    if not str(input_path).endswith('.wav'):
        audio_path = Path(input_path).with_suffix('.audio.wav')
        print(f"Extracting audio → {audio_path}")
        extract_audio(input_path, audio_path)

    print("Loading audio...")
    audio, sr = load_audio(str(audio_path), sr=sample_rate, mono=True)
    print(f"Audio: {len(audio)/sr:.1f}s at {sr}Hz")

    print("Loading model...")
    transcriptor = PianoTranscription(device=device)

    print("Transcribing...")
    transcriptor.transcribe(audio, str(output_midi))
    print(f"MIDI → {output_midi}")


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Audio-based piano transcription')
    p.add_argument('input', help='Video or WAV file')
    p.add_argument('-o', '--output', default='output.mid')
    p.add_argument('--device', default='cpu', help='cpu or cuda')
    a = p.parse_args()
    transcribe(a.input, a.output, a.device)
