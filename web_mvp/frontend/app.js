// 글로벌 상태 관리
let gameState = {
    company: null,
    time: null,
    selectedDifficulty: 'normal',
    desks: [],
    candidates: [],
    hiredEmployees: {},
    selectedCandidateTag: null,
    isPlacementMode: false,
    placementCandidateTag: null,
    placementSalary: 0
};

// Canvas 설정
const canvas = document.getElementById('game-canvas');
const ctx = canvas.getContext('2d');
let canvasWidth = 0;
let canvasHeight = 0;

// 아이소메트릭 그리드 설정
const gridSize = 5; // 5x5 그리드 오피스
const tileWidth = 80;
const tileHeight = 40;
let originX = 0;
let originY = 0;

// 색상 팔레트 (Neon Dark UI에 적합한 Low-poly 색상)
const COLORS = {
    floor: '#1a1d29',
    floorBorder: '#2e344d',
    deskLeft: '#4b5563',
    deskRight: '#374151',
    deskTop: '#6b7280',
    monitorBody: '#1f2937',
    monitorScreen: '#0284c7',
    monitorScreenGlow: '#38bdf8',
    chairLeft: '#3b82f6',
    chairRight: '#2563eb',
    chairTop: '#60a5fa',
    skin: '#fbcfe8',
    shirtLeft: '#8b5cf6',
    shirtRight: '#6d28d9',
    shirtTop: '#a78bfa',
    hair: '#1e1b4b',
    gridHighlight: 'rgba(16, 185, 129, 0.4)',
    gridHighlightBorder: '#10b981'
};

// 페이지 로드 시 초기화
window.addEventListener('load', () => {
    setupEventListeners();
    loadDifficulties();
    fetchGameState().then(() => {
        // 게임 루프 시작 (시작 화면 단계에서도 돌지만 캔버스가 숨겨져 있어 무해하다)
        requestAnimationFrame(gameLoop);
    });
});

window.addEventListener('resize', resizeCanvas);

function resizeCanvas() {
    const rect = canvas.parentElement.getBoundingClientRect();
    canvasWidth = rect.width;
    canvasHeight = rect.height;
    canvas.width = canvasWidth;
    canvas.height = canvasHeight;
    
    // 그리드 원점 정중앙 설정
    originX = canvasWidth / 2;
    originY = canvasHeight / 2 - 40;
}

// REST API 호출 - 게임 상태 받아오기
// ----------------------------------------------------
// 🚀 시작 세팅 화면
// ----------------------------------------------------
function showSetupScreen() {
    document.getElementById('setup-screen').classList.remove('d-none');
    document.getElementById('game-container').classList.add('d-none');
    document.getElementById('setup-company-name').focus();
}

function showGameScreen() {
    document.getElementById('setup-screen').classList.add('d-none');
    document.getElementById('game-container').classList.remove('d-none');
    // 숨겨져 있는 동안 캔버스 크기가 0이었으므로 노출 직후 다시 계산한다
    resizeCanvas();
}

// 난이도 목록을 백엔드에서 받아 버튼으로 렌더링
async function loadDifficulties() {
    try {
        const response = await fetch('/api/difficulties');
        if (!response.ok) throw new Error('난이도 목록을 불러올 수 없습니다.');
        const data = await response.json();

        gameState.selectedDifficulty = data.default;
        const listEl = document.getElementById('difficulty-list');
        listEl.innerHTML = '';

        data.options.forEach(opt => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = `difficulty-option ${opt.key === data.default ? 'active' : ''}`;
            btn.dataset.key = opt.key;
            btn.innerHTML = `
                ${opt.label}
                <span class="difficulty-meta">
                    자금 $${(opt.funds / 1000).toLocaleString()}k<br>평판 ${opt.reputation.toLocaleString()}
                </span>
            `;
            btn.onclick = () => selectDifficulty(opt.key);
            listEl.appendChild(btn);
        });
    } catch (error) {
        showSetupError('난이도 목록을 불러오지 못했습니다: ' + error.message);
    }
}

