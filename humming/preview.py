"""추출한 음을 들려주는 기본 미리듣기(합성음).

나중에 피아노·하프 모듈이 완성되면 같은 메서드 이름(play_note / play_sequence / stop)을
가진 객체를 HummingEngine(player=...)에 넣어 주면 그대로 교체된다.
"""
import time
from typing import List, Optional
import numpy as np
import sounddevice as sd

from .model import Note
from .pitch import SR, midi_to_hz


def tone(midi: int, duration_ms: int, sr: int = SR) -> np.ndarray:
    """배음 4개 + 지수 감쇠 = 간단한 피아노풍 소리"""
    n = int(sr * duration_ms / 1000)
    t = np.arange(n) / sr
    f = float(midi_to_hz(midi))
    y = np.zeros(n)
    for k, amp in ((1, 1.0), (2, 0.5), (3, 0.25), (4, 0.12)):
        y += amp * np.sin(2 * np.pi * f * k * t)
    env = np.exp(-3.0 * t) * np.minimum(1.0, t / 0.01)
    return (y * env * 0.3).astype(np.float32)


def render(notes: List[Note], sr: int = SR) -> np.ndarray:
    """음 목록을 실제 타이밍대로 한 버퍼에 섞는다."""
    if not notes:
        return np.zeros(sr // 2, dtype=np.float32)
    total_ms = max(n.start_ms + n.duration_ms for n in notes) + 800
    buf = np.zeros(int(sr * total_ms / 1000), dtype=np.float32)
    for n in notes:
        s = int(sr * n.start_ms / 1000)
        seg = tone(n.final_midi, max(n.duration_ms, 150) + 300, sr)
        seg = seg[: len(buf) - s]
        buf[s : s + len(seg)] += seg
    peak = np.abs(buf).max()
    return buf / peak * 0.8 if peak > 0 else buf


class TonePlayer:
    def __init__(self, sr: int = SR):
        self.sr = sr
        self._started_at: Optional[float] = None
        self._notes: List[Note] = []

    def play_note(self, midi: int, duration_ms: int = 400) -> None:
        sd.stop()
        sd.play(tone(midi, duration_ms + 300, self.sr), self.sr)

    def play_sequence(self, notes: List[Note]) -> None:
        sd.stop()
        self._notes = list(notes)
        self._started_at = time.time()
        sd.play(render(notes, self.sr), self.sr)

    def stop(self) -> None:
        sd.stop()
        self._started_at = None

    def current_index(self) -> Optional[int]:
        """지금 울리고 있는 음의 번호 (화면 하이라이트용). 재생 중이 아니면 None"""
        if self._started_at is None:
            return None
        ms = (time.time() - self._started_at) * 1000
        for i, n in enumerate(self._notes):
            if n.start_ms <= ms < n.start_ms + n.duration_ms:
                return i
        if self._notes and ms > self._notes[-1].start_ms + self._notes[-1].duration_ms + 800:
            self._started_at = None
        return None


if __name__ == "__main__":
    p = TonePlayer()
    demo = [Note(60, 60.0, 0, 400, 1.0), Note(64, 64.0, 450, 400, 1.0), Note(67, 67.0, 900, 700, 1.0)]
    p.play_sequence(demo)
    print("도·미·솔이 들리면 통과")
    sd.wait()
