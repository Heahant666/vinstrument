import time


class PianoAnimation:
    """건반 슬라이드 모션.

    창(보이는 7칸)의 논리 위치는 Piano 쪽에서 즉시 바꾸고, 이 객체는 '아직 못 따라온 거리'만
    계산한다. 그래서 1칸·1옥타브·자동 슬라이드가 모두 같은 코드로 움직인다.
    """

    def __init__(self, base_duration=0.18, per_key=0.04, max_duration=0.45):
        self.base_duration = base_duration   # 1칸 이동에 걸리는 기본 시간(초)
        self.per_key = per_key               # 칸이 늘어날 때마다 더해지는 시간
        self.max_duration = max_duration     # 아무리 멀어도 이 시간 안에 끝낸다

        self.is_sliding = False
        self.start_time = 0.0
        self.duration = base_duration
        self.steps = 0        # 이번에 창이 움직인 흰건반 칸 수 (양수 = 높은 음 쪽)
        self.direction = 0    # steps의 부호 (기존 코드 호환용)
        self.progress = 0.0   # 0.0 ~ 1.0 (가속·감속 적용 후)

    def start(self, steps):
        """steps 칸만큼 움직이는 모션을 시작한다. 이미 움직이는 중이거나 0칸이면 무시."""
        if self.is_sliding or steps == 0:
            return False
        self.is_sliding = True
        self.steps = int(steps)
        self.direction = 1 if steps > 0 else -1
        self.duration = min(self.max_duration, self.base_duration + self.per_key * abs(steps))
        self.start_time = time.perf_counter()
        self.progress = 0.0
        return True

    def update(self):
        """매 프레임 호출. 이번 프레임에 모션이 끝났으면 True."""
        if not self.is_sliding:
            return False
        t = min(1.0, (time.perf_counter() - self.start_time) / self.duration)
        self.progress = t * t * (3.0 - 2.0 * t)   # 부드럽게 출발하고 부드럽게 멈춤
        if t >= 1.0:
            self.is_sliding = False
            self.progress = 1.0
            return True
        return False

    def reset(self):
        self.is_sliding = False
        self.start_time = 0.0
        self.steps = 0
        self.direction = 0
        self.progress = 0.0

    def get_offset(self, key_width):
        """건반을 그릴 때 더할 가로 픽셀. 모션 시작 시 옛 위치에서 출발해 0으로 줄어든다."""
        if not self.is_sliding:
            return 0.0
        return self.steps * key_width * (1.0 - self.progress)