function selectDifficulty(key) {
    gameState.selectedDifficulty = key;
    document.querySelectorAll('.difficulty-option').forEach(el => {
        el.classList.toggle('active', el.dataset.key === key);
    });
}

function showSetupError(text) {
    const el = document.getElementById('setup-error');
    el.textContent = text;
    el.classList.remove('d-none');
}

// 창업하기 → 게임 시작
async function startGame() {
    const btn = document.getElementById('setup-start-btn');
    const name = document.getElementById('setup-company-name').value.trim();

    if (!name) {
        showSetupError('회사명을 입력해주세요.');
        return;
    }

    btn.disabled = true;
    try {
        const response = await fetch('/api/setup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                company_name: name,
                difficulty: gameState.selectedDifficulty
            })
        });
        const data = await response.json();

        if (!response.ok) {
            showSetupError(data.detail || '게임을 시작할 수 없습니다.');
            return;
        }

        document.getElementById('setup-error').classList.add('d-none');
        await fetchGameState();
        showToast(`🚀 ${data.company_name} 창업! 좋은 개발자를 모아보세요.`);
    } catch (error) {
        showSetupError('시작 실패: ' + error.message);
    } finally {
        btn.disabled = false;
    }
}

async function fetchGameState() {
    try {
        const response = await fetch('/api/state');
        if (!response.ok) throw new Error('상태를 불러올 수 없습니다.');
        const data = await response.json();

        // 아직 창업 전이면 시작 화면을 띄우고 나머지는 건너뛴다
        if (!data.is_started) {
            showSetupScreen();
            return;
        }
        showGameScreen();

        gameState.company = data.company;
        gameState.time = data.time;
        gameState.desks = data.desks;
        gameState.candidates = data.candidates;
        gameState.hiredEmployees = data.hired_employees;
        
        updateUI();
    } catch (error) {
        showToast('❌ 서버 연결 실패: ' + error.message);
    }
}

// UI 갱신 함수
function updateUI() {
    if (!gameState.company) return;

    // 회사 현황 업데이트
    document.getElementById('company-name').textContent = gameState.company.name;
    document.getElementById('company-funds').textContent = `$${gameState.company.funds.toLocaleString()}`;
    document.getElementById('company-reputation').textContent = gameState.company.reputation.toLocaleString();
    document.getElementById('company-staff').textContent = `${gameState.company.staff_count} 명`;

    // 시간 진행 현황
    if (gameState.time) {
        document.getElementById('company-week').textContent = `${gameState.time.week} 주차`;
        document.getElementById('company-payroll').textContent =
            `$${gameState.time.weekly_payroll.toLocaleString()}`;

        const advanceBtn = document.getElementById('advance-week-btn');
        advanceBtn.disabled = gameState.time.is_bankrupt;
        advanceBtn.textContent = gameState.time.is_bankrupt ? '파산 — 진행 불가' : '다음 주로 →';
        document.getElementById('rest-week-btn').disabled = gameState.time.is_bankrupt;
    }

    // 지원자 리스트 렌더링
    const listEl = document.getElementById('candidate-list');
    listEl.innerHTML = '';
    
    gameState.candidates.forEach(cand => {
        const item = document.createElement('div');
        item.className = `candidate-item ${gameState.selectedCandidateTag === cand.tag ? 'active' : ''}`;
        item.onclick = () => selectCandidate(cand.tag);
        
        item.innerHTML = `
            <div class="candidate-item-header">
                <span class="candidate-name">${cand.name}</span>
                <span class="badge ${cand.education === 'PhD' || cand.education === 'MD' ? 'purple' : ''}">${cand.education}</span>
            </div>
            <div class="candidate-meta">
                <span>${cand.main_field} 전문</span>
                <span>희망연봉: $${cand.current_salary.toLocaleString()}</span>
            </div>
        `;
        listEl.appendChild(item);
    });
}

