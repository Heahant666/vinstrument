"""허밍 엔진 패키지. 외부(main.py, 악기 모듈)는 HummingEngine과 Note/HummingResult만 쓰면 된다."""
from .model import Note, HummingResult, midi_to_name, midi_to_solfege

try:                                    # 3단계(analyzer.py)를 만들기 전에도 패키지가 열리게
    from .analyzer import analyze_audio
except ImportError:
    analyze_audio = None