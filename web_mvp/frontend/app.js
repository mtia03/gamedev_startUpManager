// 글로벌 상태 관리
let gameState = {
    company: null,
    time: null,
    office: null,
    selectedDifficulty: 'normal',
    seenCandidates: new Set(),
    // 지원자별 대화 기록과 협상 상태. 창을 닫았다 열어도 유지된다.
    chatLogs: {},
    negotiation: {},
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
// 🧑‍💻 면접 대기 줄
// ----------------------------------------------------
async function openPoolModal() {
    document.getElementById('pool-modal').classList.remove('d-none');
    await fetchGameState();
    // 목록을 열어봤으면 '새 지원자' 배지를 내린다
    (gameState.candidates || []).forEach(c => gameState.seenCandidates.add(c.tag));
    renderPoolSummary();
    renderPool();
}

// 사무실 확장
async function upgradeOffice() {
    const o = gameState.office;
    if (!o || !o.next) return;
    const msg = `${o.next.label}로 확장할까요?\n\n`
        + `책상 ${o.desks} → ${o.next.desks}개\n`
        + `비용 $${o.next.cost.toLocaleString()}\n\n`
        + '확장 직후 몇 주간 지원자가 몰립니다.';
    if (!confirm(msg)) return;

    const r = await postJson('/api/office/upgrade', {});
    if (r) {
        showToast(`🏢 ${r.label}로 확장했습니다. (책상 ${r.desks}개)`);
        await fetchGameState();
    }
}

function closePoolModal() {
    document.getElementById('pool-modal').classList.add('d-none');
}

function renderPool() {
    const body = document.getElementById('pool-body');
    const list = gameState.candidates || [];
    if (!list.length) {
        body.innerHTML = `<p class="biz-empty">
            지원자가 없습니다. 주차를 진행하면 새 지원자가 찾아옵니다.</p>`;
        return;
    }
    body.innerHTML = `
        <p class="biz-sub" style="margin-bottom:14px;">
            대기 ${list.length}명 · 지원자는 일정 기간이 지나면 스스로 지원을 철회합니다.
        </p>
        <div class="pool-grid">${list.map(renderPoolCard).join('')}</div>
    `;
    wirePool();
}

// 대기 줄 카드용 축약 칩. 면접으로 알아낸 것만 뜬다.
function poolDiscoveryChips(c) {
    const chips = [];
    chips.push(c.circumstance
        ? `<span class="disc circumstance"><span class="t">사정</span>${c.circumstance.label}</span>`
        : `<span class="disc unknown"><span class="t">사정</span>?</span>`);

    if (!c.needs_known) {
        chips.push(`<span class="disc unknown"><span class="t">원하는 것</span>?</span>`);
    } else if (!c.needs || !c.needs.length) {
        chips.push(`<span class="disc need"><span class="t">원하는 것</span>연봉만 본다</span>`);
    } else {
        c.needs.forEach(n =>
            chips.push(`<span class="disc need"><span class="t">원함</span>${n.label}</span>`));
    }
    return chips.join('');
}

function renderPoolCard(c) {
    const traits = (c.traits || []).map(t =>
        `<span class="trait ${t.tone}" title="${t.desc}">${t.label}</span>`).join('');

    // 지원자 스탯은 추정 구간으로만 보인다. 면접을 통해 좁혀진다.
    const stats = Object.entries(c.stat_ranges || {}).map(([f, r]) => `
        <div class="stat-cell ${f === c.main_field ? 'main' : ''}">
            <span class="k">${FIELD_LABEL[f]}</span>
            <span class="v ${r.exact ? '' : 'est'}">
                ${r.exact ? r.low : `${r.low}~${r.high}`}
            </span>
        </div>`).join('');

    const dropped = c.initial_demand && c.current_salary < c.initial_demand
        ? `<small>최초 $${c.initial_demand.toLocaleString()}</small>` : '';

    return `
        <div class="pool-card ${gameState.selectedCandidateTag === c.tag ? 'selected' : ''}">
            <div class="pool-top">
                <div>
                    <div class="pool-name">${c.name}
                        <span class="biz-tier">${c.education}</span>
                    </div>
                    <div class="biz-sub">
                        ${FIELD_LABEL[c.main_field]} 전문 · ${c.class_hint}
                        ${c.is_ace ? '<span class="ace-badge">에이스</span>' : ''}
                    </div>
                    <div class="biz-sub reveal-hint">
                        파악도 ${c.reveal_level}/${c.max_reveal_level}
                        ${c.reveal_level >= c.max_reveal_level
                            ? '· 정확히 파악함'
                            : '· 실력을 물어보면 더 좁혀집니다'}
                    </div>
                    <div class="biz-sub">
                        ${c.negotiation_turns ? `협상 ${c.negotiation_turns}회 진행` : '아직 접촉 전'}
                    </div>
                    ${c.interview_open
                        ? '<span class="live-badge">면접 중 · 이번 주 마감</span>' : ''}
                </div>
                <div class="pool-demand">
                    $${c.current_salary.toLocaleString()}
                    ${dropped}
                    <small>희망 연봉</small>
                </div>
            </div>

            <div class="trait-row">${traits}</div>
            <div class="discovery">${poolDiscoveryChips(c)}</div>
            ${c.urgency ? `<span class="urgency ${c.urgency.level}">"${c.urgency.hint}"</span>` : ''}
            <div class="stat-row">${stats}</div>

            <div class="pool-actions">
                <button class="btn btn-primary btn-sm" data-interview="${c.tag}">면접 보기</button>
                <button class="btn btn-secondary btn-sm"
                        data-drop="${c.tag}" data-name="${c.name}">탈락</button>
            </div>
        </div>
    `;
}

function wirePool() {
    document.querySelectorAll('[data-interview]').forEach(el => {
        el.onclick = () => {
            selectCandidate(el.dataset.interview);
            closePoolModal();
            const sidebar = document.getElementById('right-sidebar');
            if (!sidebar.classList.contains('expanded')) toggleInterviewExpand();
        };
    });
    document.querySelectorAll('[data-drop]').forEach(el => {
        el.onclick = async () => {
            if (!confirm(`${el.dataset.name}를 탈락시킬까요? 지원 목록에서 사라집니다.`)) return;
            const r = await postJson('/api/candidates/reject', { developer_tag: el.dataset.drop });
            if (r) {
                showToast(`${r.name} 지원자를 탈락시켰습니다.`);
                if (gameState.selectedCandidateTag === el.dataset.drop) clearInterviewPanel();
                await fetchGameState();
                renderPool();
            }
        };
    });
}

// ----------------------------------------------------
// 👥 팀 & 기록
// ----------------------------------------------------
const LOG_KINDS = [
    { key: '', label: '전체' },
    { key: 'business', label: '사업' },
    { key: 'reward', label: '보상' },
    { key: 'salary', label: '급여' },
    { key: 'morale', label: '사기' },
    { key: 'resign', label: '이탈' },
    { key: 'hire', label: '채용' },
    { key: 'danger', label: '위험' }
];

let teamTab = 'staff';
let logKind = '';
let logRows = [];

async function openTeamModal() {
    document.getElementById('team-modal').classList.remove('d-none');
    await refreshTeam();
}

function closeTeamModal() {
    document.getElementById('team-modal').classList.add('d-none');
}

async function refreshTeam() {
    await fetchGameState();
    if (teamTab === 'log') {
        const url = '/api/events?limit=200' + (logKind ? `&kind=${logKind}` : '');
        try {
            const r = await fetch(url);
            logRows = r.ok ? (await r.json()).events : [];
        } catch (e) {
            logRows = [];
        }
    }
    renderTeam();
}

function renderTeam() {
    document.querySelectorAll('.team-tab').forEach(el => {
        el.classList.toggle('active', el.dataset.tab === teamTab);
    });
    const body = document.getElementById('team-body');
    body.innerHTML = teamTab === 'staff' ? renderStaffList() : renderLogList();
    wireTeamPanel();
}

function renderStaffList() {
    const staff = Object.values(gameState.hiredEmployees);
    if (!staff.length) {
        return '<p class="biz-empty">재직 중인 직원이 없습니다.</p>';
    }
    const payroll = gameState.time ? gameState.time.weekly_payroll : 0;
    return `
        <p class="biz-sub" style="margin-bottom:14px;">
            재직 ${staff.length}명 · 주당 인건비 합계 $${payroll.toLocaleString()}
        </p>
        ${staff.map(renderStaffCard).join('')}
    `;
}

function renderStaffCard(d) {
    const traits = d.traits.map(t =>
        `<span class="trait ${t.tone}" title="${t.desc}">${t.label}</span>`).join('');

    const stats = Object.entries(d.stats).map(([f, v]) => `
        <div class="stat-cell ${f === d.main_field ? 'main' : ''}">
            <span class="k">${FIELD_LABEL[f]}</span>
            <span class="v">${v}</span>
        </div>`).join('');

    const work = d.assignment
        ? `${d.assignment.business} · ${d.assignment.task}`
        : '대기 중 (배치된 업무 없음)';

    return `
        <div class="staff-card">
            <div class="staff-top">
                <div>
                    <div class="staff-name">${d.name}
                        <span class="biz-tier">${d.education}</span>
                    </div>
                    <div class="staff-sub">
                        ${FIELD_LABEL[d.main_field]} 전문 · CA ${d.CA} / PA ${d.PA}
                    </div>
                    <div class="staff-sub">담당: ${work}</div>
                </div>
                <div>
                    <div class="staff-salary">
                        $${d.weekly_salary.toLocaleString()}
                        <small>주급 · 연 $${d.annual_salary.toLocaleString()}</small>
                    </div>
                </div>
            </div>

            <div class="trait-row">${traits}</div>

            <div class="gauge-row">
                <div class="gauge">
                    <label>사기 ${d.morale}</label>
                    <div class="gauge-bar"><div class="gauge-fill morale" style="width:${d.morale}%"></div></div>
                </div>
                <div class="gauge">
                    <label>피로 ${d.fatigue}</label>
                    <div class="gauge-bar"><div class="gauge-fill fatigue" style="width:${d.fatigue}%"></div></div>
                </div>
                <div class="gauge">
                    <label>생산성 ${Math.round(d.productivity * 100)}%</label>
                    <div class="gauge-bar"><div class="gauge-fill prod" style="width:${d.productivity * 100}%"></div></div>
                </div>
            </div>

            <div class="stat-row">${stats}</div>

            <div class="staff-actions">
                <button class="btn btn-secondary btn-sm" data-fire="${d.tag}" data-name="${d.name}">해고</button>
            </div>
        </div>
    `;
}

function renderLogList() {
    const filters = LOG_KINDS.map(k =>
        `<button class="log-filter ${logKind === k.key ? 'active' : ''}"
                 data-kind="${k.key}">${k.label}</button>`).join('');

    const rows = logRows.length
        ? logRows.map(e => `
            <div class="log-item ${e.kind}">
                <span class="log-week">${e.week}주</span>
                <span>${e.text}</span>
            </div>`).join('')
        : '<p class="biz-empty">해당하는 기록이 없습니다.</p>';

    return `<div class="log-filters">${filters}</div>${rows}`;
}

function wireTeamPanel() {
    document.querySelectorAll('[data-kind]').forEach(el => {
        el.onclick = () => { logKind = el.dataset.kind; refreshTeam(); };
    });
    document.querySelectorAll('[data-fire]').forEach(el => {
        el.onclick = async () => {
            if (!confirm(`${el.dataset.name} 님을 해고할까요? 퇴직금 4주치가 지급됩니다.`)) return;
            const r = await postJson('/api/fire', { developer_tag: el.dataset.fire });
            if (r) {
                showToast(`${r.name} 님을 해고했습니다. (퇴직금 $${r.severance.toLocaleString()})`);
                await refreshTeam();
            }
        };
    });
}

// ----------------------------------------------------
// 📋 사업 관리
// ----------------------------------------------------
const FIELD_LABEL = {
    FE: '프론트', BE: '백엔드', Mobile: '모바일',
    AI: 'AI', Ops: '인프라', UIUX: 'UI/UX'
};
const STATUS_LABEL = {
    locked: '잠김', ready: '착수 가능', active: '진행 중', done: '완료'
};

let bizData = { offered: [], active: [], completed: [], busy_developers: [] };
let bizTab = 'active';
// 화면에서 고른 배치 인원 (task_tag -> [dev_tag])
let pendingAssign = {};

async function openBizModal() {
    document.getElementById('biz-modal').classList.remove('d-none');
    await refreshBusinesses();
}

function closeBizModal() {
    document.getElementById('biz-modal').classList.add('d-none');
}

async function refreshBusinesses() {
    try {
        const response = await fetch('/api/businesses');
        if (!response.ok) throw new Error('사업 목록을 불러올 수 없습니다.');
        bizData = await response.json();
        renderPoolSummary();
        renderBusinesses();
    } catch (error) {
        document.getElementById('biz-body').innerHTML =
            `<p class="biz-empty">${error.message}</p>`;
    }
}

function renderBusinesses() {
    document.querySelectorAll('.biz-tab').forEach(el => {
        el.classList.toggle('active', el.dataset.tab === bizTab);
    });

    const body = document.getElementById('biz-body');
    const list = bizData[bizTab] || [];
    if (!list.length) {
        const msg = { active: '진행 중인 사업이 없습니다. 수주 대기 탭에서 사업을 수주하세요.',
                      offered: '수주 가능한 사업이 없습니다.',
                      completed: '아직 완료한 사업이 없습니다.' }[bizTab];
        body.innerHTML = `<p class="biz-empty">${msg}</p>`;
        return;
    }
    body.innerHTML = list.map(b => renderBizCard(b)).join('');
    wireBizCard();
}

function renderBizCard(b) {
    const fields = [...new Set(b.tasks.map(t => t.field))]
        .map(f => FIELD_LABEL[f]).join(' · ');
    const done = b.tasks.filter(t => t.status === 'done').length;

    let actions = '';
    if (bizTab === 'offered') {
        actions = `<button class="btn btn-success btn-sm" data-accept="${b.tag}">수주하기</button>`;
    } else if (bizTab === 'active') {
        actions = `<button class="btn btn-secondary btn-sm" data-abandon="${b.tag}">사업 포기</button>`;
    }

    const rewardLine = bizTab === 'completed'
        ? `$${b.payout.toLocaleString()} <span class="biz-sub">/ $${b.reward.toLocaleString()}</span>`
        : `$${b.reward.toLocaleString()}`;

    return `
        <div class="biz-card">
            <div class="biz-card-top">
                <div>
                    <div class="biz-title">
                        <span class="biz-tier">${b.tier}</span>${b.name}
                    </div>
                    <div class="biz-sub">
                        ${b.tier_name} · 업무 ${b.tasks.length}개 (완료 ${done}) ·
                        목표 ${b.target_weeks}주 · 권장 ${b.crew}명 · 필요 분야 ${fields}
                    </div>
                    <div class="biz-sub">명성 +${b.reputation_gain.toLocaleString()}</div>
                </div>
                <div>
                    <div class="biz-reward">${rewardLine}</div>
                    <div style="margin-top:8px; text-align:right;">${actions}</div>
                </div>
            </div>
            ${b.tasks.map(t => renderTask(b, t)).join('')}
        </div>
    `;
}

function renderTask(b, t) {
    const pct = Math.round(t.ratio * 100);
    // 완료된 업무만 결과를 확정 표시한다 (실패는 되감기라 아직 진행 중)
    const gradeText = t.status === 'done' && t.grade
        ? ` · 결과 <strong>${t.grade_label}</strong>`
        : '';
    const reqNames = t.requires.length
        ? `선행 업무 ${t.requires.length}개 완료 필요`
        : '선행 없음';

    let panel = '';
    if (bizTab === 'active' && (t.status === 'ready' || t.status === 'active')) {
        panel = renderAssignBox(b, t);
    }

    // 실패로 되감긴 이력
    const setback = t.last_setback
        ? `<span class="setback">⚠ ${t.last_setback.grade === 'critical' ? '완전 실패' : '실패'}로
             진행률이 ${t.last_setback.kept}%로 되감겼습니다. 다시 밀어붙이면 됩니다.
             ${t.attempts > 1 ? `(시도 ${t.attempts}회)` : ''}</span>`
        : '';

    const statusCls = t.last_setback && t.status !== 'done' ? 'retry' : t.status;
    const statusTxt = t.last_setback && t.status !== 'done'
        ? '재도전 중' : STATUS_LABEL[t.status];

    return `
        <div class="task-row">
            <div class="task-head">
                <span class="task-field">${FIELD_LABEL[t.field]}</span>
                <span class="task-name">${t.name}</span>
                <span class="task-status ${statusCls}">${statusTxt}</span>
            </div>
            ${setback}
            <div class="task-bar"><div class="task-bar-fill" style="width:${pct}%"></div></div>
            <div class="task-meta">
                <span>${Math.round(t.progress)} / ${t.required} 공수 (${pct}%)</span>
                <span>${reqNames}${gradeText}</span>
            </div>
            ${panel}
        </div>
    `;
}

function renderAssignBox(b, t) {
    const chosen = pendingAssign[t.tag] || t.assigned;
    const busy = new Set(bizData.busy_developers);
    t.assigned.forEach(tag => busy.delete(tag));   // 이 업무 인원은 선택 가능

    const chips = Object.values(gameState.hiredEmployees).map(d => {
        const isBusy = busy.has(d.tag);
        const on = chosen.includes(d.tag);
        const isMain = d.main_field === t.field;
        return `
            <div class="assign-chip ${on ? 'on' : ''} ${isBusy ? 'busy' : ''}"
                 data-pick="${t.tag}" data-dev="${d.tag}" data-busy="${isBusy}">
                <span>${d.name}</span>
                <span class="${isMain ? 'main-tag' : ''}">
                    ${FIELD_LABEL[d.main_field]} ${d.stats[t.field]}
                </span>
            </div>`;
    }).join('');

    const label = t.status === 'active' ? '배치 변경' : '배치 확정 후 착수';
    return `
        <div class="assign-box">
            <div class="assign-list">${chips || '<span class="biz-sub">재직 중인 직원이 없습니다.</span>'}</div>
            <div class="assign-actions">
                <button class="btn btn-primary btn-sm"
                        data-assign="${t.tag}" data-biz="${b.tag}">${label}</button>
            </div>
            <div class="biz-info" id="info-${t.tag}">
                주분야가 맞는 인원을 넣어야 속도가 제대로 납니다. 다른 분야는 기여가 1/4로 줄어듭니다.
            </div>
        </div>
    `;
}

function wireBizCard() {
    document.querySelectorAll('[data-pick]').forEach(el => {
        el.onclick = () => {
            if (el.dataset.busy === 'true') {
                showToast('⚠️ 다른 업무에 배치된 인원입니다.');
                return;
            }
            const taskTag = el.dataset.pick;
            const devTag = el.dataset.dev;
            const cur = pendingAssign[taskTag]
                || [...(findTask(taskTag)?.assigned || [])];
            const i = cur.indexOf(devTag);
            if (i >= 0) cur.splice(i, 1); else cur.push(devTag);
            pendingAssign[taskTag] = cur;
            renderBusinesses();
        };
    });

    document.querySelectorAll('[data-accept]').forEach(el => {
        el.onclick = () => bizAction('/api/businesses/accept',
            { business_tag: el.dataset.accept }, '사업을 수주했습니다.');
    });
    document.querySelectorAll('[data-abandon]').forEach(el => {
        el.onclick = () => {
            if (!confirm('정말 포기할까요? 위약금과 명성 하락이 있습니다.')) return;
            bizAction('/api/businesses/abandon',
                { business_tag: el.dataset.abandon }, '사업을 포기했습니다.');
        };
    });
    document.querySelectorAll('[data-assign]').forEach(el => {
        el.onclick = () => assignAndStart(el.dataset.biz, el.dataset.assign);
    });
}

function findTask(taskTag) {
    for (const b of bizData.active) {
        const t = b.tasks.find(x => x.tag === taskTag);
        if (t) return t;
    }
    return null;
}

async function bizAction(url, body, okMessage) {
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await response.json();
        if (!response.ok) {
            showToast('⚠️ ' + (data.detail || '요청에 실패했습니다.'));
            return null;
        }
        await fetchGameState();
        await refreshBusinesses();
        if (okMessage) showToast('✅ ' + okMessage);
        return data;
    } catch (error) {
        showToast('❌ ' + error.message);
        return null;
    }
}

