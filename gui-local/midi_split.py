#!/usr/bin/env python3
"""
@file midi_split.py
@brief Merge multi-channel video2midi output into one channel, then split into
       right hand / left hand tracks for piano sheet music.

@details Takes the raw video2midi MIDI output (which may have notes spread
across multiple MIDI channels due to multi-color detection), merges all notes
to a single channel, then splits into two tracks based on pitch:
  - Right hand: notes above F4 (MIDI > 65)
  - Left hand: notes at F4 and below (MIDI <= 65)
  - If right hand has 4+ simultaneous notes, the lowest are moved to left hand
Outputs a Type 1 MIDI with 2 tracks on channel 0 for proper MuseScore import
as a single piano with grand staff.

@author Willis Zhang
@date 2026-06-22
"""

import mido
import sys
import os


def merge_channels(input_path, output_path):
    """
    @brief Merge all MIDI channels to channel 0 in a single-track MIDI.

    @param input_path Path to the raw video2midi MIDI output
    @param output_path Path to save the merged MIDI
    @return int Total number of notes in the merged file
    """
    mid = mido.MidiFile(input_path)

    # Count notes before
    before_count = sum(
        1 for track in mid.tracks
        for msg in track
        if msg.type == 'note_on' and msg.velocity > 0
    )

    # Merge all channels to channel 0, remove duplicate program_changes
    new_track = mido.MidiTrack()
    for msg in mid.tracks[0]:
        if msg.type == 'program_change':
            continue
        if msg.type in ('note_on', 'note_off', 'control_change'):
            msg.channel = 0
        new_track.append(msg)

    mid.tracks[0] = new_track
    mid.save(output_path)

    after_count = sum(
        1 for msg in new_track
        if msg.type == 'note_on' and msg.velocity > 0
    )

    print(f"Merged: {before_count} -> {after_count} notes (channels merged to 0)")
    assert before_count == after_count, "ERROR: Note count mismatch after merge!"
    return after_count


