"""오디오 배열 → HummingResult. 마이크·화면과 무관한 순수 분석 함수라 wav 파일로도 테스트 가능."""
import sys
import wave
from typing import Tuple
import numpy as np
from .model import HummingResult
from .pitch import SR, preprocess, analyze_frames
from .segmenter import segment
from .candidates import attach_candidates


def analyze_audio(y: np.ndarray, sr: int = SR, note_range: Tuple[int, int] = (21, 108)) -> HummingResult:
    y = preprocess(y, sr)
    fd = analyze_frames(y, sr)
    notes = segment(fd)
    attach_candidates(notes, note_range)
    return HummingResult(notes, sr, int(len(y) / sr * 1000))


def load_wav(path: str):
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        raw = w.readframes(w.getnframes())
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if w.getnchannels() > 1:
            data = data.reshape(-1, w.getnchannels()).mean(axis=1)
    return data, sr


def print_result(res: HummingResult) -> None:
    print(f"총 {len(res.notes)}개 음, 녹음 {res.duration_ms/1000:.1f}초")
    for i, n in enumerate(res.notes):
        alt = ", ".join(f"{c}" for c in n.candidates)
        flag = f"  !{','.join(n.flags)}" if n.flags else ""
        print(f"{i:2d}. {n.name:4s}({n.solfege}) midi={n.midi} 측정={n.midi_float:.2f} "
              f"{n.start_ms:5d}ms +{n.duration_ms:4d}ms conf={n.confidence:.2f} 후보=[{alt}]{flag}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python -m humming.analyzer recordings/last.wav")
        sys.exit(0)
    y, sr = load_wav(sys.argv[1])
    print_result(analyze_audio(y, sr))
