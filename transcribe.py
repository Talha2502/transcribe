import sys
import json
from app.transcriber import transcribe_file


def main():
    if len(sys.argv) < 2:
        print("Usage: python transcribe.py <audio_file>")
        sys.exit(1)

    result = transcribe_file(sys.argv[1])

    print(f"\nLanguage: {result['language']} ({result['language_confidence']:.0%})")
    print(f"Duration: {result['duration_seconds']:.1f}s")

    print("\n--- Transcription with Timestamps ---")
    for seg in result["segments"]:
        start = f"{int(seg['start']//60)}:{int(seg['start']%60):02d}"
        end = f"{int(seg['end']//60)}:{int(seg['end']%60):02d}"
        print(f"[{start} - {end}] {seg['text']}")

    print(f"\n--- Full Text ---\n{result['full_text']}\n")

    if len(sys.argv) > 2 and sys.argv[2] == "--json":
        output_path = sys.argv[1].rsplit(".", 1)[0] + "_transcript.json"
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()