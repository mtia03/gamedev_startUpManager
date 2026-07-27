from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
import random
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

# 리포 루트의 .env를 읽는다 (서버는 web_mvp/backend에서 실행되므로 두 단계 위).
# 이미 설정된 환경 변수가 있으면 그쪽이 우선한다.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# 기존 모델 모듈 임포트 (폴더 내 파일)
from company_model import Corporate
from developer_model import Developer

app = FastAPI()

# CORS 설정 (개발 및 테스트 원활화를 위해 설정)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gemini API 클라이언트 초기화
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# 키가 없어도 서버는 뜨게 한다. genai.Client()는 빈 키를 받으면 즉시 예외를 던지므로
# 생성 자체를 건너뛰고, 면접 대화 API가 호출될 때만 막는다.
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
if client is None:
    print("[경고] GEMINI_API_KEY가 없습니다. 면접 대화를 제외한 기능만 동작합니다.")

# ── 턴 루프 튜닝 파라미터 ──────────────────────────────────────
# current_salary는 '연봉'으로 취급한다 (프론트 표기 및 채용 협상 기준과 동일).
WEEKS_PER_YEAR = 52

FATIGUE_PER_WEEK = 5        # 주당 누적 피로
FATIGUE_BURNOUT = 70        # 이 이상이면 사기가 깎이기 시작
MORALE_DROP_BURNOUT = 4     # 번아웃 상태의 주당 사기 감소
MORALE_RECOVER = 2          # 정상 근무 주의 사기 회복
MORALE_DROP_UNPAID = 25     # 급여 미지급 시 사기 폭락

TOXIC_THRESHOLD = 15        # 정신병 수치가 이 이상이면 주변에 악영향
TOXIC_MORALE_DROP = 2       # 빌런 1명당 다른 직원의 주당 사기 감소

# 휴식 주간: 그 주는 일을 시키지 않는다. 급여는 그대로 나간다.
REST_FATIGUE_RECOVER = 20   # 휴식 시 회복하는 피로
REST_MORALE_RECOVER = 5     # 휴식 시 회복하는 사기

# 퇴사 판정: 사기가 이 아래로 떨어지면 매주 확률적으로 퇴사한다.
MORALE_QUIT_THRESHOLD = 20  # 사기 0이면 확률 100%, 임계값이면 0%
FATIGUE_QUIT_LIMIT = 90     # 이 이상 지친 상태면 퇴사 확률 가산
FATIGUE_QUIT_BONUS = 0.15

# 연봉 산출: CA(총 능력치)에 비례한다.
# 실측 CA 평균 — None 34 / BD 76 / MD 120 / PhD 181
# → 대략 None $42k / BD $70k / MD $99k / PhD $140k 가 되도록 맞춘 계수
SALARY_PER_CA = 670
SALARY_BASE = 19000

# 난이도 프리셋: 시작 자금과 회사 평판을 결정한다.
# 평판은 developer_model의 학력 가중치 구간(5000 / 10000)을 각각 넘도록 잡아서
# 난이도마다 실제로 지원자 수준이 달라지게 한다.
DIFFICULTIES = {
    "easy":   {"label": "쉬움",   "funds": 500000, "reputation": 10000},
    "normal": {"label": "보통",   "funds": 300000, "reputation": 6000},
    "hard":   {"label": "어려움", "funds": 180000, "reputation": 2000},
}
DEFAULT_DIFFICULTY = "normal"


def productivity(dev):
    """사기·피로가 반영된 개인 업무 효율 (0.0~1.0).

    scripts/project_balance.py의 morale_eff와 동일한 식이다.
    프로젝트 시스템이 붙으면 이 값이 처리량에 그대로 곱해진다.
    """
    return (0.5 + 0.5 * dev.morale / 100) * (1 - 0.4 * dev.fatigue / 100)


