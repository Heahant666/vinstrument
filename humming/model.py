"""허밍 엔진이 주고받는 데이터 형태. numpy 없이 순수 파이썬만 사용."""
from dataclasses import dataclass, field, asdict
from typing import List, Optional
import json

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
SOLFEGE = ["도", "도#", "레", "레#", "미", "파", "파#", "솔", "솔#", "라", "라#", "시"]


def midi_to_name(midi: int) -> str:
    """60 -> 'C4'"""
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def midi_to_solfege(midi: int) -> str:
    """60 -> '도4'"""
    return f"{SOLFEGE[midi % 12]}{midi // 12 - 1}"


@dataclass
class Note:
    midi: int                 # 엔진이 1차로 판단한 음 (정수 MIDI 번호, C4 = 60)
    midi_float: float         # 실제 측정된 음높이 (소수). 후보 계산의 근거
    start_ms: int             # 녹음 시작 기준 시작 시각
    duration_ms: int          # 음 길이
    confidence: float         # 0~1, 높을수록 확실
    candidates: List[int] = field(default_factory=list)  # 대안 음 2개
    selected: Optional[int] = None    # 사용자가 고른 음. None이면 midi 그대로
    flags: List[str] = field(default_factory=list)       # "short", "unstable", "low_conf", "octave_jump", "borderline"
    octave_hint: int = 0      # +1 / -1 이면 한 옥타브 위/아래 후보 근거 있음

    @property
    def final_midi(self) -> int:
        return self.midi if self.selected is None else self.selected

    @property
    def name(self) -> str:
        return midi_to_name(self.final_midi)

    @property
    def solfege(self) -> str:
        return midi_to_solfege(self.final_midi)

    @property
    def uncertain(self) -> bool:
        return len(self.flags) > 0

    def options(self) -> List[int]:
        """화면에 보여 줄 3개: 원래 음 + 후보 2개"""
        return [self.midi] + list(self.candidates)


@dataclass
class HummingResult:
    notes: List[Note]
    sample_rate: int
    duration_ms: int

    def to_payload(self) -> List[dict]:
        """악기 엔진(피아노·하프)에 넘기는 최종 데이터. 선택이 반영된 값만 담는다."""
        return [
            {"midi": n.final_midi, "name": n.name, "solfege": n.solfege,
             "start_ms": n.start_ms, "duration_ms": n.duration_ms}
            for n in self.notes
        ]

    def save_json(self, path: str) -> None:
        data = {"sample_rate": self.sample_rate, "duration_ms": self.duration_ms,
                "notes": [asdict(n) for n in self.notes]}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def load_json(path: str) -> "HummingResult":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return HummingResult([Note(**n) for n in data["notes"]],
                             data["sample_rate"], data["duration_ms"])
