# preprocessing_2nd: 2차 데이터 전처리

2차 데이터(2025.09 수집, sub1·3–14, 운동 10종, 균형/불균형, 자체 개발 디바이스로 좌·우 팔 동시 측정)를 NAS의 원본 CSV부터 모델 입력 파일까지 만드는 전처리 파이프라인입니다. **순서대로 실행되는 스크립트 5개**(step1–5)로 구성됩니다.

```
NAS CSV(좌·우) ─step2(점검)→ step3 전극 선택 → step4 좌우 병합 + label + beep (2000Hz) → step5 IMU 66Hz
(라벨 ─step1→ beep 보정 라벨 은 NAS 라벨을 만든 보정 과정. 참고용이며 실행할 필요 없음)
```

### 프로젝트 목적

**팔(상완)에 붙인 EMG/IMU만으로** 아래 세 가지가 가능한지 검증하는 프로젝트입니다 (삼성 산학). 2차 데이터는 자체 개발 디바이스를 **양팔 상완**에 하나씩 착용하고 수집했습니다.

| 과제 | 내용 | 이 파이프라인의 산출물 |
|---|---|---|
| 운동 종목 classification | 10종 운동 자동 인식 | `merged_dataset.csv` (STEP4), `imu_downsampled_66hz.csv` (STEP5) |
| 운동 횟수 counting | rep 자동 카운트, 운동 구간 인식 | `merged_dataset.csv`의 `label` (STEP4) |
| balance(불균형) detection | 좌우 근력·자세 불균형 인식 | `merged_dataset.csv` (STEP4) |

### 실험 개요

| 항목 | 내용 |
|---|---|
| 피험자 | 13명 (sub1, sub3–14). 9번 피험자는 BTE, Barbell Curl, Push-up, Pull-up을 수행하지 않음 |
| 운동 | 10종: Deadlift, Overhead Press(`ohp`), Dips, Bench Press, Barbell Curl, Barbell Row, Lat Pulldown(`lpd`), Barbell Triceps Extension(`bte`), Pull-up, Push-up |
| 균형 자세 | 운동별 4세트 × 6회. 1RM 적용 종목은 세트마다 자가 응답 1RM의 30–40% / 50–60% / 70% / 80% |
| 불균형 자세 | **Deadlift, Lat Pulldown, Overhead Press, Bench Press, BTE 5종뿐입니다.** 좌측·우측 불균형 각 1세트 × 6회, 약 50% 1RM |
| 영상 | 정면 촬영 |
| beep | ① 동작 신호: 한 번의 동작이 끝나면 다음 beep이 울리고 그에 맞춰 다음 rep 수행 (간격 일정하지 않음) ② 영상 ↔ 센서 시간 보정의 기준 (6절) |

### 센서 배치 (자체 개발 디바이스, 팔마다 1대, 디바이스마다 EMG 4ch + IMU 6축)

| 항목 | 내용 |
|---|---|
| 착용 | 오른팔·왼팔 상완에 디바이스 1대씩. 측정 1회 = **오른쪽 CSV 1개 + 왼쪽 CSV 1개** |
| EMG | 디바이스당 전극 4개 (`EMG0_Raw`–`EMG3_Raw`). **같은 근육에 전극 2개씩**: 0·1번이 한 쌍, 2·3번이 한 쌍. 2000 Hz, ADC 원시값 (기준선 약 1,858, 범위 0–3,744) |
| IMU | 디바이스당 가속도 3축 + 자이로 3축 (`ax, ay, az, gx, gy, gz`). 실제 갱신은 약 66 Hz이며, EMG와 같은 2000 Hz 행에 같은 값이 반복 저장됨 |

| 디바이스 | 0·1번 쌍 → `EMG_0` | 2·3번 쌍 → `EMG_2` |
|---|---|---|
| 오른팔 | **이두** → `right_biceps` | **삼두** → `right_triceps` |
| 왼팔 | **삼두** → `left_triceps` | **이두** → `left_biceps` |