# 인메모리 게임 글로벌 상태 관리자
class GameState:
    def __init__(self):
        # 시작 화면에서 설정을 받기 전까지는 빈 상태로 둔다.
        # 회사 객체 생성은 개발자를 대량 생성하는 무거운 작업이라 start()로 미룬다.
        self.is_started = False
        self.company = None
        self.difficulty = DEFAULT_DIFFICULTY
        self.desks = []
        self.candidates = {}
        self.conversation_histories = {}
        self.hired_employees = {}
        self.week = 1
        self.is_bankrupt = False

    def start(self, company_name, difficulty):
        """시작 화면의 설정으로 게임을 초기화한다. 이미 진행 중이면 새 판으로 덮어쓴다."""
        preset = DIFFICULTIES[difficulty]

        # 1. 플레이어의 스타트업 생성 (직원 0명으로 초기화)
        self.company = Corporate(0)
        self.company.corporateName = company_name
        self.company.staffNums = 0
        self.company.staff_tags = []
        self.company.reputation = preset["reputation"]
        self.company.funds = preset["funds"]
        self.difficulty = difficulty

        # 2. 오피스 책상 레이아웃 (그리드 좌표)
        self.desks = [
            {"id": 1, "x": 1, "y": 1, "developer_tag": None},
            {"id": 2, "x": 1, "y": 3, "developer_tag": None},
            {"id": 3, "x": 3, "y": 1, "developer_tag": None},
            {"id": 4, "x": 3, "y": 3, "developer_tag": None},
        ]

        # 3. 지원자 풀 (Pool)
        self.candidates = {}
        self.conversation_histories = {}  # dev_tag -> 대화 요약
        self.generate_new_candidates(3)

        # 4. 채용된 직원 객체 매핑 (tag -> Developer 인스턴스)
        self.hired_employees = {}

        # 5. 시간 진행 상태
        self.week = 1
        self.is_bankrupt = False
        self.is_started = True

    def weekly_payroll(self):
        """재직자 전원의 주당 급여 합계 (연봉 / 52)."""
        return sum(int(dev.current_salary / WEEKS_PER_YEAR)
                   for dev in self.hired_employees.values())

    def resign_employee(self, tag):
        """직원을 퇴사 처리하고 책상을 비운다."""
        dev = self.hired_employees.pop(tag)
        for desk in self.desks:
            if desk["developer_tag"] == tag:
                desk["developer_tag"] = None
        if tag in self.company.staff_tags:
            self.company.staff_tags.remove(tag)
        self.company.staffNums = len(self.hired_employees)
        return dev

    def advance_week(self, rest=False):
        """1주 진행: 급여 지출 → 사기·피로 변동 → 퇴사 판정.

        rest=True면 그 주는 일을 시키지 않는다 (피로 회복, 급여는 그대로 지출).
        발생한 사건 목록을 반환한다.
        """
        events = []
        payroll = self.weekly_payroll()
        if rest:
            events.append("이번 주는 휴식 주간입니다. 팀이 재충전합니다.")

        # 1. 급여 지급 (자금이 모자라면 미지급 처리)
        paid = payroll <= self.company.funds
        if paid:
            self.company.funds -= payroll
            if payroll:
                events.append(f"급여 ${payroll:,} 지급 (재직자 {len(self.hired_employees)}명)")
        else:
            events.append(
                f"자금 부족으로 급여 ${payroll:,}를 지급하지 못했습니다. 팀의 사기가 급락합니다.")

        # 2. 팀 내 유해 인원 수 (자기 자신은 제외하고 계산한다)
        toxic_tags = {tag for tag, dev in self.hired_employees.items()
                      if dev.psychological_issue >= TOXIC_THRESHOLD}
        if toxic_tags and len(self.hired_employees) > 1:
            events.append(f"팀 분위기를 해치는 인원 {len(toxic_tags)}명이 주변 사기를 갉아먹고 있습니다.")

        # 3. 직원별 상태 변동
        burnout_names = []
        for tag, dev in self.hired_employees.items():
            if rest:
                dev.fatigue = max(0, dev.fatigue - REST_FATIGUE_RECOVER)
            else:
                dev.fatigue = min(100, dev.fatigue + FATIGUE_PER_WEEK)

            if not paid:
                delta = -MORALE_DROP_UNPAID
            elif rest:
                delta = REST_MORALE_RECOVER
            else:
                delta = MORALE_RECOVER

            if dev.fatigue >= FATIGUE_BURNOUT:
                delta -= MORALE_DROP_BURNOUT
                burnout_names.append(f"{dev.first_name} {dev.last_name}")

            others_toxic = len(toxic_tags - {tag})
            delta -= others_toxic * TOXIC_MORALE_DROP

            dev.morale = max(0, min(100, dev.morale + delta))

        if burnout_names:
            events.append(f"번아웃 위험: {', '.join(burnout_names)}")

        # 4. 퇴사 판정 (사기가 낮을수록, 지쳐 있을수록 확률이 오른다)
        for tag, dev in list(self.hired_employees.items()):
            if dev.morale >= MORALE_QUIT_THRESHOLD:
                continue
            chance = (MORALE_QUIT_THRESHOLD - dev.morale) / MORALE_QUIT_THRESHOLD
            if dev.fatigue >= FATIGUE_QUIT_LIMIT:
                chance += FATIGUE_QUIT_BONUS
            if random.random() < chance:
                self.resign_employee(tag)
                events.append(f"{dev.first_name} {dev.last_name} 님이 회사를 떠났습니다. (사기 {dev.morale})")

        # 5. 파산 판정
        if not paid:
            self.is_bankrupt = True
            events.append("회사가 급여를 감당하지 못하는 상태입니다. (파산)")

        self.week += 1
        return {"payroll": payroll, "paid": paid, "events": events}

    def generate_new_candidates(self, count):
        for _ in range(count):
            dev = Developer(True, self.company.reputation)
            # 스탯에 비례한 연봉 산출 (기본값)
            dev.current_salary = int(dev.CA * SALARY_PER_CA + SALARY_BASE)
            dev.disliked_people = []
            
            self.candidates[dev.tag] = dev
            self.conversation_histories[dev.tag] = ""