// 지원자 선택 시 우측 사이드바 로드
function selectCandidate(tag) {
    if (gameState.isPlacementMode) {
        showToast('⚠️ 책상 배치를 먼저 마쳐주세요.');
        return;
    }
    
    gameState.selectedCandidateTag = tag;
    updateUI();
    
    const cand = gameState.candidates.find(c => c.tag === tag);
    if (!cand) return;
    
    // 면접 패널 띄우기
    document.getElementById('interview-header-empty').classList.add('d-none');
    const panel = document.getElementById('interview-active-panel');
    panel.classList.remove('d-none');
    
    document.getElementById('interview-dev-name').textContent = cand.name;
    document.getElementById('interview-dev-edu').textContent = cand.education;
    document.getElementById('interview-dev-field').textContent = cand.main_field;
    document.getElementById('interview-dev-salary').textContent = `$${cand.current_salary.toLocaleString()}`;
    
    // CA 능력치 게이지
    const maxCA = 300;
    const percent = Math.min((cand.CA / maxCA) * 100, 100);
    document.getElementById('stat-ca-val').textContent = cand.CA;
    document.getElementById('stat-ca-bar').style.width = `${percent}%`;
    
    // 채팅 내용 초기화 및 첫 프롬프트 생성
    const messagesEl = document.getElementById('chat-messages');
    messagesEl.innerHTML = `
        <div class="msg candidate">
            안녕하세요! ${gameState.company.name} 면접에 참여하게 된 개발자 ${cand.name}입니다. 
            저는 주로 <strong class="text-warning">${cand.main_field}</strong> 파트를 담당하고 있습니다. 
            스타트업에 입사하기 전, 연봉 협상과 근무 조건 조율을 정중히 요청드립니다.
        </div>
    `;
    
    // 채용 버튼 감추기
    document.getElementById('hire-confirm-btn').classList.add('d-none');
    const statusBox = document.getElementById('decision-status-box');
    statusBox.className = 'decision-status';
    document.getElementById('decision-status-text').textContent = '대화 진행 중...';
}

// 실시간 채팅 전송
async function sendChatMessage() {
    const inputEl = document.getElementById('chat-input');
    const msgText = inputEl.value.trim();
    if (!msgText) return;
    
    const tag = gameState.selectedCandidateTag;
    if (!tag) return;
    
    // 1. 유저 메시지 화면에 추가
    appendMessage('user', msgText);
    inputEl.value = '';
    
    // 2. 타이핑 로더 활성화
    const loader = document.getElementById('llm-typing-indicator');
    loader.classList.remove('d-none');
    scrollToBottom();
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ developer_tag: tag, message: msgText })
        });
        
        if (!response.ok) throw new Error('서버 처리 도중 에러가 발생했습니다.');
        const data = await response.json();
        
        // 3. 타이핑 로더 비활성화 및 답변 추가
        loader.classList.add('d-none');
        appendMessage('candidate', data.dialogue);
        
        // 4. 채용 상태 갱신
        const statusBox = document.getElementById('decision-status-box');
        const hireBtn = document.getElementById('hire-confirm-btn');
        
        if (data.hired) {
            statusBox.className = 'decision-status accepted';
            document.getElementById('decision-status-text').textContent = `협상 완료 (제안 연봉: $${data.salary_demanded.toLocaleString()})`;
            hireBtn.classList.remove('d-none');
            
            gameState.placementCandidateTag = tag;
            gameState.placementSalary = data.salary_demanded;
        } else {
            statusBox.className = 'decision-status';
            document.getElementById('decision-status-text').textContent = `협상 진행 중 (지원자 요구: $${data.salary_demanded.toLocaleString()})`;
            hireBtn.classList.add('d-none');
        }
        
    } catch (error) {
        loader.classList.add('d-none');
        showToast('❌ 오류: ' + error.message);
    }
    
    scrollToBottom();
}

