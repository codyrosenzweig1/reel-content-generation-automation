#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = REPO_ROOT / ".env"

VENV_XTTS = REPO_ROOT / "venv-xtts"
VENV_RVC = REPO_ROOT / "venv-rvc"
VENV_ALIGN = REPO_ROOT / "venv-align"
VENV_CORE = REPO_ROOT / "venv-core"

DATA_DIR = REPO_ROOT / "data"
FINAL_DIR = DATA_DIR / "final"

def venv_python(venv: Path) -> str:
    exe = venv / "bin" / "python"
    if not exe.exists():
        raise FileNotFoundError(f"Python not found in {venv}")
    return str(exe)

def run_python_inline(venv: Path, code: str, env: Optional[dict] = None) -> None:
    py = venv_python(venv)
    env_vars = os.environ.copy()
    if env:
        env_vars.update(env)
    # Ensure repo modules are importable
    preamble = f"""
import sys
from pathlib import Path
BASE_DIR = Path('{REPO_ROOT.as_posix()}')
if str(BASE_DIR / 'pipeline_modules') not in sys.path:
    sys.path.insert(0, str(BASE_DIR / 'pipeline_modules'))
"""
    joined = preamble + "\n" + code
    subprocess.run([py, "-c", joined], check=True, env=env_vars)

def has_module(venv: Path, module: str) -> bool:
    try:
        run_python_inline(venv, f"__import__('{module}')")
        return True
    except Exception:
        return False

def choose_general_env() -> Path:
    if VENV_CORE.exists():
        return VENV_CORE
    if VENV_RVC.exists():
        return VENV_RVC
    raise RuntimeError("Neither venv-core nor venv-rvc exists")

def ensure_envs_exist() -> None:
    missing = [v for v in [VENV_XTTS, VENV_RVC, VENV_ALIGN, VENV_CORE] if not v.exists()]
    if missing:
        names = ", ".join(str(m) for m in missing)
        raise RuntimeError(f"Missing venvs: {names}. Run scripts/setup_env.sh first.")

def echo(msg: str) -> None:
    print(msg, flush=True)

def generate_script(topic: str, tone: str, account: str, env_for_openai: Path) -> None:
    echo(f"Using env for script generation: {env_for_openai}")
    echo("Generating dialogue script")
    code = f"""
from dotenv import load_dotenv
from pathlib import Path
from pipeline_modules.script_generator import script_generator as generate_script
load_dotenv(dotenv_path=Path('{ENV_FILE.as_posix()}'))
path = generate_script({topic!r}, {tone!r}, {account!r})
print(f"Saved script to {{path}}")
"""
    run_python_inline(env_for_openai, code)

def run_xtts_batch() -> None:
    echo("Running XTTS batch synthesis")
    code = f"""
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(dotenv_path=Path('{ENV_FILE.as_posix()}'))
from pipeline_modules.run_xtts_batch import run_xtts
run_xtts()
print("XTTS conversion completed")
"""
    run_python_inline(VENV_XTTS, code)

def run_rvc_batch(rvc_env: Path) -> None:
    echo(f"Running RVC batch conversion in: {rvc_env}")
    code = """
from pipeline_modules.convert_batch import batch_convert
batch_convert()
print("RVC conversion completed")
"""
    run_python_inline(rvc_env, code)

def generate_timing_maps(topic: str) -> None:
    echo("Generating timing maps")
    code = f"""
from pipeline_modules.generate_timing_maps import main as generate_timing_maps
generate_timing_maps({topic!r}, phoneme_align=True)
print("Timing maps generated")
"""
    run_python_inline(VENV_ALIGN, code)

