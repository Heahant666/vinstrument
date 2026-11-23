"""OpenCV 프레임 위에 허밍 UI를 그린다: 마이크/텍스트 아이콘, 진행 바, 음 띠, 후보 팝업, '+' 삽입 버튼.

main.py의 웹캠 루프에서 매 프레임 view.draw(frame)을 부르고,
창을 만든 뒤 view.attach(창이름) 한 번만 부르면 마우스가 연결된다.
"""
from typing import Callable, List, Optional, Tuple

import cv2

from .engine import HummingEngine, RECORDING, READY
from .model import midi_to_name


Rect = Tuple[int, int, int, int]

WHITE, GRAY, DARK = (255, 255, 255), (160, 160, 160), (40, 40, 40)
RED, GREEN, YELLOW, BLUE = (
    (60, 60, 230),
    (80, 200, 80),
    (0, 200, 255),
    (255, 170, 60),
)


def _inside(r: Rect, x: int, y: int) -> bool:
    return (
        r[0] <= x < r[0] + r[2]
        and r[1] <= y < r[1] + r[3]
    )


class HummingView:
    def __init__(
        self,
        engine: HummingEngine,
        on_add_pick: Optional[Callable[[int], None]] = None,
        on_text_input: Optional[Callable[[str], None]] = None,
    ):
        self.engine = engine
        self.on_add_pick = on_add_pick
        self.on_text_input = on_text_input

        self.mouse = (-1, -1)

        # 클릭 및 드래그 상태
        self._click: Optional[Tuple[int, int]] = None
        self._pending_click: Optional[Tuple[int, int]] = None
        self._dragging_strip = False
        self._drag_moved = False
        self._drag_last_x = 0

        self.hover: Optional[int] = None

        # 화면에 보이는 음표의 실제 인덱스
        self._visible_indices: List[int] = []
        self._note_rects: List[Rect] = []

        # (rect, note_index, midi)
        self._option_rects: List[
            Tuple[Rect, int, int]
        ] = []

        self.mic_rect: Rect = (0, 0, 0, 0)
        self.text_icon_rect: Rect = (0, 0, 0, 0)
        self.add_end_rect: Rect = (0, 0, 0, 0)
        self.add_after_rect: Rect = (0, 0, 0, 0)

        self.left_arrow_rect: Rect = (0, 0, 0, 0)
        self.right_arrow_rect: Rect = (0, 0, 0, 0)

        self.box_w = 56
        self.box_h = 40
        self.strip_y = 24

        # 1ms당 화면 픽셀 수
        # 1000ms 음표는 약 200px
        self.pixels_per_ms = 0.20

        # 짧은 음표도 클릭할 수 있도록 최소 너비 지정
        self.min_box_w = 24

        # 실제 픽셀 단위 가로 스크롤
        self.scroll_offset = 0.0
        self.max_scroll = 0.0

        self._content_left = 20
        self._content_right = 0
        self._viewport_width = 1

    # --------------------------------------------------
    # 마우스
    # --------------------------------------------------

    def attach(self, window_name: str) -> None:
        cv2.setMouseCallback(window_name, self._on_mouse)

    def _on_mouse(self, event, x, y, flags, param):
        self.mouse = (x, y)

        if event == cv2.EVENT_LBUTTONDOWN:
            self._pending_click = (x, y)
            self._click = None
            self._drag_moved = False

            strip_top = self.strip_y - 8
            strip_bottom = self.strip_y + self.box_h + 8

            in_strip = strip_top <= y <= strip_bottom

            # 화살표와 '+' 버튼은 드래그 시작 영역에서 제외
            in_arrow = (
                _inside(self.left_arrow_rect, x, y)
                or _inside(self.right_arrow_rect, x, y)
            )

            in_plus = (
                _inside(self.add_end_rect, x, y)
                or _inside(self.add_after_rect, x, y)
            )

            self._dragging_strip = (
                in_strip and not in_arrow and not in_plus
            )

            self._drag_last_x = x

        elif event == cv2.EVENT_MOUSEMOVE:
            if (
                self._dragging_strip
                and flags & cv2.EVENT_FLAG_LBUTTON
            ):
                dx = x - self._drag_last_x

                if abs(dx) > 0:
                    self.scroll_offset -= dx

                    self.scroll_offset = max(
                        0.0,
                        min(self.scroll_offset, self.max_scroll),
                    )

                    if abs(
                        x - (
                            self._pending_click[0]
                            if self._pending_click else x
                        )
                    ) > 3:
                        self._drag_moved = True
                        self._pending_click = None

                self._drag_last_x = x

        elif event == cv2.EVENT_LBUTTONUP:
            if self._dragging_strip and not self._drag_moved:
                self._click = self._pending_click

            elif not self._dragging_strip:
                self._click = self._pending_click

            self._pending_click = None
            self._dragging_strip = False

    # --------------------------------------------------
    # 전체 화면 그리기
    # --------------------------------------------------

    def draw(self, frame):
        h, w = frame.shape[:2]

        self.engine.update()
        self._handle_click()

        self._draw_mic(frame, h)
        self._draw_text_icon(frame, h)

        if self.engine.state == RECORDING:
            self._draw_progress(frame, w, h)

        if self.engine.state == READY:
            self._draw_notes(frame, w)

        msg_x = 122 if self.engine.state != RECORDING else 70
        cv2.putText(
            frame,
            self.engine.message,
            (msg_x, h - 14),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            WHITE,
            1,
            cv2.LINE_AA,
        )

        return frame

    # --------------------------------------------------
    # 마이크 & 텍스트 입력 아이콘
    # --------------------------------------------------

    def _draw_mic(self, frame, h):
        cx, cy, r = 36, h - 36, 22

        self.mic_rect = (
            cx - r,
            cy - r,
            2 * r,
            2 * r,
        )

        color = RED if self.engine.state == RECORDING else WHITE

        cv2.circle(
            frame,
            (cx, cy),
            r,
            color,
            2,
            cv2.LINE_AA,
        )

        cv2.rectangle(
            frame,
            (cx - 6, cy - 14),
            (cx + 6, cy + 2),
            color,
            -1,
        )

        cv2.line(
            frame,
            (cx, cy + 4),
            (cx, cy + 12),
            color,
            2,
        )

        if self.engine.state == RECORDING:
            lvl = int(self.engine.recorder.level() * 40)

            cv2.rectangle(
                frame,
                (cx + r + 6, cy + 12),
                (cx + r + 12, cy + 12 - lvl),
                GREEN,
                -1,
            )

    def _draw_text_icon(self, frame, h):
        # 녹음 중에는 진행 바와 겹치지 않게 숨김
        if self.engine.state == RECORDING:
            self.text_icon_rect = (0, 0, 0, 0)
            return

        x, y, bw, bh = 68, h - 54, 36, 36
        self.text_icon_rect = (x, y, bw, bh)

        hovered = _inside(self.text_icon_rect, *self.mouse)
        fill = (85, 85, 85) if hovered else DARK
        border = WHITE if hovered else GRAY

        cv2.rectangle(frame, (x, y), (x + bw - 1, y + bh - 1), fill, -1)
        cv2.rectangle(frame, (x, y), (x + bw - 1, y + bh - 1), border, 1)

        # 텍스트(T + 줄) 아이콘 모양
        cv2.line(frame, (x + 8, y + 10), (x + 20, y + 10), WHITE, 2, cv2.LINE_AA)
        cv2.line(frame, (x + 14, y + 10), (x + 14, y + 26), WHITE, 2, cv2.LINE_AA)
        cv2.line(frame, (x + 22, y + 16), (x + 28, y + 16), GRAY, 1, cv2.LINE_AA)
        cv2.line(frame, (x + 22, y + 22), (x + 28, y + 22), GRAY, 1, cv2.LINE_AA)

    @staticmethod
    def prompt_text_dialog() -> Optional[str]:
        import tkinter as tk
        from tkinter import simpledialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            value = simpledialog.askstring(
                "텍스트 음계 입력",
                "음계를 입력하세요 (예: 도,레,미 / 4도,도4 / C4,D4,E4)\n옥타브 생략 시 기본 4옥타브로 생성됩니다:",
                parent=root,
            )
        finally:
            root.destroy()
        return value

    # --------------------------------------------------
    # 녹음 진행 바
    # --------------------------------------------------

    def _draw_progress(self, frame, w, h):
        rec = self.engine.recorder

        frac = min(1.0, rec.elapsed() / rec.max_sec)

        x0, x1, y = 70, w - 20, h - 40

        cv2.rectangle(
            frame,
            (x0, y - 6),
            (x1, y + 6),
            DARK,
            -1,
        )

        cv2.rectangle(
            frame,
            (x0, y - 6),
            (x0 + int((x1 - x0) * frac), y + 6),
            RED,
            -1,
        )

        xm = x0 + int(
            (x1 - x0) * rec.min_sec / rec.max_sec
        )

        cv2.line(
            frame,
            (xm, y - 10),
            (xm, y + 10),
            YELLOW,
            2,
        )

        cv2.putText(
            frame,
            f"{rec.elapsed():.1f} / {rec.max_sec:.0f} s",
            (x1 - 90, y - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            WHITE,
            1,
            cv2.LINE_AA,
        )

    # --------------------------------------------------
    # 음표 너비 계산
    # --------------------------------------------------

    def _calc_note_width(self, duration_ms: int) -> int:
        """
        음표 길이에 비례해 너비 계산.
        긴 음표에 최대 너비 제한을 두지 않는다.
        """
        scaled = int(
            round(duration_ms * self.pixels_per_ms)
        )

        return max(self.min_box_w, scaled)

    # --------------------------------------------------
    # '+' 버튼
    # --------------------------------------------------

    def _draw_plus_box(
        self,
        frame,
        r: Rect,
        label: str = "+",
    ):
        if r[2] <= 0 or r[3] <= 0:
            return

        hovered = _inside(r, *self.mouse)

        fill = BLUE if hovered else (70, 70, 70)

        cv2.rectangle(
            frame,
            (r[0], r[1]),
            (r[0] + r[2] - 1, r[1] + r[3] - 1),
            fill,
            -1,
        )

        cv2.rectangle(
            frame,
            (r[0], r[1]),
            (r[0] + r[2] - 1, r[1] + r[3] - 1),
            WHITE if hovered else GRAY,
            1,
        )

        self._label(frame, label, r)

    # --------------------------------------------------
    # 반투명 좌우 화살표
    # --------------------------------------------------

    def _draw_translucent_arrow(
        self,
        frame,
        r: Rect,
        direction: str,
        hovered: bool,
    ):
        if r[2] <= 0 or r[3] <= 0:
            return

        overlay = frame.copy()

        fill = (
            (110, 110, 110)
            if hovered
            else (45, 45, 45)
        )

        cv2.rectangle(
            overlay,
            (r[0], r[1]),
            (r[0] + r[2] - 1, r[1] + r[3] - 1),
            fill,
            -1,
        )

        alpha = 0.65 if hovered else 0.35

        cv2.addWeighted(
            overlay,
            alpha,
            frame,
            1.0 - alpha,
            0,
            frame,
        )

        color = WHITE if hovered else GRAY

        cx = r[0] + r[2] // 2
        cy = r[1] + r[3] // 2

        # 화살표를 선으로 그림
        if direction == "left":
            pts = [
                (cx + 5, cy - 9),
                (cx - 5, cy),
                (cx + 5, cy + 9),
            ]
        else:
            pts = [
                (cx - 5, cy - 9),
                (cx + 5, cy),
                (cx - 5, cy + 9),
            ]

        cv2.polylines(
            frame,
            [__import__("numpy").array(pts, dtype="int32")],
            False,
            color,
            2,
            cv2.LINE_AA,
        )

    # --------------------------------------------------
    # 음표 띠
    # --------------------------------------------------

    def _draw_notes(self, frame, w):
        notes = self.engine.notes
        playing = self.engine.playing_index()

        self._note_rects = []
        self._option_rects = []
        self._visible_indices = []

        self.add_end_rect = (0, 0, 0, 0)
        self.add_after_rect = (0, 0, 0, 0)

        self.left_arrow_rect = (0, 0, 0, 0)
        self.right_arrow_rect = (0, 0, 0, 0)

        if not notes:
            self.scroll_offset = 0.0
            self.max_scroll = 0.0
            self.hover = None

            self.add_end_rect = (
                20,
                self.strip_y,
                self.box_h,
                self.box_h,
            )

            self._draw_plus_box(
                frame,
                self.add_end_rect,
            )
            return

        margin = 20
        arrow_w = 28
        arrow_gap = 4
        end_btn_w = self.box_h

        # 전체 음표가 차지하는 시간 계산
        total_ms = max(
            n.start_ms + n.duration_ms
            for n in notes
        )

        content_width = total_ms * self.pixels_per_ms

        full_width = w - margin * 2

        scrollable = content_width > full_width

        if scrollable:
            self._content_left = (
                margin + arrow_w + arrow_gap
            )

            self._content_right = (
                w - margin - arrow_w - arrow_gap
            )
        else:
            self._content_left = margin
            self._content_right = w - margin

        self._viewport_width = max(
            1,
            self._content_right - self._content_left,
        )

        self.max_scroll = max(
            0.0,
            content_width - self._viewport_width,
        )

        self.scroll_offset = max(
            0.0,
            min(self.scroll_offset, self.max_scroll),
        )

        # 화살표를 보여줄 조건
        strip_zone = (
            margin,
            self.strip_y - 8,
            w - margin * 2,
            self.box_h + 16,
        )

        near_strip = _inside(
            strip_zone,
            *self.mouse,
        )

        show_nav = (
            scrollable
            and (
                near_strip
                or self._dragging_strip
            )
        )

        # 화면에 표시할 음표 계산
        new_hover = None

        for idx, n in enumerate(notes):
            x1 = int(
                round(
                    self._content_left
                    + n.start_ms * self.pixels_per_ms
                    - self.scroll_offset
                )
            )

            bw = self._calc_note_width(n.duration_ms)
            x2 = x1 + bw

            # 화면 밖 음표 제외
            visible_x1 = max(
                self._content_left,
                x1,
            )

            visible_x2 = min(
                self._content_right,
                x2,
            )

            if visible_x2 <= visible_x1:
                continue

            r = (
                visible_x1,
                self.strip_y,
                visible_x2 - visible_x1,
                self.box_h,
            )

            self._visible_indices.append(idx)
            self._note_rects.append(r)

            if _inside(r, *self.mouse):
                new_hover = idx

        # 기존 팝업 또는 '+' 버튼 위에 마우스가 있으면
        # 기존 hover 상태를 유지
        on_popup = (
            self.hover is not None
            and self.hover in self._visible_indices
            and any(
                _inside(rr, *self.mouse)
                for rr, _, _ in self._option_rects_for(
                    self.hover
                )
            )
        )

        on_after_btn = (
            self.hover is not None
            and self.hover in self._visible_indices
            and _inside(
                self._calc_after_rect(self.hover),
                *self.mouse,
            )
        )

        if new_hover is None and (
            on_popup or on_after_btn
        ):
            new_hover = self.hover

        self.hover = new_hover

        # 음표 그리기
        for idx, r in zip(
            self._visible_indices,
            self._note_rects,
        ):
            n = notes[idx]

            fill = DARK

            if idx == playing:
                fill = GREEN
            elif n.selected is not None:
                fill = BLUE

            cv2.rectangle(
                frame,
                (r[0], r[1]),
                (
                    r[0] + r[2] - 1,
                    r[1] + r[3] - 1,
                ),
                fill,
                -1,
            )

            border = (
                YELLOW
                if n.uncertain
                else GRAY
            )

            cv2.rectangle(
                frame,
                (r[0], r[1]),
                (
                    r[0] + r[2] - 1,
                    r[1] + r[3] - 1,
                ),
                border,
                2 if idx == self.hover else 1,
            )

            # 너무 좁은 박스에는 글자를 표시하지 않음
            if r[2] >= 34:
                self._label(frame, n.name, r)

        # 좌우 화살표
        if show_nav:
            if self.scroll_offset > 0:
                self.left_arrow_rect = (
                    margin,
                    self.strip_y,
                    arrow_w,
                    self.box_h,
                )

                self._draw_translucent_arrow(
                    frame,
                    self.left_arrow_rect,
                    "left",
                    _inside(
                        self.left_arrow_rect,
                        *self.mouse,
                    ),
                )

            if self.scroll_offset < self.max_scroll:
                self.right_arrow_rect = (
                    w - margin - arrow_w,
                    self.strip_y,
                    arrow_w,
                    self.box_h,
                )

                self._draw_translucent_arrow(
                    frame,
                    self.right_arrow_rect,
                    "right",
                    _inside(
                        self.right_arrow_rect,
                        *self.mouse,
                    ),
                )

        # 마지막 음표 뒤에 '+' 버튼 표시
        last = notes[-1]

        last_end_x = int(
            round(
                self._content_left
                + (last.start_ms + last.duration_ms)
                * self.pixels_per_ms
                - self.scroll_offset
            )
        )

        plus_x = last_end_x + 2

        if (
            last_end_x <= self._content_right
            and plus_x + end_btn_w <= self._content_right
        ):
            self.add_end_rect = (
                plus_x,
                self.strip_y,
                end_btn_w,
                self.box_h,
            )

            self._draw_plus_box(
                frame,
                self.add_end_rect,
            )

        # 호버한 음표 바로 뒤에 '+' 및 후보 팝업
        if (
            self.hover is not None
            and self.hover in self._visible_indices
        ):
            candidate = self._calc_after_rect(
                self.hover
            )

            if (
                candidate[2] > 0
                and candidate[0] + candidate[2]
                <= self._content_right
            ):
                self.add_after_rect = candidate

                self._draw_plus_box(
                    frame,
                    self.add_after_rect,
                )

                self._draw_options(
                    frame,
                    self.hover,
                )

    # --------------------------------------------------
    # 음표 위치 계산
    # --------------------------------------------------

    def _vis_pos(self, idx: int) -> int:
        return self._visible_indices.index(idx)

    def _calc_after_rect(self, i: int) -> Rect:
        if i not in self._visible_indices:
            return (0, 0, 0, 0)

        r = self._note_rects[self._vis_pos(i)]

        sw = 22
        sh = 22

        return (
            r[0] + r[2] + 2,
            r[1],
            sw,
            sh,
        )

    # --------------------------------------------------
    # 후보 음표 위치
    # --------------------------------------------------

    def _option_rects_for(
        self,
        i: int,
    ) -> List[Tuple[Rect, int, int]]:
        if i not in self._visible_indices:
            return []

        r = self._note_rects[
            self._vis_pos(i)
        ]

        opts = sorted(
            self.engine.options(i),
            reverse=True,
        )

        out = []

        for k, midi in enumerate(opts):
            rr = (
                r[0],
                r[1] + r[3] + 8 + k * (self.box_h + 4),
                max(r[2] + 14, 54),
                self.box_h,
            )

            out.append((rr, i, midi))

        return out

    def _draw_options(self, frame, i: int):
        self._option_rects = (
            self._option_rects_for(i)
        )

        n = self.engine.notes[i]

        for rr, _, midi in self._option_rects:
            chosen = midi == n.final_midi

            fill = (
                BLUE
                if chosen
                else (70, 70, 70)
            )

            cv2.rectangle(
                frame,
                (rr[0], rr[1]),
                (
                    rr[0] + rr[2] - 1,
                    rr[1] + rr[3] - 1,
                ),
                fill,
                -1,
            )

            cv2.rectangle(
                frame,
                (rr[0], rr[1]),
                (
                    rr[0] + rr[2] - 1,
                    rr[1] + rr[3] - 1,
                ),
                WHITE if _inside(
                    rr,
                    *self.mouse,
                ) else GRAY,
                1,
            )

            tag = (
                midi_to_name(midi)
                + ("*" if midi == n.midi else "")
            )

            self._label(frame, tag, rr)

    # --------------------------------------------------
    # 글자
    # --------------------------------------------------

    def _label(self, frame, text: str, r: Rect):
        scale = 0.5 if r[2] >= 40 else 0.4

        (tw, th), _ = cv2.getTextSize(
            text,
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            1,
        )

        cv2.putText(
            frame,
            text,
            (
                r[0] + (r[2] - tw) // 2,
                r[1] + (r[3] + th) // 2,
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            WHITE,
            1,
            cv2.LINE_AA,
        )

    # --------------------------------------------------
    # 클릭 처리
    # --------------------------------------------------

    def _handle_click(self):
        if self._click is None:
            return

        x, y = self._click
        self._click = None

        # 마이크 클릭
        if _inside(self.mic_rect, x, y):
            self.engine.toggle_record()
            return

        # 텍스트 모드 아이콘 클릭
        if _inside(self.text_icon_rect, x, y):
            text = self.prompt_text_dialog()
            if text and text.strip():
                if callable(self.on_text_input):
                    self.on_text_input(text.strip())
                elif hasattr(self.engine, "set_notes_from_text"):
                    self.engine.set_notes_from_text(text.strip(), auto_play=True)
            return

        if self.engine.state != READY:
            return

        # 왼쪽 화살표
        if _inside(self.left_arrow_rect, x, y):
            self.scroll_offset = max(
                0.0,
                self.scroll_offset
                - self._viewport_width * 0.8,
            )

            self.hover = None
            return

        # 오른쪽 화살표
        if _inside(self.right_arrow_rect, x, y):
            self.scroll_offset = min(
                self.max_scroll,
                self.scroll_offset
                + self._viewport_width * 0.8,
            )

            self.hover = None
            return

        # 호버한 음표 바로 뒤에 '+' 클릭
        if (
            self.hover is not None
            and _inside(self.add_after_rect, x, y)
        ):
            pos = self.hover + 1
            self.hover = None

            if callable(self.on_add_pick):
                self.on_add_pick(pos)

            return

        # 마지막 음표 뒤에 '+' 클릭
        if _inside(self.add_end_rect, x, y):
            pos = len(self.engine.notes)
            self.hover = None

            if callable(self.on_add_pick):
                self.on_add_pick(pos)

            return

        # 후보 음표 선택
        for rr, idx, midi in self._option_rects:
            if _inside(rr, x, y):
                self.engine.select(idx, midi)
                return

        # 음표 클릭 → 해당 음표 미리듣기
        for idx, r in zip(
            self._visible_indices,
            self._note_rects,
        ):
            if _inside(r, x, y):
                note = self.engine.notes[idx]

                self.engine.play_note(
                    note.final_midi,
                    note.duration_ms,
                )

                return