"""음성 전처리 + 프레임별 음높이(F0) 추출. YIN 알고리즘을 numpy로 직접 구현."""
from dataclasses import dataclass
import numpy as np

SR = 22050          # 분석용 샘플레이트 (녹음도 이 값으로)
FRAME = 2048        # 한 프레임 길이 (약 93ms)
HOP = 256           # 프레임 간격 (약 11.6ms)
FMIN, FMAX = 70.0, 1000.0   # 허밍으로 낼 수 있는 음높이 범위 (Hz)


def hz_to_midi(hz):
    return 69.0 + 12.0 * np.log2(np.asarray(hz, dtype=float) / 440.0)


def midi_to_hz(midi):
    return 440.0 * 2.0 ** ((np.asarray(midi, dtype=float) - 69.0) / 12.0)


def preprocess(y: np.ndarray, sr: int = SR) -> np.ndarray:
    """모노 변환 → 직류 제거 → 60Hz 이하 저음 잡음 제거 → 크기 정규화"""
    y = np.asarray(y, dtype=np.float32)
    if y.ndim > 1:
        y = y.mean(axis=1)
    if len(y) == 0:
        return y
    y = y - y.mean()
    spec = np.fft.rfft(y)
    freqs = np.fft.rfftfreq(len(y), 1.0 / sr)
    spec[freqs < 60.0] = 0.0                      # 책상 진동, 에어컨 웅웅 소리 제거
    y = np.fft.irfft(spec, len(y))
    peak = np.abs(y).max()
    if peak > 1e-6:
        y = y / peak * 0.9
    return y.astype(np.float32)


def _frames(y: np.ndarray, frame: int, hop: int) -> np.ndarray:
    if len(y) < frame:
        y = np.pad(y, (0, frame - len(y)))
    n = 1 + (len(y) - frame) // hop
    idx = np.arange(frame)[None, :] + hop * np.arange(n)[:, None]
    return y[idx]


def yin_f0(frames: np.ndarray, sr: int, fmin: float, fmax: float, threshold: float = 0.15):
    """프레임마다 기본 주파수(Hz)와 비주기성(0에 가까울수록 또렷한 음)을 돌려준다.

    YIN: 신호를 tau만큼 밀었을 때 자기 자신과 얼마나 다른지(차이 함수)를 계산하고,
    차이가 처음으로 작아지는 tau가 한 주기. f0 = sr / tau.
    """
    n_frames, W = frames.shape
    tau_max = int(sr / fmin)
    tau_min = max(2, int(sr / fmax))
    N = W - tau_max                               # 비교에 쓰는 샘플 수 (tau마다 동일)
    x = frames - frames.mean(axis=1, keepdims=True)

    # 차이 함수 d(tau) = sum_j (x_j - x_{j+tau})^2 = E0 + E_tau - 2*C(tau)
    cs = np.concatenate([np.zeros((n_frames, 1)), np.cumsum(x * x, axis=1)], axis=1)
    taus = np.arange(tau_max + 1)
    e0 = cs[:, N] - cs[:, 0]
    e_tau = cs[:, N + taus] - cs[:, taus]
    nfft = 1 << int(np.ceil(np.log2(W + N)))
    X = np.fft.rfft(x, nfft, axis=1)
    B = np.fft.rfft(x[:, :N], nfft, axis=1)
    c = np.fft.irfft(X * np.conj(B), nfft, axis=1)[:, : tau_max + 1]
    d = np.maximum(e0[:, None] + e_tau - 2.0 * c, 0.0)

    # 누적 평균 정규화 (CMNDF): tau=0 근처가 항상 작게 나오는 문제를 없앤다
    cum = np.cumsum(d[:, 1:], axis=1)
    dprime = np.ones_like(d)
    dprime[:, 1:] = d[:, 1:] * taus[1:] / np.maximum(cum, 1e-12)

    f0 = np.full(n_frames, np.nan)
    aperiodicity = np.ones(n_frames)
    for i in range(n_frames):
        dp = dprime[i]
        below = np.where(dp[tau_min:tau_max] < threshold)[0]
        if len(below):
            tau = int(below[0]) + tau_min
            while tau + 1 < tau_max and dp[tau + 1] < dp[tau]:   # 골짜기 바닥까지 내려감
                tau += 1
        else:
            tau = int(np.argmin(dp[tau_min:tau_max])) + tau_min
        # 포물선 보정으로 소수점 tau 추정 (정확도 ↑)
        shift = 0.0
        if 1 <= tau < tau_max:
            a, b, c2 = dp[tau - 1], dp[tau], dp[tau + 1]
            denom = a - 2.0 * b + c2
            if abs(denom) > 1e-12:
                shift = float(np.clip(0.5 * (a - c2) / denom, -1, 1))
        f0[i] = sr / (tau + shift)
        aperiodicity[i] = dp[tau]
    return f0, aperiodicity


