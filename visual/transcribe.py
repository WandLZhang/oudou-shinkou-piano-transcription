"""
Visual piano transcription — detects pressed keys from video frame color analysis.

White keys: HSV saturation thresholding (pink/salmon tint vs pure white).
Black keys: Red channel dominance (R>80, R>G*1.5, R>B*1.5).
"""

import argparse
import json
import sys

import cv2
import numpy as np
import mido

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
BLACK_SEMITONES = {1, 3, 6, 8, 10}


def midi_note_name(n):
    return f"{NOTE_NAMES[n % 12]}{(n // 12) - 1}"


def detect_black_keys(keyboard_gray, min_width=10):
    kb_h = keyboard_gray.shape[0]
    row = keyboard_gray[int(kb_h * 0.15), :]
    is_black = row < 80
    transitions = np.diff(is_black.astype(int))
    starts = np.where(transitions == 1)[0]
    ends = np.where(transitions == -1)[0]
    if len(ends) < len(starts):
        ends = np.append(ends, len(row) - 1)
    return [(s, e) for s, e in zip(starts, ends) if (e - s) > min_width]


def build_key_map(black_keys, keyboard_width):
    centers = [(s + e) // 2 for s, e in black_keys]
    if len(centers) < 2:
        return []

    gaps = [centers[i + 1] - centers[i] for i in range(len(centers) - 1)]
    median_gap = np.median(gaps)
    threshold = median_gap * 1.3

    groups = []
    cur = [0]
    for i, gap in enumerate(gaps):
        if gap > threshold:
            groups.append(cur)
            cur = [i + 1]
        else:
            cur.append(i + 1)
    groups.append(cur)

    first_size = len(groups[0])
    octave = 0 if first_size in (1, 3) else 1
    black_idx = {1: 4, 2: 0, 3: 2}.get(first_size, 0)

    black_in_octave = [('C#', 1), ('D#', 3), ('F#', 6), ('G#', 8), ('A#', 10)]
    key_map = []
    avg_w = int(np.mean([e - s for s, e in black_keys]))

    for group in groups:
        for ki in group:
            s, e = black_keys[ki]
            _, semitone = black_in_octave[black_idx]
            midi = 12 * (octave + 1) + semitone
            key_map.append({'type': 'black', 'midi': midi, 'x0': s, 'x1': e})
            black_idx += 1
            if black_idx >= 5:
                black_idx = 0
                octave += 1

    bk = {k['midi']: (k['x0'] + k['x1']) // 2 for k in key_map}
    lowest = max(21, min(bk) - 2)
    highest = min(108, max(bk) + 2)
    hw = int(avg_w * 0.9)

    for midi in range(lowest, highest + 1):
        if midi % 12 in BLACK_SEMITONES:
            continue
        cx = _white_center(midi, bk, avg_w)
        if cx is not None:
            key_map.append({
                'type': 'white', 'midi': midi,
                'x0': max(0, cx - hw), 'x1': min(keyboard_width, cx + hw),
            })

    key_map.sort(key=lambda k: k['midi'])
    return key_map


def _white_center(midi, bk, bw):
    n = midi % 12
    offsets = {
        0: [(midi + 1, -1.5)],
        2: [(midi - 1, 0), (midi + 1, 0)],
        4: [(midi - 1, 1.5)],
        5: [(midi + 1, -1.5)],
        7: [(midi - 1, 0), (midi + 1, 0)],
        9: [(midi - 1, 0), (midi + 1, 0)],
        11: [(midi - 1, 1.5)],
    }
    refs = offsets.get(n, [])
    if len(refs) == 2 and refs[0][0] in bk and refs[1][0] in bk:
        return (bk[refs[0][0]] + bk[refs[1][0]]) // 2
    for ref_midi, mult in refs:
        if ref_midi in bk:
            return bk[ref_midi] + int(bw * mult)
    return None


def detect_pressed(kb_bgr, kb_hsv, key_map, kb_h):
    pressed = set()
    for key in key_map:
        x0, x1 = key['x0'], key['x1']
        if key['type'] == 'white':
            y0, y1 = int(kb_h * 0.70), int(kb_h * 0.95)
            region = kb_hsv[y0:y1, x0:x1]
            if region.size == 0:
                continue
            mask = (
                ((region[:, :, 0] <= 20) | (region[:, :, 0] >= 170))
                & (region[:, :, 1] >= 25)
                & (region[:, :, 2] >= 180)
            )
            if np.count_nonzero(mask) / max(mask.size, 1) > 0.15:
                pressed.add(key['midi'])
        else:
            for yf in (0.05, 0.15, 0.25, 0.35):
                y = int(kb_h * yf)
                region = kb_bgr[max(0, y - 2):y + 3, x0:x1]
                if region.size == 0:
                    continue
                r = region[:, :, 2].astype(float)
                g = region[:, :, 1].astype(float)
                b = region[:, :, 0].astype(float)
                red = (r > 80) & (r > g * 1.5) & (r > b * 1.5)
                if np.count_nonzero(red) / max(red.size, 1) > 0.15:
                    pressed.add(key['midi'])
                    break
    return pressed


def transcribe(video_path, output_midi, output_json=None,
               kb_top=0.75, kb_bottom=1.0, fps_sample=30, velocity=80):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"Cannot open {video_path}", file=sys.stderr)
        return

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    vfps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    skip = max(1, int(vfps / fps_sample))

    print(f"Video: {w}x{h} @ {vfps:.0f}fps, {total/vfps:.0f}s | sampling every {skip} frames")

    ret, frame = cap.read()
    if not ret:
        print("Cannot read first frame", file=sys.stderr)
        return

    y0, y1 = int(h * kb_top), int(h * kb_bottom)
    kb = frame[y0:y1, :]
    gray = cv2.cvtColor(kb, cv2.COLOR_BGR2GRAY)
    blacks = detect_black_keys(gray)
    key_map = build_key_map(blacks, w)
    nw = sum(1 for k in key_map if k['type'] == 'white')
    nb = sum(1 for k in key_map if k['type'] == 'black')
    print(f"Keys: {nw} white + {nb} black = {nw + nb} total")

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    events = []
    active = set()
    frame_num = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_num % skip != 0:
            frame_num += 1
            continue

        t = frame_num / vfps
        kb = frame[y0:y1, :]
        hsv = cv2.cvtColor(kb, cv2.COLOR_BGR2HSV)
        pressed = detect_pressed(kb, hsv, key_map, kb.shape[0])

        for n in pressed - active:
            events.append({'type': 'note_on', 'midi': n, 'time': t})
        for n in active - pressed:
            events.append({'type': 'note_off', 'midi': n, 'time': t})
        active = pressed
        frame_num += 1

    for n in active:
        events.append({'type': 'note_off', 'midi': n, 'time': total / vfps})
    cap.release()

    events.sort(key=lambda e: (e['time'], e['type'] == 'note_on'))
    unique = sorted(set(e['midi'] for e in events if e['type'] == 'note_on'))
    print(f"Events: {len(events)} | Unique notes: {len(unique)}")
    print(f"Notes: {', '.join(midi_note_name(n) for n in unique)}")

    _write_midi(events, output_midi, velocity)
    print(f"MIDI → {output_midi}")

    if output_json:
        def conv(o):
            if isinstance(o, np.integer): return int(o)
            if isinstance(o, np.floating): return float(o)
            raise TypeError(type(o))

        with open(output_json, 'w') as f:
            json.dump({'events': events, 'key_map': key_map,
                       'fps': vfps, 'duration': total / vfps}, f, indent=2, default=conv)
        print(f"JSON → {output_json}")


def _write_midi(events, path, velocity=80, tpb=480, bpm=120):
    mid = mido.MidiFile(ticks_per_beat=tpb)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm)))

    spt = 60.0 / (bpm * tpb)
    last = 0
    for e in sorted(events, key=lambda e: e['time']):
        tick = int(e['time'] / spt)
        delta = max(0, tick - last)
        last = tick
        track.append(mido.Message(
            e['type'], note=e['midi'],
            velocity=velocity if e['type'] == 'note_on' else 0, time=delta))
    mid.save(str(path))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Visual piano transcription')
    p.add_argument('video', help='Video file path')
    p.add_argument('-o', '--output', default='output.mid')
    p.add_argument('--json', help='Also save events as JSON')
    p.add_argument('--fps', type=float, default=30)
    p.add_argument('--kb-top', type=float, default=0.75)
    p.add_argument('--kb-bottom', type=float, default=1.0)
    p.add_argument('--velocity', type=int, default=80)
    a = p.parse_args()
    transcribe(a.video, a.output, a.json, a.kb_top, a.kb_bottom, a.fps, a.velocity)
