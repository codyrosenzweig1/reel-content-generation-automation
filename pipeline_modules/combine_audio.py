#!/usr/bin/env python3
import sys
import subprocess
from pathlib import Path

try:
    from pydub import AudioSegment
except ImportError:
    sys.exit("Error: pydub is required. Install with `pip install pydub`.")

def combine_wavs(input_dir: Path, output_path: Path, speed: float = 1.05):
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Collect and sort WAV files
    wav_files = sorted(input_dir.glob("*.wav"))
    if not wav_files:
        raise FileNotFoundError(f"No .wav files found in {input_dir}")

    # Concatenate all clips
    combined = AudioSegment.empty()
    for wav in wav_files:
        print(f"Adding {wav.name}…")
        combined += AudioSegment.from_wav(wav)

    # Export to a temp file
    temp_path = output_path.with_suffix(".tmp.wav")
    print(f"Exporting combined audio to {temp_path}…")
    combined.export(temp_path, format="wav")

    # Speed‑up with ffmpeg
    print(f"Speeding up audio by {speed}× and writing to {output_path}…")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(temp_path),
        "-filter:a", f"atempo={speed}",
        "-c:a", "pcm_s16le",
        str(output_path)
    ]
    subprocess.run(cmd, check=True)

    # Remove temp
    temp_path.unlink()
    print("Done.")

if __name__ == "__main__":
    if len(sys.argv) not in (3,4):
        print(f"Usage: {sys.argv[0]} <input_directory> <output_wav> [speed]")
        sys.exit(1)

    in_dir = Path(sys.argv[1])
    out_file = Path(sys.argv[2])
    speed = float(sys.argv[3]) if len(sys.argv) == 4 else 1.05

    combine_wavs(in_dir, out_file, speed)