function appendMessage(sender, text) {
    const container = document.getElementById('chat-messages');
    const msg = document.createElement('div');
    msg.className = `msg ${sender}`;
    msg.innerHTML = text.replace(/\n/g, '<br>');
    container.appendChild(msg);
}

function scrollToBottom() {
    const container = document.getElementById('chat-messages');
    container.scrollTop = container.scrollHeight;
}

// 이벤트 리스너 세팅
// 1주 진행 요청 (rest=true면 휴식 주간)
async function advanceWeek(rest = false) {
    const btn = document.getElementById('advance-week-btn');
    const restBtn = document.getElementById('rest-week-btn');
    if (btn.disabled) return;

    btn.disabled = true;
    restBtn.disabled = true;
    try {
        const response = await fetch('/api/advance_week', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rest: rest })
        });
        const data = await response.json();

        if (!response.ok) {
            showToast('⚠️ ' + (data.detail || '주차를 진행할 수 없습니다.'));
            return;
        }

        await fetchGameState();

        const messages = [`🗓️ ${data.week}주차 시작`, ...data.events];
        if (data.is_bankrupt) messages.push('💀 게임 오버 — 회사가 파산했습니다.');
        showToastQueue(messages);
    } catch (error) {
        showToast('❌ 주차 진행 실패: ' + error.message);
    } finally {
        // 파산 여부는 갱신된 상태를 기준으로 updateUI가 다시 판단한다
        const dead = gameState.time && gameState.time.is_bankrupt;
        restBtn.disabled = !!dead;
        if (!dead) btn.disabled = false;
    }
}

function setupEventListeners() {
    // 시작 세팅 화면
    document.getElementById('setup-start-btn').addEventListener('click', startGame);
    document.getElementById('setup-company-name').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            startGame();
        }
    });

    // 채팅 전송 버튼 클릭
    document.getElementById('chat-send-btn').addEventListener('click', sendChatMessage);

    // 주차 진행
    document.getElementById('advance-week-btn').addEventListener('click', () => advanceWeek(false));
    document.getElementById('rest-week-btn').addEventListener('click', () => advanceWeek(true));
    
    // 엔터키 채팅 전송 (쉬프트 제외)
    document.getElementById('chat-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage();
        }
    });

    // 최종 채용 및 배치 모드 진입
    document.getElementById('hire-confirm-btn').addEventListener('click', () => {
        gameState.isPlacementMode = true;
        document.getElementById('placement-overlay').classList.add('active');
        showToast('🎯 오피스 맵에서 빈 책상을 선택해 직원을 배치하세요.');
    });

    // 배치 모드 취소
    document.getElementById('cancel-placement-btn').addEventListener('click', () => {
        gameState.isPlacementMode = false;
        document.getElementById('placement-overlay').classList.remove('active');
    });

    // Canvas 클릭 처리 (배치)
    canvas.addEventListener('click', handleCanvasClick);
}

// Canvas 클릭 시 책상 매핑
async function handleCanvasClick(e) {
    if (!gameState.isPlacementMode) return;
    
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    
    // 마우스 클릭 위치에 가장 가까운 빈 책상 찾기
    let clickedDesk = null;
    let minDistance = 50; // 클릭 허용 범위 반경 (픽셀 단위)
    
    gameState.desks.forEach(desk => {
        if (desk.developer_tag !== null) return; // 이미 주인이 있는 책상 제외
        
        // 해당 책상의 스크린 쿼터뷰 중심 좌표 계산
        const sc = isoToScreen(desk.x, desk.y);
        const deskScreenX = sc.x;
        const deskScreenY = sc.y - 10; // 가구 높이를 고려한 클릭 중심 조정
        
        const dist = Math.hypot(mouseX - deskScreenX, mouseY - deskScreenY);
        if (dist < minDistance) {
            minDistance = dist;
            clickedDesk = desk;
        }
    });
    
    if (clickedDesk) {
        // 백엔드로 채용 패키지 전송
        try {
            const response = await fetch('/api/hire', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    developer_tag: gameState.placementCandidateTag,
                    desk_id: clickedDesk.id,
                    salary: gameState.placementSalary
                })
            });
            
            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || '채용 처리에 실패했습니다.');
            }
            
            showToast('🎉 새로운 팀원이 채용되었습니다! 책상 배치가 완료되었습니다.');
            
            // 상태 해제
            gameState.isPlacementMode = false;
            document.getElementById('placement-overlay').classList.remove('active');
            
            // 우측 사이드바 초기화
            gameState.selectedCandidateTag = null;
            document.getElementById('interview-active-panel').classList.add('d-none');
            document.getElementById('interview-header-empty').classList.remove('d-none');
            
            // 상태 갱신
            await fetchGameState();
            
        } catch (error) {
            showToast('❌ 채용 실패: ' + error.message);
        }
    } else {
        showToast('❓ 반짝이는 빈 책상을 정확히 클릭해 주세요.');
    }
}

