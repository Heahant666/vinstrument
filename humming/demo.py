"""허밍 엔진 단독 데모. 웹캠 위에 UI를 띄운다.

실행:  python -m humming.demo
녹음:  마이크 아이콘 클릭 = 녹음 시작/정지(최대 15초)
재생:  SPACE = 전체 재생/정지 · 음 클릭 = 그 음만 듣기
고치기: 음 위에 마우스 = 후보 3개 → 클릭 = 선택
편집(마우스를 올린 음 기준):
        ↑ / ↓ = 길게 / 짧게 · X = 삭제 · Z = 되돌리기
        I = 그 음 뒤에 허밍으로 삽입 (Shift+I = 앞에) · 마우스가 띠 밖이면 맨 뒤
        N = 그 음 뒤에 직접 골라 삽입 (Shift+N = 앞에) → ↑ / ↓ (또는 , / .) 로 음 선택, Enter 확정, C 취소
기타:  R = 초기화 · J = 결과 json 저장 · ESC = 종료
"""
import cv2
import numpy as np

from .engine import HummingEngine
from .view import HummingView
from .editor import NoteEditor

WINDOW = "Virtual Instrument - Humming"
UP_KEYS = (2490368, 65362, 82)
DOWN_KEYS = (2621440, 65364, 84)


def _insert_pos(view, engine, before: bool) -> int:
    """삽입 위치: 마우스를 올린 음의 앞/뒤. 띠 밖이면 맨 뒤."""
    total = len(engine.result.notes) if engine.result else 0
    if view.hover is None:
        return total
    return view.hover if before else view.hover + 1


def main():
    engine = HummingEngine(min_sec=0, max_sec=15)   # 최소 제한 없음, 15초에 자동 종료
    editor = NoteEditor(engine)
    view = HummingView(engine, on_add_pick=editor.begin_pick)

    cap = cv2.VideoCapture(0)
    cv2.namedWindow(WINDOW)
    view.attach(WINDOW)

    while True:
        ret, frame = cap.read()
        if not ret:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)   # 카메라가 없어도 UI는 보이게
        else:
            frame = cv2.flip(frame, 1)

        editor.update()                      # 삽입용 녹음이 끝났으면 결과를 끼워 넣음
        frame = view.draw(frame)
        editor.draw(frame, view)             # 고르기 커서·편집 메시지 덧그리기
        cv2.imshow(WINDOW, frame)

        raw_key = cv2.waitKeyEx(1)
        key = raw_key & 0xFF
        if key == 27:
            break

        # ---- 직접 고르기 모드 중에는 이 키들만 ----
        if editor.pick_at is not None:
            if raw_key in UP_KEYS or key == ord("."):
                editor.pick_move(+1)       # 위쪽 키로 음높이 올리기
            elif raw_key in DOWN_KEYS or key == ord(","):
                editor.pick_move(-1)       # 아래쪽 키로 음높이 내리기
            elif key == 13:                  # Enter
                editor.pick_confirm()
                view.hover = None
            elif key in (ord("c"), ord("C")):
                editor.pick_cancel()
            continue

        if key == ord(" "):
            engine.toggle_play()
        elif key == ord("r"):
            engine.reset()
            editor.undo_stack.clear()
            view.hover = None
        elif key == ord("j"):
            engine.save("recordings/last_result.json")
            engine.message = "Saved recordings/last_result.json"
        # ---- 편집 ----
        elif raw_key in UP_KEYS and view.hover is not None:
            editor.change_duration(view.hover, longer=True)    # 위쪽 키로 길이 늘리기
        elif raw_key in DOWN_KEYS and view.hover is not None:
            editor.change_duration(view.hover, longer=False)   # 아래쪽 키로 길이 줄이기
        elif key in (ord("x"), ord("X")) and view.hover is not None:
            editor.delete(view.hover)
            view.hover = None
        elif key in (ord("z"), ord("Z")):
            editor.undo()
            view.hover = None
        elif key in (ord("i"), ord("I")):
            editor.begin_hum_insert(_insert_pos(view, engine, before=(key == ord("I"))))
            view.hover = None
        elif key in (ord("n"), ord("N")):
            editor.begin_pick(_insert_pos(view, engine, before=(key == ord("N"))))

    engine.stop()
    cap.release()
    cv2.destroyAllWindows()
    print("최종 데이터:", engine.get_payload())


if __name__ == "__main__":
    main()