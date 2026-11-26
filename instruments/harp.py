"""12현 하프 화면 UI.

소리는 내지 않는다. 손가락이 현을 가로지르면 PluckEvent를 만들어
  1) 현 진동 애니메이션·하이라이트를 켜고
  2) add_listener()로 등록된 함수(팀원 오디오 모듈)에 넘기고
  3) pop_events() 큐에도 쌓아 둔다.

좌표계 주의: 이 파일의 "left/right"는 모두 **화면 기준**이다. camera.py가 좌우 반전(거울)을 하므로
MIRROR_MODE=True일 때 화면 오른쪽 = 사용자의 오른손 쪽이다. 사용자 기준 방향이 필요하면 user_side()를 쓴다.
"""
import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, Dict, List, Optional, Tuple

import cv2
import numpy as np

from humming.model import NOTE_NAMES, midi_to_name

# ==================================================
# 설정값
# ==================================================
# 현 12개. 목록의 첫 음 = 가장 바깥(긴 현, 낮은 음), 마지막 = 가장 안쪽(짧은 현, 높은 음)
HARP_NOTES = ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5", "D5", "E5", "F5", "G5"]

# ---- 좌/우 배치 설정 ----
HARP_SIDE = "auto"            # 시작 모드. "auto" = 사용자 상체 반대편 | "left" / "right" = 화면 기준 고정
MIRROR_MODE = True            # camera.py가 좌우 반전하므로 True. 화면에 보이는 그대로 판단하면 된다
SIDE_DEADZONE = 0.08          # 상체가 화면 중앙 ±8% 안이면 판단 보류(현재 배치 유지)
SIDE_HOLD_SEC = 0.6           # 같은 판단이 이 시간 이어져야 배치를 바꿈 (깜빡임 방지)
SIDE_MIN_INTERVAL_SEC = 1.0   # 한 번 바뀐 뒤 최소 이 시간은 유지
SIDE_MODES = ("auto", "left", "right")   # 아이콘 클릭 순서

PLUCK_COOLDOWN_SEC = 0.12   # 같은 손가락이 같은 현을 다시 튕길 수 있는 최소 간격
VIBRATE_SEC = 0.45          # 현 진동 애니메이션 길이
ACTIVE_FINGERS = ("thumb", "index", "middle", "ring")   # 새끼손가락(pinky, 랜드마크 20)은 제외

# 현 색 (BGR). 실제 하프처럼 C=빨강, F=파랑, 나머지는 구분되는 밝은 색
COLOR_C = (70, 70, 235)
COLOR_F = (235, 150, 60)
COLOR_BY_PC = {           # 그 외 음이름별 색 (pitch class)
    2: (235, 235, 235),   # D 흰색
    4: (120, 235, 235),   # E 노랑
    7: (120, 235, 120),   # G 연두
    9: (235, 200, 120),   # A 하늘
    11: (235, 120, 200),  # B 분홍
}
HUMMING_COLOR = (255, 0, 255)    # 허밍 재생 중인 현 (보라색, 피아노와 동일)
PRESSED_COLOR = (0, 255, 255)    # 방금 튕긴 현 (노란색, 피아노와 동일)
FRAME_COLOR = (90, 60, 30)       # 하프 몸체(목·울림판) 색


def note_name_to_midi(name: str) -> int:
    """'C4' → 60, 'F#5' → 78"""
    pc = name[:-1]
    return (int(name[-1]) + 1) * 12 + NOTE_NAMES.index(pc)


def string_color(midi: int) -> Tuple[int, int, int]:
    pc = midi % 12
    if pc == 0:
        return COLOR_C
    if pc == 5:
        return COLOR_F
    return COLOR_BY_PC.get(pc, (200, 200, 200))


# ==================================================
# 데이터
# ==================================================
@dataclass
class HarpString:
    index: int                      # 0 = 가장 바깥(긴 현)
    midi: int
    name: str
    color: Tuple[int, int, int]
    top: Tuple[int, int] = (0, 0)   # 화면 좌표. draw()에서 매 프레임 갱신
    bottom: Tuple[int, int] = (0, 0)
    vibrate_until: float = 0.0      # 이 시각까지 진동 애니메이션
    vibrate_amp: float = 0.0        # 진동 폭(픽셀)
    pressed_until: float = 0.0      # 이 시각까지 '튕김' 색

    def is_vibrating(self, now: float) -> bool:
        return now < self.vibrate_until


