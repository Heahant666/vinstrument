
import cv2
import mediapipe as mp
import time
from pathlib import Path


class HandTracker:
    def __init__(self):
        # 모델 파일의 경로 설정
        # 프로젝트/assets/hand_landmarker.task
        model_path = (
            Path(__file__).resolve().parent.parent
            / "assets"
            / "hand_landmarker.task"
        )

        # 모델 파일이 존재하는지 확인
        if not model_path.exists():
            raise FileNotFoundError(
                f"손 인식 모델 파일을 찾을 수 없습니다: {model_path}"
            )

        # MediaPipe Tasks의 기본 설정
        base_options = mp.tasks.BaseOptions(
            model_asset_path=str(model_path)
        )

        # 손 인식 옵션 설정
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=2,  # 최대 2개의 손 인식
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5
        )

        # 손 인식 객체 생성
        self.detector = (
            mp.tasks.vision.HandLandmarker.create_from_options(options)
        )

        # 영상 처리용 시간값
        self.start_time = time.perf_counter()
        self.last_timestamp = -1

    def process(self, frame):
        # OpenCV의 BGR 이미지를 RGB로 변환
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # MediaPipe 이미지 객체 생성
        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb_frame
        )

        # VIDEO 모드에서는 프레임마다 증가하는 시간값이 필요함
        timestamp_ms = int(
            (time.perf_counter() - self.start_time) * 1000
        )

        # 시간값이 중복되지 않도록 보정
        timestamp_ms = max(
            timestamp_ms, self.last_timestamp + 1
        )
        self.last_timestamp = timestamp_ms

        # 손 인식 실행
        results = self.detector.detect_for_video(
            mp_image, timestamp_ms
        )

        # 인식된 손이 없으면 None 반환
        if not results.hand_landmarks:
            return None

        # 첫 번째로 인식된 손의 랜드마크 가져오기
        landmarks = results.hand_landmarks[0]

        h, w, _ = frame.shape

        # 손 관절을 연결하는 선 목록
        connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),
            (0, 5), (5, 6), (6, 7), (7, 8),
            (5, 9), (9, 10), (10, 11), (11, 12),
            (9, 13), (13, 14), (14, 15), (15, 16),
            (13, 17), (17, 18), (18, 19), (19, 20),
            (0, 17)
        ]

        # 랜드마크 좌표를 픽셀 좌표로 변환
        points = []
        for landmark in landmarks:
            x = int(landmark.x * w)
            y = int(landmark.y * h)
            points.append((x, y))

        # 손 관절 연결선 그리기
        for start, end in connections:
            cv2.line(
                frame,
                points[start],
                points[end],
                (255, 0, 0),
                2
            )

        # 21개 관절에 점 표시
        for point in points:
            cv2.circle(frame, point, 5, (0, 255, 0), -1)

        # 검지 끝부분은 8번 랜드마크
        x, y = points[8]

        # 검지 끝부분 강조
        cv2.circle(frame, (x, y), 10, (0, 0, 255), -1)

        # 검지 좌표 표시
        cv2.putText(
            frame,
            f"Index: ({x}, {y})",
            (x + 15, y - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 255),
            2
        )

        # 검지 끝 좌표 반환
        return (x, y)

    def close(self):
        # MediaPipe 사용 종료
        self.detector.close()
