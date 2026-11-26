import cv2
from camera.camera import Camera
from camera.hand_tracker import HandTracker
from camera.body_tracker import BodyTracker
from instruments.piano import Piano, MIN_MIDI, MAX_MIDI
from instruments.harp import Harp
from humming.engine import HummingEngine
from humming.view import HummingView
from humming.editor import NoteEditor
from input.piano_input import PianoInput
from input.harp_input import HarpInput
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


def main():

    # 악기 선택
    selected_instrument = select_instrument()

    # 종료 선택 시 프로그램 종료
    if selected_instrument is None:
        return

    camera = Camera()
    tracker = HandTracker()
    # 하프 좌/우 배치용 상체(얼굴) 위치 검출. 피아노에서는 필요 없으므로 만들지 않는다
    body_tracker = BodyTracker() if selected_instrument == "harp" else None

    # 두 악기 모두 만들어 두고, 고른 쪽만 쓴다
    piano = Piano()
    piano_input = PianoInput()
    harp = Harp()
    harp_input = HarpInput()
    instrument = piano if selected_instrument == "piano" else harp

    # 고른 악기에 따른 player 설정
    if selected_instrument == "piano":
        player = PianoPlayer()
    else:
        print("하프가 선택됨")
        player = PianoPlayer()   # 하프 플레이어 구현 전까지 임시

    # 허밍 후보·텍스트 입력 범위를 악기가 보여 줄 수 있는 범위와 같게 맞춘다
    # (피아노 C3~B5, 하프 C4~G5). Piano에는 note_range 속성이 없으므로 상수로 대신한다
    note_range = getattr(instrument, "note_range", (MIN_MIDI, MAX_MIDI))
    engine = HummingEngine(player=player, min_sec=0, max_sec=15, note_range=note_range)
    print("[DEBUG] Engine에 연결된 플레이어:", type(engine.player).__name__)
    editor = NoteEditor(engine)
    view = HummingView(
        engine,
        on_add_pick=editor.begin_pick,
        on_delete=editor.delete,
        on_undo=editor.undo,
    )

    cv2.namedWindow(WINDOW)

    # 마우스 콜백은 창마다 하나뿐 → 허밍과 악기 둘에게 넘겨 주는 함수로 묶는다
    def on_mouse(event, x, y, flags, param):
        view._on_mouse(event, x, y, flags, param)
        instrument.handle_mouse(event, x, y, flags, param)

    cv2.setMouseCallback(WINDOW, on_mouse)

    try:
        while True:
            frame = camera.get_frame()
            if frame is None:
                break

            # 얼굴 검출은 손 관절을 그리기 전의 깨끗한 프레임에서
            body = body_tracker.process(frame) if body_tracker else None
            hand_data = tracker.process(frame)
            frame_w = frame.shape[1]

            # 지금 허밍이 재생 중이면 그 음(과 다음 음들)을 구한다
            playing_index = engine.playing_index()
            if playing_index is not None:
                notes = engine.notes
                midi = notes[playing_index].final_midi
                upcoming = [n.final_midi for n in notes[playing_index + 1: playing_index + 7]]
            else:
                midi, upcoming = None, []

            if selected_instrument == "piano":

                # ---- 피아노 자유 연주: 손가락 누름 → 소리 ----
                pressed_notes = []
                if not piano.animation.is_sliding:
                    pressed_notes = piano_input.update(hand_data, piano)
                    piano.highlight_notes(pressed_notes)

                for m in pressed_notes:
                    player.play_note(m)

                # ---- 허밍 재생 시 자동 슬라이드 + 보라색 하이라이트 ----
                piano.follow_humming_note(midi, upcoming)
                piano.highlight_humming_note(midi)

                frame = piano.draw(frame)

            else:

                # ---- 하프 자유 연주: 손끝(새끼 제외)이 현을 가로지르면 튕김 ----
                harp.update_side(body["center_x"] if body else None)   # 사용자 상체 반대쪽에 배치
                for ev in harp_input.update(hand_data, harp, frame_w):
                    player.play_note(ev.midi)                 # 하프 플레이어 완성 전까지 임시

                # ---- 허밍 재생 시 하이라이트 (12현이 전부 보이므로 슬라이드 없음) ----
                harp.highlight_humming_note(midi)

                frame = harp.draw(frame)

            # 허밍 UI는 악기·손 위에 그려야 하므로 둘 다 그린 뒤에
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

            # ---- 건반 수동 슬라이드 (좌우 방향키, 피아노에서만 의미 있음) ----
            if raw_key in RIGHT_KEYS:
                if selected_instrument == "piano":
                    piano.start_slide(1)
            elif raw_key in LEFT_KEYS:
                if selected_instrument == "piano":
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
        player.close()          # engine.player와 같은 객체라 한 번만 닫는다
        camera.release()
        tracker.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()