def combine_audio(general_env: Path) -> None:
    echo("Combining audio tracks")
    code = f"""
from pathlib import Path
from pipeline_modules.combine_audio import combine_wavs
BASE_DIR = Path('{REPO_ROOT.as_posix()}')
CONVERTED_DIR  = BASE_DIR / 'data' / 'audio' / 'converted'
OUT = BASE_DIR / 'data' / 'final' / 'final_output.wav'
OUT.parent.mkdir(parents=True, exist_ok=True)
combine_wavs(CONVERTED_DIR, OUT)
print(f"Combined audio written to {{OUT}}")
"""
    run_python_inline(general_env, code)

def build_subtitles(general_env: Path) -> None:
    echo("Building ASS subtitles")
    code = f"""
from pathlib import Path
from pipeline_modules.generate_ass import build_ass_from_whisperx as generate_ass_subtitles
BASE_DIR = Path('{REPO_ROOT.as_posix()}')
timestamps = BASE_DIR / 'data' / 'final' / 'word_timestamps.json'
ass_file   = BASE_DIR / 'data' / 'final' / 'dialogue.ass'
ass_file.parent.mkdir(parents=True, exist_ok=True)
generate_ass_subtitles(timestamps, ass_file)
print(f"ASS subtitles written to {{ass_file}}")
"""
    run_python_inline(general_env, code)

def assemble_reel(general_env: Path, topic: str) -> None:
    echo("Assembling final reel")
    code = f"""
from pathlib import Path
from pipeline_modules.assemble_reel import assemble_reel
BASE_DIR = Path('{REPO_ROOT.as_posix()}')
bg          = BASE_DIR / 'data' / 'backgrounds' / 'bg_full.mp4'
audio_final = BASE_DIR / 'data' / 'final' / 'final_output.wav'
ass_file    = BASE_DIR / 'data' / 'final' / 'dialogue.ass'
sentence_map= BASE_DIR / 'data' / 'final' / 'sentence_map.json'
script_json = BASE_DIR / f'data/scripts/{topic}.json'
images_dir  = BASE_DIR / 'data' / 'images'
out_path    = BASE_DIR / 'data' / 'final' / 'reel_final.mp4'
out_path.parent.mkdir(parents=True, exist_ok=True)
assemble_reel(bg, audio_final, ass_file, sentence_map, script_json, images_dir, out_path)
print(f"Final reel written to {{out_path}}")
"""
    run_python_inline(general_env, code)

def choose_env_with_module(mod: str, candidates: Iterable[Path]) -> Path:
    for v in candidates:
        if v.exists() and has_module(v, mod):
            return v
    raise RuntimeError(f"Could not find module {mod} in any provided envs")

def clean_workspace() -> None:
    # Remove large intermediate artefacts to save space, keep only the final reel
    keep = {FINAL_DIR / "final_output.wav", FINAL_DIR / "dialogue.ass", FINAL_DIR / "reel_final.mp4",
            FINAL_DIR / "word_timestamps.json", FINAL_DIR / "sentence_map.json"}
    if not DATA_DIR.exists():
        return
    for root, dirs, files in os.walk(DATA_DIR):
        for f in files:
            p = Path(root) / f
            if p not in keep:
                try:
                    p.unlink()
                except Exception:
                    pass

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("topic")
    parser.add_argument("tone")
    parser.add_argument("account")
    parser.add_argument("--keep-intermediates", action="store_true", help="do not delete intermediate files")
    args = parser.parse_args()

    ensure_envs_exist()
    general_env = choose_general_env()

    # openai_env = choose_env_with_module("openai", [general_env, VENV_CORE, VENV_RVC, VENV_XTTS, VENV_ALIGN])
    rvc_env = choose_env_with_module("rvc", [VENV_RVC, VENV_CORE, general_env, VENV_XTTS, VENV_ALIGN])

    # generate_script(args.topic, args.tone, args.account, openai_env)
    # run_xtts_batch()
    run_rvc_batch(rvc_env)
    generate_timing_maps(args.topic)
    combine_audio(general_env)
    build_subtitles(general_env)
    assemble_reel(general_env, args.topic)

    if not args.keep_intermediates:
        clean_workspace()

    print("Pipeline complete")

if __name__ == "__main__":
    main()