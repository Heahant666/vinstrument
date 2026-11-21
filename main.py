import cv2

from camera.camera import Camera
from camera.hand_tracker import HandTracker
from instruments.piano import Piano
from humming.engine import HummingEngine            # ★
from humming.view import HummingView                # ★
from humming.editor import NoteEditor               # ★ 9단계 전이면 이 줄과 editor 줄 4개를 뺀다

WINDOW = "Virtual Instrument"


def main():
    camera = Camera()
    tracker = HandTracker()
    piano = Piano()
    engine = HummingEngine(min_sec=0, max_sec=15, note_range=(60, 83))   # ★ 피아노가 보여 주는 옥타브 4~5 범위
    view = HummingView(engine)                                           # ★
    editor = NoteEditor(engine)                                          # ★

    cv2.namedWindow(WINDOW)

    # ★ 마우스 콜백은 창마다 하나뿐 → 허밍과 피아노 둘에게 넘겨 주는 함수로 묶는다
    #   (view.attach(WINDOW)는 부르지 않는다. 부르면 피아노 콜백이 덮여 옥타브 버튼이 안 눌린다)
    def on_mouse(event, x, y, flags, param):
        view._on_mouse(event, x, y, flags, param)       # 허밍: 마이크 아이콘·음 호버·후보 선택
        piano.handle_mouse(event, x, y, flags, param)   # 피아노: < > 옥타브 버튼

    cv2.setMouseCallback(WINDOW, on_mouse)

    try:
        while True:
            frame = camera.get_frame()
            if frame is None:
                break

            # 손 인식 (frame 위에 관절도 그려짐)
            hand_data = tracker.process(frame)

            # 피아노 건반 그리기
            piano.draw(frame)

            # ★ 허밍 UI는 건반·손 위에 그려야 하므로 둘 다 그린 뒤에
            editor.update()                 # 삽입용 녹음이 끝났으면 결과를 끼움
            view.draw(frame)                # 마이크 아이콘·진행 바·음 띠·후보 팝업
            editor.draw(frame, view)        # 직접 삽입 커서·편집 메시지

            cv2.imshow(WINDOW, frame)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                break

            # ★ 허밍 키 처리: humming/demo.py 의 while 안에 있는
            #   `if key == ord(' '):` 부터 그 아래 elif 묶음 전체를 여기에 그대로 붙인다
            #   (SPACE 재생, ] [ 길이, X 삭제, I 허밍 삽입, N 직접 삽입, , . Enter C, Z 되돌리기)

            # 방향키로 전환 (팀원 작업 영역, 그대로 둠)
            # elif key == 81:
            #     piano.change_octave(-1)
            # elif key == 83:
            #     piano.change_octave(1)

    finally:
        engine.stop()                       # ★ 녹음·재생 중이면 정리
        camera.release()
        tracker.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()