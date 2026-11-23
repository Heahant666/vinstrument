import cv2
from humming.model import midi_to_name
from instruments.piano_animation import PianoAnimation


class Piano:
    def __init__(self):
        self.x = 50  # 피아노를 그리기 시작할 왼쪽 첫 x좌표 (임의)
        self.y = 150  # 피아노를 그리기 시작할 왼쪽 첫 y좌표 (임의)
        self.width = 800  # 피아노의 너비
        self.height = 200  # 피아노의 높이

        # 현재 표시할 옥타브
        self.octave = 4
        # 현재 건반의 시작 음 (0=C, 1=D, 2=E, 3=F, 4=G, 5=A, 6=B)
        self.start_note = 0

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

        # 건반 슬라이드 애니메이션 객체
        self.animation = PianoAnimation(duration=0.2)

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


    # 건반을 온음계 한 칸씩 이동
    def move_keyboard(self, direction):
        current_note = self.start_note

        if direction == 1:
            # B5를 넘어가려는 경우 이동하지 않음
            if current_note == 0 and self.octave >= 5:
                return

            if current_note == 6:
                self.start_note = 0
                self.octave += 1
            else:
                self.start_note += 1

        elif direction == -1:
            # C3보다 낮아지려는 경우 이동하지 않음
            if current_note == 0 and self.octave <= 3:
                return

            if current_note == 0:
                self.start_note = 6
                self.octave -= 1
            else:
                self.start_note -= 1

    def start_slide(self, direction):
        # 이미 슬라이드 중이면 새로운 입력 무시
        if self.animation.is_sliding:
            return

        # 방향에 맞춰 애니메이션 시작
        self.animation.start(direction)

    def update_animation(self):
        # 애니메이션이 진행 중이 아니라면 아무것도 하지 않음
        if not self.animation.is_sliding:
            return

        # 애니메이션 진행 상태 갱신
        completed = self.animation.update()

        # 애니메이션이 끝났다면 건반 위치 변경
        if completed:
            self.move_keyboard(self.animation.direction)

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

        # 애니메이션 진행 상태 갱신
        self.update_animation()

        # 웹캠 해상도에 맞춰 건반 크기 설정
        self.width = int(w * 0.9)
        self.height = int(h * 0.35)

        # 건반을 화면 가운데 배치
        self.x = (w - self.width) // 2
        self.y = int(h * 0.50)

        self.white_key_width = self.width / 7
        self.black_key_width = self.white_key_width * 0.6
        self.black_key_height = self.height * 0.6

        # 현재 애니메이션 진행률에 따른 이동 거리
        offset = self.animation.get_offset(self.white_key_width)

        # 이동 방향에 따라 화면 밖의 건반도 추가로 그림
        if self.animation.is_sliding:
            if self.animation.direction == 1:
                key_range = range(8)
            else:
                key_range = range(-1, 7)
        else:
            key_range = range(7)

        # MIDI 번호 매핑
        white_notes = [0, 2, 4, 5, 7, 9, 11]

        black_notes = {
            0: 1,
            1: 3,
            3: 6,
            4: 8,
            5: 10
        }

        # 음이름 변환용 배열
        note_names = ["C", "C#", "D", "D#", "E", "F",
                      "F#", "G", "G#", "A", "A#", "B"]

        # --------------------------------
        # 1. 흰 건반 그리기
        # --------------------------------
        white_overlay = frame.copy()

        for i in key_range:
            x1 = int(self.x + i * self.white_key_width + offset)
            x2 = int(self.x + (i + 1) * self.white_key_width + offset)

            note_index = (self.start_note + i) % 7
            octave_offset = (self.start_note + i) // 7

            midi = 12 * (self.octave + octave_offset + 1) + white_notes[note_index]

            color = self.get_key_color(midi, (255, 255, 255))

            cv2.rectangle(
                white_overlay,
                (x1, self.y),
                (x2, self.y + self.height),
                color,
                -1
            )

        cv2.addWeighted(white_overlay, 0.35, frame, 0.65, 0, frame)

        # 흰 건반 테두리
        for i in key_range:
            x1 = int(self.x + i * self.white_key_width + offset)
            x2 = int(self.x + (i + 1) * self.white_key_width + offset)

            cv2.rectangle(
                frame,
                (x1, self.y),
                (x2, self.y + self.height),
                (0, 0, 0),
                2
            )

        # 흰 건반 음이름 표시
        label_overlay = frame.copy()

        for i in key_range:
            # 현재 건반의 음계와 옥타브 계산
            note_index = (self.start_note + i) % 7
            octave_offset = (self.start_note + i) // 7

            midi = 12 * (self.octave + octave_offset + 1) + white_notes[note_index]

            # MIDI 번호를 음이름으로 변환
            note_name = note_names[midi % 12]
            octave_number = (midi // 12) - 1

            label = f"{note_name}{octave_number}"

            # 건반 중앙 아래쪽에 글자 배치
            center_x = int(
                self.x + (i + 0.5) * self.white_key_width + offset
            )

            text_size = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )[0]

            text_x = center_x - text_size[0] // 2
            text_y = self.y + self.height - 15

            cv2.putText(
                label_overlay,
                label,
                (text_x, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (50, 50, 50),
                1,
                cv2.LINE_AA
            )

        # 글자 반투명 합성
        cv2.addWeighted(label_overlay, 0.55, frame, 0.45, 0, frame)

        # --------------------------------
        # 2. 검은 건반 그리기
        # --------------------------------
        black_overlay = frame.copy()

        for i in key_range:
            note_index = (self.start_note + i) % 7
            octave_offset = (self.start_note + i) // 7

            if note_index not in black_notes:
                continue

            midi = 12 * (self.octave + octave_offset + 1) + black_notes[note_index]

            center_x = int(
                self.x + (i + 1) * self.white_key_width + offset
            )

            x1 = int(center_x - self.black_key_width / 2)
            x2 = int(center_x + self.black_key_width / 2)

            color = self.get_key_color(midi, (0, 0, 0))

            cv2.rectangle(
                black_overlay,
                (x1, self.y),
                (x2, int(self.y + self.black_key_height)),
                color,
                -1
            )

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
        # 5. 전체 옥타브 표시
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

        # 검은 건반의 반음 번호
        black_notes = {
            0: 1,
            1: 3,
            3: 6,
            4: 8,
            5: 10
        }

        white_notes = [0, 2, 4, 5, 7, 9, 11]

        # 1. 검은 건반부터 검사
        for i in range(7):
            note_index = (self.start_note + i) % 7
            octave_offset = (self.start_note + i) // 7

            if note_index not in black_notes:
                continue

            center_x = self.x + (i + 1) * self.white_key_width

            x1 = center_x - self.black_key_width / 2
            x2 = center_x + self.black_key_width / 2

            y2 = self.y + self.black_key_height

            if x1 <= x <= x2 and detection_top <= y <= y2:
                midi = (
                    12 * (self.octave + octave_offset + 1)
                    + black_notes[note_index]
                )
                return midi

        # 2. 흰 건반 검사
        index = int((x - self.x) / self.white_key_width)
        index = min(index, 6)

        note_index = (self.start_note + index) % 7
        octave_offset = (self.start_note + index) // 7

        midi = (
            12 * (self.octave + octave_offset + 1)
            + white_notes[note_index]
        )

        return midi