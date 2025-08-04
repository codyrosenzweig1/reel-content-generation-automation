from dotenv import load_dotenv
import os
import subprocess
from pathlib import Path

# === Configuration ===
account = "tech_account"
local_dir = Path("../data/scripts")  # Local scripts folder
remote_dir = f"/root/rvc_core/content_generation/data/{account}/scripts"

# Load SSH config
load_dotenv("../.env.local")
SSH_KEY_PATH = os.getenv("SSH_KEY_PATH")
SERVER_IP = os.getenv("SERVER_IP")
REMOTE_USER = "root"

def upload_scripts_to_cloud():
    if not SSH_KEY_PATH or not SERVER_IP:
        raise EnvironmentError("Missing SSH_KEY_PATH or SERVER_IP in environment variables.")

    ssh_key_path = os.path.expanduser(SSH_KEY_PATH)

    # Ensure remote directory exists using SSH
    mkdir_command = [
        "ssh",
        "-i", ssh_key_path,
        f"{REMOTE_USER}@{SERVER_IP}",
        f"mkdir -p {remote_dir}"
    ]

    try:
        subprocess.run(mkdir_command, check=True)
        print(f"📁 Ensured remote directory exists: {remote_dir}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create remote directory: {e}")
        return

    # Construct rsync command
    rsync_command = [
        "rsync",
        "-avz",  # archive mode, verbose, compressed
        "-e", f"ssh -i {ssh_key_path}",
        str(local_dir) + "/",  # Trailing slash = send *contents*
        f"{REMOTE_USER}@{SERVER_IP}:{remote_dir}"
    ]

    try:
        print(f"📤 Uploading scripts to {SERVER_IP} via rsync...")
        subprocess.run(rsync_command, check=True)
        print("✅ Upload complete.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Upload failed: {e}")

if __name__ == "__main__":
    upload_scripts_to_cloud()
