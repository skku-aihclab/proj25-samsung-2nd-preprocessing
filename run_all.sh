#!/usr/bin/env bash
# 2차 데이터 전처리 전체 실행 (preprocessing_2nd/ 에서: bash run_all.sh)
# 입력: data/emg_data, data/labels, data/beep, data/meta
# step1(라벨 beep 보정)은 data/labels 를 만든 참고용 코드라 포함하지 않음
set -e
cd "$(dirname "$0")"
python src/step2_check_inputs.py
python src/step3_select_channels.py
python src/step4_merge.py
python src/step5_downsample_imu.py
