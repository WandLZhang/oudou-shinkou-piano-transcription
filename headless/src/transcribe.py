"""
Visual piano transcription from video with colored key highlights.
Detects which piano keys are pressed by analyzing color changes frame-by-frame.
"""

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import mido


def detect_keyboard_region(frame, y_ratio_start=0.75, y_ratio_end=1.0):
    """Find the keyboard region in the frame (bottom portion)."""
    h, w = frame.shape[:2]
    y_start = int(h * y_ratio_start)
    y_end = int(h * y_ratio_end)
    return frame[y_start:y_end, :], y_start


def detect_black_keys(keyboard_gray, min_width=10):
    """Detect black key positions from a grayscale keyboard image."""
    kb_h = keyboard_gray.shape[0]
    scan_y = int(kb_h * 0.15)
    row = keyboard_gray[scan_y, :]

    is_black = row < 80
    transitions = np.diff(is_black.astype(int))
    starts = np.where(transitions == 1)[0]
    ends = np.where(transitions == -1)[0]

    if len(ends) < len(starts):
        ends = np.append(ends, len(row) - 1)

    return [(s, e) for s, e in zip(starts, ends) if (e - s) > min_width]


def group_black_keys(black_keys):
    """Group black keys into octave groups (2s and 3s) and return the grouping pattern."""
    centers = [(s + e) // 2 for s, e in black_keys]
    if len(centers) < 2:
        return []

    gaps = [centers[i + 1] - centers[i] for i in range(len(centers) - 1)]
    median_gap = np.median(gaps)
    threshold = median_gap * 1.3

    groups = []
    current_group = [0]
    for i, gap in enumerate(gaps):
        if gap > threshold:
            groups.append(current_group)
            current_group = [i + 1]
        else:
            current_group.append(i + 1)
    groups.append(current_group)

    return groups


def build_key_map(black_keys, keyboard_width):
    """Build a mapping from pixel regions to MIDI note numbers.

    Standard 88-key piano: A0 (MIDI 21) to C8 (MIDI 108).
    Black keys pattern: 1 single (Bb0), then 7x (pair + triple).
    """
    groups = group_black_keys(black_keys)

    black_note_names_in_octave = ['C#', 'D#', 'F#', 'G#', 'A#']
    white_note_names_in_octave = ['C', 'D', 'E', 'F', 'G', 'A', 'B']

    key_map = []

    if len(groups) == 0:
        return key_map

    first_group_size = len(groups[0])
    if first_group_size == 1:
        start_octave = 0
        start_black_idx = 4  # A# = index 4 in black_note_names
    elif first_group_size == 2:
        start_octave = 1
        start_black_idx = 0  # C#
    elif first_group_size == 3:
        start_octave = 0
        start_black_idx = 2  # F#
    else:
        start_octave = 1
        start_black_idx = 0

    black_midi_notes = []
    octave = start_octave
    black_idx = start_black_idx

    for group in groups:
        for _ in group:
            note_name = black_note_names_in_octave[black_idx]
            if note_name == 'C#':
                midi_num = 12 * (octave + 1) + 1
            elif note_name == 'D#':
                midi_num = 12 * (octave + 1) + 3
            elif note_name == 'F#':
                midi_num = 12 * (octave + 1) + 6
            elif note_name == 'G#':
                midi_num = 12 * (octave + 1) + 8
            elif note_name == 'A#':
                midi_num = 12 * (octave + 1) + 10

            black_midi_notes.append(midi_num)
            black_idx += 1
            if black_idx >= 5:
                black_idx = 0
                octave += 1

    for i, (bk, midi_num) in enumerate(zip(black_keys, black_midi_notes)):
        s, e = bk
        key_map.append({
            'type': 'black',
            'midi': midi_num,
            'x_start': s,
            'x_end': e,
            'x_center': (s + e) // 2,
        })

    white_keys = compute_white_key_regions(black_keys, black_midi_notes, keyboard_width)
    key_map.extend(white_keys)

    key_map.sort(key=lambda k: k['midi'])
    return key_map


def compute_white_key_regions(black_keys, black_midi_notes, keyboard_width):
    """Compute white key pixel regions from black key positions."""
    white_keys = []

    all_white_midi = []
    if black_midi_notes:
        lowest = max(21, black_midi_notes[0] - 2)
        highest = min(108, black_midi_notes[-1] + 2)
    else:
        return white_keys

    for midi in range(lowest, highest + 1):
        note_in_octave = midi % 12
        if note_in_octave in [1, 3, 6, 8, 10]:  # black keys
            continue
        all_white_midi.append(midi)

    if not all_white_midi:
        return white_keys

    black_centers = [(s + e) // 2 for s, e in black_keys]
    black_widths = [e - s for s, e in black_keys]
    avg_black_width = np.mean(black_widths) if black_widths else 16

    for midi in all_white_midi:
        note_in_octave = midi % 12

        x_center = estimate_white_key_center(midi, black_keys, black_midi_notes, avg_black_width)
        if x_center is None:
            continue

        half_width = int(avg_black_width * 0.9)
        white_keys.append({
            'type': 'white',
            'midi': midi,
            'x_start': max(0, x_center - half_width),
            'x_end': min(keyboard_width, x_center + half_width),
            'x_center': x_center,
        })

    return white_keys


def estimate_white_key_center(midi, black_keys, black_midi_notes, avg_black_width):
    """Estimate the center x position of a white key based on neighboring black keys."""
    note_in_octave = midi % 12

    bk_dict = {}
    for (s, e), m in zip(black_keys, black_midi_notes):
        bk_dict[m] = (s + e) // 2

    if note_in_octave == 0:  # C: between B(below) and C#
        c_sharp = midi + 1
        if c_sharp in bk_dict:
            return bk_dict[c_sharp] - int(avg_black_width * 1.5)
    elif note_in_octave == 2:  # D: between C# and D#
        c_sharp = midi - 1
        d_sharp = midi + 1
        if c_sharp in bk_dict and d_sharp in bk_dict:
            return (bk_dict[c_sharp] + bk_dict[d_sharp]) // 2
    elif note_in_octave == 4:  # E: between D# and F#
        d_sharp = midi - 1
        if d_sharp in bk_dict:
            return bk_dict[d_sharp] + int(avg_black_width * 1.5)
    elif note_in_octave == 5:  # F: between E and F#
        f_sharp = midi + 1
        if f_sharp in bk_dict:
            return bk_dict[f_sharp] - int(avg_black_width * 1.5)
    elif note_in_octave == 7:  # G: between F# and G#
        f_sharp = midi - 1
        g_sharp = midi + 1
        if f_sharp in bk_dict and g_sharp in bk_dict:
            return (bk_dict[f_sharp] + bk_dict[g_sharp]) // 2
    elif note_in_octave == 9:  # A: between G# and A#
        g_sharp = midi - 1
        a_sharp = midi + 1
        if g_sharp in bk_dict and a_sharp in bk_dict:
            return (bk_dict[g_sharp] + bk_dict[a_sharp]) // 2
    elif note_in_octave == 11:  # B: between A# and next C#
        a_sharp = midi - 1
        if a_sharp in bk_dict:
            return bk_dict[a_sharp] + int(avg_black_width * 1.5)

    return None


def detect_pressed_keys(keyboard_bgr, keyboard_hsv, key_map, keyboard_height,
                        hue_range=(0, 20), sat_min=25, val_min=180):
    """Detect which keys are pressed based on color in the current frame.

    For white keys: look for pink/salmon tint (elevated saturation on bright keys).
    For black keys: look for red channel dominance (red highlight on dark surface).
    """
    pressed = set()
    kb_h = keyboard_height

    for key in key_map:
        x_start = key['x_start']
        x_end = key['x_end']

        if key['type'] == 'white':
            y_start = int(kb_h * 0.70)
            y_end = int(kb_h * 0.95)
            region = keyboard_hsv[y_start:y_end, x_start:x_end]
            if region.size == 0:
                continue

            h_channel = region[:, :, 0]
            s_channel = region[:, :, 1]
            v_channel = region[:, :, 2]

            mask = ((h_channel <= hue_range[1]) | (h_channel >= 170)) & \
                   (s_channel >= sat_min) & \
                   (v_channel >= val_min)

            ratio = np.count_nonzero(mask) / max(mask.size, 1)
            if ratio > 0.15:
                pressed.add(key['midi'])

        elif key['type'] == 'black':
            # Scan multiple vertical strips across the black key
            for y_frac in [0.05, 0.15, 0.25, 0.35]:
                y = int(kb_h * y_frac)
                region = keyboard_bgr[max(0, y - 2):y + 3, x_start:x_end]
                if region.size == 0:
                    continue

                r_ch = region[:, :, 2].astype(float)
                g_ch = region[:, :, 1].astype(float)
                b_ch = region[:, :, 0].astype(float)

                red_mask = (r_ch > 80) & (r_ch > g_ch * 1.5) & (r_ch > b_ch * 1.5)
                ratio = np.count_nonzero(red_mask) / max(red_mask.size, 1)
                if ratio > 0.15:
                    pressed.add(key['midi'])
                    break

    return pressed


def midi_note_name(midi_num):
    """Convert MIDI number to note name."""
    names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = (midi_num // 12) - 1
    note = names[midi_num % 12]
    return f"{note}{octave}"


def transcribe_video(video_path, output_midi, output_json=None,
                     kb_y_start=0.75, kb_y_end=1.0,
                     fps_sample=None, velocity=80):
    """Main transcription pipeline."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"Error: cannot open video {video_path}", file=sys.stderr)
        return

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if fps_sample is None:
        fps_sample = video_fps

    frame_skip = max(1, int(video_fps / fps_sample))

    print(f"Video: {width}x{height} @ {video_fps:.1f}fps, {total_frames} frames ({total_frames/video_fps:.1f}s)")
    print(f"Sampling every {frame_skip} frames ({fps_sample:.1f} effective fps)")

    ret, first_frame = cap.read()
    if not ret:
        print("Error: cannot read first frame", file=sys.stderr)
        return

    keyboard, y_offset = detect_keyboard_region(first_frame, kb_y_start, kb_y_end)
    gray = cv2.cvtColor(keyboard, cv2.COLOR_BGR2GRAY)
    black_keys = detect_black_keys(gray)
    print(f"Detected {len(black_keys)} black keys")

    key_map = build_key_map(black_keys, width)
    white_count = sum(1 for k in key_map if k['type'] == 'white')
    black_count = sum(1 for k in key_map if k['type'] == 'black')
    print(f"Key map: {white_count} white + {black_count} black = {len(key_map)} total keys")

    if key_map:
        lowest = min(k['midi'] for k in key_map)
        highest = max(k['midi'] for k in key_map)
        print(f"Range: {midi_note_name(lowest)} ({lowest}) to {midi_note_name(highest)} ({highest})")

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    note_events = []
    currently_pressed = set()
    frame_num = 0
    processed = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_num % frame_skip != 0:
            frame_num += 1
            continue

        timestamp = frame_num / video_fps

        keyboard = frame[int(height * kb_y_start):int(height * kb_y_end), :]
        kb_hsv = cv2.cvtColor(keyboard, cv2.COLOR_BGR2HSV)
        kb_h = keyboard.shape[0]

        pressed = detect_pressed_keys(keyboard, kb_hsv, key_map, kb_h)

        new_notes = pressed - currently_pressed
        released_notes = currently_pressed - pressed

        for note in new_notes:
            note_events.append({
                'type': 'note_on',
                'midi': note,
                'name': midi_note_name(note),
                'time': timestamp,
                'frame': frame_num,
            })

        for note in released_notes:
            note_events.append({
                'type': 'note_off',
                'midi': note,
                'name': midi_note_name(note),
                'time': timestamp,
                'frame': frame_num,
            })

        currently_pressed = pressed
        processed += 1
        frame_num += 1

        if processed % 500 == 0:
            print(f"  Processed {processed} frames ({timestamp:.1f}s), {len(note_events)} events so far")

    for note in currently_pressed:
        note_events.append({
            'type': 'note_off',
            'midi': note,
            'name': midi_note_name(note),
            'time': total_frames / video_fps,
            'frame': total_frames,
        })

    cap.release()

    note_events.sort(key=lambda e: (e['time'], e['type'] == 'note_on'))

    print(f"\nTotal events: {len(note_events)}")
    unique_notes = set(e['midi'] for e in note_events if e['type'] == 'note_on')
    print(f"Unique notes played: {len(unique_notes)}")
    print(f"Notes: {', '.join(midi_note_name(n) for n in sorted(unique_notes))}")

    write_midi(note_events, output_midi, velocity=velocity)
    print(f"MIDI saved to: {output_midi}")

    if output_json:
        def convert(obj):
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        with open(output_json, 'w') as f:
            json.dump({
                'video': str(video_path),
                'fps': video_fps,
                'total_frames': total_frames,
                'duration': total_frames / video_fps,
                'key_map': key_map,
                'events': note_events,
            }, f, indent=2, default=convert)
        print(f"JSON saved to: {output_json}")


def write_midi(events, output_path, velocity=80, ticks_per_beat=480, bpm=120):
    """Write note events to a MIDI file."""
    mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm)))

    seconds_per_tick = 60.0 / (bpm * ticks_per_beat)

    sorted_events = sorted(events, key=lambda e: e['time'])

    last_tick = 0
    for event in sorted_events:
        tick = int(event['time'] / seconds_per_tick)
        delta = max(0, tick - last_tick)
        last_tick = tick

        if event['type'] == 'note_on':
            track.append(mido.Message('note_on', note=event['midi'],
                                      velocity=velocity, time=delta))
        elif event['type'] == 'note_off':
            track.append(mido.Message('note_off', note=event['midi'],
                                      velocity=0, time=delta))

    mid.save(str(output_path))


def main():
    parser = argparse.ArgumentParser(description='Visual piano transcription from video')
    parser.add_argument('video', help='Path to video file')
    parser.add_argument('-o', '--output', default='output.mid', help='Output MIDI file path')
    parser.add_argument('--json', help='Also save events as JSON')
    parser.add_argument('--fps', type=float, default=30, help='Sampling FPS (default: 30)')
    parser.add_argument('--kb-top', type=float, default=0.75,
                        help='Keyboard region top (0-1 ratio, default: 0.75)')
    parser.add_argument('--kb-bottom', type=float, default=1.0,
                        help='Keyboard region bottom (0-1 ratio, default: 1.0)')
    parser.add_argument('--velocity', type=int, default=80, help='MIDI velocity (default: 80)')

    args = parser.parse_args()

    transcribe_video(
        video_path=args.video,
        output_midi=args.output,
        output_json=args.json,
        kb_y_start=args.kb_top,
        kb_y_end=args.kb_bottom,
        fps_sample=args.fps,
        velocity=args.velocity,
    )


if __name__ == '__main__':
    main()
