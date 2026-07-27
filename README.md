# Dream Startup — 스타트업 경영 시뮬레이션

IT 스타트업을 창업해 개발자를 채용하고 프로젝트를 굴리는 경영 시뮬레이션 게임입니다.
채용 면접을 LLM과의 자유 대화로 진행하는 것이 핵심 아이디어이고, 현재는 그 부분을
검증하는 웹 MVP와 밸런스 설계 문서가 있는 프로토타입 단계입니다.

## 무엇이 돌아가나

**웹 MVP** (`web_mvp/`) — FastAPI 백엔드 + 정적 프론트엔드로 만든 채용 루프 데모입니다.

**시작 화면**에서 회사명과 난이도를 정하면 게임이 시작됩니다. 난이도는 시작 자금과
회사 평판을 결정하고, 평판은 지원자 학력 분포에 직접 영향을 줍니다.

| 난이도 | 시작 자금 | 평판 | 200명 표본 PhD |
|---|---|---|---|
| 쉬움 | $500,000 | 10,000 | 13명 |
| 보통 | $300,000 | 6,000 | 5명 |
| 어려움 | $180,000 | 2,000 | 1명 |

- 지원자 3명이 항상 대기하고, 채용하면 자동으로 새 지원자가 충전됩니다
- 각 지원자와 **자연어로 면접 대화**를 나눌 수 있습니다 (Gemini 사용)
- 마음에 들면 연봉을 제시하고 빈 책상에 배치해 채용합니다
- 자금이 부족하거나 책상이 차 있으면 채용이 거부됩니다

**주차를 진행**하면 매주 급여가 나가고 팀 상태가 변합니다.

- 일할수록 피로가 쌓이고, 피로가 높으면 사기가 깎입니다
- 사기가 바닥나면 **직원이 퇴사**하고 책상이 비워집니다
- 정신병 수치가 높은 직원은 주변 동료의 사기를 갉아먹습니다
- 급여를 못 주면 사기 폭락과 함께 파산합니다
- **휴식 주간**을 쓰면 피로를 회복하지만 급여는 그대로 나갑니다

게임 상태는 서버 메모리에만 있어서 재시작하면 초기화됩니다.

**도메인 모델** (`company.py`, `developer.py`) — 회사와 개발자를 생성하는 코어 로직입니다.
개발자는 6개 필드(FE · BE · Mobile · AI · Ops · UIUX) 스탯과 주력 분야를 가지며, 학력(None ·
BD · MD · PhD)에 따라 스탯 분포가 달라집니다. 회사 명성(reputation)이 높을수록 고학력
지원자가 나올 확률이 올라갑니다. `main.py`를 실행하면 샘플 데이터를 만들어 JSON으로 떨궈줍니다.

## 실행

Python 3.13과 [uv](https://docs.astral.sh/uv/)가 필요합니다.

### 1. 의존성 설치

```bash
uv sync
```

### 2. API 키 설정

면접 대화 기능은 Gemini API를 씁니다. [Google AI Studio](https://aistudio.google.com/apikey)에서
키를 발급받아 환경 변수로 넣어주세요.

```bash
$env:GEMINI_API_KEY = "발급받은_키"
```

macOS/Linux는 `export GEMINI_API_KEY="발급받은_키"` 를 쓰면 됩니다.
키 없이도 서버는 뜨지만 면접 대화만 실패합니다.

### 3. 서버 실행

`web_mvp/backend` 디렉터리에서 실행해야 합니다 (프론트엔드 경로가 상대경로로 잡혀 있습니다).

```bash
uv run uvicorn main:app --reload --port 8000
```

macOS/Linux는 `./web_mvp/run.sh` 로 한 번에 실행할 수 있습니다.
브라우저에서 `http://localhost:8000` 을 열면 됩니다.

### 도메인 모델만 돌려보기

```bash
uv run python main.py
```

회사 3개와 개발자 2명을 만들어 `corporate.json`, `dev.json`으로 저장합니다.

## API

| 메서드 | 경로 | 설명 |
|---|---|---|
| `GET` | `/api/difficulties` | 시작 화면에 표시할 난이도 목록 |
| `POST` | `/api/setup` | 회사명·난이도로 게임 시작 (재호출 시 새 판으로 초기화) |
| `GET` | `/api/state` | 회사 정보, 책상 배치, 지원자 목록, 재직자 목록 조회 |
| `POST` | `/api/chat` | 지원자와 면접 대화 (`developer_tag`, `message`) |
| `POST` | `/api/hire` | 책상을 지정해 채용 (`developer_tag`, `desk_id`, `salary`) |
| `POST` | `/api/advance_week` | 1주 진행 — 급여 지출, 사기·피로 변동, 퇴사·파산 판정 (`rest`) |

## 구조

```
├── company.py / developer.py    # 회사 · 개발자 도메인 모델
├── main.py                      # 모델 동작 확인용 CLI 진입점
├── pygrammer.py                 # LLM으로 회사명 후보 생성 → CSV
├── chatTest.py                  # 면접 프롬프트 실험용 스크립트
├── jsonTest.py                  # 생성 데이터 확인용 tkinter 뷰어
├── resources/                   # 이름 · 성 · 회사명 데이터셋
├── scripts/                     # 밸런스 시뮬레이션 (아래 참고)
├── docs/                        # 설계 문서
└── web_mvp/
    ├── backend/                 # FastAPI 서버
    └── frontend/                # 정적 UI
```

## 설계 문서

- [`docs/devlog-2026-07-27.md`](docs/devlog-2026-07-27.md) — 턴 루프 · 사업 시스템 · 협상 재설계 개발 기록
- [`docs/llm-prompt-design.md`](docs/llm-prompt-design.md) — 면접 · 요구치 산출 프롬프트 설계와 작업 백로그
- [`docs/project-requirement-model.md`](docs/project-requirement-model.md) — 프로젝트 요구 모델
- [`docs/project-scale-spec.md`](docs/project-scale-spec.md) — 규모별 스펙 정의

## 밸런스 스크립트

수치 튜닝용 시뮬레이터입니다. 리포 루트에서 실행하세요.

```bash
uv run python scripts/stat_survey.py
```

- `stat_survey.py` — 현재 생성기가 뽑는 개발자 스탯 분포 측정
- `scale_model.py` — 프로젝트 규모 → 요구 인원 · 능력치 공식 산출
- `project_balance.py` — 규모별 적정 인원과 완료 주차 시뮬레이션

## 현재 한계

- 게임 상태가 인메모리라 서버 재시작 시 초기화됩니다
- 채용과 주차 진행까지 동작하고, 프로젝트 착수·진행은 아직 미구현입니다
- **수입이 없습니다.** 지출만 있어서 오래 진행하면 반드시 파산합니다
- CORS가 전체 허용(`*`)이라 로컬 개발 전용입니다
