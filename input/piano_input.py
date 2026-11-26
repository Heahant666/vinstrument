class PianoInput:

    def __init__(self):
        # 각 손가락의 동작 상태 저장
        self.finger_states = {}

        # 하강 및 상승 판정 기준
        self.down_threshold = 18
        self.up_threshold = 3
        self.min_gesture = 18

        # 하강 동작을 인정하는 최소 프레임 수
        self.min_down_count = 2

        # 좌우 이동 허용 범위
        # 흰 건반 너비의 45%까지는 같은 건반으로 취급
        self.x_tolerance_ratio = 0.45

    def update(self, hand_data, piano):

        active_fingers = set()
        pressed_notes = []

        for hand in hand_data["hands"]:

            handedness = hand["handedness"]

            for finger_name, finger_data in hand["fingers"].items():

                x, y = finger_data["pixel"]

                # 현재 손의 손목 좌표
                wrist_x, wrist_y = hand["wrist"]

                # 손목을 기준으로 한 손가락 끝의 상대 위치
                relative_y = y - wrist_y
                finger_id = (handedness, finger_name)
                active_fingers.add(finger_id)

                # 현재 손가락이 위치한 건반 확인
                midi = piano.get_key_at(x, y)
    

                # 인식 범위 밖이면 기록 삭제
                if midi is None:
                    self.finger_states.pop(finger_id, None)
                    continue

                # 좌우 이동 허용 범위 계산
                x_tolerance = (
                    piano.white_key_width * self.x_tolerance_ratio
                )

                # 처음 인식된 손가락
                if finger_id not in self.finger_states:

                    self.finger_states[finger_id] = {
                        "state": "ready",
                        "start_x": x,
                        "start_y": relative_y,
                        "last_y": relative_y,
                        "bottom_y": relative_y,
                        "down_count": 0,
                        "up_count": 0,
                        "midi": midi
                    }

                    continue

                data = self.finger_states[finger_id]
            
                # ------------------------------------
                # 건반 변경 확인
                # ------------------------------------

                # 현재 인식된 MIDI 번호가 달라지면
                # 새로운 건반에서 동작 추적을 다시 시작
                if data["midi"] != midi:

                    data.update({
                        "state": "ready",
                        "start_x": x,
                        "start_y": relative_y,
                        "last_y": relative_y,
                        "bottom_y": relative_y,
                        "down_count": 0,
                        "up_count": 0,
                        "midi": midi
                    })

                    continue
                # ------------------------------------
                # 1단계: 아래로 내려가는 동작
                # ------------------------------------

                if data["state"] == "ready":

                    # 가장 아래쪽 위치 갱신
                    data["bottom_y"] = max(
                        data["bottom_y"], relative_y
                    )

                    # 시작 위치에서 얼마나 내려갔는지 계산
                    moved_down = data["bottom_y"] - data["start_y"]

                    # 일정 거리 이상 내려갔다면 상승 대기 상태로 변경
                    if moved_down >= self.down_threshold:
                        data["state"] = "waiting_up"

                # ------------------------------------
                # 2단계: 다시 올라오는 동작
                # ------------------------------------

                # ------------------------------------

                elif data["state"] == "waiting_up":

                    # 가장 아래쪽 위치에서 현재 위치까지 올라온 거리
                    moved_up = data["bottom_y"] - relative_y

                    # 충분히 내려갔다가 일정 거리 이상 올라왔는지 확인
                    if moved_up >= self.up_threshold:

                        pressed_notes.append(data["midi"])

                        print(
                            f"PRESS: {data['midi']} "
                            f"({handedness}, {finger_name})"
                        )

                        # 한 동작에서 중복 입력 방지
                        data["state"] = "waiting_reset"
                # ------------------------------------
                # 3단계: 초기 위치로 돌아오기
                # ------------------------------------

                elif data["state"] == "waiting_reset":

                    if relative_y <= data["start_y"] + 5:

                        data.update({
                            "state": "ready",
                            "start_x": x,
                            "start_y": relative_y,
                            "bottom_y": relative_y,
                            "down_count": 0,
                            "up_count": 0
                        })

                # 다음 프레임과 비교하기 위해 현재 Y좌표 저장
                data["last_y"] = relative_y

        # 현재 프레임에서 사라진 손가락 제거
        for finger_id in list(self.finger_states):

            if finger_id not in active_fingers:
                del self.finger_states[finger_id]

        return pressed_notes
