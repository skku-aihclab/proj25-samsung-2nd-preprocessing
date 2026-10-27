"""
STEP 3. EMG 채널 선택

디바이스 한쪽에는 EMG 전극이 4개 있고, 같은 근육에 붙은 두 전극이 한 쌍 (0·1, 2·3).
쌍마다 전극 하나를 골라 EMG_0, EMG_2 로 남긴다. 기준은 엑셀의 전극별 유효 표시({r,l}_0~3 ∈ {o, v}).

1) 묶음 단위로 전극 고정
   묶음 = (subject, 운동, 균형/불균형, 좌/우). 모두 엑셀 값(subject_id, exercise, bal/unbal) 기준.
   파일명은 실험 중 직접 입력해 오타가 있을 수 있으므로 파일을 찾는 데만 씀.
   쌍마다 묶음 안에서 유효 표시가 더 많은 전극을 고른다 (같으면 앞 번호, 둘 다 0이면 선택 없음).
   → 같은 묶음의 측정들은 모두 같은 전극을 씀
2) 파일별 적용
   고정된 전극이 그 측정에서도 유효하면 사용. 유효하지 않으면 다른 전극으로 바꾸지 않고 그 쌍은 비움.

출력
    data/interim/preprocessed/<엑셀 파일명>.csv   (EMG0~3_Raw → 선택된 전극만 EMG_0, EMG_2 로 남김)
    data/output/channel_selection.csv            (파일별 {side}_EMG_0_from, {side}_EMG_2_from, 묶음 선택)

실행 (preprocessing_2nd/ 에서)
    python src/step3_select_channels.py
"""
import os
from collections import defaultdict

import pandas as pd
from tqdm import tqdm

from config import *
from common import load_meta, build_emg_index, find_emg_file


def is_valid(row, side, ch):
    return str(row[f"{side}_{ch}"]).strip().lower() in VALID_NORMAL_DATA


def group_key(row, side):
    return (f"sub{row['subject_id']}", str(row["exercise"]).strip(), str(row["bal/unbal"]).strip().lower(), side)


def decide_group_channels(meta):
    """묶음별·쌍별 고정 전극 {key: {pair_idx: 채널 번호 | None}}"""
    counts = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for _, row in meta.iterrows():
        for side in ("r", "l"):
            if pd.isna(row[f"csv_filename_{side}"]):
                continue
            key = group_key(row, side)
            for p, (a, b) in enumerate(CHANNEL_PAIRS):
                counts[key][p][0] += is_valid(row, side, a)
                counts[key][p][1] += is_valid(row, side, b)

    decided = {}
    for key, pairs in counts.items():
        decided[key] = {}
        for p, (a, b) in enumerate(CHANNEL_PAIRS):
            n_a, n_b = pairs[p]
            decided[key][p] = None if n_a == 0 and n_b == 0 else (a if n_a >= n_b else b)
    return decided


def channels_for_file(row, side, decided):
    """파일에 실제 적용할 전극 {target: 채널 번호 | None}"""
    key = group_key(row, side)
    out = {}
    for p, (a, b) in enumerate(CHANNEL_PAIRS):
        ch = decided[key][p]
        out[f"EMG_{a}"] = ch if ch is not None and is_valid(row, side, ch) else None
    return out, key


def apply_selection(df, selection):
    """EMG0~3_Raw 중 선택된 전극만 EMG_0 / EMG_2 로 남기고 나머지 EMG 원본 컬럼 제거"""
    raw_cols = [f"EMG{i}_Raw" for i in range(4)]
    rename = {f"EMG{ch}_Raw": target for target, ch in selection.items() if ch is not None}
    df = df.rename(columns=rename)
    return df.drop(columns=[c for c in raw_cols if c in df.columns])


def run():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SELECTED_DIR.mkdir(parents=True, exist_ok=True)

    meta = load_meta()
    emg_index = build_emg_index()
    decided = decide_group_channels(meta)
    rows, n_saved = [], 0

    for _, row in tqdm(meta.iterrows(), total=len(meta), desc="채널 선택"):
        for side in ("r", "l"):
            fname = row[f"csv_filename_{side}"]
            path = find_emg_file(emg_index, fname)
            if path is None:
                continue
            selection, key = channels_for_file(row, side, decided)
            apply_selection(pd.read_csv(path), selection).to_csv(SELECTED_DIR / str(fname).strip(), index=False)
            n_saved += 1

            rec = {"video_name": row["video_name"], "side": side, "csv_filename": fname, "group": "/".join(key)}
            for p, (a, _) in enumerate(CHANNEL_PAIRS):
                ch = selection[f"EMG_{a}"]
                rec[f"EMG_{a}_from"] = f"{side}_{ch}" if ch is not None else "None"
                rec[f"EMG_{a}_group_choice"] = f"{side}_{decided[key][p]}" if decided[key][p] is not None else "None"
            rows.append(rec)

    pd.DataFrame(rows).to_csv(CHANNEL_SELECTION_CSV, index=False)
    n_empty = sum(r[f"EMG_{a}_from"] == "None" for r in rows for a, _ in CHANNEL_PAIRS)
    print(f"[DONE] 파일 {n_saved}개 → {SELECTED_DIR}")
    print(f"[INFO] 선택 결과 → {CHANNEL_SELECTION_CSV} (비어 있는 쌍 {n_empty}개)")


if __name__ == "__main__":
    run()
