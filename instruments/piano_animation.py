
import time


class PianoAnimation:

    def __init__(self, duration=0.2):
        # 슬라이드 애니메이션 소요 시간 (초)
        self.duration = duration

        # 애니메이션 실행 상태
        self.is_sliding = False

        # 슬라이드 시작 시각
        self.start_time = 0.0

        # 슬라이드 방향 (1: 오른쪽, -1: 왼쪽)
        self.direction = 0

        # 애니메이션 진행률 (0.0 ~ 1.0)
        self.progress = 0.0

    def start(self, direction):
        # 이미 슬라이드 중이면 새로운 입력 무시
        if self.is_sliding:
            return False

        self.is_sliding = True
        self.start_time = time.perf_counter()
        self.direction = direction
        self.progress = 0.0

        return True

    def update(self):
        # 슬라이드 중이 아니라면 종료
        if not self.is_sliding:
            return False

        # 애니메이션 경과 시간 계산
        elapsed = time.perf_counter() - self.start_time

        # 진행률 계산
        self.progress = min(elapsed / self.duration, 1.0)

        # 애니메이션 완료
        if self.progress >= 1.0:
            self.is_sliding = False
            return True

        return False

    def reset(self):
        # 애니메이션 상태 초기화
        self.is_sliding = False
        self.start_time = 0.0
        self.direction = 0
        self.progress = 0.0

    def get_offset(self, key_width):
        # 슬라이드 중이 아니라면 이동 거리 없음
        if not self.is_sliding:
            return 0

        # 진행률에 따라 건반 이동 거리 계산
        offset = -self.direction * key_width * self.progress

        return offset