@dataclass
class PluckEvent:
    """현이 튕겨졌을 때 오디오 모듈에 넘기는 표준 이벤트"""
    string_index: int
    midi: int
    note_name: str
    finger_id: Tuple[str, str]      # (handedness, finger)  예: ("Right", "index")
    timestamp: float                # time.perf_counter() 값
    velocity: float = 1.0           # 0~1. 손가락이 현을 지난 속도(세기). 플레이어가 무시해도 됨

    def to_dict(self) -> dict:
        return {"string_index": self.string_index, "midi": self.midi, "note_name": self.note_name,
                "finger_id": list(self.finger_id), "timestamp": self.timestamp, "velocity": self.velocity}


# ==================================================
# 손가락 필터 (새끼손가락 제외)
# ==================================================
def active_fingertips(hand_data) -> List[Tuple[Tuple[str, str], Tuple[int, int]]]:
    """hand_tracker 결과에서 엄지·검지·중지·약지 끝점만 [(finger_id, (x, y)), ...]로 돌려준다."""
    out = []
    if not hand_data or not hand_data.get("detected"):
        return out
    for hand in hand_data["hands"]:
        handed = hand["handedness"]
        for finger_name in ACTIVE_FINGERS:
            f = hand["fingers"].get(finger_name)
            if f is None:
                continue
            out.append(((handed, finger_name), tuple(f["pixel"])))
    return out