def split_hands(input_path, output_path, split_point=65, max_rh_chord=3):
    """
    @brief Split a single-channel MIDI into right hand and left hand tracks.

    @param input_path Path to the merged single-channel MIDI
    @param output_path Path to save the split MIDI
    @param split_point MIDI note number for the split boundary.
           Notes <= split_point go to LH, notes > split_point go to RH.
           Default 65 = F4 (F above middle C).
    @param max_rh_chord Maximum simultaneous notes allowed in RH.
           If exceeded, lowest notes are moved to LH. Default 3.
    @return tuple (rh_count, lh_count, total)
    """
    mid = mido.MidiFile(input_path)
    old_track = mid.tracks[0]

    # Collect all events with absolute times
    events = []
    abs_time = 0
    meta_events = []

    for msg in old_track:
        abs_time += msg.time
        if msg.is_meta:
            meta_events.append((abs_time, msg.copy()))
        elif msg.type == 'note_on' and msg.velocity > 0:
            events.append({
                'type': 'note_on', 'time': abs_time,
                'note': msg.note, 'velocity': msg.velocity, 'hand': None
            })
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            events.append({
                'type': 'note_off', 'time': abs_time,
                'note': msg.note, 'velocity': 0, 'hand': None
            })

    note_ons = [e for e in events if e['type'] == 'note_on']

    # Group simultaneous note_ons (within 10 ticks)
    chords = []
    current_chord = []
    for e in note_ons:
        if not current_chord or abs(e['time'] - current_chord[0]['time']) <= 10:
            current_chord.append(e)
        else:
            chords.append(current_chord)
            current_chord = [e]
    if current_chord:
        chords.append(current_chord)

    # Assign hands based on pitch split
    for chord in chords:
        for e in chord:
            if e['note'] <= split_point:
                e['hand'] = 'LH'
            else:
                e['hand'] = 'RH'

        # If RH has too many notes, move lowest to LH
        rh_notes = sorted(
            [e for e in chord if e['hand'] == 'RH'],
            key=lambda x: x['note']
        )
        while len(rh_notes) > max_rh_chord:
            rh_notes[0]['hand'] = 'LH'
            rh_notes = rh_notes[1:]

    # Assign note_offs to the same hand as their note_on
    active_notes = {}
    for e in events:
        if e['type'] == 'note_on':
            active_notes[e['note']] = e['hand']
        elif e['type'] == 'note_off':
            e['hand'] = active_notes.get(e['note'], 'RH')

    # Build separate event lists for each hand
    rh_events = []
    lh_events = []
    for e in events:
        msg = mido.Message(
            e['type'], channel=0,
            note=e['note'], velocity=e['velocity'], time=0
        )
        if e['hand'] == 'RH':
            rh_events.append((e['time'], msg))
        else:
            lh_events.append((e['time'], msg))

    # Meta events go to RH track
    for t, msg in meta_events:
        rh_events.append((t, msg))

    rh_events.sort(key=lambda x: x[0])
    lh_events.sort(key=lambda x: x[0])

    def to_track(events, name):
        """Convert absolute-time events to a MIDI track with delta times."""
        track = mido.MidiTrack()
        track.append(mido.MetaMessage('track_name', name=name, time=0))
        prev = 0
        for t, msg in events:
            msg.time = t - prev
            track.append(msg)
            prev = t
        if not any(m.type == 'end_of_track' for m in track if m.is_meta):
            track.append(mido.MetaMessage('end_of_track', time=0))
        return track

    # Create Type 1 MIDI with 2 tracks (same channel for proper grand staff)
    new_mid = mido.MidiFile(type=1, ticks_per_beat=mid.ticks_per_beat)
    new_mid.tracks.append(to_track(rh_events, 'Piano'))
    new_mid.tracks.append(to_track(lh_events, 'Piano'))

    rh_count = sum(1 for m in new_mid.tracks[0] if m.type == 'note_on' and m.velocity > 0)
    lh_count = sum(1 for m in new_mid.tracks[1] if m.type == 'note_on' and m.velocity > 0)

    new_mid.save(output_path)

    print(f"Split at MIDI {split_point} (max {max_rh_chord} notes per RH chord):")
    print(f"  Right hand: {rh_count} notes")
    print(f"  Left hand:  {lh_count} notes")
    print(f"  Total:      {rh_count + lh_count}")

    return rh_count, lh_count, rh_count + lh_count


def main():
    """
    @brief Main entry point. Takes a video2midi output MIDI and produces
    merged and split versions.

    Usage: python midi_split.py <input.mid> [split_point] [max_rh_chord]
      split_point: MIDI note for LH/RH boundary (default 65 = F4)
      max_rh_chord: max simultaneous RH notes (default 3)
    """
    if len(sys.argv) < 2:
        print("Usage: python midi_split.py <input.mid> [split_point] [max_rh_chord]")
        print("  split_point: MIDI note for LH/RH boundary (default 65 = F4)")
        print("  max_rh_chord: max simultaneous RH notes (default 3)")
        sys.exit(1)

    input_path = sys.argv[1]
    split_point = int(sys.argv[2]) if len(sys.argv) > 2 else 65
    max_rh_chord = int(sys.argv[3]) if len(sys.argv) > 3 else 3

    base = os.path.splitext(input_path)[0]
    merged_path = base + '-merged.mid'
    split_path = base + '-split.mid'

    print(f"Input: {input_path}")
    print(f"---")

    total = merge_channels(input_path, merged_path)
    print(f"Saved merged: {merged_path}")
    print(f"---")

    rh, lh, total2 = split_hands(merged_path, split_path, split_point, max_rh_chord)
    print(f"Saved split: {split_path}")
    print(f"---")

    assert total == total2, f"ERROR: Note count mismatch! Merged={total}, Split={total2}"
    print(f"✅ All {total} notes preserved through merge and split pipeline.")


if __name__ == '__main__':
    main()