// 배치를 저장하고, 아직 시작 전이면 착수까지 진행
async function assignAndStart(bizTag, taskTag) {
    const devs = pendingAssign[taskTag] || findTask(taskTag)?.assigned || [];
    if (!devs.length) {
        showToast('⚠️ 배치할 인원을 선택하세요.');
        return;
    }

    const res = await bizAction('/api/businesses/assign',
        { business_tag: bizTag, task_tag: taskTag, developer_tags: devs }, null);
    if (!res) return;

    const info = document.getElementById('info-' + taskTag);
    if (info) {
        info.innerHTML = `성공 확률 <strong>${Math.round(res.success_probability * 100)}%</strong>
            · 주당 처리량 <strong>${res.weekly_throughput}</strong>`;
    }

    const task = findTask(taskTag);
    if (task && task.status === 'active') {
        showToast('✅ 배치를 변경했습니다.');
        return;
    }

    // 착수 시도. 게이트 미달이면 사유를 보여주고 강행 여부를 묻는다
    let start = await postJson('/api/businesses/start_task',
        { business_tag: bizTag, task_tag: taskTag, force: false });
    if (start && start.status === 'gate_failed') {
        const msg = '요구 조건 미충족:\n\n' + start.gate_reasons.join('\n')
            + `\n\n강행하면 성공 확률이 ${Math.round(start.penalty * 100)}%로 줄어듭니다. 진행할까요?`;
        if (!confirm(msg)) return;
        start = await postJson('/api/businesses/start_task',
            { business_tag: bizTag, task_tag: taskTag, force: true });
    }

    if (start && start.status === 'success') {
        delete pendingAssign[taskTag];
        showToast(`🚀 업무 착수 (성공 확률 ${Math.round(start.success_probability * 100)}%)`);
    }
    await refreshBusinesses();
}