# ==================================================
# 하프
# ==================================================
class Harp:
    def __init__(self, notes: List[str] = None, side: str = HARP_SIDE):
        names = list(notes or HARP_NOTES)
        self.strings: List[HarpString] = [
            HarpString(i, note_name_to_midi(n), n, string_color(note_name_to_midi(n)))
            for i, n in enumerate(names)
        ]
        self._midi_to_string: Dict[int, HarpString] = {s.midi: s for s in self.strings}

        # 좌/우 배치 (화면 기준)
        self.side_mode = side                      # "auto" / "left" / "right"
        self.screen_side = "right" if side == "auto" else side
        self._side_changed_at = time.perf_counter()
        self._side_vote = None
        self._side_vote_t0 = self._side_changed_at
        self.side_button = None
        # 하프 위치 고정 상태
        self.is_position_locked = False
        self.lock_button = None

        # 허밍·하이라이트
        self.humming_highlighted_key: Optional[int] = None

        # 이벤트 출력
        self._listeners: List[Callable[[PluckEvent], None]] = []
        self.events: Deque[PluckEvent] = deque(maxlen=256)

        # 피아노와 같은 이름으로 두어 main.py가 공통 코드로 다룰 수 있게 함
        self.animation = _NoAnimation()

    # ---------- 공통 인터페이스 (Piano와 같은 이름) ----------
    @property
    def note_range(self) -> Tuple[int, int]:
        """허밍 후보·텍스트 입력 범위를 맞출 때 사용"""
        return self.strings[0].midi, self.strings[-1].midi

    @property
    def midis(self) -> List[int]:
        return [s.midi for s in self.strings]

    def string_for_midi(self, midi: Optional[int]) -> Optional[HarpString]:
        """정확히 그 음의 현. 없으면 None"""
        return None if midi is None else self._midi_to_string.get(midi)

    def nearest_string(self, midi: Optional[int]) -> Optional[HarpString]:
        """반음(C#4 등)처럼 현이 없는 음이면 가장 가까운 현"""
        if midi is None:
            return None
        return min(self.strings, key=lambda s: (abs(s.midi - midi), s.midi))

    def snap_midi(self, midi: int) -> int:
        """하프에 없는 음을 가장 가까운 현의 음으로 바꾼다"""
        return self.nearest_string(midi).midi

    def highlight_notes(self, midis) -> None:
        now = time.perf_counter()
        for m in midis:
            s = self.string_for_midi(m)
            if s:
                s.pressed_until = now + 0.12

    def highlight_humming_note(self, midi: Optional[int]) -> None:
        self.humming_highlighted_key = midi

    def follow_humming_note(self, midi, upcoming=()) -> None:
        """12현이 항상 다 보이므로 슬라이드할 것이 없다 (피아노와 인터페이스만 맞춤)"""
        return

    def handle_mouse(self, event, x, y, flags, param) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:

            # 좌우 배치 버튼
            b = getattr(self, "side_button", None)
            if b and b[0] <= x <= b[2] and b[1] <= y <= b[3]:
                self.cycle_side_mode()
                return

            # 위치 고정 버튼
            b = getattr(self, "lock_button", None)
            if b and b[0] <= x <= b[2] and b[1] <= y <= b[3]:
                self.toggle_position_lock()

    def get_key_at(self, x, y) -> Optional[int]:
        """손끝이 어느 현에 가장 가까운지(12px 안). 피아노의 get_key_at 대응"""
        best, best_d = None, 12.0
        for s in self.strings:
            d = _point_segment_distance((x, y), s.top, s.bottom)
            if d < best_d:
                best, best_d = s.midi, d
        return best

    # ---------- 이벤트 출력 ----------
    def add_listener(self, fn: Callable[[PluckEvent], None]) -> None:
        """팀원 오디오 모듈 연결: harp.add_listener(lambda ev: player.play_note(ev.midi))"""
        self._listeners.append(fn)

    def pop_events(self) -> List[PluckEvent]:
        """콜백 대신 큐로 받고 싶을 때. 쌓인 이벤트를 모두 꺼내 돌려준다"""
        out = list(self.events)
        self.events.clear()
        return out

    def pluck(self, string_index: int, finger_id=("Unknown", "index"), velocity: float = 1.0) -> PluckEvent:
        """현을 튕긴다: 진동 애니메이션 + 이벤트 발행"""
        s = self.strings[string_index]
        now = time.perf_counter()
        s.vibrate_until = now + VIBRATE_SEC
        s.vibrate_amp = 4.0 + 6.0 * max(0.0, min(1.0, velocity))
        s.pressed_until = now + 0.12
        ev = PluckEvent(string_index, s.midi, s.name, tuple(finger_id), now, float(velocity))
        self.events.append(ev)
        for fn in self._listeners:
            fn(ev)
        return ev

    # ---------- 좌/우 배치 ----------
    def _set_side(self, side: str) -> None:
        if side != self.screen_side:
            self.screen_side = side
            self._side_changed_at = time.perf_counter()

    def cycle_side_mode(self) -> None:
        """좌/우 아이콘 클릭: auto → left → right → auto"""
        self.side_mode = SIDE_MODES[
            (SIDE_MODES.index(self.side_mode) + 1) % len(SIDE_MODES)
        ]
        if self.side_mode != "auto":
            self._set_side(self.side_mode)
        self._side_vote = None

    def toggle_position_lock(self):
        """현재 하프 위치 고정/해제"""
        self.is_position_locked = not self.is_position_locked
        self._side_vote = None

    def update_side(self, user_x, frame_width: Optional[int] = None) -> None:
        """
        매 프레임 호출.
        user_x는 화면 기준 사용자 중심 x의 정규화 좌표(0~1).
        기존 호출부와의 호환을 위해 (hand_data, frame_width)도 받는다.
        사용자가 왼쪽에 있으면 하프는 오른쪽, 오른쪽에 있으면 왼쪽에 둔다.
        """
        now = time.perf_counter()
        # 위치 고정 상태에서는 자동 배치 중지
        if self.is_position_locked:
            return

        # 이전 버전 호출부: update_side(hand_data, frame_width)
        if not isinstance(user_x, (int, float)):
            hand_data = user_x
            if not isinstance(frame_width, (int, float)) or frame_width <= 0:
                return
            if not hand_data or not hand_data.get("detected"):
                normalized_x = None
            else:
                centers = []
                for hand in hand_data.get("hands", []):
                    palm = hand.get("palm_center")
                    if palm is not None and len(palm) >= 2:
                        x = float(palm[0])
                    else:
                        fingers = hand.get("fingers", {})
                        xs = [
                            float(f["pixel"][0])
                            for f in fingers.values()
                            if f and f.get("pixel") is not None
                            and len(f["pixel"]) >= 2
                        ]
                        if not xs:
                            continue
                        x = sum(xs) / len(xs)
                    if 0 <= x < frame_width:
                        centers.append(x)
                if centers:
                    normalized_x = (sum(centers) / len(centers)) / float(frame_width)
                else:
                    tips = active_fingertips(hand_data)
                    xs = [
                        float(point[0]) for _, point in tips
                        if point is not None and len(point) >= 2
                        and 0 <= float(point[0]) < frame_width
                    ]
                    normalized_x = (
                        sum(xs) / len(xs) / float(frame_width) if xs else None
                    )
        else:
            normalized_x = float(user_x)

        if self.side_mode != "auto":
            self._set_side(self.side_mode)
            return

        if normalized_x is None:
            self._side_vote = None
            return

        rel = normalized_x - 0.5
        if abs(rel) < SIDE_DEADZONE:
            self._side_vote = None
            return

        want = "left" if rel > 0 else "right"
        if want == self.screen_side:
            self._side_vote = None
            return

        if self._side_vote != want:
            self._side_vote = want
            self._side_vote_t0 = now
            return

        if (now - self._side_vote_t0 >= SIDE_HOLD_SEC
                and now - self._side_changed_at >= SIDE_MIN_INTERVAL_SEC):
            self._set_side(want)
            self._side_vote = None

    def _draw_side_button(self, frame) -> None:
        """화면 오른쪽 아래의 좌/우 배치 전환 버튼을 그린다."""
        h, w = frame.shape[:2]
        size = 36
        x, y = w - 20 - size - 44, h - 54
        self.side_button = (x, y, x + size, y + size)

        cv2.rectangle(frame, (x, y), (x + size - 1, y + size - 1),
                      (40, 40, 40), -1)
        cv2.rectangle(frame, (x, y), (x + size - 1, y + size - 1),
                      (160, 160, 160), 1)
        cy = y + 12
        cv2.arrowedLine(frame, (x + 8, cy), (x + 28, cy),
                        (255, 255, 255), 1, cv2.LINE_AA, tipLength=0.35)
        cv2.arrowedLine(frame, (x + 28, cy + 7), (x + 8, cy + 7),
                        (255, 255, 255), 1, cv2.LINE_AA, tipLength=0.35)
        label = {"auto": "AUTO", "left": "L", "right": "R"}[self.side_mode]
        tw = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.35, 1)[0][0]
        cv2.putText(frame, label, (x + (size - tw) // 2, y + size - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 200, 255), 1,
                    cv2.LINE_AA)

    def _draw_lock_button(self, frame):
        """하프 위치 고정 버튼"""
        h, w = frame.shape[:2]

        size = 36
        x, y = w - 20 - size, h - 54

        self.lock_button = (x, y, x + size, y + size)

        color = (0, 200, 255) if self.is_position_locked else (160, 160, 160)

        cv2.rectangle(
            frame, (x, y), (x + size, y + size),
            (40, 40, 40), -1
        )

        cv2.rectangle(
            frame, (x, y), (x + size, y + size),
            color, 2
            )

        label = "LOCK" if self.is_position_locked else "FREE"

        cv2.putText(
            frame, label,
            (x + 2, y + 23),
            cv2.FONT_HERSHEY_SIMPLEX,
         0.35, color, 1, cv2.LINE_AA
        )

    # ---------- 배치 계산 ----------
    def layout(self, w: int, h: int) -> None:
        """현의 양 끝 좌표를 프레임 크기와 좌/우 쪽에 맞춰 계산한다. draw()가 매 프레임 호출."""
        n = len(self.strings)
        region_w = int(w * 0.42)
        y_bot = h - 80                         # 아래 마이크 아이콘·메시지 줄 위
        y_top = int(h * 0.22)                  # 위 허밍 음 띠 아래
        full_len = y_bot - y_top
        short_len = int(full_len * 0.45)
        lean = int(region_w * 0.12)            # 바깥 현이 위에서 바깥으로 기울어지는 폭(부채꼴)

        if self.screen_side == "right":
            x_outer, x_inner, out_sign = w - 30, w - 30 - region_w, +1
        else:
            x_outer, x_inner, out_sign = 30, 30 + region_w, -1

        for i, s in enumerate(self.strings):
            t = i / (n - 1)                                    # 0 = 바깥, 1 = 안쪽
            bx = int(x_outer + (x_inner - x_outer) * t)
            length = int(full_len - (full_len - short_len) * t)
            tx = int(bx + out_sign * lean * (1 - t))
            s.bottom = (bx, y_bot)
            s.top = (tx, y_bot - length)

    # ---------- 그리기 ----------
    def draw(self, frame):
        h, w = frame.shape[:2]
        self.layout(w, h)
        now = time.perf_counter()

        # 1. 몸체: 목(위쪽 곡선)과 울림판(아래 굵은 선)
        tops = np.array([s.top for s in self.strings], dtype=np.int32)
        bots = np.array([s.bottom for s in self.strings], dtype=np.int32)
        overlay = frame.copy()
        body = np.concatenate([tops, bots[::-1]])
        cv2.fillPoly(overlay, [body], (40, 30, 20))
        cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)
        cv2.polylines(frame, [tops], False, FRAME_COLOR, 10, cv2.LINE_AA)
        cv2.line(frame, tuple(bots[0]), tuple(bots[-1]), FRAME_COLOR, 14, cv2.LINE_AA)

        # 2. 현
        for s in self.strings:
            color, thick = s.color, 2
            if s.midi == self.humming_highlighted_key or (
                self.humming_highlighted_key is not None
                and self.string_for_midi(self.humming_highlighted_key) is None
                and self.nearest_string(self.humming_highlighted_key) is s
            ):
                color, thick = HUMMING_COLOR, 5
            elif now < s.pressed_until:
                color, thick = PRESSED_COLOR, 4

            if s.is_vibrating(now):
                self._draw_vibrating(frame, s, color, thick, now)
            else:
                cv2.line(frame, s.top, s.bottom, color, thick, cv2.LINE_AA)

            # 음이름 라벨 (울림판 아래)
            label = s.name
            tw = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0][0]
            cv2.putText(frame, label, (s.bottom[0] - tw // 2, s.bottom[1] + 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, s.color, 1, cv2.LINE_AA)

        # 3. 안내 글자
        cv2.putText(frame, f"HARP  {self.strings[0].name} - {self.strings[-1].name}",
                    (self.strings[-1].top[0] - 60 if self.screen_side == "right" else 30, int(h * 0.22) - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)
        self._draw_side_button(frame)
        self._draw_lock_button(frame)

        return frame

    @staticmethod
    def _draw_vibrating(frame, s: HarpString, color, thick, now: float) -> None:
        """현을 좌우로 흔들리는 사인 곡선으로 그린다. 시간이 지날수록 폭이 줄어든다"""
        remain = (s.vibrate_until - now) / VIBRATE_SEC          # 1 → 0
        amp = s.vibrate_amp * remain
        phase = now * 60.0                                       # 흔들림 속도
        pts = []
        steps = 24
        for k in range(steps + 1):
            t = k / steps
            x = s.top[0] + (s.bottom[0] - s.top[0]) * t
            y = s.top[1] + (s.bottom[1] - s.top[1]) * t
            x += amp * math.sin(math.pi * t) * math.sin(phase)   # 양 끝은 고정, 가운데가 가장 크게
            pts.append((int(x), int(y)))
        cv2.polylines(frame, [np.array(pts, dtype=np.int32)], False, color, thick, cv2.LINE_AA)


class _NoAnimation:
    """Piano.animation 자리에 두는 빈 객체 (하프는 슬라이드가 없다)"""
    is_sliding = False

    def update(self):
        return False


# ==================================================
# 기하 도우미
# ==================================================
def _cross(o, a, b) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def segments_intersect(p1, p2, q1, q2) -> bool:
    """선분 p1-p2 와 q1-q2 가 만나는지 (끝점이 닿는 경우 포함)"""
    d1, d2 = _cross(q1, q2, p1), _cross(q1, q2, p2)
    d3, d4 = _cross(p1, p2, q1), _cross(p1, p2, q2)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and d1 != 0 and d2 != 0 and d3 != 0 and d4 != 0:
        return True

    # 한 점이 다른 선분 위에 정확히 놓인 경우
    def on_seg(a, b, c):
        return min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= c[1] <= max(a[1], b[1])

    return (d1 == 0 and on_seg(q1, q2, p1)) or (d2 == 0 and on_seg(q1, q2, p2)) or \
           (d3 == 0 and on_seg(p1, p2, q1)) or (d4 == 0 and on_seg(p1, p2, q2))


def _point_segment_distance(p, a, b) -> float:
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


if __name__ == "__main__":
    # 자가 테스트: 카메라 없이 검은 화면에 하프를 그리고, 가짜 손가락이 현을 가로지르게 한다.
    # 실행: python -m instruments.harp   (ESC로 종료)
    from input.harp_input import HarpInput

    harp = Harp()
    harp.add_listener(lambda ev: print(f"PLUCK {ev.note_name:3s} midi={ev.midi} by {ev.finger_id} vel={ev.velocity:.2f}"))
    inp = HarpInput()
    t0 = time.perf_counter()
    while True:
        frame = np.zeros((480, 640, 3), np.uint8)
        t = time.perf_counter() - t0
        harp.layout(640, 480)
        # 가짜 검지: 현들 가운데 높이에서 좌우로 왕복
        x0, x1 = harp.strings[0].bottom[0], harp.strings[-1].bottom[0]
        x = int(x0 + (x1 - x0) * (0.5 + 0.5 * math.sin(t * 1.2)))
        y = (harp.strings[-1].top[1] + harp.strings[0].bottom[1]) // 2
        fake = {"detected": True, "hands": [{"handedness": "Right",
                 "fingers": {"index": {"pixel": (x, y)}, "pinky": {"pixel": (x, y - 40)}}}]}
        inp.update(fake, harp, 640)
        harp.draw(frame)
        cv2.circle(frame, (x, y), 8, (0, 0, 255), -1)
        cv2.imshow("harp test", frame)
        if cv2.waitKey(15) & 0xFF == 27:
            break
    cv2.destroyAllWindows()