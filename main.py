import cv2
from camera.camera import Camera
from camera.hand_tracker import HandTracker
from instruments.piano import Piano


def main():
    camera = Camera()
    tracker = HandTracker()
    piano = Piano()

    try:
        while True:
            # 웹캠 영상 가져오기
            frame = camera.get_frame()

            

            if frame is None:
                break

            #모든 손가락 좌표 가져오기
            hand_data = tracker.process(frame)

            #피아노 건반 그리기
            piano.draw(frame)

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

            key = cv2.waitKey(1) & 0xFF

            if key == 27:  # ESC
                break

            elif key == 81:  # 왼쪽 방향키
                piano.change_octave(-1)

            elif key == 83:  # 오른쪽 방향키
                piano.change_octave(1)

            

    finally:
        camera.release()
        tracker.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()