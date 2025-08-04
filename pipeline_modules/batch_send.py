import os
import subprocess
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)

PROJECT_NAME = "quantum_entanglement"
BASE_DIR = Path(__file__).parent.resolve()
CONVERTED_DIR = (BASE_DIR / "audio/converted" / PROJECT_NAME).resolve()
SSH_DEST = "codyrosenzweig@192.168.0.142"  # Your Mac's IP or hostname
LOCAL_TARGET_DIR = "~/Downloads/converted_audio"  # Destination folder on Mac

def batch_send():
    logging.info(f"📤 Sending files from: {CONVERTED_DIR}")

    wav_files = sorted(CONVERTED_DIR.glob("*.wav"))

    if not wav_files:
        logging.info("No .wav files found to send.")
        return

    for wav_path in wav_files:
        remote_path = f"{SSH_DEST}:{LOCAL_TARGET_DIR}"
        command = ["scp", str(wav_path), remote_path]

        logging.info(f"🚚 Transferring: {wav_path.name} → {remote_path}")
        result = subprocess.run(command)

        if result.returncode == 0:
            logging.info(f"✅ Success: {wav_path.name}")
            try:
                os.remove(wav_path)
                logging.info(f"🗑️ Deleted: {wav_path.name}")
            except Exception as e:
                logging.warning(f"⚠️ Could not delete {wav_path.name}: {e}")
        else:
            logging.warning(f"❌ Failed: {wav_path.name}")

if __name__ == "__main__":
    batch_send()
