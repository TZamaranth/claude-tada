"""Generate the bundled sound library from scratch (Python stdlib only).

Every sample in sounds/*.wav comes from this script: oscillators, filtered
noise and plucked-string models. No recordings, no samples from anywhere else,
so the files carry no third-party copyright. They are released under CC0 (see
sounds/CREDITS.md).

Usage: python tools/make-sounds.py
Writes sounds/<name>.wav for every sound below, plus sounds/catalog.tsv
(name, kind, description), which the scripts and the preview page read.

Each sound is a function registered with @sound. To add one, write a function
that returns a list of samples and decorate it; the random seeds are fixed so
every run produces identical files.
"""

import math
import random
import struct
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

SAMPLE_RATE = 44100
REPOSITORY_DIRECTORY = Path(__file__).resolve().parent.parent
SOUNDS_DIRECTORY = REPOSITORY_DIRECTORY / "sounds"

Signal = list[float]
FrequencyCurve = Callable[[float], float]

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------


def note(midi_note: float) -> float:
    return 440.0 * 2 ** ((midi_note - 69) / 12)


def sample_count(seconds: float) -> int:
    return int(SAMPLE_RATE * seconds)


def steady(frequency: float) -> FrequencyCurve:
    return lambda time_seconds: frequency


def glide(start_frequency: float, end_frequency: float, glide_seconds: float) -> FrequencyCurve:
    """Exponential pitch slide (sounds even to the ear), then holds the end pitch."""
    ratio = end_frequency / start_frequency
    return lambda time_seconds: start_frequency * ratio ** min(1.0, time_seconds / glide_seconds)


def with_vibrato(curve: FrequencyCurve, rate_hz: float, depth: float) -> FrequencyCurve:
    return lambda time_seconds: curve(time_seconds) * (1 + depth * math.sin(2 * math.pi * rate_hz * time_seconds))


def wave_sine(phase: float) -> float:
    return math.sin(2 * math.pi * phase)


def wave_square(phase: float) -> float:
    return 1.0 if phase < 0.5 else -1.0


def wave_pulse(phase: float) -> float:
    return 1.0 if phase < 0.25 else -1.0


def wave_triangle(phase: float) -> float:
    return 4 * abs(phase - 0.5) - 1


def wave_saw(phase: float) -> float:
    return 2 * phase - 1


def oscillator(waveform: Callable[[float], float], frequency_at: FrequencyCurve, seconds: float) -> Signal:
    """Phase-accumulating oscillator, so pitch slides stay smooth."""
    phase = 0.0
    output: Signal = []
    for index in range(sample_count(seconds)):
        output.append(waveform(phase))
        phase = (phase + frequency_at(index / SAMPLE_RATE) / SAMPLE_RATE) % 1.0
    return output


def noise(seconds: float, seed: int) -> Signal:
    generator = random.Random(seed)
    return [generator.uniform(-1.0, 1.0) for _ in range(sample_count(seconds))]


def decay(signal: Signal, attack_seconds: float, decay_seconds: float) -> Signal:
    """Linear attack, then exponential decay with the given time constant."""
    output: Signal = []
    for index, value in enumerate(signal):
        time_seconds = index / SAMPLE_RATE
        attack = min(1.0, time_seconds / attack_seconds) if attack_seconds > 0 else 1.0
        output.append(value * attack * math.exp(-time_seconds / decay_seconds))
    return output


def adsr(signal: Signal, attack_seconds: float, decay_seconds: float, sustain_level: float, release_seconds: float) -> Signal:
    """Classic envelope; the release starts release_seconds before the signal ends."""
    total_seconds = len(signal) / SAMPLE_RATE
    release_start = total_seconds - release_seconds
    output: Signal = []
    for index, value in enumerate(signal):
        time_seconds = index / SAMPLE_RATE
        if time_seconds < attack_seconds:
            level = time_seconds / attack_seconds
        elif time_seconds < attack_seconds + decay_seconds:
            level = 1 - (1 - sustain_level) * (time_seconds - attack_seconds) / decay_seconds
        else:
            level = sustain_level
        if time_seconds > release_start:
            level *= max(0.0, (total_seconds - time_seconds) / release_seconds)
        output.append(value * level)
    return output