async function postJson(url, body) {
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await response.json();
        if (!response.ok) {
            showToast('⚠️ ' + (data.detail || '요청에 실패했습니다.'));
            return null;
        }
        return data;
    } catch (error) {
        showToast('❌ ' + error.message);
        return null;
    }
}

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
        gameState.office = data.office;
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

    // 사무실 현황
    if (gameState.office) {
        const o = gameState.office;
        document.getElementById('company-office').textContent =
            `${o.label} · 책상 ${o.desks}`;
        const upBtn = document.getElementById('upgrade-office-btn');
        if (o.next) {
            upBtn.classList.remove('d-none');
            upBtn.disabled = gameState.company.funds < o.next.cost;
            upBtn.title = `책상 ${o.desks} → ${o.next.desks}개 · $${o.next.cost.toLocaleString()}`;
        } else {
            upBtn.classList.add('d-none');
        }
    }

    // 지원자 요약 (자세한 내용은 팝업)
    renderPoolSummary();
}

// 패널 이동 버튼의 숫자와 알림 점을 갱신한다
function renderPoolSummary() {
    const list = gameState.candidates || [];
    document.getElementById('pool-count').textContent = `${list.length}명`;

    const fresh = list.some(c => !gameState.seenCandidates.has(c.tag));
    document.getElementById('pool-new').classList.toggle('d-none', !fresh);

    const active = (bizData.active || []).length;
    document.getElementById('biz-count').textContent = `${active}건`;
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
    
    renderInsight(cand);
    
    // 이 지원자와의 대화가 처음이면 인사말을 만들어 기록에 넣는다
    if (!gameState.chatLogs[tag]) {
        gameState.chatLogs[tag] = [{
            sender: 'candidate',
            html: `안녕하세요! ${gameState.company.name} 면접에 참여하게 된 개발자 ${cand.name}입니다.
                   저는 주로 <strong class="text-warning">${cand.main_field}</strong> 파트를 담당하고 있습니다.
                   스타트업에 입사하기 전, 연봉 협상과 근무 조건 조율을 정중히 요청드립니다.`
        }];
    }
    // 다른 지원자를 떠나보낸 뒤 잠겼을 수 있는 입력창을 되살린다
    document.getElementById('chat-input').disabled = false;
    document.getElementById('chat-send-btn').disabled = false;

    renderChatLog(tag);
    restoreNegotiationState(tag, cand);
    scrollToBottom();
}

