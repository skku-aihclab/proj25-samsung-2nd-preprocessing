"""
STEP 4. 좌·우 병합 + 영상 라벨 + beep  (2000Hz)

측정(video_name) 1건마다
    1) step3 결과(interim/preprocessed/)의 오른쪽·왼쪽 CSV를 읽어 Save_Time, Index_Time, EMG_0, EMG_2, IMU 6축만 남김
    2) TimeStamp = 날짜 + 첫 Save_Time + Index_Time
    3) 컬럼 이름 변경 (좌우 전극 배치가 반대)
         오른쪽: EMG_0 → right_biceps,  EMG_2 → right_triceps,  ax.. → right_ax..
         왼쪽  : EMG_0 → left_triceps,  EMG_2 → left_biceps,    ax.. → left_ax..
    4) 오른쪽 시간축 기준으로 왼쪽을 가장 가까운 TimeStamp에 붙임 (merge_asof, nearest)
       한쪽 파일만 있으면 그쪽만 사용
    5) label: 라벨의 절대시각(Abs_Time + Start/Peak/End)에 가장 가까운 샘플에 1/2/3 (나머지 0)
    6) beep : beep 시각에 가장 가까운 샘플에 1 (나머지 0)
    7) 엑셀 메타 컬럼 추가

출력
    data/output/merged_dataset.csv
    컬럼: TimeStamp, Index_Time, Save_Time, right_biceps, right_triceps, right_ax..gz,
          left_triceps, left_biceps, left_ax..gz, beep, label, + 메타(META_COLS)

실행 (preprocessing_2nd/ 에서)
    python src/step4_merge.py
"""
import numpy as np
import pandas as pd
from tqdm import tqdm

from config import *
from common import load_meta, normalize_filename, add_timestamp, load_label_abs, load_beep_times


def build_selected_index():
    """interim/preprocessed/ 파일을 {정규화 파일명: 경로}로 색인"""
    return {normalize_filename(p.name): p for p in SELECTED_DIR.glob("*.csv")}


def load_side(index, fname, video_name, side):
    if pd.isna(fname) or normalize_filename(fname) not in index:
        return None
    df = pd.read_csv(index[normalize_filename(fname)])
    keep = ["Save_Time", "Index_Time", "EMG_0", "EMG_2"] + IMU_AXES
    df = add_timestamp(df[[c for c in keep if c in df.columns]].copy(), video_name)
    df["Save_Time"] = df["Save_Time"].iloc[0]
    df = df.rename(columns=EMG_RENAME[side])
    prefix = "right_" if side == "r" else "left_"
    return df.rename(columns={a: prefix + a for a in IMU_AXES if a in df.columns})


def nearest_indices(times, targets):
    """정렬된 times(ns)에서 각 target(ns)에 가장 가까운 위치"""
    pos = np.clip(np.searchsorted(times, targets), 1, len(times) - 1)
    left, right = times[pos - 1], times[pos]
    return np.where(np.abs(targets - left) <= np.abs(right - targets), pos - 1, pos)


def mark_labels(df, video_name):
    df["label"] = 0
    lab = load_label_abs(video_name)
    if lab is None:
        return df, None
    times = df["TimeStamp"].values.astype("datetime64[ns]").astype("int64")
    for col, code in LABEL_CODE.items():
        t = lab[f"Abs_{col}"].dropna().values.astype("datetime64[ns]").astype("int64")
        if len(t):
            df.loc[df.index[nearest_indices(times, t)], "label"] = code
    expected = {c: int(lab[f"Abs_{c}"].notna().sum()) for c in LABEL_CODE}
    actual = {c: int((df["label"] == code).sum()) for c, code in LABEL_CODE.items()}
    return df, (expected, actual)


def mark_beeps(df, beep_filename):
    df["beep"] = 0
    beeps = load_beep_times(beep_filename)
    if beeps is None or len(beeps) == 0:
        return df, None
    times = df["TimeStamp"].values.astype("datetime64[ns]").astype("int64")
    t = beeps.values.astype("datetime64[ns]").astype("int64")
    df.loc[df.index[nearest_indices(times, t)], "beep"] = 1
    return df, (len(t), int(df["beep"].sum()))


def run():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if MERGED_CSV.exists():
        MERGED_CSV.unlink()

    meta = load_meta()
    index = build_selected_index()
    header, n_done, warnings = True, 0, []

    for _, row in tqdm(meta.iterrows(), total=len(meta), desc="병합"):
        video = row["video_name"]
        if pd.isna(video):
            continue
        df_r = load_side(index, row["csv_filename_r"], video, "r")
        df_l = load_side(index, row["csv_filename_l"], video, "l")

        if df_r is not None and df_l is not None:
            df = pd.merge_asof(df_r.sort_values("TimeStamp"),
                               df_l.drop(columns=["Index_Time", "Save_Time"]).sort_values("TimeStamp"),
                               on="TimeStamp", direction="nearest")
        elif df_r is not None or df_l is not None:
            df = df_r if df_r is not None else df_l
        else:
            continue
        df = df.reset_index(drop=True)

        df, lab_check = mark_labels(df, video)
        if lab_check and lab_check[0] != lab_check[1]:
            warnings.append(f"{video} 라벨 개수 불일치 (같은 샘플에 겹침): 라벨 {lab_check[0]} / 표시 {lab_check[1]}")
        df, beep_check = mark_beeps(df, row["beep_filename"])
        if beep_check and beep_check[0] != beep_check[1]:
            warnings.append(f"{video} beep 개수 불일치: 파일 {beep_check[0]} / 표시 {beep_check[1]}")

        for col in META_COLS:
            df[col] = row[col] if col in row else np.nan

        # 컬럼을 고정해 이어쓰기 (한쪽만 있는 측정은 반대쪽 컬럼이 NaN)
        df = df.reindex(columns=["TimeStamp", "Index_Time", "Save_Time"] + EMG_COLS + IMU_COLS + ["beep", "label"] + META_COLS)
        df.to_csv(MERGED_CSV, mode="a", header=header, index=False)
        header, n_done = False, n_done + 1

    print(f"[DONE] 측정 {n_done}건 → {MERGED_CSV}")
    for w in warnings:
        print("[경고]", w)


if __name__ == "__main__":
    run()
