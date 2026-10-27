"""
공통 함수: 메타데이터 로딩, 원본 파일 찾기, 시간 변환, 라벨/beep 읽기
"""
import os
import pandas as pd

from config import *


## 메타데이터
def load_meta():
    """
    video_csv_info.xlsx 중 처리 대상 행만 반환
    - normal_data ∈ {o, v} (대소문자 무관)
    - 예비 실험 subject(sub77, sub78) 제외
    - 추가 세션(fatigue_a/b, MVC_b/t) 제외
    """
    df = pd.read_excel(META_PATH)
    df = df[df["normal_data"].astype(str).str.strip().str.lower().isin(VALID_NORMAL_DATA)]
    exercise = df["exercise"].astype(str).str.strip().str.lower()
    df = df[~exercise.str.startswith(EXCLUDED_EXERCISE_PREFIXES)]
    pattern = "|".join(EXCLUDED_SUBJECTS)
    for side in ("r", "l"):
        df = df[~df[f"csv_filename_{side}"].astype(str).str.contains(pattern, na=False)]
    return df.reset_index(drop=True)


## 원본 CSV 찾기
def normalize_filename(filename):
    """파일명에서 첫 'NINA' 이후만 사용 (앱이 앞에 붙이는 접두사 무시)"""
    filename = str(filename).strip()
    return filename[filename.index("NINA"):] if "NINA" in filename else filename


def build_emg_index():
    """emg_data/ 아래 CSV를 {정규화 파일명: 경로}로 색인 (하위 폴더 포함)"""
    index = {}
    for dirpath, _, filenames in os.walk(EMG_DIR):
        for f in filenames:
            if f.lower().endswith(".csv"):
                index[normalize_filename(f)] = os.path.join(dirpath, f)
    return index


def find_emg_file(emg_index, fname):
    if pd.isna(fname):
        return None
    return emg_index.get(normalize_filename(fname))


## 시간
def add_timestamp(df_csv, video_name):
    """
    TimeStamp = (video_name 앞 8자리 날짜) + (첫 행 Save_Time) + Index_Time
    - Save_Time: PC가 패킷을 받은 시각 (간격 불규칙) → 시작 시각으로만 사용
    - Index_Time: 0.5ms 등간격 상대시간 → 샘플 시간축
    """
    date_val = pd.to_datetime(str(video_name)[:8], format="%Y%m%d").date()
    first_time = pd.to_datetime(df_csv["Save_Time"].iloc[0], format="%H.%M.%S.%f").time()
    base = pd.Timestamp.combine(date_val, first_time)
    df_csv["TimeStamp"] = base + pd.to_timedelta(df_csv["Index_Time"], unit="s")
    return df_csv


def fix_time_format(x):
    """'08.911' → '00:00:08.911', '00:08.911' → '00:00:08.911' (Timedelta 변환용)"""
    parts = str(x).split(":")
    if len(parts) == 1:
        return f"00:00:{x}"
    if len(parts) == 2:
        return f"00:{x}"
    return str(x)


## 라벨 / beep
def read_csv_any_encoding(path):
    try:
        return pd.read_csv(path)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="cp949")


def label_path_of(video_name):
    return LABEL_DIR / str(video_name).replace(".mp4", ".csv")


def load_label_abs(video_name):
    """
    라벨 CSV → 절대시각 Abs_Start / Abs_Peak / Abs_End
    - Start/Peak/End: 영상 기준 상대시간 ('mm:ss.mmm' 또는 'ss.mmm')
    - Abs_Time: 영상 시작 절대시각 ('YYYY-MM-DD HH:MM:SS:mmm' 또는 '...SS.mmm')
    없으면 None
    """
    path = label_path_of(video_name)
    if not path.exists():
        return None
    df = read_csv_any_encoding(path)
    abs_time = df["Abs_Time"].astype(str).str.replace(r":(\d{3})$", r".\1", regex=True)
    df["Abs_Time"] = pd.to_datetime(abs_time, format="%Y-%m-%d %H:%M:%S.%f", errors="coerce")
    for col in ("Start", "Peak", "End"):
        if col in df.columns:
            rel = pd.to_timedelta(df[col].astype(str).apply(fix_time_format), errors="coerce")
            df[f"Abs_{col}"] = df["Abs_Time"] + rel
        else:
            df[f"Abs_{col}"] = pd.NaT
    return df


def load_beep_times(beep_filename):
    """beep CSV의 Timestamp ('YYYY-MM-DD HH:MM:SS.mmm') 목록. 없으면 None"""
    if pd.isna(beep_filename):
        return None
    path = BEEP_DIR / str(beep_filename).strip()
    if not path.exists():
        return None
    df = read_csv_any_encoding(path)
    return pd.to_datetime(df["Timestamp"], format="%Y-%m-%d %H:%M:%S.%f", errors="coerce").dropna()
