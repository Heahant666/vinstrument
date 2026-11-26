import cv2
from humming.model import midi_to_name
from instruments.piano_animation import PianoAnimation

# 흰 건반의 반음 번호 (C D E F G A B)
WHITE_NOTES = [0, 2, 4, 5, 7, 9, 11]
# 흰 건반 인덱스(0=C,1=D,3=F,4=G,5=A) 바로 오른쪽에 있는 검은 건반의 반음 번호
BLACK_NOTES = {0: 1, 1: 3, 3: 6, 4: 8, 5: 10}

# 지원 음역. 지금은 C3~B5. 88키 전체로 넓힐 때는 21, 108로 바꾸면 창 이동·범위 제한이 모두 따라온다
MIN_MIDI, MAX_MIDI = 48, 83
VISIBLE_KEYS = 7            # 한 번에 보이는 흰 건반 수

PRESSED_COLOR = (0, 255, 255)    # 손가락으로 누른 건반 (노란색)
HUMMING_COLOR = (255, 0, 255)    # 허밍 재생 중인 건반 (보라색)
WHITE, BLACK = (255, 255, 255), (0, 0, 0)


class Piano:
    def __init__(self):
        self.x = 50  # 피아노를 그리기 시작할 왼쪽 첫 x좌표 (draw에서 다시 계산)
        self.y = 150  # 피아노를 그리기 시작할 왼쪽 첫 y좌표 (draw에서 다시 계산)
        self.width = 800  # 피아노의 너비
        self.height = 200  # 피아노의 높이

        # 현재 창의 위치 = octave * 7 + start_note (절대 흰건반 번호)
        self.octave = 4
        # 현재 건반의 시작 음 (0=C, 1=D, 2=E, 3=F, 4=G, 5=A, 6=B)
        self.start_note = 0

        self.white_key_count = VISIBLE_KEYS
        self.white_key_width = self.width / VISIBLE_KEYS
        self.black_key_width = self.white_key_width
        self.black_key_height = self.height * 0.6

        # 옥타브 이동 버튼 위치
        self.prev_button = (15, 300, 85, 350)
        self.next_button = (555, 300, 625, 350)

        # 눌린 건반의 MIDI 번호와 남은 표시 프레임을 저장
        self.highlighted_keys = {}
        self.humming_highlighted_key = None

        # 건반 슬라이드 애니메이션 (1칸·1옥타브·자동 슬라이드 공용)
        self.animation = PianoAnimation()

    # --------------------------------------------------
    # 창 위치 계산 (옥타브·시작음 두 변수를 숫자 하나로 다룬다)
    # --------------------------------------------------

    @staticmethod
    def midi_to_white_index(midi):
        """MIDI → (절대 흰건반 번호, 검은건반 여부). 검은 건반은 바로 왼쪽 흰건반 번호를 돌려준다."""
        octave = midi // 12 - 1
        pc = midi % 12
        left = max(i for i, p in enumerate(WHITE_NOTES) if p <= pc)
        return octave * 7 + left, pc not in WHITE_NOTES

    def _span(self, midi):
        """이 음이 '보인다'고 하려면 보여야 하는 흰건반 번호 범위 (검은 건반은 양옆 둘 다)."""
        idx, is_black = self.midi_to_white_index(midi)
        return idx, (idx + 1 if is_black else idx)

    def _limits(self):
        """창의 첫 칸이 될 수 있는 최소·최대 흰건반 번호"""
        lo, _ = self.midi_to_white_index(MIN_MIDI)
        hi, _ = self.midi_to_white_index(MAX_MIDI)
        return lo, hi - (VISIBLE_KEYS - 1)

    def window_start(self):
        """현재 창의 첫 흰건반 번호"""
        return self.octave * 7 + self.start_note

    def _is_visible(self, midi, start=None):
        start = self.window_start() if start is None else start
        first, last = self._span(midi)
        return start <= first and last <= start + VISIBLE_KEYS - 1

    def set_window_start(self, idx):
        """창의 첫 흰건반 번호를 즉시 바꾼다(모션 없음). 창이 항상 MIN_MIDI~MAX_MIDI 안에 들어오게 잘라낸다."""
        lo, hi = self._limits()
        idx = max(lo, min(hi, idx))
        self.octave, self.start_note = divmod(idx, 7)

    def _slide_to(self, idx):
        """창을 idx로 옮기되 건반이 미끄러지는 모션으로 보여 준다. 실제로 움직인 칸 수를 돌려준다."""
        if self.animation.is_sliding:
            return 0
        lo, hi = self._limits()
        idx = max(lo, min(hi, idx))
        steps = idx - self.window_start()
        if steps == 0:
            return 0
        self.octave, self.start_note = divmod(idx, 7)   # 논리 위치는 즉시 바꾸고
        self.animation.start(steps)                      # 그림만 뒤따라온다
        return steps

    def _white_midi(self, i):
        """현재 창에서 i번째 흰건반의 MIDI (슬라이드 중엔 화면 밖 번호도 들어온다)"""
        note_index = (self.start_note + i) % 7
        octave_offset = (self.start_note + i) // 7
        return 12 * (self.octave + octave_offset + 1) + WHITE_NOTES[note_index]

    def _black_midi(self, i):
        """현재 창에서 i번째 흰건반 오른쪽 검은 건반의 MIDI. 없으면 None"""
        note_index = (self.start_note + i) % 7
        if note_index not in BLACK_NOTES:
            return None
        octave_offset = (self.start_note + i) // 7
        return 12 * (self.octave + octave_offset + 1) + BLACK_NOTES[note_index]

    # --------------------------------------------------
    # 하이라이트
    # --------------------------------------------------

    def highlight_notes(self, pressed_notes):
        """눌린 건반을 3프레임 동안 색으로 표시"""
        for midi in pressed_notes:
            self.highlighted_keys[midi] = 3

    def highlight_humming_note(self, midi):
        """허밍 재생 중인 음을 표시 (None이면 해제)"""
        self.humming_highlighted_key = midi

    def get_key_color(self, midi, default_color):
        if midi in self.highlighted_keys:
            return PRESSED_COLOR
        if midi == self.humming_highlighted_key:
            return HUMMING_COLOR
        return default_color

    # --------------------------------------------------
    # 자동 슬라이드
    # --------------------------------------------------

    def _starts_showing(self, midis):
        """주어진 음들이 모두 보이는 창 시작 위치 목록"""
        lo, hi = self._limits()
        first = min(self._span(m)[0] for m in midis)
        last = max(self._span(m)[1] for m in midis)
        return [s for s in range(last - (VISIBLE_KEYS - 1), first + 1) if lo <= s <= hi]

    def follow_humming_note(self, midi, upcoming=()):
        """재생 중인 음(또는 바로 다음 음)이 화면 밖이면 보이는 위치로 미끄러진다.

        upcoming: 이어서 나올 음들의 MIDI 목록. 다음 음이 화면 밖이면 지금 음이 울리는 동안
        미리 움직여 두고, 여러 후보 위치 중 뒤따르는 음이 가장 많이 보이는 곳을 고른다.
        """
        if midi is None or self.animation.is_sliding:
            return
        upcoming = list(upcoming)
        if self._is_visible(midi):
            if not upcoming or self._is_visible(upcoming[0]):
                return
            cands = self._starts_showing([midi, upcoming[0]])   # 지금 음을 놓치지 않으면서 다음 음도
            if not cands:
                return                                           # 둘을 함께 못 보이면 다음 음 차례에 이동
        else:
            cands = self._starts_showing([midi])
            if not cands:
                lo, hi = self._limits()
                cands = [max(lo, min(hi, self._span(midi)[0]))]

        start = self.window_start()

        def score(s):
            shown = 0
            for m in upcoming:                     # 연속으로 보이는 다음 음 개수
                if self._is_visible(m, s):
                    shown += 1
                else:
                    break
            return (shown, -abs(s - start))        # 많이 보일수록, 덜 움직일수록 좋다

        self._slide_to(max(cands, key=score))

    # --------------------------------------------------
    # 수동 이동
    # --------------------------------------------------

    def change_octave(self, direction):
        """화면 화살표 버튼: 한 옥타브(흰건반 7칸) 슬라이드"""
        self._slide_to(self.window_start() + VISIBLE_KEYS * direction)

    def start_slide(self, direction):
        """키보드 방향키: 흰건반 1칸 슬라이드 (사이 검은건반은 함께 따라온다)"""
        self._slide_to(self.window_start() + direction)

    def move_keyboard(self, direction):
        """모션 없이 1칸 이동 (호환용)"""
        self.set_window_start(self.window_start() + direction)

    def update_animation(self):
        self.animation.update()

    # 마우스 클릭 처리
    def handle_mouse(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            x1, y1, x2, y2 = self.prev_button
            if x1 <= x <= x2 and y1 <= y <= y2:
                self.change_octave(-1)

            x1, y1, x2, y2 = self.next_button
            if x1 <= x <= x2 and y1 <= y <= y2:
                self.change_octave(1)

    # --------------------------------------------------
    # 그리기
    # --------------------------------------------------

    def _draw_range(self):
        """그릴 흰건반 인덱스. 슬라이드 중엔 옛 위치에서 넘어오는 건반까지 포함"""
        if not self.animation.is_sliding:
            return range(VISIBLE_KEYS)
        s = self.animation.steps
        return range(min(0, -s) - 1, max(VISIBLE_KEYS, VISIBLE_KEYS - s) + 1)

    @staticmethod
    def _paint_strong(frame, rects, alpha):
        """강조 건반(눌림·허밍)을 진하게 칠하고 같은 색 테두리를 두른다"""
        if not rects:
            return
        overlay = frame.copy()
        for x1, x2, y1, y2, color in rects:
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
        cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)
        for x1, x2, y1, y2, color in rects:
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)

    def draw(self, frame):
        h, w, _ = frame.shape

        # 애니메이션 진행 상태 갱신
        self.animation.update()

        # 웹캠 해상도에 맞춰 건반 크기 설정
        self.width = int(w * 0.9)
        self.height = int(h * 0.10)
        self.x = (w - self.width) // 2
        self.y = int(h * 0.75)

        self.white_key_width = self.width / VISIBLE_KEYS
        self.black_key_width = self.white_key_width * 0.6
        self.black_key_height = self.height

        kw = self.white_key_width
        offset = self.animation.get_offset(kw)
        key_range = self._draw_range()
        left_lim, right_lim = self.x, self.x + self.width
        y_top, y_bot = self.y, self.y + self.height
        y_black = int(self.y + self.black_key_height)

        def clip(x1, x2):
            """건반 영역 밖으로 나간 부분은 잘라낸다 (슬라이드 중 옆으로 흘러나가지 않게)"""
            x1, x2 = max(x1, left_lim), min(x2, right_lim)
            return (x1, x2) if x2 > x1 else None

        def white_bounds(i):
            # 왼쪽에 검은 건반이 있으면 그 절반만큼 공간 확보
            left_gap = (
                self.black_key_width / 2
                if self._black_midi(i - 1) is not None else 0
            )

            # 오른쪽에 검은 건반이 있으면 그 절반만큼 공간 확보
            right_gap = (
                self.black_key_width / 2
                if self._black_midi(i) is not None else 0
            )

            x1 = int(self.x + i * kw + offset + left_gap)
            x2 = int(self.x + (i + 1) * kw + offset - right_gap)

            return x1, x2

        # --------------------------------
        # 1. 흰 건반 (연하게) + 강조 건반 (진하게)
        # --------------------------------
        white_overlay = frame.copy()
        strong = []
        for i in key_range:
            x1, x2 = white_bounds(i)
            c = clip(x1, x2)
            if c is None:
                continue
            color = self.get_key_color(self._white_midi(i), WHITE)
            cv2.rectangle(white_overlay, (c[0], y_top), (c[1], y_bot), WHITE, -1)
            if color != WHITE:
                strong.append((c[0], c[1], y_top, y_bot, color))
        cv2.addWeighted(white_overlay, 0.35, frame, 0.65, 0, frame)
        self._paint_strong(frame, strong, 0.8)

        # 흰 건반 테두리
        for i in key_range:
            x1, x2 = white_bounds(i)
            c = clip(x1, x2)

            if c is None:
                continue

            cv2.rectangle(
                frame,
                (c[0], y_top),
                (c[1], y_bot),
                BLACK,
                1
            )
        # 흰 건반 음이름
        label_overlay = frame.copy()
        for i in key_range:
            center_x = int(self.x + (i + 0.5) * kw + offset)
            if not (left_lim <= center_x <= right_lim):
                continue
            label = midi_to_name(self._white_midi(i))
            tw = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0][0]
            cv2.putText(label_overlay, label, (center_x - tw // 2, y_bot - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (50, 50, 50), 1, cv2.LINE_AA)
        cv2.addWeighted(label_overlay, 0.55, frame, 0.45, 0, frame)

        # --------------------------------
        # 2. 검은 건반
        # --------------------------------
        black_overlay = frame.copy()
        strong = []

        for i in key_range:
            midi = self._black_midi(i)

            if midi is None:
                continue

            center_x = self.x + (i + 1) * kw + offset

            c = clip(
                int(center_x - self.black_key_width / 2),
                int(center_x + self.black_key_width / 2)
            )

            if c is None:
                continue

            color = self.get_key_color(midi, BLACK)

            # 검은 건반을 투명하게 그림
            cv2.rectangle(
                black_overlay,
                (c[0], y_top),
                (c[1], y_bot),
                BLACK,
                -1
            )

            if color != BLACK:
                strong.append(
                    (c[0], c[1], y_top, y_bot, color)
                )

        # 검은 건반 투명도 적용 (흰 건반과 동일하게 0.35)
        cv2.addWeighted(black_overlay, 0.35, frame, 0.65, 0, frame)

        # 눌린 검은 건반 강조
        self._paint_strong(frame, strong, 0.85)

        # --------------------------------
        # 3. 이전 / 다음 버튼
        # --------------------------------
        cv2.rectangle(frame, self.prev_button[:2], self.prev_button[2:], (100, 100, 100), -1)
        cv2.putText(frame, "<", (40, 335), cv2.FONT_HERSHEY_SIMPLEX, 1, WHITE, 2)
        cv2.rectangle(frame, self.next_button[:2], self.next_button[2:], (100, 100, 100), -1)
        cv2.putText(frame, ">", (585, 335), cv2.FONT_HERSHEY_SIMPLEX, 1, WHITE, 2)

        # --------------------------------
        # 4. 현재 보이는 범위 표시 (예: "G4 - F5")
        # --------------------------------
        cv2.putText(frame,
                    f"{midi_to_name(self._white_midi(0))} - {midi_to_name(self._white_midi(VISIBLE_KEYS - 1))}",
                    (250, 235), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # --------------------------------
        # 5. 하이라이트 지속 시간 감소
        # --------------------------------
        for midi in list(self.highlighted_keys.keys()):
            self.highlighted_keys[midi] -= 1
            if self.highlighted_keys[midi] <= 0:
                del self.highlighted_keys[midi]

        return frame

    # --------------------------------------------------
    # 손끝 좌표 → 건반
    # --------------------------------------------------
    def get_key_at(self, x, y):
        detection_top = self.y - 60

        if not (
            self.x <= x <= self.x + self.width
            and detection_top <= y <= self.y + self.height
        ):
            return None

        kw = self.white_key_width

        # 흰 건반 실제 경계
        def white_bounds(i):
            left_gap = (
                self.black_key_width / 2
                if self._black_midi(i - 1) is not None else 0
            )

            right_gap = (
                self.black_key_width / 2
                if self._black_midi(i) is not None else 0
            )

            x1 = int(self.x + i * kw + left_gap)
            x2 = int(self.x + (i + 1) * kw - right_gap)

            return x1, x2

        # 1. 검은 건반 판정
        for i in range(VISIBLE_KEYS):
            midi = self._black_midi(i)

            if midi is None:
                continue

            center_x = self.x + (i + 1) * kw

            x1 = center_x - self.black_key_width / 2
            x2 = center_x + self.black_key_width / 2

            if x1 <= x <= x2:
                return midi

        # 2. 흰 건반 판정
        for i in range(VISIBLE_KEYS):
            x1, x2 = white_bounds(i)

            if x1 <= x <= x2:
                return self._white_midi(i)

        return None