// ----------------------------------------------------
// 🎨 아이소메트릭(쿼터뷰) 드로잉 엔진 파트
// ----------------------------------------------------

// 1. 그리드 좌표 -> 스크린 좌표 변환
function isoToScreen(x, y) {
    const screenX = originX + (x - y) * (tileWidth / 2);
    const screenY = originY + (x + y) * (tileHeight / 2);
    return { x: screenX, y: screenY };
}

// 2. 3D 입체 큐브 그리기 헬퍼 함수
// x, y : 그리드 좌표
// z : 높이 레벨 (0이 바닥)
// w, l, h : 각각 그리드 비율 기준 가로, 세로, 픽셀 기준 높이
function drawCube(x, y, z, w, l, h, colorLeft, colorRight, colorTop) {
    // 큐브 바닥 중앙의 스크린 좌표
    const base = isoToScreen(x, y);
    const screenX = base.x;
    const screenY = base.y - z; // 높이 오프셋만큼 위로 이동
    
    // 입체 크기 계산 (픽셀 기준)
    const dw = w * (tileWidth / 2);
    const dl = l * (tileHeight / 2);
    
    // 6개의 기하점 정의
    const pCenterBottom = { x: screenX, y: screenY };
    const pLeft = { x: screenX - dw, y: screenY + dw * 0.5 };
    const pRight = { x: screenX + dl, y: screenY + dl * 0.5 };
    const pCenterTop = { x: screenX + (dl - dw), y: screenY + (dw + dl) * 0.5 };
    
    // 상단 덮개용 점
    const ptCenterBottom = { x: pCenterBottom.x, y: pCenterBottom.y - h };
    const ptLeft = { x: pLeft.x, y: pLeft.y - h };
    const ptRight = { x: pRight.x, y: pRight.y - h };
    const ptCenterTop = { x: pCenterTop.x, y: pCenterTop.y - h };
    
    // 1) 좌측 면 그리기 (그늘)
    ctx.fillStyle = colorLeft;
    ctx.beginPath();
    ctx.moveTo(pCenterBottom.x, pCenterBottom.y);
    ctx.lineTo(pLeft.x, pLeft.y);
    ctx.lineTo(ptLeft.x, ptLeft.y);
    ctx.lineTo(ptCenterBottom.x, ptCenterBottom.y);
    ctx.closePath();
    ctx.fill();
    
    // 2) 우측 면 그리기 (그늘)
    ctx.fillStyle = colorRight;
    ctx.beginPath();
    ctx.moveTo(pCenterBottom.x, pCenterBottom.y);
    ctx.lineTo(pRight.x, pRight.y);
    ctx.lineTo(ptRight.x, ptRight.y);
    ctx.lineTo(ptCenterBottom.x, ptCenterBottom.y);
    ctx.closePath();
    ctx.fill();
    
    // 3) 상단 면 그리기 (가장 밝음)
    ctx.fillStyle = colorTop;
    ctx.beginPath();
    ctx.moveTo(ptCenterBottom.x, ptCenterBottom.y);
    ctx.lineTo(ptLeft.x, ptLeft.y);
    ctx.lineTo(ptCenterTop.x, ptCenterTop.y);
    ctx.lineTo(ptRight.x, ptRight.y);
    ctx.closePath();
    ctx.fill();
}

