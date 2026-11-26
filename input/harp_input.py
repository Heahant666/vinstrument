"""손끝 이동 선분이 하프 현을 가로지르면 '튕김'으로 판정한다.

PianoInput과 같은 자리(input/)에 두고, main.py에서 매 프레임
    events = harp_input.update(hand_data, harp, frame_width)
를 부른다. 판정에 성공하면 harp.pluck()을 호출해 애니메이션·이벤트가 함께 처리된다.
새끼손가락은 instruments.harp.active_fingertips()가 걸러내므로 여기엔 들어오지 않는다.
"""
import math
import time
from typing import Dict, List, Tuple

from instruments.harp import Harp, PluckEvent, active_fingertips, segments_intersect, PLUCK_COOLDOWN_SEC

MAX_GAP_SEC = 0.15           # 손가락이 이보다 오래 안 보였다가 나타나면 이전 위치를 버린다(점프 오탐 방지)
MAX_JUMP_RATIO = 0.25        # 한 프레임에 화면 너비의 25% 이상 움직였으면 추적 오류로 보고 무시
FULL_VELOCITY_PX_S = 900.0   # 이 속도(픽셀/초) 이상이면 velocity 1.0


class HarpInput:
    def __init__(self, cooldown: float = PLUCK_COOLDOWN_SEC):
        self.cooldown = cooldown
        self._last_pos: Dict[Tuple[str, str], Tuple[Tuple[int, int], float]] = {}   # finger_id → ((x,y), 시각)
        self._last_pluck: Dict[Tuple[Tuple[str, str], int], float] = {}             # (finger_id, 현) → 시각

    def reset(self) -> None:
        self._last_pos.clear()
        self._last_pluck.clear()

    def update(self, hand_data, harp: Harp, frame_width: int = 640) -> List[PluckEvent]:
        now = time.perf_counter()
        events: List[PluckEvent] = []
        seen = set()

        for finger_id, cur in active_fingertips(hand_data):
            seen.add(finger_id)
            prev = self._last_pos.get(finger_id)
            self._last_pos[finger_id] = (cur, now)
            if prev is None:
                continue
            (px, py), pt = prev
            dt = now - pt
            if dt <= 0 or dt > MAX_GAP_SEC:
                continue
            dist = math.hypot(cur[0] - px, cur[1] - py)
            if dist == 0 or dist > frame_width * MAX_JUMP_RATIO:
                continue
            velocity = min(1.0, (dist / dt) / FULL_VELOCITY_PX_S)

            # 이전 위치 → 현재 위치 선분이 가로지른 현을 모두 튕김 (빠르게 쓸면 글리산도)
            for s in harp.strings:
                if not segments_intersect((px, py), cur, s.top, s.bottom):
                    continue
                key = (finger_id, s.index)
                if now - self._last_pluck.get(key, 0.0) < self.cooldown:
                    continue
                self._last_pluck[key] = now
                events.append(harp.pluck(s.index, finger_id, velocity))

        # 사라진 손가락 정리
        for fid in list(self._last_pos):
            if fid not in seen:
                del self._last_pos[fid]
        return events