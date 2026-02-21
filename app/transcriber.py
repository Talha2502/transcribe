import sys
import os
import tempfile

from faster_whisper import WhisperModel
from pydub import AudioSegment

from app.config import SUPPORTED_FORMATS, CHUNK_MINUTES, WHISPER_MODEL, WHISPER_DEVICE


def accept_audio(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format '{ext}'. Supported: {SUPPORTED_FORMATS}")

    file_size = os.path.getsize(file_path) / (1024 * 1024)
    print(f"Accepted: {file_path}")
    print(f"  Format: {ext}")
    print(f"  Size: {file_size:.2f} MB")
    return file_path


def convert_to_wav(file_path):
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".wav":
        print("Already WAV, no conversion needed")
        return file_path

    print(f"Converting {ext} to .wav ...")
    audio = AudioSegment.from_file(file_path)
    audio = audio.set_frame_rate(16000).set_channels(1)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    audio.export(tmp.name, format="wav")
    print("Conversion done")
    return tmp.name


def split_long_audio(file_path, chunk_minutes=CHUNK_MINUTES):
    audio = AudioSegment.from_wav(file_path)
    duration_minutes = len(audio) / (1000 * 60)

    if duration_minutes <= chunk_minutes:
        print(f"Audio is {duration_minutes:.1f} min, no splitting needed")
        return [file_path]

    print(f"Audio is {duration_minutes:.1f} min, splitting into {chunk_minutes}-min chunks...")
    chunk_length_ms = chunk_minutes * 60 * 1000
    chunks = []

    for i in range(0, len(audio), chunk_length_ms):
        chunk = audio[i:i + chunk_length_ms]
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        chunk.export(tmp.name, format="wav")
        chunks.append(tmp.name)

    print(f"Split into {len(chunks)} chunks")
    return chunks


def transcribe_audio(file_path):
    print("Loading model...")
    model = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE)

    print("Transcribing...")
    segments, info = model.transcribe(file_path)

    print(f"Detected language: {info.language} ({info.language_probability:.0%} confidence)")

    results = []
    full_text = ""

    for segment in segments:
        results.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip()
        })
        full_text += segment.text

    print("\n--- Transcription with Timestamps ---")
    for r in results:
        start = f"{int(r['start']//60)}:{int(r['start']%60):02d}"
        end = f"{int(r['end']//60)}:{int(r['end']%60):02d}"
        print(f"[{start} - {end}] {r['text']}")

    print(f"\n--- Full Text ---\n{full_text.strip()}\n")
    return results

def transcribe_file(file_path):
    file_path = accept_audio(file_path)
    wav_path = convert_to_wav(file_path)
    chunks = split_long_audio(wav_path)

    all_segments = []
    full_text = ""
    language = None
    language_confidence = None

    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            print(f"\n--- Chunk {i+1}/{len(chunks)} ---")

        print("Loading model...")
        model = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE)
        segments, info = model.transcribe(chunk)

        if language is None:
            language = info.language
            language_confidence = info.language_probability

        for segment in segments:
            all_segments.append({
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text.strip()
            })
            full_text += segment.text

    audio = AudioSegment.from_file(file_path)
    duration = len(audio) / 1000.0

    return {
        "full_text": full_text.strip(),
        "segments": all_segments,
        "language": language,
        "language_confidence": round(language_confidence, 4) if language_confidence else None,
        "duration_seconds": round(duration, 2)
    }



if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 transcribe.py <audio_file>")
        sys.exit(1)

    file_path = accept_audio(sys.argv[1])
    wav_path = convert_to_wav(file_path)
    chunks = split_long_audio(wav_path)

    all_results = []
    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            print(f"\n--- Chunk {i+1}/{len(chunks)} ---")
        results = transcribe_audio(chunk)
        all_results.extend(results)