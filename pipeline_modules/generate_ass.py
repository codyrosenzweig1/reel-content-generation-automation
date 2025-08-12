import json
import re
from pathlib import Path

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,64,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,2,0,2,10,10,1200,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

def seconds_to_ass(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    cs = int((t - int(t)) * 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"

def build_ass_from_whisperx(word_json_path: Path, ass_out_path: Path, window_size: int = 4):
    # Tunables for timing feel
    LEAD_SEC = 0.08
    COMPRESS = 0.88
    COMMA_GAP = 0.16
    FULLSTOP_GAP = 0.32
    PUNCT_SHOW_CAP = 0.14
    SAFETY_MARGIN = 0.02

    data = json.loads(word_json_path.read_text())
    # Optional sentence map to recover exact sentence-ending punctuation like ? and !
    sentence_punct_by_end_index = {}
    sentence_map_path = word_json_path.parent / "sentence_map.json"
    if sentence_map_path.exists():
        try:
            sent_map = json.loads(sentence_map_path.read_text())
            # Expect a list of sentences, each with at least {"text", "start", "end"}
            # We will later align by end time to the last word index within the sentence
            sentence_entries = []
            if isinstance(sent_map, list):
                sentence_entries = sent_map
            elif isinstance(sent_map, dict):
                # Common variants
                sentence_entries = sent_map.get("sentences") or sent_map.get("segments") or []
            # Pre-extract desired ending punctuation
            def trailing_punct(s: str) -> str:
                if not isinstance(s, str):
                    return ""
                s = s.strip()
                m = re.search(r"([\.!?…]+)\s*$", s)
                return m.group(1)[-1] if m else ""
            sentence_meta = []
            for seg in sentence_entries:
                t = seg.get("text") if isinstance(seg, dict) else None
                st = seg.get("start") if isinstance(seg, dict) else None
                en = seg.get("end") if isinstance(seg, dict) else None
                if t is None or st is None or en is None:
                    continue
                p = trailing_punct(t)
                if p:
                    try:
                        sentence_meta.append({"end": float(en), "punct": p})
                    except Exception:
                        pass
        except Exception:
            sentence_meta = []
    else:
        sentence_meta = []

    # Normalise input: accept list of words, or dicts with word_segments/words, or segments->words
    words_raw = []
    if isinstance(data, list):
        words_raw = data
    elif isinstance(data, dict):
        if isinstance(data.get("word_segments"), list):
            words_raw = data["word_segments"]
        elif isinstance(data.get("words"), list):
            words_raw = data["words"]
        elif isinstance(data.get("segments"), list):
            for seg in data["segments"]:
                seg_words = seg.get("words") or []
                if isinstance(seg_words, list):
                    words_raw.extend(seg_words)

    # Coerce to unified schema: {text, start, end}
    normalised_words = []
    for w in words_raw:
        if not isinstance(w, dict):
            continue
        start = w.get("start")
        end = w.get("end")
        # Sometimes timestamps appear as [start, end] under key 'ts'
        if (start is None or end is None) and isinstance(w.get("ts"), (list, tuple)) and len(w["ts"]) == 2:
            try:
                start, end = float(w["ts"][0]), float(w["ts"][1])
            except Exception:
                start, end = None, None
        text = (w.get("word") or w.get("text") or w.get("token") or "").strip()
        if start is None or end is None or not text:
            continue
        try:
            start_f = float(start)
            end_f = float(end)
        except Exception:
            continue
        normalised_words.append({"text": text, "start": start_f, "end": end_f, "punct": w.get("punct", "")})

    # Ensure chronological order
    normalised_words.sort(key=lambda x: x["start"]) 

    # Align sentence end times to word indices so we can place exact punctuation like ? and !
    sentence_end_index = {}
    if sentence_meta:
        # Build a list of word end times for binary search
        word_ends = [w.get("end", 0.0) for w in normalised_words]
        for meta in sentence_meta:
            try:
                sent_end = float(meta["end"]) if isinstance(meta.get("end"), (int, float)) else None
                if sent_end is None:
                    continue
                # find the last word whose end is <= sent_end + small epsilon
                eps = 0.04
                idx = None
                for i, we in enumerate(word_ends):
                    if we <= sent_end + eps:
                        idx = i
                    else:
                        break
                if idx is not None:
                    sentence_end_index[idx] = meta["punct"]
            except Exception:
                continue

    # Precompute adjusted timings with per‑word lead and compression
    adjusted = []
    for idx, w in enumerate(normalised_words):
        s = max(0.0, w["start"] - LEAD_SEC)
        dur = max(0.0, w["end"] - w["start"]) * COMPRESS
        e = s + dur
        # Constrain so it never pushes past the next word hard start minus a safety margin
        if idx + 1 < len(normalised_words):
            next_s = normalised_words[idx + 1]["start"] - LEAD_SEC
            e = min(e, max(s, next_s - SAFETY_MARGIN))
        adjusted.append({"text": w["text"], "start": s, "end": e, "punct": w.get("punct", "")})

    lines = [ASS_HEADER]

    # Helper to choose punctuation based on gap
    def pick_punct(gap: float) -> str:
        if gap >= FULLSTOP_GAP:
            return "."
        if gap >= COMMA_GAP:
            return ","
        return ""

    for i in range(0, len(adjusted), window_size):
        clump = adjusted[i:i + window_size]
        if not clump:
            continue

        for j, w in enumerate(clump):
            # Compute start and end, then optionally extend a touch at punctuation
            start = w["start"]
            end = w["end"]

            # Index of this word across the whole sequence
            global_index = i + j

            # Determine the punctuation that truly belongs to this word
            # Prefer explicit per-word punctuation, then sentence-end punctuation
            effective_punct = (w.get("punct", "") or sentence_end_index.get(global_index, ""))

            # If this word truly ends a sentence, give it a tiny visual hold
            if effective_punct and global_index + 1 < len(adjusted):
                next_word = adjusted[global_index + 1]
                gap = max(0.0, next_word["start"] - end)
                hold = min(PUNCT_SHOW_CAP, max(0.0, gap - SAFETY_MARGIN))
                end = min(end + hold, next_word["start"] - SAFETY_MARGIN)
            elif global_index + 1 < len(adjusted):
                # Fallback: infer commas/full stops from gaps only when neither source provided punctuation
                next_word = adjusted[global_index + 1]
                gap = max(0.0, next_word["start"] - end)
                inferred = pick_punct(gap)
                if inferred:
                    effective_punct = effective_punct or inferred
                    hold = min(PUNCT_SHOW_CAP, max(0.0, gap - SAFETY_MARGIN))
                    end = min(end + hold, next_word["start"] - SAFETY_MARGIN)

            ass_start = seconds_to_ass(start)
            ass_end = seconds_to_ass(end)

            # Build the text for this window with punctuation attached to its owning word
            phrase_parts = []
            for k, word_data in enumerate(clump):
                word_text = word_data["text"]
                gi = i + k
                # Punctuation to render for this word (explicit per-word, plus sentence-end if present)
                word_punct = (word_data.get("punct", "") or "")
                if gi in sentence_end_index and sentence_end_index[gi] and sentence_end_index[gi] not in word_punct:
                    word_punct = f"{word_punct}{sentence_end_index[gi]}"

                token = f"{word_text}{word_punct}"
                if k == j:
                    # Highlight the word together with its punctuation
                    phrase_parts.append(f"{{\\b1\\c&H00FF00&}}{token}{{\\b0\\c&H00FFFFFF&}}")
                else:
                    phrase_parts.append(token)

            text_line = " ".join(phrase_parts)

            lines.append(f"Dialogue: 0,{ass_start},{ass_end},Default,,0,0,0,,{text_line}\n")

    ass_out_path.write_text("".join(lines))
    print(f"✅ Wrote ASS subtitles to {ass_out_path}")

if __name__ == "__main__":
    build_ass_from_whisperx(
        Path("data/final/preview_audio.json"),
        Path("data/final/dialogue.ass")
    )