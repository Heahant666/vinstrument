"""각 음에 대해 '비슷한 대안 음 2개'를 고른다.

규칙
1. 측정된 소수 음높이(midi_float)에 가까운 순서로 다른 정수 음을 고른다.
   예) 측정 60.4 → 1차 60(C4). 후보는 61(거리 0.6), 59(거리 1.4) 순.
2. 후보는 원래 음에서 ±2반음 안으로 제한한다 (너무 다른 음은 추천하지 않음).
3. 다만 프레임에 옥타브 튐 근거가 있으면 두 번째 후보를 ±12(옥타브)로 바꾼다.
   허밍 음높이 추정에서 가장 흔한 실수가 옥타브 오류이기 때문.
4. 악기 음역(min_midi~max_midi) 밖은 제외한다.
"""
from typing import List, Tuple
from .model import Note

MAX_DIST = 2


def make_candidates(note: Note, note_range: Tuple[int, int] = (21, 108)) -> List[int]:
    lo, hi = note_range
    base, mf = note.midi, note.midi_float
    nearby = [base + d for d in range(-MAX_DIST, MAX_DIST + 1) if d != 0 and lo <= base + d <= hi]
    nearby.sort(key=lambda c: (abs(c - mf), abs(c - base)))   # 측정값에 가까운 순

    picks: List[int] = []
    if nearby:
        picks.append(nearby[0])
    if note.octave_hint != 0:
        octave = base + 12 * note.octave_hint
        if lo <= octave <= hi and octave not in picks:
            picks.append(octave)
    for c in nearby:
        if len(picks) >= 2:
            break
        if c not in picks:
            picks.append(c)
    return picks[:2]


def attach_candidates(notes: List[Note], note_range: Tuple[int, int] = (21, 108)) -> None:
    for n in notes:
        n.candidates = make_candidates(n, note_range)
