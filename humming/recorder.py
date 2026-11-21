"""마이크 녹음. 아이콘 클릭으로 시작/정지, 최소 10초·최대 15초 제한.

sounddevice의 InputStream은 별도 스레드에서 콜백으로 소리를 조금씩 넘겨준다.
그래서 녹음 중에도 웹캠 화면 루프가 멈추지 않는다.
"""
import os
import threading
import time
import wave
import numpy as np
import sounddevice as sd

from .pitch import SR


class Recorder:
    def __init__(self, sr: int = SR, min_sec: float = 0.0, max_sec: float = 15.0):
        self.sr = sr
        self.min_sec = min_sec
        self.max_sec = max_sec
        self._chunks = []
        self._stream = None
        self._t0 = None
        self._lock = threading.Lock()
        self._level = 0.0

    # ---- 상태 ----
    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def elapsed(self) -> float:
        return 0.0 if self._t0 is None else time.time() - self._t0

    def can_stop(self) -> bool:
        return self.elapsed() >= self.min_sec

    def should_auto_stop(self) -> bool:
        return self.is_recording and self.elapsed() >= self.max_sec

    def level(self) -> float:
        """최근 입력 크기(0~1). 화면에 마이크 레벨 바를 그릴 때 사용"""
        return self._level

    # ---- 동작 ----
    def start(self) -> None:
        if self.is_recording:
            return
        self._chunks = []
        self._t0 = time.time()
        self._stream = sd.InputStream(samplerate=self.sr, channels=1, dtype="float32",
                                      blocksize=1024, callback=self._callback)
        self._stream.start()

    def _callback(self, indata, frames, time_info, status):
        mono = indata[:, 0].copy()
        with self._lock:
            self._chunks.append(mono)
        self._level = float(min(1.0, np.abs(mono).max() * 3))

    def stop(self) -> np.ndarray:
        """녹음을 끝내고 전체 소리를 float32 배열로 돌려준다 (최대 max_sec까지 자름)."""
        if not self.is_recording:
            return np.zeros(0, dtype=np.float32)
        self._stream.stop()
        self._stream.close()
        self._stream = None
        with self._lock:
            y = np.concatenate(self._chunks) if self._chunks else np.zeros(0, dtype=np.float32)
        self._t0 = None
        return y[: int(self.max_sec * self.sr)]

    @staticmethod
    def save_wav(path: str, y: np.ndarray, sr: int) -> None:
        """디버그용. 16bit wav로 저장 (python -m humming.analyzer 파일경로 로 다시 분석 가능)"""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        pcm = (np.clip(y, -1, 1) * 32767).astype(np.int16)
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    # 자가 테스트: 3초만 녹음해서 크기 확인 (제한 시간은 테스트용으로 짧게)
    print(sd.query_devices())
    rec = Recorder(min_sec=0, max_sec=3)
    print("3초 동안 '아~' 하세요")
    rec.start()
    while not rec.should_auto_stop():
        time.sleep(0.05)
    y = rec.stop()
    print(f"샘플 {len(y)}개, 최대 진폭 {np.abs(y).max():.3f} (0.05 미만이면 마이크가 너무 작음)")
    Recorder.save_wav("recordings/test.wav", y, rec.sr)
    print("recordings/test.wav 저장됨")