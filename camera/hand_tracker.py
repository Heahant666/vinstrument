import cv2
import mediapipe as mp
import time
from pathlib import Path


class HandTracker:
    def __init__(self):
        # 모델 파일 경로
        model_path = (
            Path(__file__).resolve().parent.parent
            / "assets"
            / "hand_landmarker.task"
        )

        if not model_path.exists():
            raise FileNotFoundError(
                f"모델 파일을 찾을 수 없습니다: {model_path}"
            )

        # MediaPipe 모델 설정
        base_options = mp.tasks.BaseOptions(
            model_asset_path=str(model_path)
        )

        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5
        )

        self.detector = (
            mp.tasks.vision.HandLandmarker.create_from_options(options)
        )

        self.start_time = time.perf_counter()
        self.last_timestamp = -1

        # 손가락 이름과 각 손가락 끝 랜드마크 번호
        self.finger_tips = {
            "thumb": 4,
            "index": 8,
            "middle": 12,
            "ring": 16,
            "pinky": 20
        }

        # 손 관절을 연결하는 선
        self.connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),
            (0, 5), (5, 6), (6, 7), (7, 8),
            (5, 9), (9, 10), (10, 11), (11, 12),
            (9, 13), (13, 14), (14, 15), (15, 16),
            (13, 17), (17, 18), (18, 19), (19, 20),
            (0, 17)
        ]

    def process(self, frame):
        # 영상 크기 확인
        h, w, _ = frame.shape

        # OpenCV BGR -> MediaPipe RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb_frame
        )

        # VIDEO 모드에 필요한 타임스탬프
        timestamp_ms = int(
            (time.perf_counter() - self.start_time) * 1000
        )

        timestamp_ms = max(
            timestamp_ms, self.last_timestamp + 1
        )
        self.last_timestamp = timestamp_ms

        # 손 인식
        results = self.detector.detect_for_video(
            mp_image, timestamp_ms
        )

        # 기본 반환 데이터
        hand_data = {
            "detected": False,
            "frame_size": {
                "width": w,
                "height": h
            },
            "hands": []
        }

        # 인식된 손이 없는 경우
        if not results.hand_landmarks:
            return hand_data

        # 인식된 모든 손을 순회
        for hand_index, landmarks in enumerate(results.hand_landmarks):

            # 왼손 / 오른손 정보
            handedness = "Unknown"

            if hand_index < len(results.handedness):
                handedness = (
                    results.handedness[hand_index][0].category_name
                )

            # 21개 관절을 픽셀 좌표로 변환
            points = []

            for landmark in landmarks:
                x = int(landmark.x * w)
                y = int(landmark.y * h)
                points.append((x, y))

            # 관절 연결선 그리기
            for start, end in self.connections:
                cv2.line(
                    frame,
                    points[start],
                    points[end],
                    (255, 0, 0),
                    2
                )

            # 모든 관절에 점 표시
            for point in points:
                cv2.circle(
                    frame, point, 4, (0, 255, 0), -1
                )

            # 다섯 손가락의 좌표 저장
            fingers = {}

            for finger_name, landmark_id in self.finger_tips.items():

                landmark = landmarks[landmark_id]
                x, y = points[landmark_id]

                # 픽셀 좌표와 정규화 좌표 모두 저장
                fingers[finger_name] = {
                    "pixel": (x, y),
                    "normalized": (landmark.x, landmark.y)
                }

                # 손가락 끝 강조 표시
                cv2.circle(
                    frame, (x, y), 9, (0, 0, 255), -1
                )

                # 손가락 이름 표시
                cv2.putText(
                    frame,
                    finger_name,
                    (x + 8, y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (0, 0, 255),
                    1
                )

            # 한 손의 데이터 구성
            one_hand = {
                "handedness": handedness,
                "fingers": fingers
            }

            hand_data["hands"].append(one_hand)

        hand_data["detected"] = len(hand_data["hands"]) > 0

        # 모든 손의 좌표 반환
        return hand_data

    def close(self):
        self.detector.close()