def lowpass(signal: Signal, cutoff_hz: float) -> Signal:
    coefficient = 1 - math.exp(-2 * math.pi * cutoff_hz / SAMPLE_RATE)
    state = 0.0
    output: Signal = []
    for value in signal:
        state += coefficient * (value - state)
        output.append(state)
    return output


def highpass(signal: Signal, cutoff_hz: float) -> Signal:
    return [value - smoothed for value, smoothed in zip(signal, lowpass(signal, cutoff_hz))]


def bandpass(signal: Signal, low_hz: float, high_hz: float) -> Signal:
    return lowpass(highpass(signal, low_hz), high_hz)


def scale(signal: Signal, gain: float) -> Signal:
    return [value * gain for value in signal]


def mix(total_seconds: float, parts: list[tuple[float, Signal]]) -> Signal:
    """Lay each (start_seconds, signal) onto a silent track; signals past the end are cut."""
    track = [0.0] * sample_count(total_seconds)
    for start_seconds, signal in parts:
        offset = sample_count(start_seconds)
        for index, value in enumerate(signal):
            if offset + index >= len(track):
                break
            track[offset + index] += value
    return track


def echo(signal: Signal, delay_seconds: float, feedback: float, tail_seconds: float) -> Signal:
    """Feedback delay; extends the signal by tail_seconds so the echoes can ring out."""
    delay_samples = sample_count(delay_seconds)
    output = signal + [0.0] * sample_count(tail_seconds)
    for index in range(delay_samples, len(output)):
        output[index] += feedback * output[index - delay_samples]
    return output


def fade_out(signal: Signal, seconds: float) -> Signal:
    fade_samples = min(len(signal), sample_count(seconds))
    output = list(signal)
    for offset in range(fade_samples):
        output[len(output) - 1 - offset] *= offset / fade_samples
    return output


def additive_bell(frequency: float, seconds: float, decay_seconds: float, partials: dict[float, float]) -> Signal:
    """Sum of sine partials (ratio -> strength); higher partials die faster, like a struck bar."""
    output = [0.0] * sample_count(seconds)
    for ratio, strength in partials.items():
        partial = decay(oscillator(wave_sine, steady(frequency * ratio), seconds), 0.003, decay_seconds / ratio)
        for index, value in enumerate(partial):
            output[index] += strength * value
    return output


def fm_tone(frequency: float, seconds: float, modulator_ratio: float, peak_index: float, index_decay_seconds: float) -> Signal:
    """Two-operator FM: the brightness (modulation index) fades faster than the note."""
    output: Signal = []
    for index in range(sample_count(seconds)):
        time_seconds = index / SAMPLE_RATE
        modulation_index = peak_index * math.exp(-time_seconds / index_decay_seconds)
        modulator = math.sin(2 * math.pi * frequency * modulator_ratio * time_seconds)
        output.append(math.sin(2 * math.pi * frequency * time_seconds + modulation_index * modulator))
    return output


def pluck(frequency: float, seconds: float, sustain: float, seed: int) -> Signal:
    """Karplus-Strong plucked string: a burst of noise recirculated through a softening loop."""
    generator = random.Random(seed)
    period = max(2, round(SAMPLE_RATE / frequency))
    buffer = lowpass([generator.uniform(-1.0, 1.0) for _ in range(period)], 6000)
    output: Signal = []
    position = 0
    for _ in range(sample_count(seconds)):
        current = buffer[position]
        following = buffer[(position + 1) % period]
        buffer[position] = sustain * 0.5 * (current + following)
        output.append(current)
        position = (position + 1) % period
    return output


