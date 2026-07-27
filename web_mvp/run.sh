#!/bin/bash

# Dream Startup Game Web MVP 구동 스크립트
# uvicorn 서버를 실행하여 백엔드 API 및 프론트엔드를 호스팅합니다.

echo "=================================================="
echo "🚀 Dream Startup Game Web MVP 서버를 시작합니다..."
echo "=================================================="

# 스크립트 파일 위치 기준 backend 폴더로 진입
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR/backend" || exit

# uv 가상환경이 동작하고 있는지 확인하고, 필요하다면 활성화/의존성 확인
# FastAPI와 uvicorn이 실행 가능한지 여부에 따라 uv run을 통해 실행합니다.
if command -v uv &> /dev/null; then
    echo "Using 'uv' environment to run the server."
    uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
else
    echo "'uv' not found. Trying to run with python3/uvicorn."
    python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
fi