game_state = GameState()


def require_started():
    """게임이 시작되지 않았으면 요청을 거부한다."""
    if not game_state.is_started:
        raise HTTPException(status_code=409, detail="게임이 아직 시작되지 않았습니다.")


# REST API 엔드포인트 정의
class SetupRequest(BaseModel):
    company_name: str
    difficulty: str = DEFAULT_DIFFICULTY

@app.get("/api/difficulties")
async def get_difficulties():
    """시작 화면에 표시할 난이도 목록"""
    return {
        "default": DEFAULT_DIFFICULTY,
        "options": [
            {"key": key, "label": v["label"],
             "funds": v["funds"], "reputation": v["reputation"]}
            for key, v in DIFFICULTIES.items()
        ]
    }

@app.post("/api/setup")
async def setup_game(req: SetupRequest):
    """시작 화면의 설정으로 게임을 시작한다 (이미 진행 중이면 새 판으로 초기화)."""
    name = req.company_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="회사명을 입력해주세요.")
    if len(name) > 30:
        raise HTTPException(status_code=400, detail="회사명은 30자 이내로 입력해주세요.")
    if req.difficulty not in DIFFICULTIES:
        raise HTTPException(status_code=400, detail="유효하지 않은 난이도입니다.")

    game_state.start(name, req.difficulty)
    return {
        "status": "success",
        "company_name": name,
        "difficulty": req.difficulty,
        "funds": game_state.company.funds,
        "reputation": game_state.company.reputation
    }

