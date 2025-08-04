import json
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
    data = json.loads(word_json_path.read_text())
    words = data.get("word_segments", [])

    lines = [ASS_HEADER]

    for i in range(0, len(words), window_size):
        clump = words[i:i + window_size]
        if not clump:
            continue

        # For each word in the clump, create a subtitle event with that word highlighted
        for j, w in enumerate(clump):
            start = seconds_to_ass(w['start'])
            end = seconds_to_ass(w['end'])

            phrase_parts = []
            for k, word_data in enumerate(clump):
                word_text = word_data["word"]
                if k == j:
                    phrase_parts.append(f"{{\\b1\\c&H00FF00&}}{word_text}{{\\b0\\c&H00FFFFFF&}}")
                else:
                    phrase_parts.append(word_text)

            text_line = " ".join(phrase_parts)
            lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text_line}\n")

    ass_out_path.write_text("".join(lines))
    print(f"✅ Wrote ASS subtitles to {ass_out_path}")

if __name__ == "__main__":
    build_ass_from_whisperx(
        Path("data/final/preview_audio.json"),
        Path("data/final/dialogue.ass")
    )