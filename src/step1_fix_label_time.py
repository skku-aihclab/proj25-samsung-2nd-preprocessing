"""
STEP 1. (참고) 영상 라벨 Abs_Time의 beep 보정 + 시각화 검수 제외
NAS 라벨 data_label/ → data_label_fixed/ → data_label_fixed_no_sensor_error_files/ 를 만든 과정.
파이프라인 입력(data/labels/)은 이미 이 결과이므로 run_all.sh 에는 포함하지 않음.

1) beep 보정 (abs_time_need_fix.xlsx 에서 video_time_error == 'o' 인 측정)
   - first_beep : 영상을 재생해 첫 beep이 들리는 순간의 영상 표시 시각 (사람이 읽어 기록, HH:MM:SS.mmm)
   - beep CSV 첫 Timestamp : 실제 첫 beep 절대시각
   - Δt = first_beep(같은 날짜) - beep CSV 첫 Timestamp,  |Δt| > MAX_BEEP_DELTA_SEC 이면 건너뜀
   - 라벨 Abs_Time 에서 Δt 를 뺌
2) 시각화 검수 제외: config.VISUAL_EXCLUDED_FILE_NO (보정 후에도 EMG와 맞지 않은 측정) 은 저장하지 않음
   - abs_time_need_fix.xlsx 의 sensor_time_error == 'o' (25건)은 data_label/ 에 이미 없음

입력
    data/label_raw/<video_name>.csv            (NAS data_label/)
    data/meta/abs_time_need_fix.xlsx           (file_no, first_beep, video_time_error)
    data/meta/video_csv_info.xlsx              (file_no → video_name, beep_filename)
    data/beep/<beep_filename>

출력
    data/interim/labels_fixed/<video_name>.csv (NAS data_label_fixed_no_sensor_error_files/ 에 해당)
    data/interim/label_fix_report.csv          (보정한 측정별 Δt, 상태)

실행 (preprocessing_2nd/ 에서)
    python src/step1_fix_label_time.py
"""
import os
import shutil

import pandas as pd

from config import *
from common import read_csv_any_encoding, load_beep_times


def parse_abs_time(s):
    """'YYYY-MM-DD HH:MM:SS:mmm' 또는 '...SS.mmm' → Timestamp"""
    s = str(s).strip()
    if s[-4] == ":":
        s = s[:-4] + "." + s[-3:]
    return pd.Timestamp(s)


def format_abs_time(t):
    """라벨 원본과 같은 'YYYY-MM-DD HH:MM:SS:mmm' 형식"""
    return f"{t:%Y-%m-%d %H:%M:%S}:{round(t.microsecond / 1000) % 1000:03d}"


def beep_delta_sec(row):
    """Δt(초) = 영상에서 들린 첫 beep 시각 - beep CSV의 첫 beep 시각"""
    beeps = load_beep_times(row["beep_filename"])
    if beeps is None or len(beeps) == 0:
        raise FileNotFoundError(f"beep 없음/읽기 실패: {row['beep_filename']}")
    first = beeps.iloc[0]
    heard = pd.Timestamp(f"{first.date()} {str(row['first_beep']).strip()}")
    return (heard - first).total_seconds()


def run():
    LABEL_FIXED_DIR.mkdir(parents=True, exist_ok=True)
    info = pd.read_excel(FIX_INFO_PATH)
    meta = pd.read_excel(META_PATH)[["file_no", "video_name", "beep_filename"]]
    fix = info[info["video_time_error"].astype(str).str.strip() == "o"][["file_no", "first_beep"]]
    fix = fix.merge(meta, on="file_no", how="left")

    excluded = set(meta.loc[meta["file_no"].isin(VISUAL_EXCLUDED_FILE_NO), "video_name"].astype(str)
                   .str.replace(".mp4", "", regex=False))
    report, fixed_names = [], set()

    # 1) beep 보정
    for _, row in fix.iterrows():
        video = str(row["video_name"]).replace(".mp4", "")
        rec = {"file_no": row["file_no"], "video_name": video, "beep_filename": row["beep_filename"],
               "delta_sec": None, "status": "fixed"}
        src = LABEL_RAW_DIR / f"{video}.csv"
        try:
            if not src.exists():
                raise FileNotFoundError("라벨 없음")
            delta = beep_delta_sec(row)
            rec["delta_sec"] = round(delta, 3)
            if abs(delta) > MAX_BEEP_DELTA_SEC:
                rec["status"] = f"skip: |Δt| > {MAX_BEEP_DELTA_SEC}s"
            elif video in excluded:
                rec["status"] = "excluded (시각화 검수)"
            else:
                df = read_csv_any_encoding(src)
                shift = pd.Timedelta(seconds=delta)
                df["Abs_Time"] = df["Abs_Time"].map(lambda v: v if pd.isna(v) else format_abs_time(parse_abs_time(v) - shift))
                df.to_csv(LABEL_FIXED_DIR / src.name, index=False)
                fixed_names.add(src.name)
        except Exception as e:
            rec["status"] = f"skip: {e}"
        report.append(rec)

    # 2) 보정 대상이 아닌 라벨은 그대로 복사 (시각화 검수 제외 대상은 빼고)
    n_copied = 0
    for f in sorted(os.listdir(LABEL_RAW_DIR)):
        if f.endswith(".csv") and f not in fixed_names and f[:-4] not in excluded:
            shutil.copy2(LABEL_RAW_DIR / f, LABEL_FIXED_DIR / f)
            n_copied += 1

    rep = pd.DataFrame(report)
    rep.to_csv(LABEL_FIX_REPORT_CSV, index=False, encoding="utf-8-sig")
    print(f"[DONE] 보정 {len(fixed_names)}개 + 그대로 복사 {n_copied}개 → {LABEL_FIXED_DIR}")
    print(rep["status"].str.split(":").str[0].value_counts().to_string())
    print(f"[INFO] 상세 → {LABEL_FIX_REPORT_CSV}")


if __name__ == "__main__":
    run()
