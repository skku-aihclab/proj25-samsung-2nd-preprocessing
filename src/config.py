"""
2차 데이터 전처리 공통 설정 (경로, 샘플링, 채널 선택 파라미터, 센서 매핑)
모든 경로는 preprocessing_2nd/ 폴더 기준으로 자동 계산됨
"""
from pathlib import Path

# ── 경로 ──
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"

EMG_DIR    = DATA_DIR / "emg_data"   # 디바이스 원본 CSV (좌·우 따로)
LABEL_DIR  = DATA_DIR / "labels"     # 영상 라벨(시간 보정본): labels/<video_name>.csv
LABEL_RAW_DIR = DATA_DIR / "label_raw"  # step1(참고): 보정 전 영상 라벨 (NAS data_label/)
BEEP_DIR   = DATA_DIR / "beep"       # beep 시각: beep/<beep_filename>
META_PATH  = DATA_DIR / "meta" / "video_csv_info.xlsx"
FIX_INFO_PATH = DATA_DIR / "meta" / "abs_time_need_fix.xlsx"   # step1(참고): first_beep, video_time_error
INTERIM_DIR = DATA_DIR / "interim"
OUTPUT_DIR  = DATA_DIR / "output"

LABEL_FIXED_DIR   = INTERIM_DIR / "labels_fixed"              # step1(참고): 보정 + 검수 제외 후 라벨
LABEL_FIX_REPORT_CSV = INTERIM_DIR / "label_fix_report.csv"   # step1(참고)
INPUT_CHECK_CSV   = INTERIM_DIR / "input_check.csv"           # step2
SELECTED_DIR      = INTERIM_DIR / "preprocessed"              # step3: 채널 선택 후 CSV
CHANNEL_SELECTION_CSV = OUTPUT_DIR / "channel_selection.csv"  # step3: 파일별 선택 전극
MERGED_CSV        = OUTPUT_DIR / "merged_dataset.csv"         # step4: 2000Hz 좌우 병합 + label + beep
IMU_66HZ_CSV      = OUTPUT_DIR / "imu_downsampled_66hz.csv"   # step5: IMU 66Hz

# ── 대상 행 ──
VALID_NORMAL_DATA = ("o", "v")          # video_csv_info.xlsx normal_data
EXCLUDED_SUBJECTS = ("sub77", "sub78")  # 예비 실험
EXCLUDED_EXERCISE_PREFIXES = ("fatigue", "mvc")   # 추가 세션(fatigue_a/b, MVC_b/t) 제외

# ── 라벨 보정 (step1, 참고) ──
MAX_BEEP_DELTA_SEC = 5.0   # |Δt|가 이보다 크면 보정하지 않음
# 보정 후에도 라벨과 EMG가 맞지 않아 시각화(RMS_visualization_fin*)를 보고 제외한 측정 (video_csv_info.xlsx file_no)
VISUAL_EXCLUDED_FILE_NO = [
    122, 123, 124, 125, 126, 127, 141, 142, 143, 144, 145, 148, 149,
    544, 546, 547, 551, 552, 553, 554, 556, 557, 567, 568, 569, 570,
    574, 577, 578, 579, 580, 582, 583, 852, 853,
]

# ── 샘플링 ──
FS = 2000                # EMG·IMU 기록 주파수 (Index_Time 간격 0.5ms)
IMU_TARGET_FS = 66       # step5

# ── 채널 선택 (step3) ──
CHANNEL_PAIRS = [(0, 1), (2, 3)]   # 같은 근육에 붙은 전극 쌍 → 쌍마다 하나 선택해 EMG_0, EMG_2로 저장

# ── 센서 매핑 (step4) ──
# 좌우 디바이스의 전극 배치가 반대: 오른쪽 EMG_0=이두, 왼쪽 EMG_0=삼두
EMG_RENAME = {
    "r": {"EMG_0": "right_biceps", "EMG_2": "right_triceps"},
    "l": {"EMG_0": "left_triceps", "EMG_2": "left_biceps"},
}
IMU_AXES = ["ax", "ay", "az", "gx", "gy", "gz"]
EMG_COLS = ["right_biceps", "right_triceps", "left_triceps", "left_biceps"]
IMU_COLS = [f"{side}_{a}" for side in ("right", "left") for a in IMU_AXES]

LABEL_CODE = {"Start": 1, "Peak": 2, "End": 3}   # step4 멀티클래스 label (0 = 없음)

META_COLS = ["csv_filename_r", "csv_filename_l", "subject_id", "bal/unbal", "exercise",
             "weight_kg", "video_name", "rep", "unbal_normalside", "beep_filename"]
IMU_META_COLS = ["video_name", "subject_id", "exercise", "weight_kg", "rep", "bal/unbal", "unbal_normalside"]
