
import numpy as np
import sounddevice as sd
import threading


class PianoPlayer:

    def __init__(self, sr=44100):
        self.sr = sr

        # 현재 재생 중인 음파 목록
        # (sound, position) 형태로 저장
        self._active_notes = []
        # 허밍 결과 전체 재생에 필요한 상태
        self._sequence_notes = []       # 재생할 Note 객체 목록
        self._sequence_audio = np.zeros(0, dtype=np.float32)  # 전체 재생 음파
        self._sequence_position = 0     # 현재 재생 위치(샘플 단위)
        self._sequence_playing = False  # 재생 중인지
        self._sequence_paused = False   # 일시정지 상태인지

        # 여러 스레드의 동시 접근 방지
        self._lock = threading.Lock()

        # 지속적인 오디오 출력 스트림
        self._stream = sd.OutputStream(
            samplerate=self.sr,
            channels=1,
            dtype="float32",
            callback=self._audio_callback
        )

        self._stream.start()

    # MIDI 번호를 주파수로 변환
    def midi_to_frequency(self, midi):
        return 440.0 * (2 ** ((midi - 69) / 12))

    # TonePlayer의 tone()을 참고한 음파 생성
    def tone(self, midi, duration_ms):

        # 재생할 샘플 개수
        n = int(self.sr * duration_ms / 1000)

        # 시간 배열
        t = np.arange(n) / self.sr

        # MIDI 번호를 주파수로 변환
        frequency = self.midi_to_frequency(midi)

        # 기본 음파 생성
        sound = np.zeros(n)

        # 기본음과 배음 3개 합성
        harmonics = (
            (1, 1.0),
            (2, 0.5),
            (3, 0.25),
            (4, 0.12)
        )

        for k, amp in harmonics:
            sound += amp * np.sin(
                2 * np.pi * frequency * k * t
            )

        # 지수 감쇠와 시작 부분 페이드 인
        envelope = (
            np.exp(-3.0 * t)
            * np.minimum(1.0, t / 0.01)
        )

        sound *= envelope

        # 최종 음량
        sound *= 0.3

        return sound.astype(np.float32)

    # 여러 음을 실제 재생 시간에 맞춰 하나의 음파로 합성
    def render(self, notes):

        if not notes:
            return np.zeros(0, dtype=np.float32)

        # 마지막 음이 끝나는 시점 계산 (+ 여운 300ms)
        total_ms = max(
            note.start_ms + max(note.duration_ms, 150) + 300
            for note in notes
        )

        # 전체 음파 버퍼 생성
        audio = np.zeros(
            int(self.sr * total_ms / 1000),
            dtype=np.float32
        )

        # 각 음을 시작 시간에 맞춰 배치
        for note in notes:

            start = int(self.sr * note.start_ms / 1000)

            sound = self.tone(
                note.final_midi,
                max(note.duration_ms, 150) + 300
            )

            # 전체 버퍼 범위를 초과하지 않도록 길이 제한
            sound = sound[:len(audio) - start]

            # 해당 위치에 음파 합성
            audio[start:start + len(sound)] += sound

        # 음량 정규화
        peak = np.max(np.abs(audio))

        if peak > 0:
            audio = audio / peak * 0.8

        return audio

    # 허밍 결과 전체 재생
    def play_sequence(self, notes):

        # 기존 재생 중인 음들을 모두 정리
        self.stop()

        print("[DEBUG] PianoPlayer.play_sequence() 호출됨!")
        print(f"[DEBUG] 전달받은 음 개수: {len(notes)}")


        if not notes:
            return

        # 재생할 음 목록 저장
        self._sequence_notes = list(notes)

        # 전체 음파 생성
        self._sequence_audio = self.render(self._sequence_notes)

        # 재생 위치 초기화
        self._sequence_position = 0

        # 재생 상태 변경
        self._sequence_playing = True
        self._sequence_paused = False

    # 자유연주 음 재생
    def play_note(self, midi, duration_ms=400):

        # 기존 TonePlayer와 동일하게 300ms 추가
        sound = self.tone(
            midi,
            duration_ms + 300
        )

        with self._lock:
            # 기존 음을 끊지 않고 새로운 음 추가
            self._active_notes.append((sound, 0))

    # 오디오 출력 콜백
    def _audio_callback(self, outdata, frames, time_info, status):

        # 이번 출력 구간 초기화
        output = np.zeros(frames, dtype=np.float32)

        with self._lock:

            # 1. 허밍 결과 전체 재생
            if self._sequence_playing and not self._sequence_paused:

                # 아직 재생할 음파가 남아 있는지 확인
                available = len(self._sequence_audio) - self._sequence_position
                length = min(frames, available)

                if length > 0:
                    output[:length] += self._sequence_audio[
                        self._sequence_position:
                        self._sequence_position + length
                    ]

                # 재생 위치 갱신
                self._sequence_position += length

                # 전체 재생이 끝났는지 확인
                if self._sequence_position >= len(self._sequence_audio):
                    self._sequence_playing = False
                    self._sequence_position = 0

            # 2. 개별 건반 연주
            remaining_notes = []

            for sound, position in self._active_notes:

                # 이번 프레임에서 재생 가능한 길이
                available = len(sound) - position
                length = min(frames, available)

                if length > 0:
                    output[:length] += sound[
                        position:position + length
                    ]

                # 재생 위치 갱신
                position += length

                # 재생이 끝나지 않은 음만 유지
                if position < len(sound):
                    remaining_notes.append((sound, position))

            self._active_notes = remaining_notes

        # 출력 음량 제한
        output = np.clip(output, -1.0, 1.0)

        outdata[:, 0] = output

    # 모든 재생 정지
    def stop(self):

        with self._lock:

            # 직접 연주 중인 음 제거
            self._active_notes.clear()

            # 허밍 결과 재생 상태 초기화
            self._sequence_position = 0
            self._sequence_playing = False
            self._sequence_paused = False

            self._sequence_audio = np.zeros(0, dtype=np.float32)
            self._sequence_notes.clear()
    # 모든 음 정지
    def stop_all(self):
        self.stop()

    # 허밍 결과 일시정지
    def pause(self):

        with self._lock:

            if not self._sequence_playing:
                return

            self._sequence_paused = True


    # 허밍 결과 이어 재생
    def resume(self):

        with self._lock:

            if not self._sequence_paused:
                return

            self._sequence_paused = False

    # 현재 재생 중인 음의 인덱스 반환
    def current_index(self):

        with self._lock:

            # 재생 중도 아니고 일시정지도 아니면 None
            if not self._sequence_playing and not self._sequence_paused:
                return None

            # 현재 재생 위치를 밀리초로 변환
            current_ms = self._sequence_position * 1000 / self.sr

            # 현재 재생 위치에 해당하는 음 찾기
            for i, note in enumerate(self._sequence_notes):

                if note.start_ms <= current_ms < note.start_ms + note.duration_ms:
                    return i

            return None


    # 재생 중인지 확인
    def is_playing(self):

        with self._lock:
            return self._sequence_playing and not self._sequence_paused


    # 일시정지 상태인지 확인
    def is_paused(self):

        with self._lock:
            return self._sequence_paused

    # 오디오 플레이어 종료
    def close(self):

        # 재생 중인 모든 음 정지
        self.stop()

        # 오디오 스트림 종료
        if self._stream.active:
            self._stream.stop()

        self._stream.close()