// 면접 창의 파악도 · 체급 · 필드별 추정 구간을 그린다.
// insight는 /api/state의 지원자 항목이나 /api/chat 응답 둘 다 같은 모양이다.
function renderInsight(info) {
    if (!info || !info.stat_ranges) return;

    const pct = info.max_reveal_level
        ? (info.reveal_level / info.max_reveal_level) * 100 : 0;
    const done = info.reveal_level >= info.max_reveal_level;

    document.getElementById('stat-ca-val').textContent =
        `${info.class_hint}${info.is_ace ? ' · 에이스' : ''}`;
    document.getElementById('stat-ca-bar').style.width = `${pct}%`;

    const tag = document.getElementById('stat-reveal');
    tag.textContent = done
        ? '파악 완료'
        : `파악 ${info.reveal_level}/${info.max_reveal_level}`;
    tag.classList.toggle('done', done);

    const mainField = gameState.candidates.find(c => c.tag === gameState.selectedCandidateTag)?.main_field;
    document.getElementById('stat-ranges').innerHTML =
        Object.entries(info.stat_ranges).map(([f, r]) => `
            <div class="mini-stat ${f === mainField ? 'main' : ''}">
                <span class="f">${FIELD_LABEL[f]}</span>
                <span class="r ${r.exact ? 'exact' : ''}">
                    ${r.exact ? r.low : `${r.low}~${r.high}`}
                </span>
            </div>`).join('');

    renderDiscovery(info);
}