BELL_PARTIALS: dict[float, float] = {1.0: 1.0, 2.0: 0.45, 3.01: 0.2, 4.2: 0.08}
METAL_BAR_PARTIALS: dict[float, float] = {1.0: 1.0, 2.76: 0.5, 5.40: 0.25, 8.93: 0.12}
GLASS_PARTIALS: dict[float, float] = {1.0: 1.0, 2.32: 0.6, 4.25: 0.35, 6.63: 0.2}

# ---------------------------------------------------------------------------
# The library
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SoundSpec:
    name: str
    kind: str  # "done" (celebratory) or "nudge" (asks for attention); any sound works for either event
    description: str
    peak: float
    build: Callable[[], Signal]


SOUND_LIBRARY: dict[str, SoundSpec] = {}


def sound(name: str, kind: str, description: str, peak: float = 0.7) -> Callable[[Callable[[], Signal]], Callable[[], Signal]]:
    def register(build: Callable[[], Signal]) -> Callable[[], Signal]:
        if name in SOUND_LIBRARY:
            raise ValueError(f"duplicate sound name: {name}")
        SOUND_LIBRARY[name] = SoundSpec(name, kind, description, peak, build)
        return build

    return register


# --- Celebratory: good for "done" -------------------------------------------


@sound("tada", "done", "Bell 'ta-da!': a pickup note, then a bright major chord. The default for done.")
def build_tada() -> Signal:
    return fade_out(
        mix(
            1.1,
            [
                (0.00, scale(additive_bell(note(79), 1.1, 0.25, BELL_PARTIALS), 0.8)),
                (0.12, additive_bell(note(84), 1.0, 0.60, BELL_PARTIALS)),
                (0.12, scale(additive_bell(note(88), 1.0, 0.55, BELL_PARTIALS), 0.6)),
                (0.14, scale(additive_bell(note(91), 1.0, 0.50, BELL_PARTIALS), 0.45)),
            ],
        ),
        0.05,
    )


@sound("coin", "done", "8-bit coin pickup: two quick chiptune notes.", peak=0.4)
def build_coin() -> Signal:
    first = oscillator(wave_pulse, steady(note(84)), 0.07)
    second = decay(oscillator(wave_pulse, steady(note(91)), 0.5), 0.002, 0.14)
    return fade_out(mix(0.57, [(0.0, first), (0.07, second)]), 0.03)


@sound("level-up", "done", "Chiptune level-up: a fast rising arpeggio.", peak=0.4)
def build_level_up() -> Signal:
    notes = [72, 76, 79, 84, 88]
    parts = [(position * 0.06, oscillator(wave_square, steady(note(midi)), 0.06)) for position, midi in enumerate(notes[:-1])]
    parts.append((0.24, decay(oscillator(wave_square, steady(note(notes[-1])), 0.45), 0.002, 0.18)))
    return fade_out(echo(lowpass(mix(0.7, parts), 5000), 0.12, 0.25, 0.3), 0.08)


@sound("power-up", "done", "Rising chiptune power-up sweep with a wobble.", peak=0.32)
def build_power_up() -> Signal:
    sweep = oscillator(wave_square, with_vibrato(glide(260, 1300, 0.55), 14, 0.06), 0.65)
    return fade_out(lowpass(adsr(sweep, 0.01, 0.1, 0.8, 0.12), 6000), 0.03)


@sound("fanfare", "done", "Brassy 'da-da-daaa!' fanfare.", peak=0.65)
def build_fanfare() -> Signal:
    def brass_chord(midi_notes: list[int], seconds: float) -> Signal:
        chord = [0.0] * sample_count(seconds)
        for midi in midi_notes:
            voice = oscillator(wave_saw, with_vibrato(steady(note(midi)), 5.5, 0.004), seconds)
            chord = [total + value for total, value in zip(chord, voice)]
        return adsr(lowpass(lowpass(chord, 2600), 3200), 0.02, 0.08, 0.75, 0.06)

    short_chord = [67, 72, 76]
    long_chord = [72, 76, 79, 84]
    parts = [(0.0, brass_chord(short_chord, 0.11)), (0.14, brass_chord(short_chord, 0.11)), (0.28, brass_chord(long_chord, 0.7))]
    return fade_out(echo(mix(1.0, parts), 0.09, 0.2, 0.25), 0.15)