def _nan_median_filter(x: np.ndarray, width: int = 5) -> np.ndarray:
    """nan은 그대로 두고, 값이 있는 곳만 주변 중앙값으로 바꿔 떨림을 줄인다."""
    half = width // 2
    padded = np.pad(x, half, constant_values=np.nan)
    win = np.lib.stride_tricks.sliding_window_view(padded, width)
    with np.errstate(all="ignore"):
        med = np.nanmedian(win, axis=1)
    return np.where(np.isnan(x), np.nan, med)


@dataclass
class FrameData:
    times_ms: np.ndarray    # 프레임 시작 시각
    midi: np.ndarray        # 프레임별 음높이(소수 MIDI). 무성/무음은 nan
    voiced: np.ndarray      # 소리를 낸 프레임인지
    rms: np.ndarray         # 프레임 음량 (긴 창, 유성 판정용)
    rms_short: np.ndarray   # 짧은 창(23ms) 음량 — 같은 음을 두 번 부른 것을 찾는 데 사용
    confidence: np.ndarray  # 1 - 비주기성
    hop_ms: float


def analyze_frames(y: np.ndarray, sr: int = SR, frame: int = FRAME, hop: int = HOP) -> FrameData:
    fr = _frames(y, frame, hop)
    rms = np.sqrt((fr ** 2).mean(axis=1))
    # 짧은 창 음량: 각 프레임 중앙 부근 512샘플. 긴 창은 짧은 끊김을 뭉개 버리기 때문
    short = 512
    center = frame // 2
    fr_short = fr[:, center - short // 2 : center + short // 2]
    rms_short = np.sqrt((fr_short ** 2).mean(axis=1))
    f0, ap = yin_f0(fr, sr, FMIN, FMAX)

    # 무음 처리: 가장 조용한 10% 프레임을 잡음 바닥으로 보고 그 3배 이상만 소리로 인정
    floor = np.percentile(rms, 10)
    rms_thr = max(floor * 3.0, 0.02)
    rms_thr = min(rms_thr, 0.3 * float(rms.max()))   # 쉼 없이 계속 소리가 나도 전부 무음 처리되지 않게 상한

    voiced = (rms > rms_thr) & (ap < 0.35) & np.isfinite(f0) & (f0 >= FMIN) & (f0 <= FMAX)

    midi = np.full(len(fr), np.nan)
    midi[voiced] = hz_to_midi(f0[voiced])
    midi = _nan_median_filter(midi, 5)
    times_ms = np.arange(len(fr)) * hop / sr * 1000.0
    return FrameData(times_ms, midi, voiced, rms, rms_short, 1.0 - ap, hop / sr * 1000.0)


if __name__ == "__main__":
    # 자가 테스트: 440Hz(A4=69) 사인파를 넣어 69 근처가 나오는지
    t = np.arange(int(SR * 1.0)) / SR
    y = 0.5 * np.sin(2 * np.pi * 440 * t)
    fd = analyze_frames(preprocess(y))
    print("중앙값 MIDI:", round(float(np.nanmedian(fd.midi)), 2), "(69.00이 정답)")
    print("유성 비율:", f"{fd.voiced.mean():.0%}")
