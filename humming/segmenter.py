"""프레임별 음높이 → 음표 목록. 같은 음이 이어진 구간을 하나로 묶고, 너무 짧은 것은 버린다."""
from typing import List
import numpy as np
from .model import Note
from .pitch import FrameData

MIN_NOTE_MS = 140       # 이보다 짧은 음은 잡음으로 간주 (기존 80 → 140)
SHORT_NOTE_MS = 200     # 이보다 짧으면 "short" 표시 (확인 권장)
BRIDGE_FRAMES = 6       # 약 70ms 끊김까지는 같은 음으로 이어 붙임 (기존 2 → 6)
HYSTERESIS = 0.95       # 반음 경계/미세 떨림에서 음이 쪼개지는 것을 방지 (기존 0.65 → 0.95)
UNSTABLE_STD = 0.45     # 음 안에서 음높이 표준편차가 이보다 크면 "unstable"
LOW_CONF = 0.70
BORDERLINE = 0.35       # 측정값이 반음 경계(x.5)에 이만큼 가까우면 "borderline"


def _split_by_dips(run: List[int], rms: np.ndarray, min_frames: int,
                   dip_ratio: float = 0.35, rise_ratio: float = 2.2) -> List[List[int]]:
    """같은 음이 이어진 구간 안에서 음량이 크게 꺼졌다가 확실히 다시 커질 때만 두 음으로 나눈다."""
    r = rms[run]
    effective_min = max(min_frames, 8)
    parts, start, peak, i = [], 0, r[0], 1
    while i < len(r):
        peak = max(peak, r[i])
        if r[i] < peak * dip_ratio:
            j = i
            while j + 1 < len(r) and r[j + 1] <= r[j]:
                j += 1                          # 바닥까지
            k = j
            while k + 1 < len(r) and r[k + 1] >= r[k]:
                k += 1                          # 다시 올라가는 곳까지
            if (
                r[k] > r[j] * rise_ratio
                and (j - start) >= effective_min
                and (len(r) - k) >= effective_min
            ):
                parts.append(run[start : j + 1])
                start, peak = j + 1, r[k]
            i = max(k, i) + 1
            continue
        i += 1
    parts.append(run[start:])
    return parts


def segment(fd: FrameData, split_repeats: bool = True) -> List[Note]:
    hop_ms = fd.hop_ms
    min_frames = max(1, int(MIN_NOTE_MS / hop_ms))
    kept: List[Note] = []
    dropped: List[tuple] = []     # (start_ms, end_ms, midi) 짧아서 버린 조각 — 옥타브 힌트에 사용

    def close(run: List[int], midi_int: int):
        if not run:
            return
        parts = _split_by_dips(run, fd.rms_short, min_frames) if split_repeats else [run]
        for part in parts:
            start = fd.times_ms[part[0]]
            end = fd.times_ms[part[-1]] + hop_ms
            dur = end - start
            vals = fd.midi[part]
            if dur < MIN_NOTE_MS:
                dropped.append((start, end, float(np.nanmedian(vals))))
                continue
            mf = float(np.nanmedian(vals))
            midi_final = int(round(mf))
            flags = []
            if abs(mf - midi_final) > BORDERLINE:
                flags.append("borderline")
            if dur < SHORT_NOTE_MS:
                flags.append("short")
            if np.nanstd(vals) > UNSTABLE_STD:
                flags.append("unstable")
            conf = float(np.mean(fd.confidence[part]))
            if conf < LOW_CONF:
                flags.append("low_conf")
            kept.append(Note(midi=midi_final, midi_float=mf,
                             start_ms=int(round(start)), duration_ms=int(round(dur)),
                             confidence=round(conf, 3), flags=flags))

    cur_midi, run, gap = None, [], 0
    for i in range(len(fd.midi)):
        if fd.voiced[i] and np.isfinite(fd.midi[i]):
            m = fd.midi[i]
            if cur_midi is None:
                cur_midi, run = int(round(m)), [i]
            elif abs(m - cur_midi) <= HYSTERESIS:
                run.append(i)
            else:
                close(run, cur_midi)
                cur_midi, run = int(round(m)), [i]
            gap = 0
        else:
            gap += 1
            if cur_midi is not None and gap > BRIDGE_FRAMES:
                close(run, cur_midi)
                cur_midi, run = None, []
    if cur_midi is not None:
        close(run, cur_midi)

    # 옥타브 힌트 1: 이웃한 두 음이 정확히 12반음 차이면, 더 짧은 쪽이 옥타브 오류일 가능성이 높다
    for a, b in zip(kept, kept[1:]):
        if abs(abs(a.midi_float - b.midi_float) - 12.0) < 1.0:
            wrong, ref = (a, b) if a.duration_ms <= b.duration_ms else (b, a)
            wrong.octave_hint = 1 if ref.midi_float > wrong.midi_float else -1
            if "octave_jump" not in wrong.flags:
                wrong.flags.append("octave_jump")
    # 옥타브 힌트 2: 버린 짧은 조각이 바로 옆 음과 12반음 차이면, 그 음도 옥타브가 틀렸을 수 있다
    for n in kept:
        if n.octave_hint:
            continue
        for (s, e, m) in dropped:
            near = (abs(s - (n.start_ms + n.duration_ms)) < 60) or (abs(e - n.start_ms) < 60) \
                   or (n.start_ms <= s <= n.start_ms + n.duration_ms)
            if near and abs(abs(m - n.midi_float) - 12) < 1.0:
                n.octave_hint = 1 if m > n.midi_float else -1
                if "octave_jump" not in n.flags:
                    n.flags.append("octave_jump")
                break
    return kept