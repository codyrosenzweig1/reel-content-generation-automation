#!/usr/bin/env python3
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
if str(BASE_DIR / "pipeline_modules") not in sys.path:
    sys.path.insert(0, str(BASE_DIR / "pipeline_modules"))

from dotenv import load_dotenv
from pipeline_modules.generate_timing_maps import main as generate_timing_maps

import openai
from pipeline_modules.script_generator import script_generator as generate_script  # Your existing script generator 'main' function
from pipeline_modules.run_xtts_batch import run_xtts
from pipeline_modules.convert_batch import batch_convert
from pipeline_modules.combine_audio import combine_wavs
from pipeline_modules.generate_ass import build_ass_from_whisperx as generate_ass_subtitles
from pipeline_modules.assemble_reel import assemble_reel

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
    script_path = generate_script(topic, tone, account)
    print(f"Saved script to {script_path}")

    print("Starting XTTS batch conversion… (skipped in this run)")
    run_xtts()
    print("XTTS conversion completed.")

    print("Starting RVC batch conversion… (skipped in this run)")
    # batch_convert()
    print("RVC conversion completed.")

    print("Generating timing maps… (with phoneme alignment if available)")
    generate_timing_maps(topic, phoneme_align=True)

    print("Combining audio tracks into final_output.wav…")
    combine_wavs(CONVERTED_DIR, BASE_DIR / "data/final/final_output.wav")

    print("Generating ASS subtitles for word highlights…")
    generate_ass_subtitles(
        BASE_DIR / "data/final/word_timestamps.json",
        BASE_DIR / "data/final/dialogue.ass"
    )

    print("Assembling reel…")
    assemble_reel(
        BASE_DIR / "data/backgrounds/bg_full.mp4",
        BASE_DIR / "data/final/final_output.wav",
        BASE_DIR / "data/final/dialogue.ass",
        BASE_DIR / "data/final/sentence_map.json",
        BASE_DIR / f"data/scripts/{topic}.json",
        BASE_DIR / "data/images",
        BASE_DIR / "data/final/reel_final.mp4"
    )

    

if __name__ == "__main__":
    main()
