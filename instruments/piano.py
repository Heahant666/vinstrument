import cv2


class Piano:
    def __init__(self):
        self.x = 50  # 피아노를 그리기 시작할 왼쪽 첫 x좌표
        self.y = 250  # 피아노를 그리기 시작할 왼쪽 첫 y좌표
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
        self.prev_button = (50, 80, 120, 130)
        self.next_button = (520, 80, 590, 130)

    # 옥타브 이동
    def change_octave(self, direction):
        self.octave = max(4, min(5, self.octave + direction))  # 옥타브 범위는 4-5로 제한

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
        h, w, _ = frame.shape  # 웹캠 해상도의 높이,너비를 가져옴

        # 웹캠 해상도에 맞춰 건반 크기 다시 설정
        self.width = int(w * 0.9)
        self.height = int(h * 0.35)

        # 건반을 화면 가운데에 배치
        self.x = (w - self.width) // 2
        self.y = int(h * 0.55)

        self.white_key_width = self.width / 7
        self.black_key_width = self.white_key_width * 0.6
        self.black_key_height = self.height * 0.6

        # 흰 건반
        for i in range(7):
            x1 = int(self.x + i * self.white_key_width)  # 각 건반의 왼쪽끝 x좌표
            x2 = int(self.x + (i + 1) * self.white_key_width)  # 각 건반의 오른쪽끝 x좌표

            # frame안에 왼쪽위, 오른쪽아래 범위에 흰색으로 색을 채움
            cv2.rectangle(
                frame,
                (x1, self.y),
                (x2, self.y + self.height),
                (255, 255, 255),
                -1,
            )
            # 같은 사각형의 테두리, 2픽셀
            cv2.rectangle(
                frame,
                (x1, self.y),
                (x2, self.y + self.height),
                (0, 0, 0),
                2,
            )

        # 검은 건반
        for i in self.black_key_positions:
            center_x = int(self.x + (i + 1) * self.white_key_width)  # 검은 건반이 위치할 중심좌표

            x1 = int(center_x - self.black_key_width / 2)  # 검은 건반 왼쪽끝
            x2 = int(center_x + self.black_key_width / 2)  # 검은 건반 오른쪽끝

            # 검은 건반 채우기
            cv2.rectangle(
                frame,
                (x1, int(self.y)),
                (x2, int(self.y + self.black_key_height)),
                (20, 20, 20),
                -1,
            )

        # 이전 옥타브 버튼
        cv2.rectangle(
            frame,
            self.prev_button[:2],
            self.prev_button[2:],
            (100, 100, 100),
            -1,
        )

        cv2.putText(
            frame,
            "<",
            (75, 115),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2,
        )

        # 다음 옥타브 버튼
        cv2.rectangle(
            frame,
            self.next_button[:2],
            self.next_button[2:],
            (100, 100, 100),
            -1,
        )

        cv2.putText(
            frame,
            ">",
            (545, 115),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2,
        )

        # 옥타브 표시
        cv2.putText(
            frame,
            f"Octave {self.octave}",
            (250, 115),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2,
        )

        return frame