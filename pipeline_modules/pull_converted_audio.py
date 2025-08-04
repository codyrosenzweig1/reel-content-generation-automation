import subprocess
import logging
from pathlib import Path
from dotenv import load_dotenv 
import os

logging.basicConfig(level=logging.INFO)
# Load environment variables
load_dotenv(dotenv_path=".env.local")

SERVER_IP = os.getenv("SERVER_IP")

# === CONFIGURATION ===
SERVER = "root@{SERVER_IP}"  # Replace with your actual server IP
REMOTE_DIR = "/root/rvc_core/audio/converted"
ARCHIVE_NAME = "converted_audio.tar.gz"
LOCAL_TARGET_DIR = Path("~/data/accounts/tech_account/audio/converted").expanduser()

# === STEPS ===
def run_command(command, desc):
    logging.info(desc)
    result = subprocess.run(command, shell=True)
    if result.returncode != 0:
        raise RuntimeError(f"❌ Command failed: {command}")

def main():
    try:
        # 1. Compress on server
        run_command(
            f'ssh {SERVER} "cd {REMOTE_DIR}/.. && tar -czf {ARCHIVE_NAME} converted"',
            "📦 Compressing audio files on server..."
        )

        # 2. Create local directory if needed
        LOCAL_DIR.mkdir(parents=True, exist_ok=True)

        # 3. SCP the archive to your Mac
        run_command(
            f"scp {SERVER}:{REMOTE_DIR}/../{ARCHIVE_NAME} {LOCAL_DIR}",
            "📥 Downloading compressed audio files..."
        )

        # 4. Extract the archive locally
        run_command(
            f"tar -xzf {LOCAL_DIR / ARCHIVE_NAME} -C {LOCAL_DIR}",
            "📂 Extracting files locally..."
        )

        # 5. Optional: delete archive on server
        run_command(
            f'ssh {SERVER} "rm {REMOTE_DIR}/../{ARCHIVE_NAME}"',
            "🧹 Cleaning up archive on server..."
        )

        logging.info("✅ All files transferred and extracted successfully!")

    except Exception as e:
        logging.error(str(e))

if __name__ == "__main__":
    main()
