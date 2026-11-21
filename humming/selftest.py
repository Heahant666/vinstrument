"""합성 허밍으로 분석기를 자동 검사. 실행: python -m humming.selftest"""
import numpy as np
from .pitch import SR, midi_to_hz
from .analyzer import analyze_audio, print_result


def hum(midi, dur, vibrato=0.3, amp=0.5):
    t = np.arange(int(SR * dur)) / SR
    f = midi_to_hz(midi) * 2 ** (vibrato / 12 * np.sin(2 * np.pi * 5.5 * t))  # 5.5Hz 비브라토
    phase = 2 * np.pi * np.cumsum(f) / SR
    y = sum(a * np.sin(k * phase) for k, a in ((1, 1), (2, .4), (3, .2)))
    env = np.minimum(1, t / 0.03) * np.minimum(1, (dur - t) / 0.05)
    return (amp * y * env).astype(np.float32)


def silence(dur):
    return np.zeros(int(SR * dur), np.float32)


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    seq = [60, 60, 67, 67, 69, 69, 67]          # 도도솔솔라라솔
    parts = [silence(0.5)]
    for i, m in enumerate(seq):
        parts += [hum(m, 0.45 if i < 6 else 0.9), silence(0.08)]
    y = np.concatenate(parts)
    y += rng.normal(0, 0.01, len(y)).astype(np.float32)
    res = analyze_audio(y)
    print_result(res)
    got = [n.final_midi for n in res.notes]
    print("정답:", seq)
    print("결과:", got)
    print("통과" if got == seq else "실패 — segmenter 임계값 확인")
