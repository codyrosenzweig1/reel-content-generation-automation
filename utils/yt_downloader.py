import subprocess
from pathlib import Path

# === Configuration ===
YOUTUBE_URL = "https://www.youtube.com/watch?v=XBIaqOm0RKQ"  # Replace with actual video
OUTPUT_DIR = Path("data/videos")
MIN_WIDTH = 1280
ASPECT_RATIO_TOLERANCE = 0.1  # Accept ~1.78 (16:9) ± this

# === Ensure directory exists ===
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === Fetch format list ===
print("🔍 Fetching format list...")
try:
    result = subprocess.check_output(["yt-dlp", "-F", YOUTUBE_URL], text=True)
except subprocess.CalledProcessError as e:
    print("❌ Failed to fetch formats:", e)
    exit(1)

# === Parse format list and select 16:9 format ===
best_format = None
for line in result.splitlines():
    if "mp4" in line and "x" in line:
        parts = line.split()
        fmt_id = parts[0]
        try:
            res_index = next(i for i, p in enumerate(parts) if "x" in p)
            width, height = map(int, parts[res_index].split("x"))
            aspect = width / height
            if abs(aspect - 16/9) < ASPECT_RATIO_TOLERANCE and width >= MIN_WIDTH:
                best_format = fmt_id
                break
        except:
            continue

if not best_format:
    print("❌ No suitable 16:9 HD format found.")
    exit(1)

# === Download video ===
print(f"⬇ Downloading format {best_format} as 16:9 HD...")
output_template = str(OUTPUT_DIR / "%(title).80s.%(ext)s")
download_cmd = ["yt-dlp", "-f", best_format, "-o", output_template, YOUTUBE_URL]

try:
    subprocess.run(download_cmd, check=True)
    print("✅ Download complete!")
except subprocess.CalledProcessError as e:
    print("❌ Download failed:", e)
