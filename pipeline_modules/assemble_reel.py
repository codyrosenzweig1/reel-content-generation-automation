#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path

LEFT_SPKRS = {"peter"}          # speakers whose PNG appears left

def _probe_duration(video: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration", "-of", "default=nw=1:nk=1", str(video)]
    )
    return float(out.strip())

def assemble_reel(
    video_mp4: Path,
    audio_wav: Path,
    subs_ass: Path,
    sentence_map_json: Path,
    _script_json: Path,
    images_dir: Path,
    output_mp4: Path,
):
    sentence_map = json.loads(sentence_map_json.read_text())

    # keep discovery order
    unique_speakers = []
    for e in sentence_map:
        if e["speaker"] not in unique_speakers:
            unique_speakers.append(e["speaker"])

    ff_inputs = ["-i", str(video_mp4), "-i", str(audio_wav)]
    dur = _probe_duration(video_mp4)

    for spk in unique_speakers:
        img = images_dir / f"{spk}.png"
        if img.exists():
            ff_inputs += ["-loop", "1", "-t", str(dur), "-i", str(img)]
        else:
            print(f"⚠️  PNG missing for {spk}, overlay skipped")

    # 0:v = bg video → burn subs → label [base]
    fc_parts = [
        f"[0:v]subtitles={subs_ass}[base]"
    ]
    last_label = "base"

    for idx, e in enumerate(sentence_map):
        spk       = e["speaker"]
        start,end = e["start"], e["end"]
        if spk not in unique_speakers:
            continue

        inp   = 2 + unique_speakers.index(spk)       # PNG input index
        sideL = spk.lower() in LEFT_SPKRS
        x_pos = "20" if sideL else "main_w-overlay_w-20"
        label_scale = f"s{idx}"                      # unique
        label_out   = f"v{idx}"

        fc_parts.append(
            f"[{inp}:v]scale=iw*0.20:-1[{label_scale}];"
            f"[{last_label}][{label_scale}]overlay="
            f"x={x_pos}:y=H-h-80:enable='between(t,{start},{end})'"
            f"[{label_out}]"
        )
        last_label = label_out

    cmd = [
        "ffmpeg", "-y",
        *ff_inputs,
        "-filter_complex", ";".join(fc_parts),
        "-map", f"[{last_label}]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac",
        str(output_mp4)
    ]

    print("🔨  FFmpeg:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"✅ Reel saved → {output_mp4}")

if __name__ == "__main__":
    BASE_DIR = Path(__file__).parent.parent.resolve()

    assemble_reel(
        video_mp4 = BASE_DIR / "data/backgrounds/bg_preview.mp4",
        audio_wav = BASE_DIR / "data/final/preview_audio.wav",
        subs_ass  = BASE_DIR / "data/final/dialogue.ass",
        sentence_map_json = BASE_DIR / "data/final/sentence_map.json",
        _script_json = BASE_DIR / "data/scripts/bluetooth.json",  # You can change this if needed
        images_dir = BASE_DIR / "data/images",
        output_mp4 = BASE_DIR / "data/final/reel_final.mp4"
    )