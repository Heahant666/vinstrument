import cv2

class Camera:
    def __init__(self, camera_id=0):
        # 웹캠 연결 (보통 기본 웹캠은 0번)
        self.cap = cv2.VideoCapture(camera_id)

        # 웹캠이 정상적으로 열렸는지 확인
        if not self.cap.isOpened():
            raise RuntimeError("웹캠을 열 수 없습니다.")

    def get_frame(self):
        # 웹캠에서 한 프레임 가져오기
        ret, frame = self.cap.read() # ret : 프레임을 정상적으로 가져왔는지 여부 frame : 실제 영상의 한 프레임

        if not ret:
            return None

        # 좌우 반전 (거울처럼 보이도록)
        frame = cv2.flip(frame, 1)

        return frame

    def release(self):
        # 웹캠 사용 종료
        self.cap.release()