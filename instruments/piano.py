import cv2
from humming.model import midi_to_name


class Piano:
    def __init__(self):
        self.x = 50  # 피아노를 그리기 시작할 왼쪽 첫 x좌표 (임의)
        self.y = 150  # 피아노를 그리기 시작할 왼쪽 첫 y좌표 (임의)
        self.width = 800  # 피아노의 너비
        self.height = 200  # 피아노의 높이

        # 현재 표시할 옥타브
        self.octave = 4

        # 한 옥타브의 흰 건반 7개
        self.white_key_count = 7
        self.white_key_width = self.width / 7

        self.black_key_width = self.white_key_width * 0.6
        self.black_key_height = self.height * 0.6

        # 검은 건반 위치
        self.black_key_positions = [0, 1, 3, 4, 5]

        # 옥타브 이동 버튼 위치
        self.prev_button = (15, 300, 85, 350)
        self.next_button = (555, 300, 625, 350)

        # 눌린 건반의 MIDI 번호와 남은 표시 프레임을 저장
        self.highlighted_keys = {}

        self.humming_highlighted_key = None

    # 눌린 건반을 색상으로 표시
    def highlight_notes(self, pressed_notes):

        # 이번에 눌린 모든 건반을 순회
        for midi in pressed_notes:

            # 해당 건반을 3프레임 동안 표시
            self.highlighted_keys[midi] = 3

    # 허밍 재생 음에 맞춰 자동으로 옥타브 변경
    def follow_humming_note(self, midi):

        # 재생 중인 음이 없으면 이동하지 않음
        if midi is None:
            return

        # MIDI 번호에서 옥타브 계산
        target_octave = (midi // 12) - 1

        # 현재 지원하는 옥타브 범위(3~5)로 제한
        target_octave = max(3, min(5, target_octave))

        # 현재 옥타브와 다르면 변경
        if self.octave != target_octave:
            self.octave = target_octave

    # 건반의 색상 결정
    def get_key_color(self, midi, default_color):

        # 손가락으로 누른 건반
        if midi in self.highlighted_keys:
            return (0, 255, 255)  # 노란색

        # 허밍 재생 중인 건반
        if midi == self.humming_highlighted_key:
            return (255, 0, 255)  # 보라색

        # 눌리지 않은 건반은 원래 색상
        return default_color

    # 허밍 재생 중인 음을 표시
    def highlight_humming_note(self, midi):

        # 이전에 표시하던 허밍 건반 초기화
        self.humming_highlighted_key = None

        # 현재 재생 중인 음이 있다면 저장
        if midi is not None:
            self.humming_highlighted_key = midi

    # 옥타브 이동
    def change_octave(self, direction):
        self.octave = max(3, min(5, self.octave + direction))  # 옥타브 범위는 3-5로 제한

    # 마우스 클릭 처리
    def handle_mouse(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:  # 마우스 왼쪽버튼을 누르면
            # 이전 옥타브 버튼의 좌표
            x1, y1, x2, y2 = self.prev_button

            # 누른 영역이 버튼 영역 안에 있다면 옥타브 변경
            if x1 <= x <= x2 and y1 <= y <= y2:
                self.change_octave(-1)

            # 다음 옥타브 버튼
            x1, y1, x2, y2 = self.next_button

            if x1 <= x <= x2 and y1 <= y <= y2:
                self.change_octave(1)

    
    # 건반 그리기
    def draw(self, frame):
        h, w, _ = frame.shape

        # 웹캠 해상도에 맞춰 건반 크기 설정
        self.width = int(w * 0.9)
        self.height = int(h * 0.35)

        # 건반을 화면 가운데 배치
        self.x = (w - self.width) // 2
        self.y = int(h * 0.50)

        self.white_key_width = self.width / 7
        self.black_key_width = self.white_key_width * 0.6
        self.black_key_height = self.height * 0.6

        # MIDI 번호 매핑
        white_notes = [0, 2, 4, 5, 7, 9, 11]

        black_notes = {
            0: 1,   # C#
            1: 3,   # D#
            3: 6,   # F#
            4: 8,   # G#
            5: 10   # A#
        }

        # --------------------------------
        # 1. 흰 건반 그리기
        # --------------------------------
        white_overlay = frame.copy()

        for i in range(7):
            x1 = int(self.x + i * self.white_key_width)
            x2 = int(self.x + (i + 1) * self.white_key_width)

            midi = 12 * (self.octave + 1) + white_notes[i]

            color = self.get_key_color(midi, (255, 255, 255))

            cv2.rectangle(
                white_overlay,
                (x1, self.y),
                (x2, self.y + self.height),
                color,
                -1
            )

        # 흰 건반 반투명 합성
        cv2.addWeighted(white_overlay, 0.35, frame, 0.65, 0, frame)

        # 흰 건반 테두리
        for i in range(7):
            x1 = int(self.x + i * self.white_key_width)
            x2 = int(self.x + (i + 1) * self.white_key_width)

            cv2.rectangle(
                frame,
                (x1, self.y),
                (x2, self.y + self.height),
                (0, 0, 0),
                2
            )

        # --------------------------------
        # 2. 검은 건반 그리기
        # --------------------------------
        black_overlay = frame.copy()

        for i in self.black_key_positions:
            center_x = int(self.x + (i + 1) * self.white_key_width)

            x1 = int(center_x - self.black_key_width / 2)
            x2 = int(center_x + self.black_key_width / 2)

            midi = 12 * (self.octave + 1) + black_notes[i]

            color = self.get_key_color(midi, (0, 0, 0))

            cv2.rectangle(
                black_overlay,
                (x1, self.y),
                (x2, int(self.y + self.black_key_height)),
                color,
                -1
            )

        # 검은 건반은 더 진하게 합성
        cv2.addWeighted(black_overlay, 0.65, frame, 0.35, 0, frame)

        # --------------------------------
        # 3. 이전 버튼
        # --------------------------------
        cv2.rectangle(
            frame,
            self.prev_button[:2],
            self.prev_button[2:],
            (100, 100, 100),
            -1
        )

        cv2.putText(
            frame,
            "<",
            (40, 335),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2
        )

        # --------------------------------
        # 4. 다음 버튼
        # --------------------------------
        cv2.rectangle(
            frame,
            self.next_button[:2],
            self.next_button[2:],
            (100, 100, 100),
            -1
        )

        cv2.putText(
            frame,
            ">",
            (585, 335),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2
        )

        # --------------------------------
        # 5. 옥타브 표시
        # --------------------------------
        cv2.putText(
            frame,
            f"Octave {self.octave}",
            (250, 235),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2
        )

        # --------------------------------
        # 6. 하이라이트 지속 시간 감소
        # --------------------------------
        for midi in list(self.highlighted_keys.keys()):
            self.highlighted_keys[midi] -= 1

            if self.highlighted_keys[midi] <= 0:
                del self.highlighted_keys[midi]

        return frame


    

    def get_key_at(self, x, y):
        # 건반보다 위쪽 100px까지 인식
        detection_top = self.y - 100

        if not (
            self.x <= x <= self.x + self.width
            and detection_top <= y <= self.y + self.height
        ):
            return None
            
        # 반음계에서 각 건반의 위치
        white_notes = [0, 2, 4, 5, 7, 9, 11]

        black_notes = {
            0: 1,  # C#
            1: 3,  # D#
            3: 6,  # F#
            4: 8,  # G#
            5: 10  # A#
        }

        # 1. 검은 건반부터 검사
        for position, semitone in black_notes.items():
            center_x = self.x + (position + 1) * self.white_key_width

            # 화면에 그려진 검은 건반과 동일한 너비로 판정
            hitbox_width = self.black_key_width

            x1 = center_x - hitbox_width / 2
            x2 = center_x + hitbox_width / 2

            y2 = self.y + self.black_key_height

            if x1 <= x <= x2 and detection_top <= y <= y2:
                midi = 12 * (self.octave + 1) + semitone
                return midi
            
        # 2. 검은 건반이 아니면 흰 건반 검사
        index = int((x - self.x) / self.white_key_width)
        index = min(index, 6)

        midi = 12 * (self.octave + 1) + white_notes[index]

        return midi