@sound("marimba", "done", "Three warm marimba notes going up.")
def build_marimba() -> Signal:
    parts = [(position * 0.1, decay(fm_tone(note(midi), 0.8, 4.0, 2.2, 0.03), 0.002, 0.28)) for position, midi in enumerate([79, 83, 86])]
    return fade_out(mix(1.0, parts), 0.1)


@sound("kalimba", "done", "Plinky thumb-piano phrase.")
def build_kalimba() -> Signal:
    def kalimba_note(frequency: float) -> Signal:
        body = decay(oscillator(wave_sine, steady(frequency), 0.9), 0.002, 0.45)
        tine_click = scale(decay(oscillator(wave_sine, steady(frequency * 5.4), 0.9), 0.001, 0.02), 0.3)
        return [low + high for low, high in zip(body, tine_click)]

    timing = [(0.0, 74), (0.11, 78), (0.22, 81), (0.4, 86)]
    return fade_out(mix(1.3, [(start, kalimba_note(note(midi))) for start, midi in timing]), 0.1)


@sound("harp", "done", "Harp glissando sweeping up a pentatonic scale.")
def build_harp() -> Signal:
    scale_notes = [72, 74, 76, 79, 81, 84, 86, 88, 91]
    parts = [(position * 0.045, pluck(note(midi), 1.3, 0.996, seed=position)) for position, midi in enumerate(scale_notes)]
    return fade_out(mix(1.6, parts), 0.25)


@sound("ding", "done", "One clear desk-bell ding.")
def build_ding() -> Signal:
    return fade_out(additive_bell(note(93), 1.3, 2.4, METAL_BAR_PARTIALS), 0.15)


@sound("doorbell", "done", "Classic 'ding-dong' doorbell.")
def build_doorbell() -> Signal:
    parts = [(0.0, additive_bell(note(76), 1.6, 2.4, METAL_BAR_PARTIALS)), (0.45, additive_bell(note(72), 1.6, 2.4, METAL_BAR_PARTIALS))]
    return fade_out(mix(1.9, parts), 0.3)


@sound("wind-chimes", "done", "A breeze through high wind chimes.", peak=0.6)
def build_wind_chimes() -> Signal:
    generator = random.Random(7)
    pentatonic = [84, 86, 88, 91, 93, 96]
    parts: list[tuple[float, Signal]] = []
    for strike in range(8):
        start = strike * 0.11 + generator.uniform(0, 0.05)
        loudness = generator.uniform(0.5, 1.0)
        parts.append((start, scale(additive_bell(note(generator.choice(pentatonic)), 1.2, 1.4, GLASS_PARTIALS), loudness)))
    return fade_out(mix(1.8, parts), 0.4)


@sound("sparkle", "done", "Magic sparkle: a quick shimmer of falling notes.", peak=0.6)
def build_sparkle() -> Signal:
    falling = [103, 100, 98, 96, 93, 91, 88]
    parts = [(position * 0.035, decay(oscillator(wave_sine, steady(note(midi)), 0.25), 0.001, 0.05)) for position, midi in enumerate(falling)]
    return fade_out(echo(mix(0.5, parts), 0.08, 0.45, 0.6), 0.2)


@sound("success", "done", "Soft two-note UI success chime.")
def build_success() -> Signal:
    def soft_note(midi: int) -> Signal:
        return decay(oscillator(wave_sine, steady(note(midi)), 0.6), 0.008, 0.22)

    return fade_out(echo(mix(0.75, [(0.0, soft_note(76)), (0.12, soft_note(83))]), 0.14, 0.25, 0.3), 0.1)