// 3. 메인 게임 루프 (60fps)
function gameLoop() {
    ctx.clearRect(0, 0, canvasWidth, canvasHeight);
    
    // 뒤쪽 타일(x+y가 작은 것)부터 그리며 Z-sorting 해결
    for (let depth = 0; depth <= (gridSize - 1) * 2; depth++) {
        for (let x = 0; x < gridSize; x++) {
            const y = depth - x;
            if (y >= 0 && y < gridSize) {
                drawTile(x, y);
                drawObjects(x, y);
            }
        }
    }
    
    requestAnimationFrame(gameLoop);
}

// 4. 바닥 타일 그리기
function drawTile(x, y) {
    const sc = isoToScreen(x, y);
    
    ctx.strokeStyle = COLORS.floorBorder;
    ctx.lineWidth = 1;
    ctx.fillStyle = COLORS.floor;
    
    ctx.beginPath();
    ctx.moveTo(sc.x, sc.y);
    ctx.lineTo(sc.x + tileWidth / 2, sc.y + tileHeight / 2);
    ctx.lineTo(sc.x, sc.y + tileHeight);
    ctx.lineTo(sc.x - tileWidth / 2, sc.y + tileHeight / 2);
    ctx.closePath();
    
    ctx.fill();
    ctx.stroke();
}

