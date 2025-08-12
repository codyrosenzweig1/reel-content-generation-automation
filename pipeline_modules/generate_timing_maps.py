#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path
import sys

# Configuration
SPEED = 1.05  # match combine_audio speed factor
BASE_DIR = Path(__file__).parent.parent.resolve()
CONVERTED_DIR = BASE_DIR / "data" / "audio" / "converted"
FINAL_DIR = BASE_DIR / "data" / "final"
FINAL_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_JSON = BASE_DIR / "data" / "scripts" / f"{sys.argv[1]}.json" if len(sys.argv)>1 else None
# Or you can hardcode the script name if you pass it differently:
# SCRIPT_JSON = BASE_DIR / "data" / "scripts" / "quantum_entanglement.json"

def get_duration(wav_path: Path) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(wav_path)
    ]).decode().strip()
    return float(out)

def fmt_srt_time(t: float) -> str:
    h = int(t//3600); m = int((t%3600)//60); s = int(t%60)
    ms = int((t - int(t)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def main(script_name: str):
    # 1) Load script
    script_path = BASE_DIR / "data" / "scripts" / f"{script_name}.json"
    script = json.loads(script_path.read_text())

    # 2) Gather sorted wavs
    wav_files = sorted(CONVERTED_DIR.glob("*.wav"))

    # 3) Build sentence_map and word_entries
    sentence_map = []
    word_entries = []
    cursor = 0.0
    idx = 1

    lines = []
    speakers = []
    for char in script["characters"]:
        for line in char["lines"]:
            speakers.append(char["name"])
            lines.append(line.strip())

    if len(lines) != len(wav_files):
        print("⚠️  Mismatch: #lines != #wav files", len(lines), len(wav_files))
        sys.exit(1)

    for line, speaker, wav in zip(lines, speakers, wav_files):
        # enforce punctuation
        if not line.endswith((".", "?", "!", "…")):
            line = line + "."

        dur = get_duration(wav)
        start = cursor
        end = cursor + dur

        # scale times by speed factor
        start_s = start / SPEED
        end_s   = end   / SPEED

        sentence_map.append({
            "index": idx,
            "speaker": speaker,
            "start":  round(start_s,3),
            "end":    round(end_s,3),
            "text":   line
        })

        # word-level with punctuation awareness and proportional timing
        # Split by whitespace but capture a single trailing punctuation mark if present
        raw_tokens = line.split()
        tokens = []  # list of dicts: {w: word, p: punct or ""}
        for tok in raw_tokens:
            w = tok.strip()
            punct = ""
            if w and w[-1] in ",.?!…":
                punct = w[-1]
                w = w[:-1]
            if w:
                tokens.append({"w": w, "p": punct})

        if not tokens:
            tokens = [{"w": line.strip().strip(",.?!…"), "p": "."}]

        # Proportional allocation by word length with small weights for punctuation holds
        def base_weight(word: str) -> int:
            return max(1, len(word))
        P_WEIGHTS = {",": 0.5, ".": 0.8, "?": 0.8, "!": 0.8, "…": 1.0}
        units = 0.0
        for t in tokens:
            units += base_weight(t["w"]) + P_WEIGHTS.get(t["p"], 0.0)
        span = max(1e-6, (end_s - start_s))
        per_unit = span / units

        cur = start_s
        for i, t in enumerate(tokens):
            w_units = base_weight(t["w"]) * per_unit
            ws = cur
            we = ws + w_units
            # add a small hold for punctuation on this word
            if t["p"]:
                we += min(0.18, P_WEIGHTS.get(t["p"], 0.0) * per_unit)
            # prevent drift past end_s
            if i == len(tokens) - 1:
                we = end_s
            word_entries.append({
                "word": t["w"],
                "start": round(ws, 3),
                "end": round(we, 3),
                "sentence_index": idx,
                "punct": t["p"]
            })
            cur = we

        cursor = end
        idx += 1

    # 4) Write sentence_map.json
    sent_path = FINAL_DIR / "sentence_map.json"
    sent_path.write_text(json.dumps(sentence_map, indent=2))
    print(f"Wrote sentence map to {sent_path}")

    # 5) Write word_timestamps.json
    word_path = FINAL_DIR / "word_timestamps.json"
    word_path.write_text(json.dumps(word_entries, indent=2))
    print(f"Wrote word timestamps to {word_path}")

    # 6) Write dialogue.srt
    srt_path = FINAL_DIR / "dialogue.srt"
    with open(srt_path, "w") as sf:
        for entry in sentence_map:
            sf.write(f"{entry['index']}\n")
            sf.write(f"{fmt_srt_time(entry['start'])} --> {fmt_srt_time(entry['end'])}\n")
            sf.write(f"{entry['text']}\n\n")
    print(f"Wrote SRT to {srt_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: generate_timing_maps.py <script_name_without_ext>")
        sys.exit(1)
    main(sys.argv[1])
