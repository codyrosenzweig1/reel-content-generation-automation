import subprocess
from pathlib import Path

HERE = Path(__file__).parent

def extract_clip(url: str, start: str, duration: str, out: str):
    """Runs extract_clip.sh to download & trim a YT clip."""
    script = HERE / "extract_clip.sh"
    subprocess.run([str(script), url, start, duration, out], check=True)