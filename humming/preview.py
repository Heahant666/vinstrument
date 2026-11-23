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
    """합성음 재생기. 동시 건반 입력과 전체 재생의 일시정지를 지원한다."""

    def __init__(self, sr: int = SR):
        self.sr = sr

        # 전체 음원 재생 관련 데이터
        self._notes: List[Note] = []
        self._audio = np.zeros(0, dtype=np.float32)
        self._started_at: Optional[float] = None
        self._position_frames = 0
        self._paused = False

        # 개별 건반의 동시 재생 관련 데이터
        self._active_notes = []
        self._lock = threading.Lock()

        # 개별 건반 재생용 오디오 스트림
        # TonePlayer 생성 시 한 번만 만들고 계속 사용
        self._stream = sd.OutputStream(
            samplerate=self.sr,
            channels=1,
            callback=self._audio_callback
        )
        self._stream.start()

    def _refresh_position(self) -> int:
        """재생 경과 시간을 샘플 프레임 위치로 갱신한다."""
        if self._started_at is None:
            return self._position_frames

        elapsed = max(0.0, time.monotonic() - self._started_at)
        position = self._position_frames + int(elapsed * self.sr)

        # 버퍼 재생이 끝났으면 처음 위치로 초기화
        if position >= len(self._audio):
            self._started_at = None
            self._position_frames = 0
            self._paused = False
            return 0

        return position

    def _start_from_saved_position(self) -> None:
        """저장된 위치부터 전체 음원을 재생한다."""
        if self._audio.size == 0:
            self._paused = False
            self._position_frames = 0
            return

        self._position_frames = min(
            max(0, self._position_frames), len(self._audio)
        )

        remaining = self._audio[self._position_frames:]

        if remaining.size == 0:
            self._position_frames = 0
            self._paused = False
            return

        sd.play(remaining, self.sr)
        self._started_at = time.monotonic()
        self._paused = False

    def _audio_callback(self, outdata, frames, time_info, status):
        """여러 건반에서 발생한 음을 하나의 출력으로 합친다."""
        output = np.zeros(frames, dtype=np.float32)

        with self._lock:
            remaining_notes = []

            for sound, position in self._active_notes:

                # 이번 출력 구간에서 재생할 수 있는 길이
                available = len(sound) - position
                length = min(frames, available)

                if length > 0:
                    output[:length] += sound[position:position + length]

                position += length

                # 아직 재생할 음이 남아 있다면 유지
                if position < len(sound):
                    remaining_notes.append((sound, position))

            self._active_notes = remaining_notes

        # 동시에 재생되는 음이 너무 커지지 않도록 제한
        output = np.clip(output, -1.0, 1.0)

        outdata[:, 0] = output

    def play_note(self, midi: int, duration_ms: int = 400) -> None:
        """음표 하나를 재생한다. 기존 음은 끊지 않는다."""
        sound = tone(midi, duration_ms + 300, self.sr)

        with self._lock:
            self._active_notes.append((sound, 0))

    def play_sequence(self, notes: List[Note]) -> None:
        """전체 음을 처음부터 재생한다."""
        self.stop()

        if not notes:
            return

        self._notes = list(notes)
        self._audio = render(self._notes, self.sr)
        self._position_frames = 0

        self._start_from_saved_position()

    def pause(self) -> None:
        """현재 재생 위치를 저장한 뒤 일시정지한다."""
        if self._started_at is None:
            return

        position = self._refresh_position()

        if self._started_at is None:
            return

        self._position_frames = position
        sd.stop()
        self._started_at = None
        self._paused = True

    def resume(self) -> None:
        """일시정지했던 위치부터 이어서 재생한다."""
        if not self._paused:
            return

        self._start_from_saved_position()

    def stop(self) -> None:
        """전체 재생과 건반 재생을 정지하고 초기화한다."""
        sd.stop()

        with self._lock:
            self._active_notes.clear()

        self._started_at = None
        self._position_frames = 0
        self._paused = False
        self._audio = np.zeros(0, dtype=np.float32)
        self._notes = []

    def is_playing(self) -> bool:
        """음과 음 사이의 무음 구간도 재생 중으로 판정한다."""
        self._refresh_position()
        return self._started_at is not None

    def is_paused(self) -> bool:
        self._refresh_position()
        return self._paused

    def close(self) -> None:
        """오디오 스트림을 종료한다."""
        self.stop()
        self._stream.stop()
        self._stream.close()

    def current_index(self) -> Optional[int]:
        """현재 재생 위치에 해당하는 음표 인덱스를 반환한다."""
        if not self._notes:
            return None

        if self._started_at is None and not self._paused:
            return None

        position = self._refresh_position()
        ms = position * 1000.0 / self.sr

        for i, note in enumerate(self._notes):
            if note.start_ms <= ms < note.start_ms + note.duration_ms:
                return i

        return None
if __name__ == "__main__":
    p = TonePlayer()
    demo = [Note(60, 60.0, 0, 400, 1.0), Note(64, 64.0, 450, 400, 1.0), Note(67, 67.0, 900, 700, 1.0)]
    p.play_sequence(demo)
    print("도·미·솔이 들리면 통과")
    sd.wait()