@sound("champagne", "done", "Cork pop, then a fizz.")
def build_champagne() -> Signal:
    pop_body = decay(oscillator(wave_sine, glide(1100, 260, 0.04), 0.12), 0.0005, 0.03)
    pop_click = scale(decay(lowpass(noise(0.03, seed=11), 4000), 0.0005, 0.006), 0.8)
    fizz = scale(adsr(highpass(noise(0.9, seed=12), 5000), 0.1, 0.2, 0.6, 0.5), 0.25)
    return fade_out(mix(1.1, [(0.0, pop_body), (0.0, pop_click), (0.08, fizz)]), 0.1)


@sound("drumroll", "done", "Snare drum roll that lands on a cymbal crash.", peak=0.75)
def build_drumroll() -> Signal:
    roll_seconds = 0.9
    snare_noise = bandpass(noise(roll_seconds, seed=21), 900, 6000)
    roll: Signal = []
    stroke_phase = 0.0
    for index, value in enumerate(snare_noise):
        time_seconds = index / SAMPLE_RATE
        stroke_rate = 18 + 14 * time_seconds / roll_seconds
        stroke_phase = (stroke_phase + stroke_rate / SAMPLE_RATE) % 1.0
        crescendo = 0.3 + 0.7 * time_seconds / roll_seconds
        roll.append(value * math.exp(-stroke_phase * 6) * crescendo)
    crash = decay(highpass(noise(1.0, seed=22), 3000), 0.002, 0.35)
    kick = decay(oscillator(wave_sine, glide(120, 50, 0.08), 0.3), 0.001, 0.09)
    return fade_out(mix(1.9, [(0.0, roll), (roll_seconds, crash), (roll_seconds, scale(kick, 1.4))]), 0.2)


@sound("cuckoo", "done", "Cuckoo-clock call.", peak=0.55)
def build_cuckoo() -> Signal:
    def call(midi: int) -> Signal:
        tone = oscillator(wave_triangle, steady(note(midi)), 0.28)
        return adsr(lowpass(tone, 2000), 0.02, 0.05, 0.8, 0.1)

    return fade_out(mix(0.75, [(0.0, call(79)), (0.32, call(75))]), 0.05)


@sound("bird", "done", "Little songbird chirps and a trill.", peak=0.5)
def build_bird() -> Signal:
    def chirp(high: float, low: float, seconds: float) -> Signal:
        return adsr(oscillator(wave_sine, glide(high, low, seconds), seconds), 0.005, 0.01, 0.9, seconds * 0.4)

    parts: list[tuple[float, Signal]] = [(index * 0.09, chirp(4200, 2600, 0.05)) for index in range(3)]
    trill = oscillator(wave_sine, with_vibrato(steady(3300), 28, 0.12), 0.3)
    parts.append((0.32, adsr(trill, 0.02, 0.05, 0.8, 0.12)))
    return fade_out(mix(0.75, parts), 0.05)


@sound("boing", "done", "Cartoon spring 'boing'.")
def build_boing() -> Signal:
    def spring_pitch(time_seconds: float) -> float:
        wobble = 0.35 * math.exp(-time_seconds / 0.25) * math.sin(2 * math.pi * 11 * time_seconds)
        return glide(150, 300, 0.12)(time_seconds) * (1 + wobble)

    body = oscillator(wave_triangle, spring_pitch, 0.8)
    return fade_out(decay(lowpass(body, 1800), 0.004, 0.3), 0.05)


@sound("slide-whistle", "done", "Goofy slide whistle going up and back down.", peak=0.42)
def build_slide_whistle() -> Signal:
    def whistle_pitch(time_seconds: float) -> float:
        if time_seconds < 0.4:
            return glide(500, 1700, 0.4)(time_seconds)
        return glide(1700, 1100, 0.2)(time_seconds - 0.4)

    tone = oscillator(wave_sine, with_vibrato(whistle_pitch, 6, 0.012), 0.65)
    breath = scale(bandpass(noise(0.65, seed=31), 1500, 4000), 0.08)
    return fade_out(adsr([value + air for value, air in zip(tone, breath)], 0.04, 0.05, 0.9, 0.08), 0.03)