@app.get("/api/state")
async def get_state():
    """게임 상태 조회 (회사 정보, 책상 배치, 구직 지원자 리스트)"""
    if not game_state.is_started:
        return {"is_started": False}

    return {
        "is_started": True,
        "difficulty": game_state.difficulty,
        "company": {
            "name": game_state.company.corporateName,
            "reputation": game_state.company.reputation,
            "funds": game_state.company.funds,
            "staff_count": game_state.company.staffNums
        },
        "time": {
            "week": game_state.week,
            "weekly_payroll": game_state.weekly_payroll(),
            "is_bankrupt": game_state.is_bankrupt
        },
        "desks": game_state.desks,
        "candidates": [
            {
                "tag": dev.tag,
                "name": f"{dev.first_name} {dev.last_name}",
                "education": dev.education,
                "main_field": dev.main_field,
                "stats": dev.stats,
                "CA": dev.CA,
                "PA": dev.PA,
                "current_salary": dev.current_salary,
                "fatigue": dev.fatigue,
                "morale": dev.morale
            }
            for dev in game_state.candidates.values()
        ],
        "hired_employees": {
            tag: {
                "tag": dev.tag,
                "name": f"{dev.first_name} {dev.last_name}",
                "education": dev.education,
                "main_field": dev.main_field,
                "stats": dev.stats,
                "CA": dev.CA,
                "fatigue": dev.fatigue,
                "morale": dev.morale,
                "productivity": round(productivity(dev), 3)
            }
            for tag, dev in game_state.hired_employees.items()
        }
    }

class ChatRequest(BaseModel):
    developer_tag: str
    message: str