// 5. 오브젝트 및 캐릭터 그리기
function drawObjects(x, y) {
    // 이 좌표에 위치한 책상 검색
    const desk = gameState.desks.find(d => d.x === x && d.y === y);
    if (!desk) return;
    
    const hasEmployee = desk.developer_tag !== null;
    const isThisDeskAvailable = !hasEmployee && gameState.isPlacementMode;
    
    // 배치 모드이고 빈 책상일 때 바닥에 초록색 반짝임 광원 그리기
    if (isThisDeskAvailable) {
        const sc = isoToScreen(x, y);
        const pulse = 0.5 + 0.5 * Math.sin(Date.now() * 0.008);
        ctx.fillStyle = `rgba(16, 185, 129, ${0.1 + pulse * 0.25})`;
        ctx.strokeStyle = COLORS.gridHighlightBorder;
        ctx.lineWidth = 2;
        
        ctx.beginPath();
        ctx.moveTo(sc.x, sc.y);
        ctx.lineTo(sc.x + tileWidth / 2, sc.y + tileHeight / 2);
        ctx.lineTo(sc.x, sc.y + tileHeight);
        ctx.lineTo(sc.x - tileWidth / 2, sc.y + tileHeight / 2);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
    }
    
    // ----------------------------------------------------
    // 가구 그리기 (의자 -> 책상/모니터 순으로 그려 겹침 보정)
    // ----------------------------------------------------
    
    // 의자 그리기 (직원 탑승 시는 사람 몸체 뒤에 일부 그리기 위해 의자를 먼저 배치)
    // 의자는 책상보다 살짝 앞에 위치시킴 (x + 0.3, y + 0.3)
    drawCube(x + 0.3, y + 0.3, 0, 0.4, 0.4, 12, '#374151', '#1f2937', '#4b5563'); // 의자 다리/받침
    drawCube(x + 0.3, y + 0.3, 12, 0.4, 0.4, 3, COLORS.chairLeft, COLORS.chairRight, COLORS.chairTop); // 의자 시트
    
    // 책상 그리기
    // w=0.8, l=0.8 크기, h=16 픽셀 높이
    drawCube(x + 0.1, y + 0.1, 0, 0.1, 0.1, 15, COLORS.deskLeft, COLORS.deskRight, COLORS.deskTop); // 좌측 다리
    drawCube(x + 0.8, y + 0.1, 0, 0.1, 0.1, 15, COLORS.deskLeft, COLORS.deskRight, COLORS.deskTop); // 우측 다리
    drawCube(x + 0.1, y + 0.8, 0, 0.1, 0.1, 15, COLORS.deskLeft, COLORS.deskRight, COLORS.deskTop); // 뒤쪽 다리
    drawCube(x, y, 15, 0.9, 0.9, 3, COLORS.deskLeft, COLORS.deskRight, COLORS.deskTop); // 상판
    
    // 모니터 그리기 (책상 위 z=18 배치)
    drawCube(x + 0.2, y + 0.2, 18, 0.1, 0.1, 4, COLORS.monitorBody, COLORS.monitorBody, COLORS.monitorBody); // 거치대
    drawCube(x + 0.15, y + 0.3, 22, 0.1, 0.4, 10, COLORS.monitorBody, COLORS.monitorBody, COLORS.monitorBody); // 모니터 본체
    
    // 모니터 화면 빛남 효과 (블루 테마)
    const monitorPulse = Math.sin(Date.now() * 0.005) > 0;
    const screenColor = monitorPulse ? COLORS.monitorScreenGlow : COLORS.monitorScreen;
    drawCube(x + 0.22, y + 0.32, 23, 0.01, 0.36, 8, screenColor, screenColor, screenColor); // 모니터 스크린
    
    // ----------------------------------------------------
    // 캐릭터 (직원) 그리기 (의자 위에 앉아있는 사람)
    // ----------------------------------------------------
    if (hasEmployee) {
        // 타이핑할 때 상하로 진동하는 모션 (Math.sin 활용)
        const animationOffset = Math.sin(Date.now() * 0.012) * 1.2;
        
        // 1. 하체/엉덩이 (의자 앉은 부분 z=15)
        drawCube(x + 0.3, y + 0.3, 15, 0.4, 0.4, 6, COLORS.shirtLeft, COLORS.shirtRight, COLORS.shirtTop);
        
        // 2. 몸통 (z=21 + 상하 바운싱)
        drawCube(x + 0.3, y + 0.3, 21 + animationOffset, 0.35, 0.35, 10, COLORS.shirtLeft, COLORS.shirtRight, COLORS.shirtTop);
        
        // 3. 머리 (z=31 + 상하 바운싱)
        drawCube(x + 0.35, y + 0.35, 31 + animationOffset, 0.25, 0.25, 6, COLORS.skin, COLORS.skin, COLORS.skin); // 얼굴
        drawCube(x + 0.33, y + 0.33, 37 + animationOffset, 0.29, 0.29, 3, COLORS.hair, COLORS.hair, COLORS.hair); // 머리카락
        
        // 4. 타이핑하는 팔 (앞으로 뻗은 큐브, 좌우로 미세 교차 타이핑 모션)
        const leftArmOffset = Math.sin(Date.now() * 0.02) * 1.5;
        const rightArmOffset = Math.cos(Date.now() * 0.02) * 1.5;
        
        // 왼팔
        drawCube(x + 0.22, y + 0.3, 25 + animationOffset + leftArmOffset, 0.1, 0.1, 2, COLORS.skin, COLORS.skin, COLORS.skin);
        // 오른팔
        drawCube(x + 0.3, y + 0.22, 25 + animationOffset + rightArmOffset, 0.1, 0.1, 2, COLORS.skin, COLORS.skin, COLORS.skin);
    }
}

// ----------------------------------------------------
// 💬 토스트 알림 메시지 헬퍼
// ----------------------------------------------------
function showToast(text) {
    const toast = document.getElementById('toast');
    toast.textContent = text;
    toast.classList.add('show');

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// 여러 건의 알림을 순차적으로 표시 (한 번에 띄우면 서로 덮어씀)
function showToastQueue(messages) {
    messages.forEach((msg, i) => {
        setTimeout(() => showToast(msg), i * 3200);
    });
}
