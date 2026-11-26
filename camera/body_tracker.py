"""사용자 상체 위치 추정. OpenCV에 내장된 얼굴 검출기(Haar cascade)를 쓰므로 추가 다운로드 없음.

얼굴 중심 x ≈ 상체 중심 x 로 본다. 하프 좌/우 배치처럼 '사용자가 화면 어느 쪽에 있나'만 필요한
용도라, 모델 파일을 더 받아야 하는 포즈(어깨) 모델은 쓰지 않는다.
"""
import cv2


class BodyTracker:
    def __init__(self, every_n_frames=3, scale=0.25, smooth=0.3, forget_after=10):
        path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.cascade = cv2.CascadeClassifier(path)
        if self.cascade.empty():
            raise FileNotFoundError(f"얼굴 검출기 파일을 열 수 없습니다: {path}")

        self.every = every_n_frames      # N 프레임마다 한 번만 검출 (속도)
        self.scale = scale               # 검출은 축소한 영상에서 (속도)
        self.smooth = smooth             # 0~1, 클수록 새 값에 빨리 따라감
        self.forget_after = forget_after # 이만큼 연속으로 못 찾으면 '없음'으로

        self._count = 0
        self._miss = 0
        self.center_x = None             # 얼굴 중심 x, 화면 너비 기준 0~1
        self.box = None                  # (x, y, w, h) 원본 프레임 픽셀

    def process(self, frame):
        """매 프레임 호출. {"detected", "center_x"(0~1 또는 None), "box"} 반환. 프레임에 그리지 않는다."""
        self._count += 1
        if self._count % self.every == 0:
            small = cv2.resize(frame, None, fx=self.scale, fy=self.scale)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            faces = self.cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=4, minSize=(24, 24))

            if len(faces):
                x, y, w, h = max(faces, key=lambda f: f[2] * f[3])    # 가장 큰 얼굴 = 가장 가까운 사용자
                cx = (x + w / 2) / small.shape[1]
                self.center_x = cx if self.center_x is None else self.center_x * (1 - self.smooth) + cx * self.smooth
                self.box = tuple(int(v / self.scale) for v in (x, y, w, h))
                self._miss = 0
            else:
                self._miss += 1
                if self._miss >= self.forget_after:
                    self.center_x, self.box = None, None

        return {"detected": self.center_x is not None, "center_x": self.center_x, "box": self.box}

    def draw(self, frame):
        """디버그용: 얼굴 상자 표시. 필요할 때만 main에서 호출."""
        if self.box:
            x, y, w, h = self.box
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 200, 255), 1)
        return frame
