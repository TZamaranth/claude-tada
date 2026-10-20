"""Generate the bundled sounds from scratch (Python stdlib only).

Every sample in sounds/*.wav comes from this script: no recordings, no samples
from anywhere else, so the files carry no third-party copyright. They are
released under CC0 (see sounds/CREDITS.md).

Usage: python tools/make-sounds.py   (writes sounds/done.wav, sounds/needs-input.wav)
"""

import math
import struct
import wave
from pathlib import Path
from typing import Callable

SAMPLE_RATE = 44100
DONE_PEAK = 0.7  # about -3 dBFS, leaves headroom so nothing clips
NEEDS_INPUT_PEAK = 0.5  # softer: a nudge, not an alarm
SOUNDS_DIRECTORY = Path(__file__).resolve().parent.parent / "sounds"

# Bell-like timbre: partial ratio -> relative strength. The slightly inharmonic
# upper partials are what make it read as a chime instead of a plain beep.
BELL_PARTIALS: dict[float, float] = {1.0: 1.0, 2.0: 0.45, 3.01: 0.2, 4.2: 0.08}


def note_frequency(midi_note: int) -> float:
    return 440.0 * 2 ** ((midi_note - 69) / 12)


def bell_tone(frequency: float, start_seconds: float, decay_seconds: float, loudness: float) -> Callable[[float], float]:
    """One struck-bell note: a 5 ms attack, then exponential decay. Higher partials die faster."""

    def sample_at(time_seconds: float) -> float:
        elapsed = time_seconds - start_seconds
        if elapsed < 0:
            return 0.0
        attack = min(1.0, elapsed / 0.005)
        total = 0.0
        for ratio, strength in BELL_PARTIALS.items():
            partial_decay = decay_seconds / ratio
            total += strength * math.exp(-elapsed / partial_decay) * math.sin(2 * math.pi * frequency * ratio * elapsed)
        return loudness * attack * total

    return sample_at


def render(tones: list[Callable[[float], float]], duration_seconds: float) -> list[float]:
    sample_count = int(SAMPLE_RATE * duration_seconds)
    samples = [sum(tone(index / SAMPLE_RATE) for tone in tones) for index in range(sample_count)]
    fade_out_samples = int(SAMPLE_RATE * 0.05)
    for offset in range(fade_out_samples):
        samples[sample_count - 1 - offset] *= offset / fade_out_samples
    return samples


def write_wav(samples: list[float], output_path: Path, peak_amplitude: float) -> None:
    loudest = max(abs(sample) for sample in samples)
    if loudest == 0:
        raise ValueError(f"refusing to write a silent file: {output_path}")
    scale = peak_amplitude / loudest
    frames = b"".join(struct.pack("<h", int(sample * scale * 32767)) for sample in samples)
    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(frames)


def done_sound() -> list[float]:
    """'Ta-da!': a quick pickup note, then a bright major triad that rings out."""
    tones = [
        bell_tone(note_frequency(79), 0.00, 0.25, 0.8),  # G5 pickup ("ta-")
        bell_tone(note_frequency(84), 0.12, 0.60, 1.0),  # C6 ("-da!")
        bell_tone(note_frequency(88), 0.12, 0.55, 0.6),  # E6
        bell_tone(note_frequency(91), 0.14, 0.50, 0.45),  # G6, a hair late for sparkle
    ]
    return render(tones, 1.1)


def needs_input_sound() -> list[float]:
    """'Hm?': two soft rising notes, like a question."""
    tones = [
        bell_tone(note_frequency(76), 0.00, 0.30, 0.7),  # E5
        bell_tone(note_frequency(81), 0.16, 0.45, 0.8),  # A5
    ]
    return render(tones, 0.8)


def main() -> None:
    SOUNDS_DIRECTORY.mkdir(exist_ok=True)
    write_wav(done_sound(), SOUNDS_DIRECTORY / "done.wav", DONE_PEAK)
    write_wav(needs_input_sound(), SOUNDS_DIRECTORY / "needs-input.wav", NEEDS_INPUT_PEAK)
    print(f"wrote done.wav and needs-input.wav to {SOUNDS_DIRECTORY}")


if __name__ == "__main__":
    main()
