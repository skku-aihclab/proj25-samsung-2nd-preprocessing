"""
STEP 5. IMU 다운샘플 (2000Hz → 66Hz)

IMU의 실제 갱신은 약 66Hz이고, 디바이스가 EMG와 같은 2000Hz 행에 같은 값을 반복 저장한다.
IMU 기반 모델용으로 측정(video_name)마다 66Hz로 리샘플한다.
    - IMU 12축(right_/left_ ax, ay, az, gx, gy, gz)만 사용, EMG는 제외
    - scipy.signal.resample (FFT 방식), 샘플 수 = 원본 행 수 × 66 / 2000
    - TimeStamp는 측정 시작~끝을 균등 간격으로 다시 생성
    - label, beep 컬럼은 포함하지 않음 (필요하면 merged_dataset.csv의 TimeStamp로 다시 매칭)

입력
    data/output/merged_dataset.csv   (step4)

출력
    data/output/imu_downsampled_66hz.csv
    컬럼: TimeStamp, right_ax..gz, left_ax..gz, + IMU_META_COLS

실행 (preprocessing_2nd/ 에서)
    python src/step5_downsample_imu.py
"""
import pandas as pd
from scipy.signal import resample
from tqdm import tqdm

from config import *

MIN_SAMPLES = 10


def downsample_trial(group):
    group = group.sort_values("TimeStamp")
    imu = group[IMU_COLS]
    n_out = int(len(group) * IMU_TARGET_FS / FS)
    if n_out < MIN_SAMPLES:
        return None
    # 한쪽 파일만 있는 측정은 반대쪽 IMU가 전부 NaN → 리샘플 후에도 NaN 유지
    present = [c for c in IMU_COLS if imu[c].notna().any()]
    out = pd.DataFrame(index=range(n_out), columns=IMU_COLS, dtype=float)
    if present:
        out[present] = resample(imu[present].interpolate(limit_direction="both").values, n_out, axis=0)
    out.insert(0, "TimeStamp", pd.date_range(group["TimeStamp"].iloc[0], group["TimeStamp"].iloc[-1], periods=n_out))
    for col in IMU_META_COLS:
        out[col] = group[col].iloc[0]
    return out


def run():
    if IMU_66HZ_CSV.exists():
        IMU_66HZ_CSV.unlink()
    usecols = ["TimeStamp"] + IMU_COLS + IMU_META_COLS
    dtypes = {"subject_id": str, "video_name": str, "unbal_normalside": str}

    # step4 출력은 측정 단위로 연속 저장되어 있으므로 청크를 읽으며 측정별로 모아서 처리
    current, buf, header, n_done, skipped = None, [], True, 0, []

    def flush(video, parts):
        nonlocal header, n_done
        out = downsample_trial(pd.concat(parts, ignore_index=True))
        if out is None:
            skipped.append(video)
            return
        out.to_csv(IMU_66HZ_CSV, mode="a", header=header, index=False)
        header, n_done = False, n_done + 1

    reader = pd.read_csv(MERGED_CSV, usecols=usecols, dtype=dtypes, parse_dates=["TimeStamp"], chunksize=2_000_000)
    for chunk in tqdm(reader, desc="청크"):
        for video, part in chunk.groupby("video_name", sort=False):
            if video != current:
                if buf:
                    flush(current, buf)
                current, buf = video, []
            buf.append(part)
    if buf:
        flush(current, buf)

    print(f"[DONE] 측정 {n_done}건 → {IMU_66HZ_CSV}")
    if skipped:
        print(f"[SKIP] {MIN_SAMPLES}샘플 미만으로 짧은 측정 {len(skipped)}건: {skipped}")


if __name__ == "__main__":
    run()