// 사정 / 원하는 것 — 대화로 알아낸 것만 보여준다.
// 모르는 항목은 물음표로 남겨서 "물어보면 알 수 있다"는 것만 알린다.
function renderDiscovery(info) {
    const row = document.getElementById('discovery-row');
    if (!row) return;

    const chips = [];

    if (info.circumstance) {
        chips.push(`<span class="disc circumstance">
            <span class="t">사정</span>${info.circumstance.label}</span>`);
    } else {
        chips.push(`<span class="disc unknown" title="왜 이직하려는지, 지금 어떤 상황인지 물어보세요">
            <span class="t">사정</span>?</span>`);
    }

    if (info.needs_known) {
        if (!info.needs || !info.needs.length) {
            chips.push(`<span class="disc need">
                <span class="t">원하는 것</span>연봉만 본다</span>`);
        } else {
            info.needs.forEach(n => {
                const met = (gameState.provenNeeds || []).includes(n.label);
                chips.push(`<span class="disc need ${met ? 'met' : ''}"
                    title="${met ? '이미 어필에 성공했습니다' : '우리 회사가 갖췄다면 어필해보세요'}">
                    <span class="t">원함</span>${n.label}${met ? ' ✓' : ''}</span>`);
            });
        }
    } else {
        chips.push(`<span class="disc unknown" title="회사를 고를 때 무엇을 중요하게 보는지 물어보세요">
            <span class="t">원하는 것</span>?</span>`);
    }

    row.innerHTML = chips.join('');
}

