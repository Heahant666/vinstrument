"""텍스트 입력('도,레,미', '4도', '도4', 'C4' 등)을 HummingResult/Note 목록으로 변환."""
import re
from typing import List, Optional, Tuple
from .model import HummingResult, Note

SOLFEGE_BASE = {
    "도": 0, "레": 2, "미": 4, "파": 5, "솔": 7, "라": 9, "시": 11,
}
NOTE_BASE = {
    "C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11,
}


def _apply_accidental(semi: int, acc: Optional[str]) -> int:
    if acc in ("#", "♯"):
        return semi + 1
    if acc in ("b", "♭", "B"):
        return semi - 1
    return semi


def parse_note_token(token: str, default_octave: int = 4) -> Optional[int]:
    raw = token.strip()
    if not raw:
        return None

    # 1) 한글 계이름 + 옥타브 앞/뒤: '도', '도4', '4도', '도#4', '4도#', '솔b3', '3솔b'
    m_ko = re.match(
        r"^(?:([0-8])\s*)?(도|레|미|파|솔|라|시)(?:([0-8]))?\s*(#|♯|b|♭)?$",
        raw,
    )
    if m_ko:
        oct_pre, name, oct_post, acc = m_ko.groups()
        semi = SOLFEGE_BASE[name]
        semi = _apply_accidental(semi, acc)
        oct_str = oct_pre or oct_post
        octave = int(oct_str) if oct_str is not None else default_octave
        return (octave + 1) * 12 + semi

    # 2) 영문 음이름 + 옥타브 앞/뒤: 'C4', '4C', 'C#4', 'Db4', 'c', 'G5'
    m_en = re.match(
        r"^(?:([0-8])\s*)?([A-Ga-g])(?:([0-8]))?\s*(#|♯|b|♭)?$",
        raw,
    )
    if m_en:
        oct_pre, name, oct_post, acc = m_en.groups()
        semi = NOTE_BASE[name.upper()]
        semi = _apply_accidental(semi, acc)
        oct_str = oct_pre or oct_post
        octave = int(oct_str) if oct_str is not None else default_octave
        return (octave + 1) * 12 + semi

    return None


def build_result_from_text(
    text: str,
    note_range: Tuple[int, int] = (21, 108),
    default_octave: int = 4,
    step_ms: int = 480,
    dur_ms: int = 420,
    sr: int = 22050,
) -> HummingResult:
    lo, hi = note_range
    # 쉼표, 슬래시, 공백 등으로 구분
    raw_tokens = re.split(r"[,\s/]+", text.strip())
    notes: List[Note] = []

    for tok in raw_tokens:
        midi = parse_note_token(tok, default_octave=default_octave)
        if midi is None:
            continue
        midi = max(lo, min(hi, midi))
        idx = len(notes)
        start_ms = idx * step_ms
        cands = [c for c in (midi + 1, midi - 1) if lo <= c <= hi][:2]
        notes.append(
            Note(
                midi=midi,
                midi_float=float(midi),
                start_ms=start_ms,
                duration_ms=dur_ms,
                confidence=1.0,
                candidates=cands,
                flags=["text"],
            )
        )

    total_ms = (notes[-1].start_ms + notes[-1].duration_ms) if notes else 0
    return HummingResult(notes=notes, sample_rate=sr, duration_ms=total_ms)