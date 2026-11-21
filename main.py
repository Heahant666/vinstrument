import cv2
from camera.camera import Camera
from camera.hand_tracker import HandTracker
from instruments.piano import Piano
from humming.engine import HummingEngine
from humming.view import HummingView
from humming.editor import NoteEditor

WINDOW = "Virtual Instrument"


def main():
    camera = Camera()
    tracker = HandTracker()
    piano = Piano()
    engine = HummingEngine(min_sec=0, max_sec=15, note_range=(60, 83))
    view = HummingView(engine)
    editor = NoteEditor(engine)

    cv2.namedWindow(WINDOW)

    # 마우스 콜백은 창마다 하나뿐이므로 허밍과 피아노 둘 다 호출하도록 묶음
    def on_mouse(event, x, y, flags, param):
        view._on_mouse(event, x, y, flags, param)
        piano.handle_mouse(event, x, y, flags, param)

    cv2.setMouseCallback(WINDOW, on_mouse)

    try:
        while True:
            frame = camera.get_frame()
            if frame is None:
                break

            # 손 인식 (frame 위에 관절도 그려짐)
            hand_data = tracker.process(frame)

            # 피아노 건반 그리기 (중복 호출 없이 한 번만 실행)
            piano.draw(frame)

            # 허밍 UI는 건반·손 위에 그려야 하므로 둘 다 그린 뒤에 배치
            editor.update()
            view.draw(frame)
            editor.draw(frame, view)

            cv2.imshow(WINDOW, frame)

            # waitKey는 루프당 한 번만 호출해야 키 입력이 씹히지 않음
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                break

            # TODO: humming/demo.py의 while 루프 안에 있는
            # `if key == ord(' '):` 부터 그 아래 elif 묶음 전체를 여기에 붙여넣기
            # (SPACE 재생, ] [ 길이, X 삭제, I 허밍 삽입, N 직접 삽입, , . Enter C, Z 되돌리기)

            # 방향키로 옥타브 전환
            # elif key == 81:  # 왼쪽 방향키
            #     piano.change_octave(-1)
            # elif key == 83:  # 오른쪽 방향키
            #     piano.change_octave(1)

    finally:
        engine.stop()
        camera.release()
        tracker.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()


            #     piano.change_octave(1)

            