// 보관해둔 대화 기록을 화면에 다시 그린다
function renderChatLog(tag) {
    const messagesEl = document.getElementById('chat-messages');
    messagesEl.innerHTML = (gameState.chatLogs[tag] || []).map(m =>
        // 어필 결과 안내는 말풍선이 아니라 별도 스타일로 그린다
        m.sender.startsWith('appeal-note')
            ? `<div class="${m.sender}">${m.html}</div>`
            : `<div class="msg ${m.sender}">${m.html}</div>`
    ).join('');
}

// 협상 진행 상황(채용 버튼 / 상태 문구)도 같이 복원한다
function restoreNegotiationState(tag, cand) {
    const state = gameState.negotiation[tag];
    const statusBox = document.getElementById('decision-status-box');
    const hireBtn = document.getElementById('hire-confirm-btn');
    const statusText = document.getElementById('decision-status-text');

    if (state && state.hired) {
        statusBox.className = 'decision-status accepted';
        statusText.textContent = `협상 완료 (제안 연봉: $${state.demand.toLocaleString()})`;
        hireBtn.classList.remove('d-none');
        gameState.placementCandidateTag = tag;
        gameState.placementSalary = state.demand;
    } else if (state) {
        statusBox.className = 'decision-status';
        const offered = state.offered ? ` / 내 제안 $${state.offered.toLocaleString()}` : '';
        statusText.textContent = `협상 진행 중 (요구 $${state.demand.toLocaleString()}${offered})`;
        hireBtn.classList.add('d-none');
    } else {
        statusBox.className = 'decision-status';
        statusText.textContent = `대화 진행 중... (희망 연봉 $${cand.current_salary.toLocaleString()})`;
        hireBtn.classList.add('d-none');
    }
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

        // 지원자가 스스로 떠난 경우 (아주 드물게 발생)
        // 패널을 바로 지우면 왜 사라졌는지 알 수 없으므로 안내를 남긴다.
        if (data.walked_away) {
            statusBox.className = 'decision-status';
            document.getElementById('decision-status-text').textContent = '협상 결렬';
            hireBtn.classList.add('d-none');

            const notice = document.createElement('div');
            notice.className = 'left-notice';
            notice.textContent =
                `이 지원자는 떠났습니다. ${data.walk_reason || ''} 지원 목록에서도 사라집니다.`;
            document.getElementById('chat-messages').appendChild(notice);
            document.getElementById('chat-input').disabled = true;
            document.getElementById('chat-send-btn').disabled = true;

            showToast('🚪 지원자가 떠났습니다.');
            await fetchGameState();
            scrollToBottom();
            return;
        }

        // 어필이 통했는지 / 허풍이 들통났는지 알려준다
        if (data.appeal) {
            gameState.provenNeeds = (gameState.provenNeeds || [])
                .concat(data.appeal.hits.filter(h => !(gameState.provenNeeds || []).includes(h)));
            appendAppealNote(data.appeal);
        }

        // 이번 대화로 파악도가 올라갔을 수 있으니 갱신
        renderInsight(data.insight);

        // 협상 상태를 보관해두면 창을 닫았다 열어도 복원된다
        gameState.negotiation[tag] = {
            hired: data.hired,
            demand: data.salary_demanded,
            offered: data.offered_salary,
        };

        if (data.hired) {
            statusBox.className = 'decision-status accepted';
            document.getElementById('decision-status-text').textContent = `협상 완료 (제안 연봉: $${data.salary_demanded.toLocaleString()})`;
            hireBtn.classList.remove('d-none');

            gameState.placementCandidateTag = tag;
            gameState.placementSalary = data.salary_demanded;
        } else {
            statusBox.className = 'decision-status';
            const offered = data.offered_salary
                ? ` / 내 제안 $${data.offered_salary.toLocaleString()}`
                : '';
            document.getElementById('decision-status-text').textContent =
                `협상 진행 중 (요구 $${data.salary_demanded.toLocaleString()}${offered})`;
            hireBtn.classList.add('d-none');
        }

        // 요구 연봉이 내려갔을 수 있으니 목록도 갱신
        await fetchGameState();

    } catch (error) {
        loader.classList.add('d-none');
        showToast('❌ 오류: ' + error.message);
    }
    
    scrollToBottom();
}

