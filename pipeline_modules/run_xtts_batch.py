#!/usr/bin/env python3
import json
import torch
from pathlib import Path
from TTS.api import TTS
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts, XttsAudioConfig, XttsArgs
from TTS.config.shared_configs import BaseDatasetConfig
import torch.serialization

import transformers, TTS as coqui_tts, torch
try:
    print("Transformers", transformers.__version__)
    print("Coqui TTS", coqui_tts.__version__)
    print("Torch", torch.__version__)
except Exception:
    pass


# Register XTTS classes for safe deserialisation when supported by PyTorch
_add_safe_globals = getattr(torch.serialization, "add_safe_globals", None)
if _add_safe_globals is not None:
    _add_safe_globals([XttsConfig, XttsAudioConfig, Xtts, BaseDatasetConfig, XttsArgs])
else:
    # PyTorch versions prior to 2.3 do not provide add_safe_globals
    pass

def run_xtts():
    """
    Batch-generate base audio for all scripts using Coqui XTTS
    with multi-clip speaker samples and per-character style reference.
    """
    # Configuration
    ROOT = Path(__file__).parent.parent.resolve()
    BASE_DIR = ROOT / "data"
    SCRIPTS_DIR = BASE_DIR / "scripts"
    OUTPUT_BASE = BASE_DIR / "audio" / "base"

    # Discover speaker sample clips
    SAMPLE_ROOT = ROOT / "xtts" / "speaker_samples"
    SPEAKER_SAMPLES = {
        "Peter": sorted((SAMPLE_ROOT / "peter").glob("*.wav")),
        "Stewie": sorted((SAMPLE_ROOT / "stewie").glob("*.wav")),
    }
    # Map each character to a single style clip
    STYLE_CLIP = {
        "Peter": SAMPLE_ROOT / "style/test", #peter" / "peter_style.wav",
        "Stewie": SAMPLE_ROOT / "style/test", #stewie" / "stewie_style.wav",
    }

    # XTTS model
    TTS_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"

    # Load model once with desired temperature
    print(f"🔊 Loading XTTS model: {TTS_MODEL}")
    tts = TTS(model_name=TTS_MODEL, progress_bar=True, gpu=False)
    # The high level TTS API handles device internally when gpu=False

    # Process each generated script
    for script_path in sorted(SCRIPTS_DIR.glob("*.json")):
        print(f"\n📜 Processing script: {script_path.name}")
        script = json.loads(script_path.read_text())

        out_dir = OUTPUT_BASE #/ script_path.stem
        out_dir.mkdir(parents=True, exist_ok=True)

        index = 1
        for character in script.get("characters", []):
            name = character.get("name")
            samples = SPEAKER_SAMPLES.get(name, [])
            samples = [p for p in samples if p.exists()]
            style_clip = STYLE_CLIP.get(name)
            if not samples or not style_clip or not style_clip.exists():
                print(f"⚠️ Missing samples or style for '{name}', skipping.")
                continue

            for line in character.get("lines", []):
                filename = f"{index:02d}_{name}.wav"
                output_path = out_dir / filename
                print(f"🎧 [{index:02d}] {name}: {line}")
                try:
                    # Ensure output directory exists
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    tts.tts_to_file(
                        text=line,
                        speaker_wav=[str(p) for p in samples],
                        # style_wav=str(style_clip),
                        language="en",
                        file_path=str(output_path),
                        temperature=0.8
                    )
                except Exception as e:
                    print(f"❌ Failed to synthesize '{filename}': {e}")
                index += 1

    print("\n✅ XTTS batch conversion complete.")

if __name__ == "__main__":
    run_xtts()