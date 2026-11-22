import cv2
from camera.camera import Camera
from camera.hand_tracker import HandTracker
from instruments.piano import Piano
from humming.engine import HummingEngine
from humming.view import HummingView
from humming.editor import NoteEditor
from input.piano_input import PianoInput

WINDOW = "Virtual Instrument"


def main():
    camera = Camera()
    tracker = HandTracker()
    piano = Piano()
    engine = HummingEngine(min_sec=0, max_sec=15, note_range=(60, 83))
    view = HummingView(engine)
    editor = NoteEditor(engine)
    piano_input = PianoInput()

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

            hand_data = tracker.process(frame)

            pressed_notes = piano_input.update(hand_data, piano)
            piano.highlight_notes(pressed_notes)

            # 눌린 건반의 MIDI 번호에 해당하는 소리 재생
            for midi in pressed_notes:
                engine.play_note(midi)

            # 현재 허밍 재생 중인 음 확인
            playing_index = engine.playing_index()

            if playing_index is not None:
                midi = engine.notes[playing_index].final_midi
            else:
                midi = None

            # 허밍 재생 중인 건반 표시
            piano.highlight_humming_note(midi)


            frame = piano.draw(frame)
            

            # 허밍 UI는 건반·손 위에 그려야 하므로 둘 다 그린 뒤에 배치
            editor.update()
            view.draw(frame)
            editor.draw(frame, view)

            cv2.imshow(WINDOW, frame)

            # waitKey는 루프당 한 번만 호출해야 키 입력이 씹히지 않음
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                break

            # 스페이스바: 허밍 음 재생 / 정지
            if key == ord(" "):
                engine.toggle_play()
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
        engine.player.close()
        #piano_input.close()


if __name__ == "__main__":
    main()


            #     piano.change_octave(1)

            
