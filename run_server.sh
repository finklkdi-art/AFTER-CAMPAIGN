#!/usr/bin/env bash
# ============================================================
#  AFTER — Campaign intelligence, after the campaign.
#  사내망 서버 호스팅 실행 스크립트 (Linux / macOS)
#
#  .streamlit/config.toml 은 1인 로컬 환경(app.py) 전용이므로
#  건드리지 않고, 서버용 설정만 CLI 플래그로 덮어쓴다.
#  (CLI 플래그가 config.toml 보다 우선순위가 높다)
#
#  최초 1회:  chmod +x run_server.sh
#  실행:      ./run_server.sh          (기본 포트 8501)
#             ./run_server.sh 9000     (포트 지정)
# ============================================================

set -euo pipefail

cd "$(dirname "$0")"

PORT="${1:-8501}"

# 한글 파일명 처리를 위해 UTF-8 로케일을 강제한다 (claude.md 1)
export PYTHONIOENCODING="utf-8"
export LANG="${LANG:-C.UTF-8}"

PY="python3"
command -v "$PY" >/dev/null 2>&1 || PY="python"

echo
echo " ============================================================"
echo "  AFTER  |  서버 모드로 기동합니다"
echo " ============================================================"
echo "  포트          : ${PORT}"
echo "  바인딩        : 0.0.0.0  (사내망 전체 인터페이스)"
echo "  업로드 상한   : 200MB"
echo "  종료          : Ctrl+C"
echo " ------------------------------------------------------------"
echo "  사내망 접속 주소를 확인하려면 다른 창에서 'hostname -I' 실행"
echo " ============================================================"
echo

exec "$PY" -m streamlit run web_main.py \
  --server.address=0.0.0.0 \
  --server.port="${PORT}" \
  --server.maxUploadSize=200 \
  --server.headless=true \
  --browser.gatherUsageStats=false
