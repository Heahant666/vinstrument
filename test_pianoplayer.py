
import time
from audio.piano_player import PianoPlayer


player = PianoPlayer()

try:
    print("C4 재생")
    player.play_note(60)

    time.sleep(0.5)

    print("E4 추가 재생 (화음 테스트)")
    player.play_note(64)

    time.sleep(2)

    print("테스트 종료")

finally:
    player.close()
