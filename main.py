import cv2
from camera.camera import Camera
from camera.hand_tracker import HandTracker
from instruments.piano import Piano, MIN_MIDI, MAX_MIDI      # ★ 범위 상수는 piano.py 수정 후 생김
from humming.engine import HummingEngine
from humming.view import HummingView
from humming.editor import NoteEditor
from input.piano_input import PianoInput
from audio.piano_player import PianoPlayer

WINDOW = "Virtual Instrument"

# waitKeyEx 방향키 코드: Windows 값 + Linux/Mac 값(65361~65364)을 함께 받는다
LEFT_KEYS = (2424832, 65361)
UP_KEYS = (2490368, 65362)
RIGHT_KEYS = (2555904, 65363)
DOWN_KEYS = (2621440, 65364)


def insert_pos(view, engine, before):
    """삽입 위치: 마우스를 올린 음의 앞/뒤. 띠 밖이면 맨 뒤."""
    total = len(engine.notes)
    if view.hover is None:
        return total
    return view.hover if before else view.hover + 1


def main():
    camera = Camera()
    tracker = HandTracker()
    piano = Piano()
    piano_input = PianoInput()
    player = PianoPlayer()

    # ★ 허밍 후보·텍스트 입력 범위를 건반이 보여 줄 수 있는 범위와 같게 맞춘다
    engine = HummingEngine(min_sec=0, max_sec=15, note_range=(MIN_MIDI, MAX_MIDI))
    editor = NoteEditor(engine)
    view = HummingView(engine, on_add_pick=editor.begin_pick)   # ★ '+' 버튼이 동작하려면 필요

    cv2.namedWindow(WINDOW)

    # 마우스 콜백은 창마다 하나뿐 → 허밍과 피아노 둘에게 넘겨 주는 함수로 묶는다
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

            # ---- 자유 연주: 손가락 누름 → 소리 ----
            pressed_notes = []
            if not piano.animation.is_sliding:
                pressed_notes = piano_input.update(hand_data, piano)
                piano.highlight_notes(pressed_notes)

            for midi in pressed_notes:
                player.play_note(midi)

            playing_index = engine.playing_index()
            if playing_index is not None:
                notes = engine.notes
                midi = notes[playing_index].final_midi
                upcoming = [n.final_midi for n in notes[playing_index + 1 : playing_index + 7]]
            else:
                midi, upcoming = None, []

            piano.follow_humming_note(midi, upcoming)
            piano.highlight_humming_note(midi)


            frame = piano.draw(frame)

            # 허밍 UI는 건반·손 위에 그려야 하므로 둘 다 그린 뒤에
            editor.update()
            view.draw(frame)
            editor.draw(frame, view)
            cv2.imshow(WINDOW, frame)

            raw_key = cv2.waitKeyEx(1)
            if raw_key == -1:                       # 눌린 키 없음
                continue
            key = raw_key & 0xFF
            if key == 27:                           # ESC
                break

            # ---- 직접 고르기(N) 모드 중에는 이 키들만 ----
            if editor.pick_at is not None:
                if raw_key in UP_KEYS or key == ord("."):
                    editor.pick_move(+1)
                elif raw_key in DOWN_KEYS or key == ord(","):
                    editor.pick_move(-1)
                elif key == 13:                     # Enter
                    editor.pick_confirm()
                    view.hover = None
                elif key in (ord("c"), ord("C")):
                    editor.pick_cancel()
                continue

            # ---- 건반 수동 슬라이드 (좌우 방향키, 흰건반 1칸 + 사이 검은건반) ----
            if raw_key in RIGHT_KEYS:
                piano.start_slide(1)
            elif raw_key in LEFT_KEYS:
                piano.start_slide(-1)

            # ---- 허밍 재생·초기화·저장 ----
            elif key == ord(" "):
                engine.toggle_play()
            elif key in (ord("r"), ord("R")):
                engine.reset()
                editor.undo_stack.clear()
                view.hover = None
            elif key in (ord("j"), ord("J")):
                engine.save("recordings/last_result.json")
                engine.message = "Saved recordings/last_result.json"

            # ---- 음 편집 (마우스를 올린 음 기준) ----
            elif raw_key in UP_KEYS and view.hover is not None:
                editor.change_duration(view.hover, longer=True)
            elif raw_key in DOWN_KEYS and view.hover is not None:
                editor.change_duration(view.hover, longer=False)
            elif key in (ord("x"), ord("X")) and view.hover is not None:
                editor.delete(view.hover)
                view.hover = None
            elif key in (ord("z"), ord("Z")):
                editor.undo()
                view.hover = None
            elif key in (ord("i"), ord("I")):      # I = 뒤에, Shift+I = 앞에 허밍으로 삽입
                editor.begin_hum_insert(insert_pos(view, engine, before=(key == ord("I"))))
                view.hover = None
            elif key in (ord("n"), ord("N")):      # N = 뒤에, Shift+N = 앞에 직접 골라 삽입
                editor.begin_pick(insert_pos(view, engine, before=(key == ord("N"))))

    finally:
        engine.stop()
        engine.player.close()
        camera.release()
        tracker.close()
        player.close()
        cv2.destroyAllWindows()



if __name__ == "__main__":
    main()