// 어필 결과를 대화 흐름 안에 남긴다 (대화 기록에도 저장돼 다시 열어도 보인다)
function appendAppealNote(appeal) {
    const parts = [];
    if (appeal.hits.length) {
        parts.push({ cls: 'hit',
            text: `✓ ${appeal.hits.join(', ')} 어필이 통했습니다. 연봉을 더 깎을 여지가 생겼습니다.` });
    }
    if (appeal.misses.length) {
        parts.push({ cls: 'miss',
            text: `✗ ${appeal.misses.join(', ')}은(는) 사실과 달랐습니다. 신뢰를 잃었습니다.` });
    }
    const tag = gameState.selectedCandidateTag;
    parts.forEach(p => {
        const el = document.createElement('div');
        el.className = `appeal-note ${p.cls}`;
        el.textContent = p.text;
        document.getElementById('chat-messages').appendChild(el);
        if (tag) {
            if (!gameState.chatLogs[tag]) gameState.chatLogs[tag] = [];
            gameState.chatLogs[tag].push({ sender: `appeal-note ${p.cls}`, html: p.text });
        }
    });
}

function appendMessage(sender, text) {
    const html = text.replace(/\n/g, '<br>');
    const container = document.getElementById('chat-messages');
    const msg = document.createElement('div');
    msg.className = `msg ${sender}`;
    msg.innerHTML = html;
    container.appendChild(msg);

    // 창을 닫았다 열어도 남아 있도록 기록에 보관
    const tag = gameState.selectedCandidateTag;
    if (tag) {
        if (!gameState.chatLogs[tag]) gameState.chatLogs[tag] = [];
        gameState.chatLogs[tag].push({ sender, html });
    }
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

    // 면접을 시작해놓고 확정하지 않은 지원자는 주차가 넘어가면 떠난다
    const pending = (gameState.candidates || []).filter(c => c.interview_open);
    if (pending.length) {
        const names = pending.map(c => `· ${c.name}`).join('\n');
        const msg = `면접이 진행 중인 지원자가 있습니다.\n\n${names}\n\n`
            + '이번 주에 채용을 확정하지 않으면 이들은 마음을 접고 떠납니다.\n'
            + '그래도 다음 주로 넘어갈까요?';
        if (!confirm(msg)) return;
    }

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

        // 열려 있는 모달은 진행 상황도 같이 갱신
        if (!document.getElementById('biz-modal').classList.contains('d-none')) {
            await refreshBusinesses();
        }
        if (!document.getElementById('team-modal').classList.contains('d-none')) {
            await refreshTeam();
        }
        if (!document.getElementById('pool-modal').classList.contains('d-none')) {
            renderPool();
        }

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

// 풀에서 사라진 지원자의 대화 기록을 버린다
function forgetCandidate(tag) {
    if (!tag) return;
    delete gameState.chatLogs[tag];
    delete gameState.negotiation[tag];
}

// 면접 패널을 빈 상태로 되돌린다 (탈락 / 이탈 / 채용 후)
function clearInterviewPanel() {
    forgetCandidate(gameState.selectedCandidateTag);
    gameState.selectedCandidateTag = null;
    gameState.placementCandidateTag = null;
    document.getElementById('interview-active-panel').classList.add('d-none');
    document.getElementById('interview-header-empty').classList.remove('d-none');
    updateUI();
}

// 면접 창 확대 / 축소
function toggleInterviewExpand() {
    const sidebar = document.getElementById('right-sidebar');
    const btn = document.getElementById('expand-interview-btn');
    const expanded = sidebar.classList.toggle('expanded');
    btn.textContent = expanded ? '⤡ 축소' : '⤢ 확대';

    let backdrop = document.getElementById('expand-backdrop');
    if (expanded) {
        if (!backdrop) {
            backdrop = document.createElement('div');
            backdrop.id = 'expand-backdrop';
            backdrop.className = 'expand-backdrop';
            backdrop.onclick = toggleInterviewExpand;
            document.body.appendChild(backdrop);
        }
    } else if (backdrop) {
        backdrop.remove();
    }
    scrollToBottom();
}

// 지원자 탈락
async function rejectCandidate() {
    const tag = gameState.selectedCandidateTag;
    if (!tag) {
        showToast('⚠️ 선택된 지원자가 없습니다.');
        return;
    }
    const cand = gameState.candidates.find(c => c.tag === tag);
    if (!confirm(`${cand ? cand.name : '이 지원자'}를 탈락시킬까요? 지원 목록에서 사라집니다.`)) return;

    const r = await postJson('/api/candidates/reject', { developer_tag: tag });
    if (r) {
        showToast(`${r.name} 지원자를 탈락시켰습니다.`);
        await fetchGameState();
        clearInterviewPanel();
    }
}

function setupEventListeners() {
    // 면접 창 확대 / 탈락
    document.getElementById('expand-interview-btn').addEventListener('click', toggleInterviewExpand);
    document.getElementById('reject-candidate-btn').addEventListener('click', rejectCandidate);

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

    // 사업 관리 모달
    document.getElementById('open-biz-btn').addEventListener('click', openBizModal);
    document.getElementById('biz-close-btn').addEventListener('click', closeBizModal);
    document.getElementById('biz-modal').addEventListener('click', (e) => {
        if (e.target.id === 'biz-modal') closeBizModal();
    });
    document.querySelectorAll('.biz-tab').forEach(el => {
        el.addEventListener('click', () => {
            bizTab = el.dataset.tab;
            renderBusinesses();
        });
    });

    // 사무실 확장
    document.getElementById('upgrade-office-btn').addEventListener('click', upgradeOffice);

    // 면접 대기 줄 모달
    document.getElementById('open-pool-btn').addEventListener('click', openPoolModal);
    document.getElementById('pool-close-btn').addEventListener('click', closePoolModal);
    document.getElementById('pool-modal').addEventListener('click', (e) => {
        if (e.target.id === 'pool-modal') closePoolModal();
    });

    // 팀 & 기록 모달
    document.getElementById('open-team-btn').addEventListener('click', openTeamModal);
    document.getElementById('team-close-btn').addEventListener('click', closeTeamModal);
    document.getElementById('team-modal').addEventListener('click', (e) => {
        if (e.target.id === 'team-modal') closeTeamModal();
    });
    document.querySelectorAll('.team-tab').forEach(el => {
        el.addEventListener('click', () => {
            teamTab = el.dataset.tab;
            refreshTeam();
        });
    });
    
    // 엔터키 채팅 전송 (쉬프트 제외)
    document.getElementById('chat-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage();
        }
    });

    // 최종 채용 및 배치 모드 진입
    document.getElementById('hire-confirm-btn').addEventListener('click', () => {
        // 확대된 면접 창과 팝업이 캔버스를 덮고 있으면 책상을 클릭할 수 없다.
        // 배치 모드로 들어가기 전에 메인 화면을 되돌려준다.
        closePoolModal();
        if (document.getElementById('right-sidebar').classList.contains('expanded')) {
            toggleInterviewExpand();
        }

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

            // 채용이 끝났으면 대화 기록은 더 필요 없다
            forgetCandidate(gameState.placementCandidateTag);

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
