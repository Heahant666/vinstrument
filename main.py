

import cv2

# 우리가 만든 클래스 가져오기
from camera.camera import Camera
from camera.hand_tracker import HandTracker

def main():
    # 웹캠 객체 생성
    camera = Camera()

    # 손 인식 객체 생성
    tracker = HandTracker()

    try:
        while True:
            # 1. 웹캠에서 영상 한 장 가져오기
            frame = camera.get_frame()

            if frame is None:
                print("카메라 영상을 가져올 수 없습니다.")
                break

            # 2. MediaPipe로 손을 인식하고 검지 좌표 가져오기
            finger_position = tracker.process(frame)

            # 3. 손이 인식되지 않은 경우
            if finger_position is None:
                cv2.putText(
                    frame,
                    "Hand not detected",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 0, 255),
                    2
                )
            else:
                # 검지 좌표 출력
                x, y = finger_position
                print(f"검지 좌표: x={x}, y={y}")

            # 4. 웹캠 영상 화면에 표시
            cv2.imshow("Virtual Instrument", frame)

            # ESC 키를 누르면 프로그램 종료
            if cv2.waitKey(1) & 0xFF == 27:
                break

    finally:
        # 프로그램 종료 시 자원 정리
        camera.release()
        tracker.close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