@app.post("/api/chat")
async def chat_with_candidate(req: ChatRequest):
    """구직 후보자와 LLM 면접 진행 API"""
    require_started()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY가 설정되지 않아 면접 대화를 사용할 수 없습니다.")
    dev_tag = req.developer_tag
    if dev_tag not in game_state.candidates:
        raise HTTPException(status_code=404, detail="지원자를 찾을 수 없습니다.")
        
    dev = game_state.candidates[dev_tag]
    previous_conversation = game_state.conversation_histories[dev_tag]
    
    # Strict JSON 스키마를 통해 AI의 답변 형식을 보장합니다.
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "dialogue": {"type": "STRING"},
            "past_conversation_summary": {"type": "STRING"},
            "hired": {"type": "BOOLEAN"},
            "salary_demanded": {"type": "INTEGER"}
        },
        "required": ["dialogue", "past_conversation_summary", "hired", "salary_demanded"]
    }
    
    system_instruction = """
    You are an AI agent acting as a software developer in a startup management game.
    Based on your current status and the user's recruitment proposal, decide whether to accept, negotiate, or reject.
    Give out KOREAN dialogue. Use English only for the summary.

    [TASK]
    1. Respond in KOREAN (dialogue). Make it realistic, matching the stats.
    2. Decide if you accept hiring (`hired` = true) or demand/negotiate salary (`hired` = false, but offer new `salary_demanded`).
    3. If the user offers a salary equal to or higher than your current_salary, you are more likely to accept.
    4. If the user treats you poorly or offers too low salary, reject or demand higher.
    5. In the JSON output, `hired` should be `true` only if you and the user have agreed and you accept to join. If you are still negotiating or rejecting, `hired` is `false`.
    6. Refuse immediately if the recruiter's reputation is too low for your class (e.g. PhD won't join low reputation).
    7. NEVER mention exact numeric stats in the dialogue (e.g., Do NOT say "My morale is 25%"). Speak naturally.
    """
    
    candidate_data = {
        "name": f"{dev.first_name} {dev.last_name}",
        "origin": dev.education,
        "tech_stack": dev.stats,
        "morale": dev.morale,
        "fatigue": dev.fatigue,
        "psychopath_score": dev.psychological_issue,
        "current_salary": dev.current_salary,
        "disliked_people": dev.disliked_people,
        "favorite_field": dev.main_field
    }
    
    player_company_info = {
        "company_name": game_state.company.corporateName,
        "reputation": game_state.company.reputation,
        "members": [f"{h.first_name} {h.last_name}" for h in game_state.hired_employees.values()]
    }
    
    prompt = f"""
    You are an AI developer looking for a job. Decide if you want to join this recruiter's startup.

    [YOUR CURRENT STATUS (Hidden Data)]
    {json.dumps(candidate_data, indent=4, ensure_ascii=False)}

    [RECRUITER'S COMPANY INFO]
    {json.dumps(player_company_info, indent=4, ensure_ascii=False)}

    [PREVIOUS CONVERSATION SUMMARY]
    {previous_conversation}
    
    [USER'S MESSAGE]
    "{req.message}"
    
    Respond accordingly and decide the values of `hired` and `salary_demanded`.
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=0.7
            )
        )
        
        if not response.text:
            raise HTTPException(status_code=500, detail="Gemini 응답이 비어있습니다.")
            
        result = json.loads(response.text)
        
        # 대화 요약 업데이트
        game_state.conversation_histories[dev_tag] = result["past_conversation_summary"]
        
        return {
            "dialogue": result["dialogue"],
            "hired": result["hired"],
            "salary_demanded": result["salary_demanded"]
        }
        
    except Exception as e:
        print(f"Error calling LLM: {e}")
        raise HTTPException(status_code=500, detail=f"LLM 처리 실패: {str(e)}")

class HireRequest(BaseModel):
    developer_tag: str
    desk_id: int
    salary: int

@app.post("/api/hire")
async def hire_developer(req: HireRequest):
    """지정된 책상에 채용한 직원을 배치하는 API"""
    require_started()
    if req.developer_tag not in game_state.candidates:
        raise HTTPException(status_code=404, detail="해당 지원자가 풀에 존재하지 않습니다.")
        
    # 빈 책상 확인
    target_desk = None
    for d in game_state.desks:
        if d["id"] == req.desk_id:
            target_desk = d
            break
            
    if not target_desk:
        raise HTTPException(status_code=400, detail="유효하지 않은 책상 ID입니다.")
    if target_desk["developer_tag"] is not None:
        raise HTTPException(status_code=400, detail="해당 책상에는 이미 다른 직원이 배치되어 있습니다.")

    # 급여는 채용 시 일시불로 빠지지 않고 매주 턴 진행에서 지출된다.
    # 여기서는 합의된 연봉을 계약 조건으로 확정만 한다.
    weekly_cost = int(req.salary / WEEKS_PER_YEAR)
    if game_state.company.funds < weekly_cost:
        raise HTTPException(
            status_code=400,
            detail="첫 주 급여도 지급할 수 없는 자금 상태입니다.")

    # 지원자 풀에서 제거하고 직원 풀에 등록
    dev = game_state.candidates.pop(req.developer_tag)
    dev.current_salary = req.salary
    game_state.conversation_histories.pop(req.developer_tag, None)
    
    target_desk["developer_tag"] = dev.tag
    game_state.hired_employees[dev.tag] = dev
    
    # 회사 직원 수 업데이트
    game_state.company.staff_tags.append(dev.tag)
    game_state.company.staffNums += 1
    
    # 구직자 후보 자동 충전 (항상 3명 유지)
    game_state.generate_new_candidates(1)
    
    return {
        "status": "success",
        "hired_developer": {
            "tag": dev.tag,
            "name": f"{dev.first_name} {dev.last_name}"
        },
        "desk_id": req.desk_id,
        "remaining_funds": game_state.company.funds,
        "weekly_cost": weekly_cost
    }

class AdvanceRequest(BaseModel):
    rest: bool = False

@app.post("/api/advance_week")
async def advance_week(req: AdvanceRequest = AdvanceRequest()):
    """1주를 진행하고 급여 지출과 직원 상태 변동을 적용하는 API

    rest=true면 휴식 주간으로 처리한다 (피로 회복, 급여는 그대로 지출).
    """
    require_started()
    if game_state.is_bankrupt:
        raise HTTPException(status_code=400, detail="이미 파산한 회사입니다. 더 진행할 수 없습니다.")

    result = game_state.advance_week(rest=req.rest)

    return {
        "status": "success",
        "week": game_state.week,
        "payroll": result["payroll"],
        "paid": result["paid"],
        "funds": game_state.company.funds,
        "is_bankrupt": game_state.is_bankrupt,
        "events": result["events"],
        "employees": [
            {
                "tag": dev.tag,
                "name": f"{dev.first_name} {dev.last_name}",
                "fatigue": dev.fatigue,
                "morale": dev.morale,
                "productivity": round(productivity(dev), 3)
            }
            for dev in game_state.hired_employees.values()
        ]
    }

# 프론트엔드 정적 파일 서빙 등록
# 백엔드가 실행될 작업 디렉토리 기준 상위/동일 레벨의 frontend 폴더를 연결합니다.
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
