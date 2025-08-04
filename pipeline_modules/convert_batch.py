import os
import sys
import subprocess
from pathlib import Path
import logging
import torch
import soundfile as sf
import gc
from rvc.modules.vc.modules import VC

logging.basicConfig(level=logging.INFO)

BASE_DIR     = Path(__file__).parent.parent.resolve()
INPUT_DIR    = BASE_DIR / "data/audio/base"
OUTPUT_DIR   = BASE_DIR / "data/audio/converted"
MODEL_DIR    = BASE_DIR / "weights"
INDEX_DIR    = MODEL_DIR / "indexes"
USE_INDEX    = True

def get_speaker_name(fp: Path) -> str:
    # filename must be <index>_<Speaker>.wav
    parts = fp.stem.split("_")
    if len(parts) < 2:
        raise ValueError(f"Unexpected filename format: {fp.name}")
    return parts[1]

def validate_model(speaker: str):
    pth = MODEL_DIR / speaker.lower() / f"{speaker.lower()}.pth"
    idx = INDEX_DIR / f"{speaker.lower()}.index"
    if not pth.exists():
        logging.error(f"❌ RVC model .pth not found for {speaker}: {pth}")
        sys.exit(1)
    # Quick validation that .pth is a PyTorch file, not a ZIP:
    try:
        torch.load(str(pth), map_location="cpu")
    except Exception as e:
        logging.error(f"❌ Failed to load {pth}: {e}")
        logging.error("Did you unzip a zip archive into the .pth? See instructions.")
        sys.exit(1)
    if USE_INDEX and not idx.exists():
        logging.warning(f"⚠️ Index file not found for {speaker}: {idx} (continuing without index)")
    return pth, idx if idx.exists() else None

def load_model(speaker: str) -> VC:
    pth, idx = validate_model(speaker)
    logging.info(f"🧠 Loading RVC model for {speaker}")
    vc = VC()
    vc.get_vc(str(pth))   # loads model
    return vc

def convert(vc: VC, file_path: Path, output_path: Path):
    speaker = get_speaker_name(file_path)
    idx_file = INDEX_DIR / f"{speaker.lower()}.index" if USE_INDEX else None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    logging.info(f"🎙️ Converting {file_path.name} → {output_path.name}")

    f0_method   = "rmvpe"
    index_file  = str(idx_file) if idx_file and idx_file.exists() else None

    tgt_sr, audio_opt, _, err = vc.vc_inference(
        sid=0,
        input_audio_path=str(file_path),
        f0_method=f0_method,
        f0_up_key=0,
        index_file=index_file,
        index_rate=0.95,
        filter_radius=3,
        resample_sr=0,
        rms_mix_rate=0.4,
        protect=0.4,
    )
    if err:
        logging.warning(f"⚠️ Error converting {file_path.name}: {err}")
        return
    sf.write(str(output_path), audio_opt, tgt_sr)
    logging.info(f"✅ Saved: {output_path}")

def batch_convert():
    logging.info(f"🔍 Scanning base files in {INPUT_DIR}")
    speaker_to_files = {}
    for fp in sorted(INPUT_DIR.rglob("*.wav")):
        speaker = get_speaker_name(fp)
        speaker_to_files.setdefault(speaker, []).append(fp)

    for speaker, files in speaker_to_files.items():
        logging.info(f"\n🎤 *** Speaker: {speaker} ({len(files)} clips) ***")
        vc = load_model(speaker)
        for fp in files:
            out_fp = OUTPUT_DIR / fp.name
            convert(vc, fp, out_fp)

        # cleanup
        del vc
        gc.collect()
        torch.cuda.empty_cache()
        logging.info(f"🧹 Unloaded {speaker} model\n")

if __name__ == "__main__":
    batch_convert()