@sound("kazoo", "done", "Kazoo 'ta-daaa!', buzzy and silly.", peak=0.55)
def build_kazoo() -> Signal:
    def kazoo_note(midi: int, seconds: float) -> Signal:
        buzz = oscillator(wave_saw, with_vibrato(steady(note(midi)), 6.5, 0.015), seconds)
        voiced = bandpass(buzz, 300, 2200)
        return adsr(voiced, 0.015, 0.05, 0.85, 0.08)

    return fade_out(mix(0.75, [(0.0, kazoo_note(67, 0.14)), (0.16, kazoo_note(72, 0.55))]), 0.05)


@sound("bubbles", "done", "Three bubbly bloops.")
def build_bubbles() -> Signal:
    def bloop(base_frequency: float) -> Signal:
        return decay(oscillator(wave_sine, glide(base_frequency, base_frequency * 2.3, 0.07), 0.15), 0.002, 0.05)

    return fade_out(mix(0.45, [(0.0, bloop(420)), (0.11, bloop(560)), (0.21, bloop(480))]), 0.03)


@sound("robot", "done", "Robot 'beep-boop-bop'.", peak=0.45)
def build_robot() -> Signal:
    def beep(frequency: float, seconds: float) -> Signal:
        carrier = oscillator(wave_square, steady(frequency), seconds)
        ring = oscillator(wave_sine, steady(37), seconds)
        return adsr(lowpass([tone * (0.6 + 0.4 * modulation) for tone, modulation in zip(carrier, ring)], 3500), 0.005, 0.01, 0.9, 0.02)

    parts = [(0.0, beep(880, 0.09)), (0.12, beep(587, 0.09)), (0.24, beep(988, 0.14))]
    return fade_out(mix(0.42, parts), 0.02)


# --- Nudges: good for "needs-input" -----------------------------------------


@sound("hm", "nudge", "Soft rising two-note chime, like a polite 'hm?'. The default for needs-input.", peak=0.5)
def build_hm() -> Signal:
    parts = [
        (0.00, scale(additive_bell(note(76), 0.8, 0.30, BELL_PARTIALS), 0.7)),
        (0.16, scale(additive_bell(note(81), 0.64, 0.45, BELL_PARTIALS), 0.8)),
    ]
    return fade_out(mix(0.8, parts), 0.05)


@sound("knock", "nudge", "Knock knock on a wooden door.", peak=0.75)
def build_knock() -> Signal:
    def knock() -> Signal:
        thump = decay(oscillator(wave_sine, glide(190, 95, 0.05), 0.15), 0.001, 0.035)
        click = scale(decay(bandpass(noise(0.05, seed=41), 400, 2500), 0.0005, 0.008), 0.9)
        return [low + high for low, high in zip(thump, click + [0.0] * (len(thump) - len(click)))]

    return mix(0.45, [(0.0, knock()), (0.17, knock())])


@sound("sonar", "nudge", "Submarine sonar ping with an echo.", peak=0.55)
def build_sonar() -> Signal:
    ping = decay(oscillator(wave_sine, steady(1150), 0.5), 0.004, 0.12)
    return fade_out(echo(ping, 0.24, 0.35, 0.7), 0.2)


@sound("blip", "nudge", "Two short, quiet UI blips.", peak=0.45)
def build_blip() -> Signal:
    def short_blip(midi: int) -> Signal:
        return decay(oscillator(wave_triangle, steady(note(midi)), 0.08), 0.002, 0.03)

    return mix(0.25, [(0.0, short_blip(88)), (0.09, short_blip(95))])


