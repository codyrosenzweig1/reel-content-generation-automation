#!/usr/bin/env python3
import sys
import subprocess

def extract_clip(url, start_time, duration, outfile):
    """
    Downloads and trims a YouTube clip:
      url        – YouTube URL
      start_time – clip start (HH:MM:SS)
      duration   – clip length (HH:MM:SS)
      outfile    – where to save the trimmed WAV
    """
    script_path = "utils/extract_clip.sh"
    try:
        subprocess.run(
            [script_path, url, start_time, duration, outfile],
            check=True
        )
        print(f"✅ Extracted and saved: {outfile}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to extract audio: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(f"Usage: {sys.argv[0]} <url> <start_time> <duration> <outfile>")
        sys.exit(1)

    _, url, start_time, duration, outfile = sys.argv
    extract_clip(url, start_time, duration, outfile)
    print("🎉 Audio extraction complete!")
