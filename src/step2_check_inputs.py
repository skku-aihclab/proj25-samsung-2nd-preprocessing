"""
STEP 2. 입력 데이터 사전 점검 (원본을 data/ 에 넣은 직후 실행)

엑셀(video_csv_info.xlsx) · 디바이스 CSV(emg_data/) · 영상 라벨(labels/) · beep(beep/)을
파이프라인과 같은 매칭 규칙으로 대조해 "조용히 빠지는 파일"을 미리 찾는다. 아무 파일도 수정하지 않음.

출력
    data/interim/input_check.csv   (issue, video_name, name, detail)

실행 (preprocessing_2nd/ 에서)
    python src/step2_check_inputs.py
"""
import os
import pandas as pd

from config import *
from common import load_meta, build_emg_index, find_emg_file, label_path_of, read_csv_any_encoding, BEEP_DIR

REQUIRED_META = ["video_name", "csv_filename_r", "csv_filename_l", "normal_data",
                 "r_0", "r_1", "r_2", "r_3", "l_0", "l_1", "l_2", "l_3", "beep_filename"]
REQUIRED_RAW = ["Save_Time", "Index_Time", "EMG0_Raw", "EMG1_Raw", "EMG2_Raw", "EMG3_Raw"] + IMU_AXES
REQUIRED_LABEL = ["Start", "Peak", "End", "Abs_Time"]


def run():
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    raw_meta = pd.read_excel(META_PATH)
    missing = [c for c in REQUIRED_META if c not in raw_meta.columns]
    if missing:
        raise ValueError(f"video_csv_info.xlsx에 필요한 컬럼이 없음: {missing}")

    meta = load_meta()
    emg_index = build_emg_index()
    rows, used = [], set()

    def add(issue, video, name, detail=""):
        rows.append({"issue": issue, "video_name": video, "name": name, "detail": detail})

    for _, r in meta.iterrows():
        video = r["video_name"]
        if pd.isna(video):
            add("meta_no_video_name", None, r.get("csv_filename_r"), "video_name 비어 있음")
            continue

        # 좌·우 원본 CSV
        for side in ("r", "l"):
            fname = r[f"csv_filename_{side}"]
            if pd.isna(fname):
                add(f"meta_no_{side}_file", video, None, f"csv_filename_{side} 비어 있음 (한쪽만 처리됨)")
                continue
            path = find_emg_file(emg_index, fname)
            if path is None:
                add("sensor_file_missing", video, fname, "emg_data/에 없음")
                continue
            used.add(path)
            cols = pd.read_csv(path, nrows=1).columns
            lack = [c for c in REQUIRED_RAW if c not in cols]
            if lack:
                add("sensor_missing_columns", video, fname, f"없는 컬럼: {lack}")
            valid = [str(r[f"{side}_{i}"]).strip().lower() in VALID_NORMAL_DATA for i in range(4)]
            for a, b in CHANNEL_PAIRS:
                if not valid[a] and not valid[b]:
                    add("channel_pair_invalid", video, fname, f"{side}_{a}, {side}_{b} 모두 유효 표시 아님 → EMG_{a} 없음")

        # 라벨
        lpath = label_path_of(video)
        if not lpath.exists():
            add("label_missing", video, lpath.name, "라벨 없음 → label 0 (센서 시간 오류로 제외된 측정일 수 있음)")
        else:
            cols = read_csv_any_encoding(lpath).columns
            lack = [c for c in REQUIRED_LABEL if c not in cols]
            if lack:
                add("label_missing_columns", video, lpath.name, f"없는 컬럼: {lack}")

        # beep
        bf = r["beep_filename"]
        if pd.isna(bf):
            add("beep_not_assigned", video, None, "beep_filename 비어 있음 → beep 0")
        elif not (BEEP_DIR / str(bf).strip()).exists():
            add("beep_missing", video, bf, "beep/에 없음 → beep 0")

    for path in sorted(set(emg_index.values()) - used):
        add("sensor_not_in_meta", None, os.path.basename(path), "엑셀 처리 대상 행에 없음 (normal_data, 예비 실험, MVC·fatigue 제외 포함)")

    report = pd.DataFrame(rows, columns=["issue", "video_name", "name", "detail"])
    report.to_csv(INPUT_CHECK_CSV, index=False, encoding="utf-8-sig")
    print(f"처리 대상 {len(meta)}행 / emg_data CSV {len(emg_index)}개")
    print("[OK] 문제 없음" if report.empty else report["issue"].value_counts().to_string())
    print(f"[INFO] 상세 → {INPUT_CHECK_CSV}")


if __name__ == "__main__":
    run()
