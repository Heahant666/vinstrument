

import numpy as np
import sounddevice as sd
import threading


class PianoPlayer:

    def __init__(self, sr=44100):
        self.sr = sr

        # 음 하나의 기본 재생 시간
        self.note_duration = 1.0

        # 자동 감쇠 시간
        self.release = 0.3

        # 현재 재생 중인 음
        self.active_notes = {}

        self.lock = threading.Lock()

        # 지속적인 오디오 스트림
        self.stream = sd.OutputStream(
            samplerate=self.sr,
            channels=1,
            dtype="float32",
            callback=self._audio_callback
        )

        self.stream.start()

    # MIDI 번호를 주파수로 변환
    def midi_to_frequency(self, midi):
        return 440.0 * (2 ** ((midi - 69) / 12))

    # 음파 생성
    def generate_tone(self, midi):
        frequency = self.midi_to_frequency(midi)

        sample_count = int(
            self.sr * (self.note_duration + self.release)
        )

        t = np.arange(sample_count) / self.sr

        wave = np.sin(2 * np.pi * frequency * t)

        return wave.astype(np.float32)

    # 새로운 음 재생
    def play_note(self, midi):

        with self.lock:

            wave = self.generate_tone(midi)

            # 이미 같은 음이 재생 중이면 새 음으로 교체
            self.active_notes[midi] = {
                "wave": wave,
                "position": 0
            }

    # 모든 음 정지
    def stop_all(self):

        with self.lock:
            self.active_notes.clear()

    # 오디오 출력 콜백
    def _audio_callback(self, outdata, frames, time_info, status):

        output = np.zeros(frames, dtype=np.float32)

        with self.lock:

            finished_notes = []

            for midi, note in self.active_notes.items():

                wave = note["wave"]
                position = note["position"]

                end = min(position + frames, len(wave))

                current_wave = wave[position:end]
                valid_frames = len(current_wave)

                if valid_frames == 0:
                    finished_notes.append(midi)
                    continue

                # 현재 재생 위치를 시간으로 변환
                times = (
                    np.arange(position, end) / self.sr
                )

                # 기본적으로 소리 크기 유지
                envelope = np.ones(valid_frames, dtype=np.float32)

                # 1초 이후 자연스럽게 감쇠
                release_mask = times >= self.note_duration

                envelope[release_mask] = np.maximum(
                    0.0,
                    1.0 - (
                        (times[release_mask] - self.note_duration)
                        / self.release
                    )
                )

                # 음파와 엔벨로프 결합
                output[:valid_frames] += current_wave * envelope

                note["position"] += valid_frames

                # 재생이 끝난 음 제거
                if note["position"] >= len(wave):
                    finished_notes.append(midi)

            for midi in finished_notes:
                self.active_notes.pop(midi, None)

        # 여러 음의 합산으로 인한 출력 초과 방지
        output = np.clip(output, -1.0, 1.0)

        outdata[:, 0] = output

    # 객체 종료
    def close(self):

        self.stop_all()

        if self.stream.active:
            self.stream.stop()

        self.stream.close()
