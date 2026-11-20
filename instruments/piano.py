
import cv2


class Piano:
    def __init__(self):
        self.x = 50
        self.y = 250
        self.width = 700
        self.height = 200

        # 현재 표시할 옥타브
        self.octave = 4

        # 한 옥타브의 흰 건반 7개
        self.white_key_count = 7
        self.white_key_width = self.width / 7

        self.black_key_width = self.white_key_width * 0.6
        self.black_key_height = self.height * 0.6

        # 검은 건반 위치
        self.black_key_positions = [0, 1, 3, 4, 5]

    # 옥타브 이동
    def change_octave(self, direction):
        self.octave += direction

        # 일단 표시 범위를 1~7옥타브로 제한
        self.octave = max(1, min(7, self.octave))

    # 건반 그리기
    def draw(self, frame):

        h, w, _ = frame.shape

        # 화면 크기에 맞춰 건반 크기 설정
        self.width = int(w * 0.9)
        self.height = int(h * 0.35)

        self.x = (w - self.width) // 2
        self.y = int(h * 0.55)

        self.white_key_width = self.width / 7
        self.black_key_width = self.white_key_width * 0.6
        self.black_key_height = self.height * 0.6

        # 흰 건반
        for i in range(7):
            x1 = int(self.x + i * self.white_key_width)
            x2 = int(self.x + (i + 1) * self.white_key_width)

            cv2.rectangle(
                frame, (x1, self.y),
                (x2, self.y + self.height),
                (255, 255, 255), -1
            )

            cv2.rectangle(
                frame, (x1, self.y),
                (x2, self.y + self.height),
                (0, 0, 0), 2
            )

        # 검은 건반
        for i in self.black_key_positions:
            center_x = int(self.x + (i + 1) * self.white_key_width)

            x1 = int(center_x - self.black_key_width / 2)
            x2 = int(center_x + self.black_key_width / 2)

            cv2.rectangle(
                frame,
                (x1, int(self.y)),
                (x2, int(self.y + self.black_key_height)),
                (20, 20, 20),
                -1
            )

        # 옥타브 표시
        cv2.putText(
            frame,
            f"Octave {self.octave}",
            (self.x, self.y - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2
        )

        return frame
