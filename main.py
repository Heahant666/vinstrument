import cv2
from camera.camera import Camera
from camera.hand_tracker import HandTracker
from instruments.piano import Piano, MIN_MIDI, MAX_MIDI      # ★ 범위 상수는 piano.py 수정 후 생김
from humming.engine import HummingEngine
from humming.view import HummingView
from humming.editor import NoteEditor
from input.piano_input import PianoInput
from audio.piano_player import PianoPlayer
import numpy as np

WINDOW = "Virtual Instrument"

# waitKeyEx 방향키 코드: Windows 값 + Linux/Mac 값(65361~65364)을 함께 받는다
LEFT_KEYS = (2424832, 65361)
UP_KEYS = (2490368, 65362)
RIGHT_KEYS = (2555904, 65363)
DOWN_KEYS = (2621440, 65364)

def select_instrument():

    window = "Select Instrument"

    while True:
        frame = np.zeros((400, 700, 3), dtype=np.uint8)

        cv2.putText(
            frame, "SELECT INSTRUMENT",
            (180, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            1, (255, 255, 255), 2
        )

        cv2.putText(
            frame, "1. Piano",
            (250, 200),
            cv2.FONT_HERSHEY_SIMPLEX,
            1, (255, 255, 255), 2
        )

        cv2.putText(
            frame, "2. Harp",
            (250, 270),
            cv2.FONT_HERSHEY_SIMPLEX,
            1, (255, 255, 255), 2
        )

        cv2.imshow(window, frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("1"):
            cv2.destroyWindow(window)
            return "piano"

        elif key == ord("2"):
            cv2.destroyWindow(window)
            return "harp"

        elif key == ord("q"):
            cv2.destroyAllWindows()
            return None


def insert_pos(view, engine, before):
    """삽입 위치: 마우스를 올린 음의 앞/뒤. 띠 밖이면 맨 뒤."""
    total = len(engine.notes)
    if view.hover is None:
        return total
    return view.hover if before else view.hover + 1

def draw_exit_button(frame):
    """화면 오른쪽 위에 Exit 버튼 표시"""

    h, w, _ = frame.shape

    # 버튼 위치와 크기
    x1 = w - 120
    y1 = 20
    x2 = w - 20
    y2 = 60

    # 버튼 배경
    cv2.rectangle(
        frame,
        (x1, y1),
        (x2, y2),
        (50, 50, 180),
        -1
    )

    # 버튼 테두리
    cv2.rectangle(
        frame,
        (x1, y1),
        (x2, y2),
        (255, 255, 255),
        2
    )

    # 버튼 글자
    cv2.putText(
        frame,
        "EXIT",
        (x1 + 20, y1 + 27),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2
    )

    return (x1, y1, x2, y2)


def main():

    # 악기 선택
    selected_instrument = select_instrument()

    if selected_instrument is None:
        return False

    
    camera = Camera()
    tracker = HandTracker()
    piano = Piano()
    piano_input = PianoInput()

    #고른 악기에 따른 player설정
    if selected_instrument == "piano" :
        player = PianoPlayer() 
    if selected_instrument == "harp":
        print("하프가 선택됨")
        player = PianoPlayer() #하프 구현전까지 임시

    
    # ★ 허밍 후보·텍스트 입력 범위를 건반이 보여 줄 수 있는 범위와 같게 맞춘다
    #사용자가 지정한 player를 engine에 전달
    engine = HummingEngine(player=player, min_sec=0, max_sec=15, note_range=(MIN_MIDI, MAX_MIDI)) 
    print("[DEBUG] Engine에 연결된 플레이어:", type(engine.player).__name__)
    editor = NoteEditor(engine)
    view = HummingView(
        engine,
        on_add_pick=editor.begin_pick,
        on_delete=editor.delete,
        on_undo=editor.undo,
    )

    exit_button_bounds = (0, 0, 0, 0)
    cv2.namedWindow(WINDOW)

    # 마우스 콜백은 창마다 하나뿐 → 허밍과 피아노 둘에게 넘겨 주는 함수로 묶는다
    exit_clicked = False

    def on_mouse(event, x, y, flags, param):
        nonlocal exit_clicked

        view._on_mouse(event, x, y, flags, param)
        piano.handle_mouse(event, x, y, flags, param)

        if event == cv2.EVENT_LBUTTONDOWN:
            x1, y1, x2, y2 = exit_button_bounds

            if x1 <= x <= x2 and y1 <= y <= y2:
                exit_clicked = True

    cv2.setMouseCallback(WINDOW, on_mouse)

    try:
        while True:
            frame = camera.get_frame()
            if frame is None:
                break

            hand_data = tracker.process(frame)

            #선택한 악기에 따라 다른 소리재생 및 ui표시
            if selected_instrument == "piano":

                # ---- 자유 연주: 손가락 누름 → 소리 ----
                pressed_notes = []
                if not piano.animation.is_sliding:
                    pressed_notes = piano_input.update(hand_data, piano)
                    piano.highlight_notes(pressed_notes)

                for midi in pressed_notes:
                    player.play_note(midi)

                # ---- 허밍 재생시 악기 위에 하이라이트 표시 ---- # 

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
            else:
                print("하프ui 출력")
                # ---- 자유 연주: 손가락 누름 → 소리 ----
                pressed_notes = []
                if not piano.animation.is_sliding:
                    pressed_notes = piano_input.update(hand_data, piano)
                    piano.highlight_notes(pressed_notes)

                for midi in pressed_notes:
                    player.play_note(midi)

                # ---- 허밍 재생시 악기 위에 하이라이트 표시 ---- # 

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
            exit_button_bounds = draw_exit_button(frame)
            cv2.imshow(WINDOW, frame)
            

            raw_key = cv2.waitKeyEx(1)

            # EXIT 버튼 클릭 확인
            if exit_clicked:
                exit_clicked = False
                break
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

    return True



if __name__ == "__main__":
    while main():
        pass