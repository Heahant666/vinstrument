"""허밍 엔진의 창구. 화면(main.py / view.py)은 이 클래스만 다루면 된다.

상태: idle(대기) → recording(녹음 중) → ready(분석 완료, 수정·재생 가능)
"""
import os
from typing import List, Optional, Tuple
import numpy as np

from .analyzer import analyze_audio
from .model import HummingResult, Note
from .pitch import SR
from .preview import TonePlayer
from .recorder import Recorder

IDLE, RECORDING, READY = "idle", "recording", "ready"


class HummingEngine:
    def __init__(self, player=None, note_range: Tuple[int, int] = (21, 108),
                 sr: int = SR, min_sec: float = 0.0, max_sec: float = 15.0,
                 save_dir: Optional[str] = "recordings"):
        self.recorder = Recorder(sr, min_sec, max_sec)
        self.player = player or TonePlayer(sr)   # 나중에 피아노/하프 플레이어로 교체 가능
        self.note_range = note_range
        self.sr = sr
        self.save_dir = save_dir
        self.state = IDLE
        self.message = "Click the mic icon and hum (max 15 s)"
        self.result: Optional[HummingResult] = None
        self.last_audio: Optional[np.ndarray] = None

    # ---------- 녹음 ----------
    def toggle_record(self) -> None:
        """마이크 아이콘 클릭 시 녹음 시작/종료."""
        # 실제 입력 스트림 상태를 기준으로 판단해 상태값과 스트림이 어긋나도 복구한다.
        if self.recorder.is_recording:
            if self.recorder.can_stop():
                self._finish()
            else:
                remain = max(0.0, self.recorder.min_sec - self.recorder.elapsed())
                self.message = (
                    f"Keep humming... {remain:.0f} s more "
                    f"(min {self.recorder.min_sec:.0f} s)"
                )
            return

        # 새 녹음 시작
        self.player.stop()
        self.result = None
        self.last_audio = None

        try:
            self.recorder.start()
        except Exception as exc:
            self.state = READY if self.result else IDLE
            self.message = f"Microphone error: {exc}"
            return

        self.state = RECORDING
        self.message = "Recording... click again to stop (auto stop at 15 s)"

    def update(self) -> str:
        """매 프레임 호출. 15초가 되면 자동 종료"""
        if self.state == RECORDING and self.recorder.should_auto_stop():
            self._finish()
        return self.state

    def _finish(self) -> None:
        y = self.recorder.stop()
        self.last_audio = y
        if self.save_dir:
            Recorder.save_wav(os.path.join(self.save_dir, "last.wav"), y, self.sr)
        self.result = analyze_audio(y, self.sr, self.note_range)
        self.state = READY
        n = len(self.result.notes)
        unsure = sum(1 for x in self.result.notes if x.uncertain)
        self.message = (f"{n} notes found ({unsure} to check). SPACE: play/stop, hover a note to fix"
                        if n else "No notes found. Hum louder / closer to the mic")

    def reset(self) -> None:
        self.player.stop()
        if self.recorder.is_recording:
            self.recorder.stop()
        self.state, self.result = IDLE, None
        self.message = "Click the mic icon and hum (max 15 s)"

    # ---------- 수정 ----------
    @property
    def notes(self) -> List[Note]:
        return self.result.notes if self.result else []

    def options(self, index: int) -> List[int]:
        """해당 음에 대해 보여 줄 3개(원래 + 후보 2개)"""
        if not (0 <= index < len(self.notes)):
            return []
        return self.notes[index].options()

    def select(self, index: int, midi: int) -> None:
        """사용자가 3개 중 하나를 고름"""
        note = self.notes[index]
        note.selected = None if midi == note.midi else midi
        self.player.play_note(midi, note.duration_ms)

    def delete(self, index: int) -> None:
        del self.notes[index]

    # ---------- 재생 ----------
    def play_all(self) -> None:
        if self.notes:
            self.player.play_sequence(self.notes)

    def play_note(self, midi: int, duration_ms: int = 400) -> None:
        self.player.play_note(midi, duration_ms)

    def stop(self) -> None:
        self.player.stop()

    def playing_index(self) -> Optional[int]:
        return self.player.current_index() if hasattr(self.player, "current_index") else None

    def is_playing(self) -> bool:
        return bool(
            self.player.is_playing()
            if hasattr(self.player, "is_playing")
            else (self.playing_index() is not None)
        )

    def is_paused(self) -> bool:
        return bool(
            self.player.is_paused()
            if hasattr(self.player, "is_paused")
            else False
        )

    def toggle_play(self) -> None:
        """재생 중 SPACE=일시정지, 일시정지 SPACE=이어 재생, 완료 SPACE=처음부터."""
        if self.is_playing():
            if hasattr(self.player, "pause"):
                self.player.pause()
            else:
                self.stop()
        elif self.is_paused():
            if hasattr(self.player, "resume"):
                self.player.resume()
            else:
                self.play_all()
        else:
            self.play_all()

    # ---------- 악기 쪽으로 넘기기 ----------
    def get_payload(self) -> List[dict]:
        """최종 데이터. 예: [{"midi":60,"name":"C4","solfege":"도4","start_ms":0,"duration_ms":480}, ...]"""
        return self.result.to_payload() if self.result else []

    def save(self, path: str) -> None:
        if self.result:
            self.result.save_json(path)

    def set_notes_from_text(self, text: str, auto_play: bool = True, default_octave: int = 4) -> bool:
        """텍스트 입력을 허밍 분석 완료(READY) 상태와 동일하게 반영하고 재생한다."""
        from .text_parser import build_result_from_text

        res = build_result_from_text(
            text,
            note_range=self.note_range,
            default_octave=default_octave,
            sr=self.sr,
        )
        if not res.notes:
            self.message = "No valid notes. Try: 도,레,미 / 4도,도4 / C4"
            return False

        self.player.stop()
        self.result = res
        self.state = READY
        self.message = f"{len(res.notes)} notes loaded. SPACE: play/stop, hover to edit"
        if auto_play:
            self.play_all()
        return True