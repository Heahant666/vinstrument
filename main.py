import cv2

from camera.camera import Camera
from camera.hand_tracker import HandTracker


def main():
    camera = Camera()
    tracker = HandTracker()

    try:
        while True:
            # 웹캠 영상 가져오기
            frame = camera.get_frame()

            if frame is None:
                break

            # 모든 손가락 좌표 가져오기
            # hand_data = tracker.process(frame)

            # if hand_data["detected"]:

            #     # 인식된 손을 하나씩 확인
            #     for hand in hand_data["hands"]:

            #         print(f"\n손 종류: {hand['handedness']}")

            #         # 다섯 손가락 좌표 출력
            #         for finger_name, coordinate in hand["fingers"].items():

            #             # 픽셀 좌표
            #             x, y = coordinate["pixel"]

            #             print(
            #                 f"{finger_name}: x={x}, y={y}"
            #             )

            # else:
            #     print("손이 인식되지 않았습니다.")

            # 화면 출력
            cv2.imshow("Virtual Instrument", frame)

            # ESC 키로 종료
            if cv2.waitKey(1) & 0xFF == 27:
                break

    finally:
        camera.release()
        tracker.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()