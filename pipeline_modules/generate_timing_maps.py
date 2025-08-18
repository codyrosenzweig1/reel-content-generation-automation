#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path
import sys
import os

# Configuration
SPEED = 1.05  # match combine_audio speed factor
BASE_DIR = Path(__file__).parent.parent.resolve()
CONVERTED_DIR = BASE_DIR / "data" / "audio" / "converted"
FINAL_DIR = BASE_DIR / "data" / "final"
FINAL_DIR.mkdir(parents=True, exist_ok=True)

# Phoneme alignment switch is controlled by function parameter, not env
_PHONEME_ALIGN = True  # default on
_WHISPERX_AVAILABLE = None  # unknown until checked

# Lazy cache for the aligner
_ALIGN_CACHE = {"model": None, "metadata": None, "device": "cpu"}

def _ensure_aligner_available() -> bool:
    """Try to import whisperx once and memoise the result."""
    global _WHISPERX_AVAILABLE, whisperx  # type: ignore
    if _WHISPERX_AVAILABLE is not None:
        return bool(_WHISPERX_AVAILABLE)
    try:
        import importlib
        whisperx = importlib.import_module("whisperx")  # type: ignore
        _WHISPERX_AVAILABLE = True
    except Exception:
        _WHISPERX_AVAILABLE = False
    return bool(_WHISPERX_AVAILABLE)

def _get_aligner():
    if not _PHONEME_ALIGN:
        return None, None, None
    if not _ensure_aligner_available():
        return None, None, None
    if _ALIGN_CACHE["model"] is not None:
        return _ALIGN_CACHE["model"], _ALIGN_CACHE["metadata"], _ALIGN_CACHE["device"]
    device = "cpu"
    align_model, metadata = whisperx.load_align_model(language_code="en", device=device)  # type: ignore
    _ALIGN_CACHE.update({"model": align_model, "metadata": metadata, "device": device})
    return align_model, metadata, device


def align_sentence_to_phones(audio_path: Path, text: str):
    """Return list of word dicts with optional phonemes for a sentence, or None if unavailable."""
    if not _PHONEME_ALIGN:
        return None
    if not _ensure_aligner_available():
        return None
    try:
        align_model, metadata, device = _get_aligner()
        if align_model is None:
            return None
        # Build a single segment that spans the whole file with our transcript text
        segs = [{"text": text, "start": 0.0, "end": float(get_duration(audio_path))}]
        audio = whisperx.load_audio(str(audio_path))
        aligned = whisperx.align(segs, align_model, metadata, audio, device, return_char_alignments=False)
        seg_list = aligned.get("segments") or []
        if not seg_list:
            return None
        words = seg_list[0].get("words") or []
        return words
    except Exception:
        return None

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

def main(script_name: str, phoneme_align: bool = True):
    global _PHONEME_ALIGN
    _PHONEME_ALIGN = bool(phoneme_align)
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
    aligned_sentences = 0
    total_sentences = 0

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
        total_sentences += 1
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

        # Try phoneme alignment for this sentence and map to our tokens when counts match
        phones_by_index = None
        aligned_words = align_sentence_to_phones(wav, line)
        if aligned_words:
            # Clean both sides for safe comparison
            aligned_clean = []
            for aw in aligned_words:
                wtxt = (aw.get("word") or aw.get("text") or "").strip()
                if not wtxt:
                    continue
                # strip simple trailing punctuation similar to our tokeniser
                if wtxt and wtxt[-1] in ",.?!…":
                    wtxt = wtxt[:-1]
                aligned_clean.append({
                    "text": wtxt,
                    "start": aw.get("start"),
                    "end": aw.get("end"),
                    # common keys in whisperx: "phones" or "phonemes", each item may have start end or duration
                    "phones": aw.get("phones") or aw.get("phonemes") or []
                })
            # Only use phones if token count matches to avoid misalignment
            if len(aligned_clean) == len(tokens):
                phones_by_index = []
                for aw in aligned_clean:
                    ph_list = []
                    for ph in aw["phones"]:
                        sym = ph.get("phone") or ph.get("phoneme") or ph.get("label")
                        ps = ph.get("start")
                        pe = ph.get("end")
                        # Some aligners give duration instead of end
                        if ps is not None and pe is None and ph.get("duration") is not None:
                            try:
                                pe = float(ps) + float(ph.get("duration"))
                            except Exception:
                                pe = None
                        if sym is None or ps is None or pe is None:
                            continue
                        # Scale to our global timeline and account for SPEED factor
                        ps_abs = start_s + float(ps) / SPEED
                        pe_abs = start_s + float(pe) / SPEED
                        ph_list.append({"symbol": str(sym), "start": round(ps_abs, 3), "end": round(pe_abs, 3)})
                    phones_by_index.append(ph_list)
                if phones_by_index:
                    aligned_sentences += 1

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
            entry = {
                "word": t["w"],
                "start": round(ws, 3),
                "end": round(we, 3),
                "sentence_index": idx,
                "punct": t["p"]
            }
            if phones_by_index and i < len(phones_by_index) and phones_by_index[i]:
                entry["phonemes"] = phones_by_index[i]
            word_entries.append(entry)
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
    print(f"Phoneme alignment coverage: {aligned_sentences}/{total_sentences} sentences ({(aligned_sentences/total_sentences*100 if total_sentences else 0):.1f}%)")
    print(f"Wrote SRT to {srt_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: generate_timing_maps.py <script_name_without_ext> [--no-phonemes]")
        sys.exit(1)
    script = sys.argv[1]
    use_phones = True
    if len(sys.argv) == 3 and sys.argv[2] == "--no-phonemes":
        use_phones = False
    main(script, phoneme_align=use_phones)
