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
import threading


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

        # 현재 재생 중인 음파 데이터 목록
        self._active_notes = []

        # 여러 스레드에서 음 데이터에 접근할 때 충돌 방지
        self._lock = threading.Lock()

        # 오디오 출력 스트림을 계속 실행
        self._stream = sd.OutputStream(
            samplerate=self.sr,
            channels=1,
            callback=self._audio_callback
        )
        self._stream.start()

    def _audio_callback(self, outdata, frames, time_info, status):
        # 이번 출력 구간을 무음으로 초기화
        output = np.zeros(frames, dtype=np.float32)

        with self._lock:
            remaining_notes = []

            for sound, position in self._active_notes:

                # 이번 프레임에서 재생할 수 있는 길이
                available = len(sound) - position
                length = min(frames, available)

                if length > 0:
                    output[:length] += sound[position:position + length]

                # 아직 재생할 음이 남아 있다면 유지
                position += length

                if position < len(sound):
                    remaining_notes.append((sound, position))

            self._active_notes = remaining_notes

        # 동시에 재생되는 음이 너무 커지지 않도록 제한
        output = np.clip(output, -1.0, 1.0)

        outdata[:, 0] = output

    def play_note(self, midi: int, duration_ms: int = 400) -> None:
        sound = tone(midi, duration_ms + 300, self.sr)

        with self._lock:
            # 기존 음을 끊지 않고 새로운 음 추가
            self._active_notes.append((sound, 0))

    def play_sequence(self, notes: List[Note]) -> None:
        self.stop()
        self._notes = list(notes)
        self._started_at = time.time()
        sd.play(render(notes, self.sr), self.sr)

    def stop(self) -> None:
        with self._lock:
            self._active_notes.clear()

        sd.stop()
        self._started_at = None

    def close(self) -> None:
        self.stop()
        self._stream.stop()
        self._stream.close()

    def current_index(self) -> Optional[int]:
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
