"""결과 음표 편집: 길이 조절 · 삭제 · 중간 삽입(허밍으로 / 직접 고르기) · 되돌리기.

엔진의 result.notes 리스트만 바꾼다. 화면(view)은 다음 프레임에 바뀐 리스트를 그대로 그리므로
view.py는 손대지 않는다. 뒤따르는 음의 start_ms는 늘어나거나 줄어든 만큼 함께 밀어서
음 사이 간격(허밍할 때의 쉼)은 그대로 유지한다.
"""
import copy
import statistics
from typing import List, Optional

import cv2

from .model import Note, HummingResult, midi_to_name

try:
    from .engine import READY, RECORDING
except ImportError:                     # 상수 이름이 다르면 문자열로
    READY, RECORDING = "ready", "recording"

GAP_MS = 80            # 삽입한 음 앞뒤에 두는 간격
MIN_DUR_MS = 80
MAX_DUR_MS = None
STEP = 1.25            # 길이 조절 배율: ] 는 ×1.25, [ 는 ÷1.25
UNDO_LIMIT = 30


class NoteEditor:
    def __init__(self, engine):
        self.engine = engine
        self.undo_stack: List[List[Note]] = []
        # 허밍 삽입 상태
        self._hum_backup: Optional[List[Note]] = None   # 녹음 전 음 목록
        self._hum_old_result = None                      # 녹음 전 result 객체(바뀜 감지용)
        self._hum_at: int = 0                            # 삽입 위치(이 인덱스 앞에 들어감)
        # 직접 고르기 삽입 상태
        self.pick_at: Optional[int] = None
        self.pick_midi: int = 60
        self.message: str = ""

    # ---------- 공통 ----------
    @property
    def notes(self) -> Optional[List[Note]]:
        r = getattr(self.engine, "result", None)
        return r.notes if r is not None else None

    def _ready(self) -> bool:
        return self.notes is not None and self.engine.state == READY

    def _push(self) -> None:
        self.undo_stack.append(copy.deepcopy(self.notes))
        del self.undo_stack[:-UNDO_LIMIT]

    def _shift(self, start_idx: int, delta_ms: int) -> None:
        for n in self.notes[start_idx:]:
            n.start_ms += delta_ms
        self._fix_total()

    def _fix_total(self) -> None:
        ns = self.notes
        self.engine.result.duration_ms = max((n.start_ms + n.duration_ms for n in ns), default=0)

    def _default_duration(self) -> int:
        ns = self.notes
        return int(statistics.median(n.duration_ms for n in ns)) if ns else 400

    def _note_range(self):
        return getattr(self.engine, "note_range", (21, 108))

    def _candidates(self, midi: int) -> List[int]:
        lo, hi = self._note_range()
        return [m for m in (midi + 1, midi - 1) if lo <= m <= hi]

    def undo(self) -> bool:
        if not self.undo_stack or self.notes is None:
            return False
        self.engine.result.notes[:] = self.undo_stack.pop()
        self._fix_total()
        self.message = "Undo"
        return True

    # ---------- 길이 ----------
    def change_duration(self, idx: int, longer: bool) -> bool:
        if not self._ready() or not (0 <= idx < len(self.notes)):
            return False
        n = self.notes[idx]
        raw_new = n.duration_ms * (STEP if longer else 1 / STEP)
        new = int(round(raw_new))
        if longer:
            if MAX_DUR_MS is not None:
                new = min(MAX_DUR_MS, new)
        else:
            new = max(MIN_DUR_MS, new)
        if new == n.duration_ms:
            return False
        self._push()
        delta = new - n.duration_ms
        n.duration_ms = new
        self._shift(idx + 1, delta)
        self.message = f"#{idx + 1} {n.name} {new} ms"
        return True
    
    # ---------- 삭제 ----------
    def delete(self, idx: int) -> bool:
        if not self._ready() or not (0 <= idx < len(self.notes)):
            return False
        self._push()
        ns = self.notes
        removed = ns.pop(idx)
        if idx < len(ns):                              # 뒤 음들을 빈자리만큼 앞으로
            span = ns[idx].start_ms - removed.start_ms
            self._shift(idx, -span)
        else:
            self._fix_total()
        self.message = f"Deleted {removed.name}"
        return True

    # ---------- 직접 삽입 ----------
    def insert_note(self, at: int, midi: int, duration_ms: Optional[int] = None) -> int:
        """at 인덱스 앞에 음 하나를 넣는다. at == len → 맨 뒤. 넣은 음의 인덱스를 돌려준다."""
        ns = self.notes
        at = max(0, min(len(ns), at))
        dur = duration_ms or self._default_duration()
        self._push()
        if at == 0:
            start = 0
            self._shift(0, dur + GAP_MS)
        else:
            prev = ns[at - 1]
            start = prev.start_ms + prev.duration_ms + GAP_MS
            if at < len(ns):
                self._shift(at, start + dur + GAP_MS - ns[at].start_ms)
        ns.insert(at, Note(midi=midi, midi_float=float(midi), start_ms=start, duration_ms=dur,
                           confidence=1.0, candidates=self._candidates(midi), flags=["manual"]))
        self._fix_total()
        self.message = f"Inserted {midi_to_name(midi)}"
        return at

    # ---------- 직접 고르기 모드 ----------
    # ---------- 직접 고르기 모드 ----------
    def begin_pick(self, at: int) -> bool:
        if not self._ready():
            return False
        ns = self.notes
        at = max(0, min(len(ns), at))
        lo, hi = self._note_range()
        default_midi = 60  # 도4 (C4)
        self.pick_midi = max(lo, min(hi, default_midi))
        self.pick_at = at
        self.message = "Pick: , / . = pitch  Enter = OK  c = cancel"
        self.engine.play_note(self.pick_midi, 300)
        return True

    def pick_move(self, step: int) -> None:
        if self.pick_at is None:
            return
        lo, hi = self._note_range()
        self.pick_midi = max(lo, min(hi, self.pick_midi + step))
        self.engine.play_note(self.pick_midi, 300)

    def pick_confirm(self) -> Optional[int]:
        if self.pick_at is None:
            return None
        idx = self.insert_note(self.pick_at, self.pick_midi)
        self.pick_at = None
        return idx

    def pick_cancel(self) -> None:
        self.pick_at = None
        self.message = "Pick cancelled"

    # ---------- 허밍으로 삽입 ----------
    def begin_hum_insert(self, at: int) -> bool:
        """녹음을 시작한다. 녹음이 끝나 분석되면 update()가 at 위치에 끼워 넣는다."""
        if not self._ready():
            return False
        self._hum_backup = copy.deepcopy(self.notes)
        self._hum_old_result = self.engine.result
        self._hum_at = max(0, min(len(self.notes), at))
        self.engine.toggle_record()
        self.message = f"Humming to insert at #{self._hum_at + 1} ... click mic to stop"
        return True

    @property
    def hum_inserting(self) -> bool:
        return self._hum_backup is not None

    def update(self) -> None:
        """매 프레임 호출. 삽입용 녹음이 끝났으면 결과를 합친다."""
        if self._hum_backup is None:
            return
        st = self.engine.state
        if st == RECORDING or st == "analyzing":
            return
        res = getattr(self.engine, "result", None)
        old, at = self._hum_backup, self._hum_at
        self._hum_backup = None
        if st != READY or res is None or res is self._hum_old_result or not res.notes:
            # 실패/취소 → 원래대로
            if res is None:
                self.engine.result = HummingResult(old, getattr(self.engine, "sample_rate", 22050), 0)
            else:
                res.notes[:] = old
            self.engine.state = READY
            self._fix_total()
            self.message = "Insert cancelled (no notes)"
            return
        new = list(res.notes)              # 복사(아래에서 res.notes를 덮어쓰므로)
        self.undo_stack.append(old)
        del self.undo_stack[:-UNDO_LIMIT]
        offset = 0 if at == 0 else old[at - 1].start_ms + old[at - 1].duration_ms + GAP_MS
        t0 = new[0].start_ms
        for n in new:
            n.start_ms = n.start_ms - t0 + offset
        end = new[-1].start_ms + new[-1].duration_ms + GAP_MS
        tail = old[at:]
        if tail:
            shift = end - tail[0].start_ms
            for n in tail:
                n.start_ms += shift
        res.notes[:] = old[:at] + new + tail
        self._fix_total()
        self.message = f"Inserted {len(new)} notes at #{at + 1}"

    # ---------- 화면 ----------
    def draw(self, frame, view) -> None:
        """view.draw() 뒤에 호출. 고르기 모드 상자와 편집 메시지를 덧그린다."""
        h, w = frame.shape[:2]
        if self.pick_at is not None:
            rects = getattr(view, "_note_rects", [])
            if rects:
                if self.pick_at < len(rects):
                    x = rects[self.pick_at][0] - 6
                else:
                    r = rects[-1]; x = r[0] + r[2] + 6
                y0, y1 = rects[0][1], rects[0][1] + rects[0][3]
            else:
                x, y0, y1 = w // 2, 20, 60
            cv2.line(frame, (x, y0 - 4), (x, y1 + 4), (0, 200, 255), 2)
            txt = f"{midi_to_name(self.pick_midi)}  (,/. pitch  Enter OK  c cancel)"
            cv2.rectangle(frame, (x - 4, y1 + 8), (x + 300, y1 + 36), (30, 30, 30), -1)
            cv2.putText(frame, txt, (x, y1 + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1)
        if self.message:
            cv2.putText(frame, self.message, (10, h - 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 255, 200), 1)