- **좌우 배치가 반대입니다.** 오른팔은 0·1번이 이두, 왼팔은 0·1번이 삼두입니다.
- 이 파이프라인에서 센서를 쓰는 곳
  - STEP3 전극 선택: 쌍마다 전극 하나만 골라 `EMG_0`, `EMG_2`로 남김
  - STEP4 병합: 위 표대로 근육 이름을 붙이고 좌우를 합침 (EMG 4ch + IMU 12축)
  - STEP5 다운샘플: IMU 12축만 사용

---

## 목차
1. [폴더 구조](#1-폴더-구조)
2. [원본 데이터 준비](#2-원본-데이터-준비)
3. [실행](#3-실행)
4. [단계별 설명](#4-단계별-설명)
5. [최종 산출물](#5-최종-산출물)
6. [배경: 시간축과 라벨 보정](#6-배경-시간축과-라벨-보정)
7. [주의사항](#7-주의사항)

---

## 1. 폴더 구조

```
preprocessing_2nd/
├── README.md
├── run_all.sh                    # 전체 실행
├── requirements.txt
├── .gitignore                    # data/ 안의 실제 데이터는 올리지 않음 (폴더 구조만 유지)
├── src/
│   ├── config.py                 # 경로·샘플링·제외 조건·센서 매핑·수동 제외 목록
│   ├── common.py                 # 메타 로딩, 원본 파일 찾기, 시간 변환, 라벨/beep 읽기
│   ├── step1_fix_label_time.py   # (참고) 라벨 Abs_Time beep 보정 + 시각화 검수 제외. NAS 라벨을 만든 코드
│   ├── step2_check_inputs.py     # 입력 점검 (누락·매칭 실패 리포트)
│   ├── step3_select_channels.py  # 전극 쌍마다 전극 선택
│   ├── step4_merge.py            # 좌우 병합 + label + beep (2000Hz)
│   └── step5_downsample_imu.py   # IMU 66Hz 다운샘플
└── data/
    ├── emg_data/                 # ① 디바이스 원본 CSV (NAS 2nd/emg_data)                              ← 직접 넣기
    ├── labels/                   # ② 영상 라벨 CSV (NAS 2nd/data_label_fixed_no_sensor_error_files)   ← 직접 넣기
    ├── beep/                     # ③ beep 시각 CSV (NAS 2nd/beep)                                      ← 직접 넣기
    ├── meta/                     # ④ video_csv_info.xlsx (NAS 2nd/video_csv_info.xlsx)                 ← 직접 넣기
    ├── label_raw/                # (참고) 보정 전 영상 라벨 (NAS 2nd/data_label). step1을 돌릴 때만 사용
    ├── interim/                  # 중간 산출물 (자동 생성)
    └── output/                   # 최종 산출물 (자동 생성)
```

---

## 2. 원본 데이터 준비

파이프라인 입력은 아래 **4가지**이며, 모두 NAS `Public/2025_samsung/2nd/`에 있습니다. 정해진 위치에 두면 나머지(전극 선택, 병합, 라벨, 다운샘플)는 스크립트가 순서대로 만듭니다.

| | 원본 | → 둘 위치 |
|---|---|---|---|
| ① | 디바이스 CSV: NAS `Public/2025_samsung/2nd/emg_data/*.csv` (3,938개) | `data/emg_data/` | 
| ② | 영상 라벨: NAS `Public/2025_samsung/2nd/data_label_fixed_no_sensor_error_files/*.csv` (676개) | `data/labels/` | 
| ③ | beep 시각: NAS `Public/2025_samsung/2nd/beep/*.csv` (685개) | `data/beep/` | 
| ④ | 메타: NAS `Public/2025_samsung/2nd/video_csv_info.xlsx` (996행) | `data/meta/` | 

NAS `Public/2025_samsung/2nd/` 아래의 날짜별 폴더(`250909/` 등)와 `merged_dataset*.csv`는 필요 없습니다.

준비가 끝나면 3절 순서대로 실행합니다. 가장 먼저 step2가 네 입력이 서로 잘 맞는지 점검합니다.

### ① 디바이스 원본 CSV → `data/emg_data/`

NAS `Public/2025_samsung/2nd/emg_data/` 안의 CSV를 그대로 복사합니다 (하위 폴더가 있어도 재귀적으로 찾음).

```
data/emg_data/
├── Data_NINA11_2025.09.09_14.27.46_sub12_ohp_1_30_6.csv
├── Data_NINA12_2025.09.12_14.52.53_sub4_dips_1_0_6.csv
└── ...
```

| 규칙 | 설명 |
|---|---|
| 파일명 | `Data_NINA{장치}_{날짜}_{시각}_sub{ID}_{운동}_{1=bal/0=unbal}_{무게}_{rep}.csv`. **바꾸지 말 것.** 실험 중 직접 입력해 오타(`t_ohp`, `barbellcrul`, `deadlfit` 등)가 있지만, 파일명은 엑셀과 매칭하는 데만 쓰고 subject·운동 등은 모두 엑셀 값을 씀 |
| 매칭 | 파일명에서 **첫 `NINA` 이후 부분**으로 엑셀 `csv_filename_r` / `csv_filename_l`과 매칭. 앞에 붙은 접두사는 무시 |
| 등록 여부 | 엑셀 처리 대상 행(아래 ④)에 있는 파일만 처리 (없으면 step2가 `sensor_not_in_meta`로 알려줌) |
| 빈 파일 | 0바이트 CSV가 141개 있음. 모두 엑셀 처리 대상이 아니라 영향 없음 |

**CSV 형식**

| 컬럼 | 의미 |
|---|---|
| `Save_Time` | PC가 데이터 패킷을 받은 시각 `HH.MM.SS.ffffff`. 패킷 단위라 여러 행이 같은 값이고 간격이 불규칙 |
| `Index_Time` | 녹화 시작부터의 상대시간(초). **정확히 0.0005초(2000 Hz) 간격** |
| `EMG0_Raw`–`EMG3_Raw` | EMG 전극 4개. ADC 정수값 |
| `ax, ay, az, gx, gy, gz` | IMU 6축 (약 66 Hz 값이 2000 Hz 행에 반복) |
| `Session, Name, Exercise, Balance, KG, SET, Count` | 디바이스 앱이 기록한 정보 (사용하지 않음. 메타는 엑셀 기준) |

### ② 영상 라벨 CSV → `data/labels/<video_name>.csv`

영상을 보며 rep마다 찍은 Start / Peak / End 시각입니다. Abs_Time은 beep으로 보정된 값입니다 (4절 STEP 1, 6절).

```
data/labels/
├── 20250909_090739.csv
├── 20250916_095045.csv
└── ...
```

| 규칙 | 설명 |
|---|---|
| 파일명 | 영상 파일명에서 `.mp4`만 뺀 것. 엑셀 `video_name`과 매칭됨 |
| 컬럼 | `Index, Start, Peak, End, Abs_Time` (rep 1개 = 1행) |
| `Start, Peak, End` | 영상 기준 상대시간 `mm:ss.mmm` (일부는 소수 1자리 `mm:ss.m`) |
| `Abs_Time` | **영상 시작의 절대시각** `YYYY-MM-DD HH:MM:SS:mmm` (파일마다 한 값) |
| 인코딩 | UTF-8 또는 CP949 모두 읽음 |

NAS 라벨 폴더는 3개이며 **`data_label_fixed_no_sensor_error_files/`만 씁니다.**

| NAS 폴더 | 개수 | 내용 | 사용 |
|---|---|---|---|
| `Public/2025_samsung/2nd/data_label/` | 706 | 원본 라벨. 영상 시간 오류가 남아 있음 | ✗ (step1 입력) |
| `Public/2025_samsung/2nd/data_label_fixed/` | 711 | beep으로 보정한 라벨. 보정 후에도 맞지 않는 측정 포함 | ✗ |
| `Public/2025_samsung/2nd/data_label_fixed_no_sensor_error_files/` | 676 | 위에서 보정 후에도 EMG와 맞지 않는 측정 35개를 시각화 검수로 뺀 것 | **✓** |

라벨이 없는 측정은 step4에서 `label`이 전부 0이 됩니다 (step2가 `label_missing`으로 알려줌). 처리 대상 711건 중 63건입니다.
- 35건: 보정 후에도 EMG와 맞지 않아 시각화 검수에서 제외 (`config.py`의 `VISUAL_EXCLUDED_FILE_NO`)
- 28건: 어느 라벨 폴더에도 없음 (라벨링하지 않은 측정)

### ③ beep 시각 CSV → `data/beep/<beep_filename>`

측정 중 울린 beep(동작 신호음)의 절대시각입니다.

| 규칙 | 설명 |
|---|---|
| 파일명 | 엑셀 `beep_filename`과 같아야 함 |
| 컬럼 | `Rep Number, Timestamp` (`YYYY-MM-DD HH:MM:SS.mmm`) |

### ④ 메타데이터 → `data/meta/video_csv_info.xlsx`

측정 1회 = 1행입니다.

| 사용하는 컬럼 | 의미 |
|---|---|
| `video_name` | 영상 파일명 (`YYYYMMDD_HHMMSS.mp4`). 앞 8자리가 **측정 날짜**로 쓰이고, 라벨 파일 매칭 키 |
| `csv_filename_r`, `csv_filename_l` | 오른쪽·왼쪽 원본 CSV 파일명 (매칭 키. 한쪽만 있어도 됨) |
| `normal_data` | `o` / `v`인 행만 처리 (대소문자 무관). 그 외(`x` 등)는 제외 |
| `r_0`–`r_3`, `l_0`–`l_3` | 전극별 유효 표시. 실험 도중 관리자의 판단하에 노이즈 시각화 후 결정.  `o` / `v` = 사용 가능, 그 외 = 사용 불가 (step3 전극 선택 기준) |
| `subject_id, exercise, bal/unbal` | 피험자, 운동, 균형(`bal`)/불균형(`unbal`). 출력 메타이자 step3 전극 묶음 기준 |
| `beep_filename` | beep CSV 파일명 (없으면 beep 0) |
| `unbal_normalside` | 불균형 측정에서 **정상 쪽 팔** (`l` / `r`). 균형 측정에서는 비어 있음 |
| `weight_kg, rep` | 무게(kg, 맨몸 운동은 0 또는 추가 중량), 목표 반복 횟수 |
| `file_no` | 측정 번호. step1의 보정 엑셀·수동 제외 목록, 시각화 그림 파일명과 연결하는 키 |

**처리 제외 (`config.py`)**
- `csv_filename_r` / `csv_filename_l`에 `sub77`, `sub78`이 들어간 행: 예비 실험 (`EXCLUDED_SUBJECTS`)
- `exercise`가 `fatigue_*`, `MVC_*`인 행: 운동 프로토콜 밖의 추가 세션 (`EXCLUDED_EXERCISE_PREFIXES`)

### 참고: NAS 라벨의 출처 (beep 보정)

NAS `data_label_fixed_no_sensor_error_files/`는 원본 라벨 `data_label/`의 `Abs_Time`을 beep으로 보정하고, 보정 후에도 맞지 않는 측정을 시각화로 검수해 뺀 결과입니다. **전처리를 돌리는 데는 필요 없으며**, 보정 과정을 확인하거나 라벨을 새로 보정할 때만 참고합니다. 보정 코드는 `step1_fix_label_time.py`입니다 (4절 STEP 1).

| step1 입력 | NAS 경로 | → 둘 위치 |
|---|---|---|
| 보정 전 라벨 | `Public/2025_samsung/2nd/data_label/*.csv` (706개) | `data/label_raw/` |
| 보정 엑셀 | `Public/2025_samsung/2nd/abs_time_need_fix.xlsx` (484행) | `data/meta/` |
| beep, 메타 | 위 ③, ④와 같음 | `data/beep/`, `data/meta/` |

**보정 엑셀(`abs_time_need_fix.xlsx`)에서 쓰는 컬럼**

| 컬럼 | 의미 |
|---|---|
| `file_no` | 측정 번호 (`video_csv_info.xlsx`의 `file_no`와 같음) |
| `video_time_error` | `o` = 영상 시간 오류가 있어 보정 대상 (307건) |
| `first_beep` | 영상을 재생해 **첫 beep이 들리는 순간의 영상 표시 시각** (`HH:MM:SS.mmm`). 사람이 읽어 기록한 값 |

- 같은 엑셀의 `sensor_time_error = o`(25건)는 센서 시간 오류로 처음부터 라벨에서 뺀 측정이라 `data_label/`에 없습니다.
- `video_name` 열에는 영상 파일명이 아니라 예전 그림 파일명(`66_6_ohp_20.0_bal_LR_EMG.png`)이 들어 있어, step1은 `file_no`로 `video_csv_info.xlsx`에서 영상 파일명과 `beep_filename`을 찾습니다.

**시각화 검수에 쓴 그림** (이 폴더의 코드로 만든 것은 아님)

| NAS 경로 | 개수 | 내용 |
|---|---|---|
| `Public/2025_samsung/2nd/RMS_visualization_fin/<운동>/` | 837 | 라벨 구간만 잘라 그린 RMS. 회색 점선 = 라벨 시점 |
| `Public/2025_samsung/2nd/RMS_visualization_fin2/<운동>/` | 837 | 같은 측정의 녹화 전체 구간 RMS (점선 없음) |

- 운동 폴더: `barbellcurl, barbellrow, benchpress, bte, deadlift, dips, lpd, ohp, pullup, pushup, fatigue_a, fatigue_b`
- 파일명: `{file_no}_{subject_id}_{exercise}_{weight_kg}_{bal|unbal}_{video_name}.png`. 예: `RMS_visualization_fin/ohp/68_6_ohp_40.0_bal_20250909_093550.mp4.png`
- 그림 한 장 = 4칸. 칸마다 왼쪽 전극 i와 오른쪽 전극 3−i의 RMS를 겹쳐 그림 (L 0 & R 3, L 1 & R 2, L 2 & R 1, L 3 & R 0)
- 제외된 35건의 그림도 두 폴더에 모두 남아 있습니다.
- `RMS_visualization_fin/RMS_visualization/`은 파일명 규칙이 다른 이전 버전 그림입니다.

---

## 3. 실행

```bash
cd preprocessing_2nd
pip install -r requirements.txt

bash run_all.sh                       # step2→5 전체

# 또는 단계별 (위에서부터 순서대로)
python src/step2_check_inputs.py      # 입력 점검 (파일 수정 없음) → data/interim/input_check.csv 확인
python src/step3_select_channels.py   # 전극 쌍마다 전극 선택
python src/step4_merge.py             # 좌우 병합 + label + beep
python src/step5_downsample_imu.py    # IMU 66Hz
```

- **step2 결과는 꼭 확인하세요.** `input_check.csv`에 나온 파일은 이후 단계에서 빠지거나 일부 정보가 비게 됩니다 (4절 STEP 2 표 참고).
- 각 단계는 이전 단계 산출물만 있으면 따로 다시 돌릴 수 있습니다.
- step4, step5는 측정 단위로 이어 쓰므로 메모리를 많이 쓰지 않습니다. 대신 **step4 출력은 2000 Hz라 수 GB 단위**가 될 수 있습니다.
- OS 제한은 없습니다 (Mac/Windows/Linux).

---

## 4. 단계별 설명

```
(참고) label_raw/ + meta/abs_time_need_fix.xlsx + beep/ ── STEP1 ─→ interim/labels_fixed/,  interim/label_fix_report.csv

emg_data/ · labels/ · beep/ · meta/ ── STEP2 (점검) ─→ interim/input_check.csv

emg_data/ + meta/ ── STEP3 ─→ interim/preprocessed/*.csv,  output/channel_selection.csv
                                  │
                    STEP4 ←───────┘  (+ labels/, beep/, meta/)
                      └─→ output/merged_dataset.csv        (2000 Hz)
                                  │
                    STEP5 ←───────┘
                      └─→ output/imu_downsampled_66hz.csv  (66 Hz)
```

### STEP 1. (참고) 라벨 beep 보정: `step1_fix_label_time.py`
NAS 라벨(`data_label_fixed_no_sensor_error_files/`)을 만든 보정 과정입니다. **일반적인 전처리에서는 실행하지 않습니다.** 보정 과정을 확인하거나 라벨을 새로 보정할 때만 씁니다.

1. 보정 엑셀에서 `video_time_error = o`인 측정을 찾습니다.
2. **Δt 계산:** `Δt = first_beep(영상에서 들린 첫 beep, beep과 같은 날짜) − beep CSV의 첫 Timestamp`
3. `|Δt| > 5초`면 보정하지 않습니다 (`MAX_BEEP_DELTA_SEC`).
4. 라벨의 `Abs_Time`에서 Δt를 빼고 원래 형식(`YYYY-MM-DD HH:MM:SS:mmm`)으로 저장합니다.
5. **시각화 검수 제외:** `VISUAL_EXCLUDED_FILE_NO`(35건)는 저장하지 않습니다. 보정 대상이 아닌 나머지 라벨은 그대로 복사합니다.
6. 출력
   - `interim/labels_fixed/<video_name>.csv`: NAS `data_label_fixed_no_sensor_error_files/`에 해당
   - `interim/label_fix_report.csv`: 보정 대상별 `file_no, video_name, beep_filename, delta_sec, status`

```bash
python src/step1_fix_label_time.py
```


### STEP 2. 입력 점검: `step2_check_inputs.py`
출력: `interim/input_check.csv` (`issue, video_name, name, detail`)

| issue | 의미 | 조치 |
|---|---|---|
| `sensor_file_missing` | 엑셀에 있는 파일이 `emg_data/`에 없음. 그쪽(좌/우)이 빠짐 | 엑셀 `csv_filename_r/l` 철자 확인 |
| `sensor_missing_columns` | 원본 CSV에 필요한 컬럼이 없음 | 원본 확인 |
| `sensor_not_in_meta` | 원본 CSV가 엑셀 처리 대상 행에 없음 (`normal_data`, 예비 실험, MVC·fatigue 제외 포함) | 원래 빠지는 게 맞음 |
| `meta_no_r_file` / `meta_no_l_file` | 엑셀에 한쪽 파일명이 비어 있음. 반대쪽 컬럼 NaN | 확인만 |
| `channel_pair_invalid` | 전극 쌍 두 개가 모두 유효 표시 아님. 해당 `EMG_0` / `EMG_2` NaN | 확인만 |
| `label_missing` / `label_missing_columns` | 라벨 파일 없음 / 컬럼 부족. `label` 전부 0 | 2절 ② 참고 |
| `beep_not_assigned` / `beep_missing` | `beep_filename` 없음 / 파일 없음. `beep` 전부 0 | 확인만 |
| `meta_no_video_name` | `video_name` 비어 있음. 행 전체 제외 | 엑셀 확인 |

### STEP 3. 전극 선택: `step3_select_channels.py`
같은 근육에 붙은 전극 2개 중 하나를 골라 `EMG_0`(0·1번 쌍), `EMG_2`(2·3번 쌍)로 남깁니다. 기준은 엑셀의 전극별 유효 표시(`{r,l}_0`–`{r,l}_3`)이며, **같은 사람·같은 운동의 측정들이 모두 같은 전극을 쓰도록** 고정합니다.

| 순서 | 내용 |
|---|---|
| 1 | **묶음 단위로 전극 고정.** 묶음 = (subject, 운동, 균형/불균형, 좌/우). 모두 엑셀 값(`subject_id`, `exercise`, `bal/unbal`). 쌍마다 묶음 안에서 **유효 표시가 더 많은 전극**을 고름 (같으면 앞 번호, 둘 다 0회면 선택 없음) |
| 2 | **파일별 적용.** 고정된 전극이 그 측정에서도 유효하면 사용. 유효하지 않으면 **다른 전극으로 바꾸지 않고 그 쌍을 비움** (이후 NaN) |

**예시** (같은 묶음의 측정 3개, 0·1번 쌍)

| 측정 | `r_0` | `r_1` | 결과 |
|---|---|---|---|
| 1 | o | o | `r_0` |
| 2 | x | o | 비움 (묶음 고정 전극 `r_0`이 무효) |
| 3 | o | x | `r_0` |

→ 묶음 안에서 `r_0` 유효 2회, `r_1` 유효 2회로 같으므로 앞 번호 `r_0`으로 고정

**출력**
- `interim/preprocessed/<엑셀 파일명>.csv`: 원본에서 `EMG0_Raw`–`EMG3_Raw`를 지우고 선택된 전극만 `EMG_0`, `EMG_2`로 남긴 파일
- `output/channel_selection.csv`: 파일마다 `video_name, side, csv_filename, group`(묶음), `EMG_0_from` / `EMG_2_from`(실제 쓴 전극, 예: `r_1`, 비면 `None`), `EMG_0_group_choice` / `EMG_2_group_choice`(묶음 고정 전극)

### STEP 4. 좌우 병합 + label + beep: `step4_merge.py`
측정(`video_name`) 1건마다:
1. `interim/preprocessed/`의 오른쪽·왼쪽 파일에서 `Save_Time, Index_Time, EMG_0, EMG_2, IMU 6축`만 남깁니다.
2. **시간축:** `TimeStamp = video_name 날짜 + 첫 행 Save_Time + Index_Time` (6절).
3. **이름 변경:** 센서 배치 표대로 `right_biceps, right_triceps, left_triceps, left_biceps`, IMU는 `right_ax…`, `left_ax…`.
4. **좌우 병합:** 오른쪽 시간축에 왼쪽을 가장 가까운 `TimeStamp`로 붙입니다 (`pandas.merge_asof`, `direction="nearest"`). 한쪽 파일만 있으면 그쪽만 쓰고 반대쪽 컬럼은 NaN입니다.
5. **`label`:** 라벨의 절대시각(6절)에 가장 가까운 샘플에 `1` = Start, `2` = Peak, `3` = End. 나머지는 `0`.
6. **`beep`:** beep 시각에 가장 가까운 샘플에 `1`. 나머지는 `0`.
7. 엑셀 메타 컬럼을 붙입니다.

라벨이나 beep 개수가 실제로 표시된 개수와 다르면 (같은 샘플에 겹친 경우) `[경고]`로 출력합니다.

**출력:** `output/merged_dataset.csv` (2000 Hz)
```
TimeStamp, Index_Time, Save_Time,
right_biceps, right_triceps, left_triceps, left_biceps,
right_ax, right_ay, right_az, right_gx, right_gy, right_gz,
left_ax,  left_ay,  left_az,  left_gx,  left_gy,  left_gz,
beep, label,
csv_filename_r, csv_filename_l, subject_id, bal/unbal, exercise, weight_kg, video_name, rep, unbal_normalside, beep_filename
```

### STEP 5. IMU 다운샘플: `step5_downsample_imu.py`
IMU 기반 모델용 66 Hz 데이터를 만듭니다. IMU의 실제 갱신은 약 66 Hz이고 2000 Hz 행에는 같은 값이 반복되어 있기 때문입니다.
- 측정마다 IMU 12축만 `scipy.signal.resample`(FFT 방식)로 리샘플합니다. 샘플 수 = 원본 행 수 × 66 / 2000.
- `TimeStamp`는 측정 시작~끝을 균등 간격으로 다시 만듭니다.
- EMG, `label`, `beep`은 포함하지 않습니다.
- 한쪽 파일만 있는 측정은 반대쪽 IMU가 NaN으로 남습니다. 66 Hz 기준 10샘플 미만인 측정은 건너뜁니다.

**출력:** `output/imu_downsampled_66hz.csv`
```
TimeStamp, right_ax..right_gz, left_ax..left_gz, video_name, subject_id, exercise, weight_kg, rep, bal/unbal, unbal_normalside
```

---

## 5. 최종 산출물

| 파일 | 위치 | 생성 단계 | 쓰는 곳 |
|---|---|---|---|
| `merged_dataset.csv` | `data/output/` | STEP4 | 2000 Hz 좌우 EMG(이두·삼두) + IMU + `label`(0/1/2/3) + `beep` + 메타. 운동 분류, counting, 불균형 분류 |
| `imu_downsampled_66hz.csv` | `data/output/` | STEP5 | 66 Hz 좌우 IMU + 메타. IMU 기반 모델 |
| `channel_selection.csv` | `data/output/` | STEP3 | 파일별 선택 전극 검수 |
| `preprocessed/*.csv` | `data/interim/` | STEP3 | 전극 선택만 끝난 파일별 원본 |
| `input_check.csv` | `data/interim/` | STEP2 | 입력 점검 |

---

## 6. 배경: 시간축과 라벨 보정

### 연구 목적
운동 수행 중 기록된 **EMG/IMU 신호**와 **비디오 기반 수동 라벨링(Start / Peak / End)** 을 같은 절대시간축에 올려, 샘플 단위 라벨이 붙은 학습 데이터를 만듭니다. 

### 문제 정의

| 구분 | 문제 |
|---|---|
| 센서 | `Save_Time`은 PC가 패킷을 받은 시각이라 여러 행이 같은 값이고 간격이 불규칙 (0.00003–0.1초). 샘플 시각으로 그대로 쓸 수 없음 |
| 비디오 라벨 | 영상 기준 **상대시간** + 영상 시작 절대시각(`Abs_Time`)으로 기록됨. 촬영 앱의 시각이 실제와 어긋나거나 `Abs_Time`이 누락·오기입된 경우가 있음 (영상 시간 오류) |
| 센서 시간 오류 | 센서 파일에 잘못된 절대시간이 저장된 경우가 있음. 예: 첫 rep이 첫 beep보다 앞에 기록됨 |
| 기준 | **beep 기록 시각과 센서 절대시간은 일치**하므로 beep을 영상 ↔ 센서 보정 기준으로 씀 |

### 해결 로직

**① 센서 시간축** (STEP4)
첫 행의 `Save_Time`만 녹화 시작 시각으로 쓰고, 각 샘플 시각은 정확히 0.0005초 간격인 `Index_Time`을 더해 만듭니다. 

```
TimeStamp = (video_name 앞 8자리 날짜) + (첫 행 Save_Time) + Index_Time
```

**② 영상 시간 오류 보정** (STEP1)
영상을 재생해 **첫 번째 beep이 들리는 순간**의 영상 표시 시각(`first_beep`)을 읽고, beep 기록 파일의 **첫 beep 실제 절대시각**과의 차이 Δt를 라벨 `Abs_Time`에서 뺍니다. 
예: `20250916_095045.mp4`는 첫 beep 기록 시각이 09:50:54.545인데 영상에서는 약 09:50:56에 들림 → 이 차이만큼 `Abs_Time`을 앞당김. 영상 시각은 눈으로 읽은 값이라 수십 ms 오차가 있습니다. 

**③ 시각화 검수 및 제외** (STEP1)
보정 후에도 라벨과 EMG가 맞지 않는 측정은 측정별 RMS 그림(2절 참고)을 하나씩 보고 수동으로 제외했습니다 (35건, `VISUAL_EXCLUDED_FILE_NO`). 센서 시간 오류 측정(25건)은 보정할 기준이 없어 처음부터 라벨에서 뺐습니다. 

**④ 라벨을 샘플에 표시** (STEP4)
보정된 `Abs_Time`에 상대시간을 더해 rep별 절대시각을 구하고, 가장 가까운 센서 샘플에 라벨을 찍습니다.

```
Abs_Start = Abs_Time + Start,   Abs_Peak = Abs_Time + Peak,   Abs_End = Abs_Time + End
```

`merged_dataset.csv`의 `beep` 컬럼은 각 동작 신호의 시각이자 보정 기준점이므로 라벨 위치를 검토할 때 함께 볼 수 있다. 정상 기록이라면 각 rep이 beep 직후에 시작한다.
