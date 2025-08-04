#!/usr/bin/env python3
import sys
from pathlib import Path

# Ensure project root is on PYTHONPATH for module imports
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT / "pipeline_modules"))

#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

import openai
from script_generator import script_generator as generate_script  # Your existing script generator 'main' function
from run_xtts_batch import run_xtts
from convert_batch import batch_convert
from combine_audio import combine_wavs
from generate_timing_maps import main as generate_timing_maps
from generate_ass import main as ass_generator
from assemble_reel import assemble_reel

# Configuration
ACCOUNT        = "tech_account"
BASE_DIR       = Path(__file__).parent.resolve()
SCRIPTS_DIR    = BASE_DIR / "data" / "scripts"
BASE_AUDIO_DIR = BASE_DIR / "data" / "audio" / "base"
CONVERTED_DIR  = BASE_DIR / "data" / "audio" / "converted"

# OpenAI model
OPENAI_MODEL = "gpt-4o-mini"


def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <topic> <tone> <account>")
        sys.exit(1)

    topic, tone, account = sys.argv[1], sys.argv[2], sys.argv[3]

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY is not set")
        sys.exit(1)
    openai.api_key = api_key

    # Generate and save the dialogue script using your script_generator module
    print(f"Generating dialogue script for topic '{topic}' with tone '{tone}'...")
    # script_path = generate_script(topic, tone, account)
    # print(f"Saved script to {script_path}")

    # Run batch XTTS conversion
    print("Starting XTTS batch conversion...")
    # run_xtts()
    print("XTTS conversion completed.")

    # Run batch RVC conversion
    print("Starting RVC batch conversion...")
    # batch_convert()
    print("RVC conversion completed.")

    # Generate out word and sentence timings to generate captions and png timings
    print("Generating timing maps...")
    # generate_timing_maps(topic)

    # Combine all converted audio files into a single output WAV + speed up 
    # combine_wavs(CONVERTED_DIR, BASE_DIR / "data/final/final_output.wav")

    # Generating word timings for intelligent subtitles
    print("Generating ASS subtitles for word highlights…")
    ass_generator(
        BASE_DIR / "data" / "final" / "word_timestamps.json",
        BASE_DIR / "data" / "final" / "dialogue.ass"
    )

    # Combining audio, mp4, subtitiles, png's
    print("Assembling reel....")
    assemble_reel(
        BASE_DIR / "data/backgrounds/bg_trimmed.mp4",
        BASE_DIR / "data/final/final_output.wav",
        BASE_DIR / "data/final/dialogue.ass",
        BASE_DIR / "data/final/sentence_map.json",
        BASE_DIR / f"data/scripts/{topic}.json",
        BASE_DIR / "data/images",
        BASE_DIR / "data/final/reel_final.mp4"
    )

    

if __name__ == "__main__":
    main()
