"""Build the recorded sounds (real-world effects and voices) from their public-domain sources.

Every entry in sounds/recordings.json names a CC0 source: a Freesound sound
(its high-quality preview) or a file inside a Kenney asset pack. This script
downloads each source once into .cache/recordings/, then decodes, trims,
levels and writes sounds/<name>.wav as 44.1 kHz mono 16-bit WAV.

Usage:
    pip install -r tools/requirements.txt
    python tools/import-recordings.py
Then run tools/make-sounds.py, which rebuilds sounds/catalog.tsv and
sounds/CREDITS.md from the same manifest.
"""

import io
import json
import math
import struct
import time
import urllib.error
import urllib.request
import wave
import zipfile
from pathlib import Path
from typing import Any

import miniaudio

SAMPLE_RATE = 44100
REPOSITORY_DIRECTORY = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPOSITORY_DIRECTORY / "sounds" / "recordings.json"
SOUNDS_DIRECTORY = REPOSITORY_DIRECTORY / "sounds"
CACHE_DIRECTORY = REPOSITORY_DIRECTORY / ".cache" / "recordings"
USER_AGENT = "claude-tada sound importer (https://github.com/TZamaranth/claude-tada)"

TARGET_LOUDNESS = 0.14  # RMS of the audible part; keeps a duck quack and an air horn comparable
PEAK_LIMIT = 0.89  # about -1 dBFS
FADE_IN_SECONDS = 0.005
DEFAULT_FADE_OUT_SECONDS = 0.08
SILENCE_THRESHOLD = 0.01  # samples quieter than this don't count toward loudness


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            return urllib.request.urlopen(request, timeout=60).read()
        except (TimeoutError, urllib.error.URLError) as error:
            last_error = error
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"could not download {url} after 3 tries: {last_error}")


def cached_download(url: str, cache_name: str) -> bytes:
    cache_path = CACHE_DIRECTORY / cache_name
    if not cache_path.exists():
        CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(download(url))
    return cache_path.read_bytes()


def source_audio_bytes(source: dict[str, Any]) -> bytes:
    if source["type"] == "freesound":
        return cached_download(source["audio"], f"freesound-{source['id']}.mp3")
    if source["type"] == "kenney":
        pack_name = source["pack"].rsplit("/", 1)[-1]
        try:
            pack_bytes = cached_download(source["pack"], pack_name)
        except RuntimeError as error:
            # kenney.nl often stalls scripted downloads; a browser download works.
            raise RuntimeError(
                f"{error}\nDownload the pack in a browser from {source['page']} and save it as "
                f"{CACHE_DIRECTORY / pack_name}, then run this again."
            ) from error
        with zipfile.ZipFile(io.BytesIO(pack_bytes)) as pack:
            return pack.read(source["file"])
    raise ValueError(f"unknown source type: {source['type']}")


def decode_to_mono(audio_bytes: bytes) -> list[float]:
    decoded = miniaudio.decode(audio_bytes, output_format=miniaudio.SampleFormat.FLOAT32, nchannels=1, sample_rate=SAMPLE_RATE)
    return list(decoded.samples)


def trim(samples: list[float], start_seconds: float, end_seconds: float | None) -> list[float]:
    start_index = int(start_seconds * SAMPLE_RATE)
    end_index = len(samples) if end_seconds is None else min(len(samples), int(end_seconds * SAMPLE_RATE))
    if end_index <= start_index:
        raise ValueError(f"empty trim window {start_seconds}..{end_seconds} for a {len(samples) / SAMPLE_RATE:.2f}s source")
    return samples[start_index:end_index]


def apply_fades(samples: list[float], fade_out_seconds: float) -> list[float]:
    output = list(samples)
    fade_in_samples = min(len(output), int(FADE_IN_SECONDS * SAMPLE_RATE))
    for index in range(fade_in_samples):
        output[index] *= index / fade_in_samples
    fade_out_samples = min(len(output), int(fade_out_seconds * SAMPLE_RATE))
    for offset in range(fade_out_samples):
        output[len(output) - 1 - offset] *= offset / fade_out_samples
    return output


def level(samples: list[float], loudness_scale: float) -> list[float]:
    """Scale so the audible part hits the target loudness, without letting the peak clip."""
    audible = [value for value in samples if abs(value) > SILENCE_THRESHOLD] or samples
    loudness = math.sqrt(sum(value * value for value in audible) / len(audible))
    peak = max(abs(value) for value in samples)
    if peak == 0:
        raise ValueError("source is silent after trimming")
    gain = min(TARGET_LOUDNESS * loudness_scale / loudness, PEAK_LIMIT / peak)
    return [value * gain for value in samples]


def write_wav(samples: list[float], output_path: Path) -> None:
    frames = b"".join(struct.pack("<h", max(-32767, min(32767, int(value * 32767)))) for value in samples)
    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(frames)


def build_recording(entry: dict[str, Any]) -> None:
    samples = decode_to_mono(source_audio_bytes(entry["source"]))
    start_seconds, end_seconds = entry.get("trim", [0.0, None])
    samples = trim(samples, start_seconds, end_seconds)
    samples = apply_fades(samples, entry.get("fade_out", DEFAULT_FADE_OUT_SECONDS))
    samples = level(samples, entry.get("loudness", 1.0))
    write_wav(samples, SOUNDS_DIRECTORY / f"{entry['name']}.wav")
    print(f"  {entry['name']:22} {len(samples) / SAMPLE_RATE:4.1f}s  from {entry['source']['page']}")


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for entry in manifest:
        if "publicdomain/zero" not in entry["source"]["license"]:
            raise ValueError(f"{entry['name']}: only CC0 sources are allowed, got {entry['source']['license']}")
    print(f"building {len(manifest)} recorded sounds")
    for entry in manifest:
        build_recording(entry)


if __name__ == "__main__":
    main()
