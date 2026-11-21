"""OpenCV 프레임 위에 허밍 UI를 그린다: 마이크 아이콘, 진행 바, 음 띠, 후보 팝업, '+' 삽입 버튼.

main.py의 웹캠 루프에서 매 프레임 view.draw(frame)을 부르고,
창을 만든 뒤 view.attach(창이름) 한 번만 부르면 마우스가 연결된다.
"""
from typing import Callable, List, Optional, Tuple
import cv2

from .engine import HummingEngine, RECORDING, READY
from .model import midi_to_name

Rect = Tuple[int, int, int, int]   # x, y, w, h

WHITE, GRAY, DARK = (255, 255, 255), (160, 160, 160), (40, 40, 40)
RED, GREEN, YELLOW, BLUE = (60, 60, 230), (80, 200, 80), (0, 200, 255), (255, 170, 60)


def _inside(r: Rect, x: int, y: int) -> bool:
    return r[0] <= x < r[0] + r[2] and r[1] <= y < r[1] + r[3]


class HummingView:
    def __init__(self, engine: HummingEngine, on_add_pick: Optional[Callable[[int], None]] = None):
        self.engine = engine
        self.on_add_pick = on_add_pick   # 인자: 삽입할 인덱스(at)
        self.mouse = (-1, -1)
        self._click: Optional[Tuple[int, int]] = None
        self.hover: Optional[int] = None          # 마우스가 올라간 음 번호
        self._note_rects: List[Rect] = []
        self._option_rects: List[Tuple[Rect, int, int]] = []   # (rect, note_index, midi)
        self.mic_rect: Rect = (0, 0, 0, 0)
        self.add_end_rect: Rect = (0, 0, 0, 0)
        self.add_after_rect: Rect = (0, 0, 0, 0)
        self.box_w, self.box_h, self.strip_y = 46, 40, 24

    # ---- 마우스 ----
    def attach(self, window_name: str) -> None:
        cv2.setMouseCallback(window_name, self._on_mouse)

    def _on_mouse(self, event, x, y, flags, param):
        self.mouse = (x, y)
        if event == cv2.EVENT_LBUTTONDOWN:
            self._click = (x, y)

    # ---- 그리기 ----
    def draw(self, frame):
        h, w = frame.shape[:2]
        self.engine.update()
        self._handle_click()
        self._draw_mic(frame, h)
        if self.engine.state == RECORDING:
            self._draw_progress(frame, w, h)
        if self.engine.state == READY:
            self._draw_notes(frame, w)
        cv2.putText(frame, self.engine.message, (70, h - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.55, WHITE, 1, cv2.LINE_AA)
        return frame

    def _draw_mic(self, frame, h):
        cx, cy, r = 36, h - 36, 22
        self.mic_rect = (cx - r, cy - r, 2 * r, 2 * r)
        color = RED if self.engine.state == RECORDING else WHITE
        cv2.circle(frame, (cx, cy), r, color, 2, cv2.LINE_AA)
        cv2.rectangle(frame, (cx - 6, cy - 14), (cx + 6, cy + 2), color, -1)   # 마이크 머리
        cv2.line(frame, (cx, cy + 4), (cx, cy + 12), color, 2)                # 손잡이
        if self.engine.state == RECORDING:
            lvl = int(self.engine.recorder.level() * 40)
            cv2.rectangle(frame, (cx + r + 6, cy + 12), (cx + r + 12, cy + 12 - lvl), GREEN, -1)

    def _draw_progress(self, frame, w, h):
        rec = self.engine.recorder
        frac = min(1.0, rec.elapsed() / rec.max_sec)
        x0, x1, y = 70, w - 20, h - 40
        cv2.rectangle(frame, (x0, y - 6), (x1, y + 6), DARK, -1)
        cv2.rectangle(frame, (x0, y - 6), (x0 + int((x1 - x0) * frac), y + 6), RED, -1)
        xm = x0 + int((x1 - x0) * rec.min_sec / rec.max_sec)
        cv2.line(frame, (xm, y - 10), (xm, y + 10), YELLOW, 2)
        cv2.putText(frame, f"{rec.elapsed():.1f} / {rec.max_sec:.0f} s", (x1 - 90, y - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, WHITE, 1, cv2.LINE_AA)

    def _draw_plus_box(self, frame, r: Rect, label: str = "+"):
        hovered = _inside(r, *self.mouse)
        fill = BLUE if hovered else (70, 70, 70)
        cv2.rectangle(frame, (r[0], r[1]), (r[0] + r[2], r[1] + r[3]), fill, -1)
        cv2.rectangle(frame, (r[0], r[1]), (r[0] + r[2], r[1] + r[3]), WHITE if hovered else GRAY, 1)
        self._label(frame, label, r)

    def _draw_notes(self, frame, w):
        notes = self.engine.notes
        playing = self.engine.playing_index()
        self._note_rects, self._option_rects = [], []
        self.add_end_rect = (0, 0, 0, 0)
        self.add_after_rect = (0, 0, 0, 0)

        end_btn_w = self.box_h
        if not notes:
            self.add_end_rect = (20, self.strip_y, end_btn_w, self.box_h)
            self._draw_plus_box(frame, self.add_end_rect)
            return

        gap = 6
        avail_w = max(60, w - 46 - end_btn_w)
        bw = min(self.box_w, max(18, (avail_w - gap * len(notes)) // max(1, len(notes))))
        x = 20
        new_hover = None
        for i, n in enumerate(notes):
            r = (x, self.strip_y, bw, self.box_h)
            self._note_rects.append(r)
            if _inside(r, *self.mouse):
                new_hover = i
            x += bw + gap

        # 팝업이나 호버 '+' 버튼 위에 마우스가 있으면 hover 유지
        on_popup = (
            self.hover is not None
            and self.hover < len(self._note_rects)
            and any(_inside(rr, *self.mouse) for rr, _, _ in self._option_rects_for(self.hover))
        )
        on_after_btn = (
            self.hover is not None
            and self.hover < len(self._note_rects)
            and _inside(self._calc_after_rect(self.hover), *self.mouse)
        )
        if new_hover is None and (on_popup or on_after_btn):
            new_hover = self.hover
        self.hover = new_hover

        for i, (n, r) in enumerate(zip(notes, self._note_rects)):
            fill = DARK
            if i == playing:
                fill = GREEN
            elif n.selected is not None:
                fill = BLUE
            cv2.rectangle(frame, (r[0], r[1]), (r[0] + r[2], r[1] + r[3]), fill, -1)
            border = YELLOW if n.uncertain else GRAY
            cv2.rectangle(frame, (r[0], r[1]), (r[0] + r[2], r[1] + r[3]), border, 2 if i == self.hover else 1)
            self._label(frame, n.name, r)

        # 음 띠 맨 뒤 '+' 버튼
        self.add_end_rect = (x + 2, self.strip_y, end_btn_w, self.box_h)
        self._draw_plus_box(frame, self.add_end_rect)

        # 호버한 음 바로 뒤에 넣는 작은 '+' 버튼 + 후보 3개 팝업
        if self.hover is not None and self.hover < len(self._note_rects):
            self.add_after_rect = self._calc_after_rect(self.hover)
            self._draw_plus_box(frame, self.add_after_rect)
            self._draw_options(frame, self.hover)

    def _calc_after_rect(self, i: int) -> Rect:
        r = self._note_rects[i]
        sw = 22
        sh = 22
        return (r[0] + r[2] + 2, r[1], sw, sh)

    def _option_rects_for(self, i: int) -> List[Tuple[Rect, int, int]]:
        r = self._note_rects[i]
        opts = sorted(self.engine.options(i), reverse=True)        # 높은 음이 위로
        out = []
        for k, midi in enumerate(opts):
            rr = (r[0], r[1] + r[3] + 8 + k * (self.box_h + 4), r[2] + 14, self.box_h)
            out.append((rr, i, midi))
        return out

    def _draw_options(self, frame, i: int):
        self._option_rects = self._option_rects_for(i)
        n = self.engine.notes[i]
        for rr, _, midi in self._option_rects:
            chosen = midi == n.final_midi
            fill = BLUE if chosen else (70, 70, 70)
            cv2.rectangle(frame, (rr[0], rr[1]), (rr[0] + rr[2], rr[1] + rr[3]), fill, -1)
            cv2.rectangle(frame, (rr[0], rr[1]), (rr[0] + rr[2], rr[1] + rr[3]), WHITE if _inside(rr, *self.mouse) else GRAY, 1)
            tag = midi_to_name(midi) + ("*" if midi == n.midi else "")
            self._label(frame, tag, rr)

    def _label(self, frame, text: str, r: Rect):
        scale = 0.5 if r[2] >= 40 else 0.4
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
        cv2.putText(frame, text, (r[0] + (r[2] - tw) // 2, r[1] + (r[3] + th) // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, scale, WHITE, 1, cv2.LINE_AA)

    # ---- 클릭 처리 ----
    def _handle_click(self):
        if self._click is None:
            return
        x, y = self._click
        self._click = None

        if _inside(self.mic_rect, x, y):
            self.engine.toggle_record()
            return
        if self.engine.state != READY:
            return

        # 호버한 음 바로 뒤에 '+' 클릭
        if self.hover is not None and _inside(self.add_after_rect, x, y):
            pos = self.hover + 1
            self.hover = None
            if callable(self.on_add_pick):
                self.on_add_pick(pos)
            return

        # 음 띠 맨 뒤 '+' 클릭
        if _inside(self.add_end_rect, x, y):
            pos = len(self.engine.notes)
            self.hover = None
            if callable(self.on_add_pick):
                self.on_add_pick(pos)
            return

        for rr, idx, midi in self._option_rects:
            if _inside(rr, x, y):
                self.engine.select(idx, midi)
                return
        for idx, r in enumerate(self._note_rects):
            if _inside(r, x, y):
                self.engine.play_note(self.engine.notes[idx].final_midi, self.engine.notes[idx].duration_ms)
                return