@sound("huh", "nudge", "Cartoon 'huh?': a voice-like rising question.", peak=0.6)
def build_huh() -> Signal:
    voice = oscillator(wave_saw, with_vibrato(glide(190, 330, 0.32), 7, 0.02), 0.42)
    vowel = bandpass(voice, 500, 1400)
    return fade_out(adsr(vowel, 0.03, 0.05, 0.9, 0.1), 0.03)


@sound("glass-tap", "nudge", "Two light taps on a glass.", peak=0.55)
def build_glass_tap() -> Signal:
    tap = additive_bell(note(96), 0.6, 0.35, GLASS_PARTIALS)
    return fade_out(mix(0.8, [(0.0, tap), (0.14, scale(tap, 0.75))]), 0.1)


@sound("triple-beep", "nudge", "Three gentle beeps.", peak=0.4)
def build_triple_beep() -> Signal:
    beep = adsr(oscillator(wave_triangle, steady(1046), 0.07), 0.005, 0.01, 0.9, 0.02)
    return mix(0.36, [(index * 0.12, beep) for index in range(3)])


@sound("tick-tock", "nudge", "A clock going tick-tock, tick-tock.", peak=0.85)
def build_tick_tock() -> Signal:
    def tick(center_hz: float, seed: int) -> Signal:
        return decay(bandpass(noise(0.04, seed=seed), center_hz * 0.7, center_hz * 1.4), 0.0005, 0.006)

    timing = [(0.0, 3200), (0.25, 2200), (0.5, 3200), (0.75, 2200)]
    return mix(0.85, [(start, tick(center, seed=50 + index)) for index, (start, center) in enumerate(timing)])


@sound("owl", "nudge", "Soft owl 'hoo-hoo'.", peak=0.45)
def build_owl() -> Signal:
    def hoot(start_hz: float, seconds: float) -> Signal:
        tone = oscillator(wave_sine, with_vibrato(glide(start_hz, start_hz * 0.92, seconds), 5, 0.01), seconds)
        breath = scale(lowpass(noise(seconds, seed=int(start_hz)), 900), 0.05)
        return adsr([value + air for value, air in zip(tone, breath)], 0.06, 0.05, 0.85, 0.12)

    return fade_out(mix(0.9, [(0.0, hoot(420, 0.28)), (0.38, hoot(400, 0.45))]), 0.05)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def write_wav(samples: Signal, output_path: Path, peak_amplitude: float) -> None:
    samples = highpass(samples, 20)  # removes DC offset, which clicks at start and stop
    fade_in_samples = min(len(samples), sample_count(0.003))
    samples = [value * min(1.0, index / fade_in_samples) for index, value in enumerate(samples)]
    loudest = max(abs(sample) for sample in samples)
    if loudest == 0:
        raise ValueError(f"refusing to write a silent file: {output_path}")
    gain = peak_amplitude / loudest
    frames = b"".join(struct.pack("<h", int(sample * gain * 32767)) for sample in samples)
    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(frames)


def write_catalog(output_path: Path) -> None:
    lines = [f"{spec.name}\t{spec.kind}\t{spec.description}" for spec in SOUND_LIBRARY.values()]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def remove_stale_wavs() -> None:
    """Delete .wav files whose sound was renamed or removed, so the folder matches the library."""
    for wav_path in SOUNDS_DIRECTORY.glob("*.wav"):
        if wav_path.stem not in SOUND_LIBRARY:
            wav_path.unlink()
            print(f"removed stale {wav_path.name}")


def main() -> None:
    SOUNDS_DIRECTORY.mkdir(exist_ok=True)
    for spec in SOUND_LIBRARY.values():
        write_wav(spec.build(), SOUNDS_DIRECTORY / f"{spec.name}.wav", spec.peak)
    remove_stale_wavs()
    write_catalog(SOUNDS_DIRECTORY / "catalog.tsv")
    print(f"wrote {len(SOUND_LIBRARY)} sounds and catalog.tsv to {SOUNDS_DIRECTORY}")


if __name__ == "__main__":
    main()
