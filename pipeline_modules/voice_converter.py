import os
from pathlib import Path
import subprocess
from utils.db_logger import log_event, save_log, init_log

# --- Robust weight_root resolution ---
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
weights_dir = project_root / "weights"
os.environ["weight_root"] = str(Path("rvc/weights").resolve())

def convert_with_rvc(account, character="stewie", f0method="rmvpe"):
    """
    Converts TTS audio to character voice using RVC-WebUI CLI
    """
    # Define paths
    base_dir = project_root / "data" / "accounts" / account / "audio"
    input_dir = base_dir / "base"
    output_dir = base_dir / "distorted"
    model_dir = weights_dir / character
    real_model_dir = project_root / "rvc" / "weights" / character

    infer_script = Path("tools") / "infer_cli.py"
    real_infer_script_path = project_root / "rvc" / infer_script

    if not real_infer_script_path.exists():
        raise FileNotFoundError(f"RVC infer script not found at {real_infer_script_path}")
    if not real_model_dir.exists():
        raise FileNotFoundError(f"RVC model directory not found at {real_model_dir}")
    
    output_dir.mkdir(parents=True, exist_ok=True)

    wav_files = list(input_dir.glob("*.wav"))
    if not wav_files:
        print(f"No .wav files found in {input_dir}. Please check your input directory.")
        return

    index_file = next(real_model_dir.glob("*.index"), None)
    if not index_file:
        raise FileNotFoundError(f"No index file found in {real_model_dir}. Please check your model directory.")
    
    for wav_file in wav_files:
        output_file = output_dir / wav_file.name
        command = [
            "python", str(infer_script),
            "--input_path", str(wav_file),
            "--opt_path", str(output_file),
            "--model_name", character,
            "--index_path", str(index_file),
            "--f0method", f0method
        ]

        log_df = init_log(project_root / "data/logs/content_log.csv")
        env = os.environ.copy()
        env["PYTHONPATH"] = str((project_root / "rvc").resolve())

        try:
            subprocess.run(command, check=True, env=env, cwd=str((project_root / "rvc").resolve()))
            print(f"✅ RVC Converted: {wav_file.name}")
            log_df = log_event(log_df, account, "rvc", "converted", wav_file.name)
        except subprocess.CalledProcessError as e:
            print(f"❌ RVC conversion failed for {wav_file.name}: {e}")
            log_df = log_event(log_df, account, "rvc", "failed", wav_file.name)
        save_log(log_df, project_root / "data/logs/content_log.csv")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("account", help="Account folder inside /data/accounts")
    parser.add_argument("--character", choices=["stewie", "peter"], default="stewie")
    parser.add_argument("--f0method", type=str, default="rmvpe", help="Pitch detection method: rmvpe or crepe")
    args = parser.parse_args()

    convert_with_rvc(args.account, args.character, args.f0method)
