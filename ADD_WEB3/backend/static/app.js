// ===== 状态管理 =====
const state = {
  currentView: "home",
  subject: null,
  trial: null,
  step: 1,
  initialAction: null,
  initialConfidence: null,
  finalAction: null,
  finalConfidence: null,
  stepStartTs: null,
  scales: null,
  glucoseFocusAction: null,
  glucoseViewMode: "baseline",
  step1ResultVisible: false,
  decisionSubmitted: false,          // 决策是否已提交
  glucoseStreamingActive: false,     // 血糖流式加载是否进行中
  glucoseDisplayedUntil: 0,          // 已显示血糖数据至第几个点
  glucoseStreamingTimer: null,       // 流式加载定时器ID
  glucoseChartPanStart: null,        // 图表拖动起点
  glucoseChartPanOffset: 0,          // 图表拖动偏移
  glucoseChartPanBound: false,
  postSubmitAdvance: null,
  conditionMenuBound: false,
  scalesEditorBound: false,
};

// ===== API 请求 =====
const api = {
  async request(url, options = {}) {
    const res = await fetch(url, options);
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || `请求失败：${res.status}`);
    }
    return res.json();
  },
  createSubject(payload) {
    return this.request("/api/subjects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  getSubject(id) { return this.request(`/api/subjects/${id}`); },
  listSubjects() { return this.request("/api/subjects"); },
  nextTrial(id) { return this.request(`/api/experiment/${id}/next`); },
  logTrial(payload) {
    return this.request("/api/experiment/log", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  submitSurvey(payload) {
    return this.request("/api/surveys", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  getScales() { return this.request("/api/scales"); },
  saveScales(scales) {
    return this.request("/api/scales", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scales }),
    });
  },
  listSurveys() { return this.request("/api/surveys"); },
  listSubjectSurveys(subjectId) { return this.request(`/api/surveys/${subjectId}`); },
  completeTraining(subjectId) {
    return this.request("/api/experiment/training-complete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject_id: subjectId }),
    });
  },
  completeRest(subjectId, restDurationSeconds) {
    return this.request("/api/experiment/rest-complete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject_id: subjectId, rest_duration_seconds: restDurationSeconds }),
    });
  },
  getDashboard() { return this.request("/api/admin/dashboard"); },
  getSequence(subjectId) { return this.request(`/api/subjects/${subjectId}/sequence`); },
  updateLatin(subjectId, value, reason) {
    return this.request(`/api/subjects/${subjectId}/admin/latin-square`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value, reason }),
    });
  },
  updateMediaOrder(subjectId, value, reason) {
    return this.request(`/api/subjects/${subjectId}/admin/media-order`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value, reason }),
    });
  },
  updateCurrentTrial(subjectId, value, reason) {
    return this.request(`/api/subjects/${subjectId}/admin/current-trial`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value, reason }),
    });
  },
};

// ===== UI 工具函数 =====
function setView(view) {
  state.currentView = view;
  ["home", "experiment", "records", "scales", "notice"].forEach((name) => {
    document.getElementById(`view-${name}`).classList.toggle("hidden", name !== view);
  });
}

function updateTopbar() {
  if (!state.subject) {
    document.getElementById("subjectId").textContent = "被试：-";
    document.getElementById("moduleInfo").textContent = "准备中";
    document.getElementById("conditionDisplay").innerHTML = '<div class="condition-chip condition-chip-empty">条件准备中…</div>';
    return;
  }
  const subj = state.subject;
  document.getElementById("subjectId").textContent = `被试：${subj.subject_id}`;
  
  let moduleText = { HOME: "首页", TRAINING: "培训", PRE_SURVEY: "前测", RUNNING: "实验中", REST: "休息", POST_SURVEY: "后测", DONE: "已完成" }[subj.current_module];
  let progressText = `${subj.current_trial_index}/${subj.total_trials}`;
  document.getElementById("moduleInfo").textContent = `${moduleText} • 进度 ${progressText}`;
  
  if (state.trial) {
    const cond = state.trial.condition_display || `条件${state.trial.condition_id}`;
    const currentPos = state.trial.trial_index + 1;
    document.getElementById("conditionDisplay").innerHTML = `
      <div class="condition-chip" id="condDropdown">
        <div class="condition-chip-title">✓ ${cond}</div>
        <div class="condition-chip-sub">位置 ${currentPos}/${state.trial.total_trials}</div>
      </div>
      <div id="conditionDropdownMenu" class="condition-menu hidden">
        <div class="condition-menu-group">
          <div class="condition-menu-heading">已完成 (${state.trial.completed_conditions.length})</div>
          ${state.trial.completed_conditions.map((completed, idx) => `
            <div class="condition-menu-item done">✓ ${idx + 1}. ${completed}</div>
          `).join("")}
        </div>
        <div class="condition-menu-group">
          <div class="condition-menu-heading accent">待完成</div>
          ${state.trial.remaining_conditions.map((item) => `
            <div class="condition-menu-item ${item.trial_index === state.trial.trial_index ? 'current' : ''}">
              ${item.trial_index === state.trial.trial_index ? '▶ ' : ''}${item.trial_index + 1}. ${item.display_name}
            </div>
          `).join("")}
        </div>
      </div>
    `;
    if (!state.conditionMenuBound) {
      document.addEventListener("click", (event) => {
        const dropdown = document.getElementById("condDropdown");
        const menu = document.getElementById("conditionDropdownMenu");
        if (!dropdown || !menu) {
          return;
        }
        if (dropdown.contains(event.target)) {
          menu.classList.toggle("hidden");
          return;
        }
        if (!menu.contains(event.target)) {
          menu.classList.add("hidden");
        }
      });
      state.conditionMenuBound = true;
    }
  }
}

// ===== 动作标签和量表配置 =====
function actionLabel(code) {
  const map = {
    A: "快走 1 公里",
    B: "快走 2 公里",
    C: "慢跑 1 公里",
    D: "慢跑 2 公里",
    E: "什么都不做",
    WALK_1KM: "快走 1 公里",
    WALK_2KM: "快走 2 公里",
    RUN_1KM: "慢跑 1 公里",
    RUN_2KM: "慢跑 2 公里",
    NONE: "什么都不做",
  };
  return map[code] || code;
}

function get5PointLabels() {
  return ["完全不同意", "不同意", "一般", "同意", "完全同意"];
}

function normalizeScalesConfig(candidate) {
  candidate = candidate || {};
  const fallback = JSON.parse(JSON.stringify(state.scales || {
    pre: { title: "前测量表", sections: [] },
    post: { title: "后测量表", sections: [] },
    task_confidence: {
      title: "单任务信心量表",
      scale: "1-5",
      item: "您对刚才选择的运动方案，有多大把握认为它是正确的？",
    },
  }));
  const normalized = JSON.parse(JSON.stringify(fallback));

  if (candidate.pre) normalized.pre = candidate.pre;
  if (candidate.post) normalized.post = candidate.post;
  if (candidate.task_confidence) {
    normalized.task_confidence = {
      ...normalized.task_confidence,
      ...candidate.task_confidence,
    };
  }

  return normalized;
}

function stopGlucoseStreaming() {
  if (state.glucoseStreamingTimer) {
    clearTimeout(state.glucoseStreamingTimer);
    state.glucoseStreamingTimer = null;
  }
  state.glucoseStreamingActive = false;
}

function playAdviceMedia() {
  const audio = document.getElementById("adviceAudio");
  if (audio && typeof audio.play === "function") {
    audio.play().catch(() => {});
  }

  const video = document.querySelector(".video-player");
  if (video && typeof video.play === "function") {
    video.play().catch(() => {});
  }
}

function startGlucoseStreaming(series, targetMinute, onComplete) {
  stopGlucoseStreaming();

  const points = (series || []).filter((point) => point.minute <= targetMinute);
  if (!points.length) {
    state.glucoseDisplayedUntil = targetMinute;
    renderExperimentTrial();
    if (onComplete) onComplete();
    return;
  }

  state.glucoseStreamingActive = true;
  state.glucoseDisplayedUntil = points[0].minute;
  renderExperimentTrial();

  let index = 1;
  const tick = () => {
    if (index < points.length) {
      state.glucoseDisplayedUntil = points[index].minute;
      index += 1;
      renderExperimentTrial();
      state.glucoseStreamingTimer = setTimeout(tick, 1000);
      return;
    }

    stopGlucoseStreaming();
    state.glucoseDisplayedUntil = targetMinute;
    renderExperimentTrial();
    if (onComplete) onComplete();
  };

  state.glucoseStreamingTimer = setTimeout(tick, 1000);
}

// ===== 首页渲染 =====
async function openSubjectFlow() {
  state.subject = await api.getSubject(state.subject.subject_id);
  updateTopbar();
  if (state.subject.current_module === "TRAINING" || !state.subject.training_completed_at) await renderTraining();
  else if (state.subject.current_module === "PRE_SURVEY") await renderPreSurvey();
  else if (state.subject.current_module === "REST") await renderRest();
  else if (state.subject.current_module === "POST_SURVEY" || state.subject.current_trial_index >= state.subject.total_trials) await renderPostSurvey();
  else await loadNextTrial();
  setView("experiment");
}

function renderHome() {
  const el = document.getElementById("view-home");
  el.innerHTML = `
    <div class="home-grid">
      <div class="card">
        <h3>📋 新建被试</h3>
        <p class="muted">开始一项新实验；被试编号默认自动生成 P001、P002...</p>
        <input id="subject_id" placeholder="被试编号，可留空自动生成" />
        <input id="subject_name" placeholder="姓名" />
        <input id="subject_phone" placeholder="电话（可选）" />
        <input id="subject_age" type="number" min="18" max="95" placeholder="年龄" />
        <select id="subject_gender">
          <option value="M">男</option>
          <option value="F">女</option>
          <option value="Other">其他</option>
        </select>
        <select id="subject_latin">
          <option value="">自动推荐拉丁方分组</option>
          <option value="1">第1组</option>
          <option value="2">第2组</option>
          <option value="3">第3组</option>
          <option value="4">第4组</option>
        </select>
        <select id="subject_media_order">
          <option value="">按编号奇偶自动分配媒介顺序</option>
          <option value="voice_first">语音先</option>
          <option value="digital_human_first">数字人先</option>
        </select>
        <button class="primary" id="btnCreate">创建并进入培训阶段</button>
      </div>

      <div class="card">
        <h3>📊 被试记录</h3>
        <p class="muted">点击继续已有被试的实验</p>
        <div id="recordsPreview">加载中...</div>
      </div>

      <div class="card">
        <h3>⚙️ 系统设置</h3>
        <p>查看和编辑实验量表、阅读须知</p>
        <button class="primary" id="gotoScales" style="width:100%;margin:8px 0;">查看量表</button>
        <button class="primary" id="gotoNotice" style="width:100%;margin:8px 0;">实验须知</button>
      </div>
    </div>
  `;

  document.getElementById("gotoScales").onclick = () => setView("scales");
  document.getElementById("gotoNotice").onclick = () => setView("notice");

  document.getElementById("btnCreate").onclick = async () => {
    try {
      const payload = {
        subject_id: document.getElementById("subject_id").value.trim() || null,
        name: document.getElementById("subject_name").value.trim() || null,
        phone: document.getElementById("subject_phone").value.trim() || null,
        national_id: null,
        age: Number(document.getElementById("subject_age").value),
        gender: document.getElementById("subject_gender").value,
        latin_square_row: document.getElementById("subject_latin").value ? Number(document.getElementById("subject_latin").value) : null,
        media_order: document.getElementById("subject_media_order").value || null,
      };
      state.subject = await api.createSubject(payload);
      await openSubjectFlow();
    } catch (e) {
      alert(`创建失败: ${e.message}`);
    }
  };

  api.listSubjects().then((rows) => {
    const html = rows.slice(0, 5).map((r) => `
      <div style="padding:12px;border-bottom:2px solid var(--light);display:flex;justify-content:space-between;align-items:center;">
        <div>
          <div style="font-weight:600;font-size:18px;">${r.subject_id}</div>
          <div style="font-size:14px;color:var(--muted);">进度 ${r.current_trial_index}/${r.total_trials}</div>
        </div>
        <button data-continue="${r.subject_id}" class="secondary">继续</button>
      </div>
    `).join("");
    document.getElementById("recordsPreview").innerHTML = html || "<p class='muted'>暂无记录</p>";
    eval(html.match(/data-continue/g) ? `
      document.querySelectorAll('[data-continue]').forEach((btn) => {
        btn.onclick = async () => {
          state.subject = await api.getSubject(btn.dataset.continue);
          updateTopbar();
          await openSubjectFlow();
        };
      });
    ` : "");
  }).catch(() => {
    document.getElementById("recordsPreview").innerHTML = "<p class='muted'>读取失败</p>";
  });
}

function trainingDemoSeries() {
  const values = [5.2, 5.4, 5.8, 6.3, 7.1, 8.0, 9.2, 10.1, 10.8, 11.2, 11.0, 10.5, 9.8];
  return values.map((value, idx) => {
    const minute = -60 + idx * 5;
    return { minute, value, kind: minute === 0 ? "decision" : "history", label: minute === 0 ? "当前时刻" : `${minute}分钟`, state: value > 10 ? "血糖偏高" : "血糖处于可接受范围" };
  });
}

function renderTraining() {
  const container = document.getElementById("view-experiment");
  const demoSeries = trainingDemoSeries();
  const actionOptions = [
    { code: "A", label: "快走 1 公里" },
    { code: "B", label: "快走 2 公里" },
    { code: "C", label: "慢跑 1 公里" },
    { code: "D", label: "慢跑 2 公里" },
    { code: "E", label: "什么都不做" },
  ];
  let page = 0;
  let practiceAction = null;
  let practiceConfidence = null;
  const explanations = [
    "这条曲线显示您过去60分钟的血糖变化",
    "红色虚线是血糖偏高的警戒线（10.0 mmol/L）",
    "曲线末端是您当前的血糖值，旁边的数字是系统预测30分钟和60分钟后的血糖",
  ];

  const render = () => {
    if (page < 3) {
      state.step1ResultVisible = false;
      state.decisionSubmitted = false;
      const chart = renderGlucoseChart(demoSeries, { min_minutes: -60, max_minutes: 0, time_marks: [-60, -45, -30, -15, 0] }, "培训演示：血糖曲线读法", {
        minute_30: { value: 10.3, text: "30分钟预测" },
        minute_60: { value: 9.6, text: "60分钟预测" },
        summary: "本图仅用于培训，不写入正式实验数据",
      });
      container.innerHTML = `
        <div class="survey-layout training-layout">
          <div class="survey-header"><h2>进入培训阶段</h2><div class="survey-section-marker">演示1：血糖曲线读法培训</div></div>
          <div class="survey-content">${chart}<div class="question-card"><div class="question-text">${explanations[page]}</div></div></div>
          <div class="survey-footer"><button class="primary" id="trainingNext">${page === 2 ? "进入操作练习" : "下一步"}</button></div>
        </div>`;
      document.getElementById("trainingNext").onclick = () => { page += 1; render(); };
      return;
    }

    if (page === 3) {
      container.innerHTML = `
        <div class="survey-layout training-layout">
          <div class="survey-header"><h2>决策操作与信心评分培训</h2><div class="survey-section-marker">请实际点击一次选项并提交一次信心评分</div></div>
          <div class="survey-content">
            <div class="question-card"><div class="question-text">请根据当前血糖情况，选择您认为最合适的运动方案</div><div class="scale-hint">选择后，系统会显示这个选择预计对您血糖的影响。例如选择快走1公里后，点击确认。</div></div>
            <div class="choice-grid">${actionOptions.map(opt => `<button class="choice-btn ${practiceAction === opt.code ? "active" : ""} ${opt.code === "A" && !practiceAction ? "training-highlight" : ""}" data-practice-action="${opt.code}"><div>选项${opt.code}</div><div>${opt.label}</div></button>`).join("")}</div>
            <div class="confidence-box"><div class="confidence-title">选择完成后，请评估您对这个决策正确程度的信心</div><div class="scale-hint">1分=完全没把握，5分=非常有把握</div><div class="confidence-buttons">${[1,2,3,4,5].map(n => `<button class="conf-btn ${practiceConfidence === n ? "active" : ""}" data-practice-conf="${n}"><div class="conf-value">${n}</div></button>`).join("")}</div></div>
          </div>
          <div class="survey-footer"><button class="primary" id="finishPractice">确认练习选择</button></div>
        </div>`;
      container.querySelectorAll("[data-practice-action]").forEach(btn => { btn.onclick = () => { practiceAction = btn.dataset.practiceAction; render(); }; });
      container.querySelectorAll("[data-practice-conf]").forEach(btn => { btn.onclick = () => { practiceConfidence = Number(btn.dataset.practiceConf); render(); }; });
      document.getElementById("finishPractice").onclick = () => {
        if (!practiceAction || !practiceConfidence) { alert("请先选择一个运动方案，并完成1-5分信心评分。"); return; }
        page = 4; render();
      };
      return;
    }

    const questions = [
      { key: "q1", text: "血糖曲线末端的数字代表？", options: [["A", "您昨天的血糖"], ["B", "您当前的血糖"], ["C", "医生设定的目标值"]], answer: "B", hint: "请重看血糖曲线读法培训。" },
      { key: "q2", text: "信心评分5分表示？", options: [["A", "完全没把握"], ["B", "一般"], ["C", "非常有把握"]], answer: "C", hint: "请重看信心评分说明。" },
      { key: "q3", text: "如果您觉得不需要运动，应该选择？", options: [["A", "慢跑2公里"], ["B", "什么都不做"], ["C", "快走1公里"]], answer: "B", hint: "请重看决策选项培训。" },
    ];
    const answers = {};
    container.innerHTML = `
      <div class="survey-layout training-layout">
        <div class="survey-header"><h2>理解确认</h2><div class="survey-section-marker">全部答对后解锁正式实验</div></div>
        <div class="survey-content"><div class="question-card"><div class="question-text">很好！您已经了解了操作方式，接下来完成3道确认题。</div></div>${questions.map(q => `<div class="question-card"><div class="question-text">${q.text}</div><div class="scale-buttons">${q.options.map(([value, text]) => `<button class="scale-btn" data-quiz="${q.key}" data-answer="${value}"><div class="score">${value}</div><div class="meaning">${text}</div></button>`).join("")}</div></div>`).join("")}</div>
        <div class="survey-footer"><button class="secondary" id="reviewTraining">重看培训</button><button class="primary" id="submitQuiz">完成培训，解锁正式实验</button></div>
      </div>`;
    container.querySelectorAll("[data-quiz]").forEach(btn => {
      btn.onclick = () => {
        answers[btn.dataset.quiz] = btn.dataset.answer;
        container.querySelectorAll(`[data-quiz="${btn.dataset.quiz}"]`).forEach(item => item.classList.remove("active"));
        btn.classList.add("active");
      };
    });
    document.getElementById("reviewTraining").onclick = () => { page = 0; render(); };
    document.getElementById("submitQuiz").onclick = async () => {
      const wrong = questions.find(q => answers[q.key] !== q.answer);
      if (wrong) { alert(`回答不正确：${wrong.hint}`); page = wrong.key === "q1" ? 0 : 3; render(); return; }
      await api.completeTraining(state.subject.subject_id);
      state.subject = await api.getSubject(state.subject.subject_id);
      updateTopbar();
      await renderPreSurvey();
    };
  };
  render();
}

// ===== 前测渲染（多模块） =====
async function renderPreSurvey() {
  const scaleCfg = await api.getScales();
  state.scales = scaleCfg.scales;
  const pre = state.scales.pre;
  
  const container = document.getElementById("view-experiment");
  
  // 多模块布局
  const sectionsHtml = pre.sections.map((section, sIdx) => `
    <div class="survey-section">
      <div class="section-title">${sIdx + 1}. ${section.name}</div>
      ${section.items.map((item, iIdx) => `
        <div class="question-card">
          <div class="question-text">${item}</div>
          <div class="scale-hint">1=非常不同意，5=完全同意</div>
          <div class="scale-buttons">
            ${[1,2,3,4,5].map(score => `
              <button class="scale-btn" data-pre-section="${sIdx}" data-pre-item="${iIdx}" data-score="${score}">
                <div class="score">${score}</div>
                <div class="meaning">${get5PointLabels()[score - 1]}</div>
              </button>
            `).join("")}
          </div>
        </div>
      `).join("")}
    </div>
  `).join("");

  container.innerHTML = `
    <div class="survey-layout">
      <div class="survey-header">
        <h2>${pre.title}</h2>
        <div class="survey-section-marker">请逐项完成以下问卷</div>
      </div>
      <div class="survey-content">
        ${sectionsHtml}
      </div>
      <div class="survey-footer">
        <button class="primary" id="submitPre" style="min-width:200px;height:50px;">提交前测，开始实验</button>
      </div>
    </div>
  `;

  const responses = {};
  container.querySelectorAll(".scale-btn").forEach((btn) => {
    btn.onclick = () => {
      const sIdx = btn.dataset.preSection;
      const iIdx = btn.dataset.preItem;
      const score = btn.dataset.score;
      if (!responses[sIdx]) responses[sIdx] = {};
      responses[sIdx][iIdx] = score;
      
      // 更新 UI
      container.querySelectorAll(`[data-pre-section="${sIdx}"][data-pre-item="${iIdx}"]`).forEach(b => {
        b.classList.remove("active");
      });
      btn.classList.add("active");
    };
  });

  document.getElementById("submitPre").onclick = async () => {
    const allScores = {};
    for (let s in responses) {
      for (let i in responses[s]) {
        allScores[`${s}_${i}`] = Number(responses[s][i]);
      }
    }
    await api.submitSurvey({
      subject_id: state.subject.subject_id,
      survey_type: "pre",
      payload: { scale: "pre_combined", answers: allScores },
    });
    await loadNextTrial();
  };
}

// ===== 实验试验渲染 =====
function renderExperimentTrial() {
  const t = state.trial;
  const c = document.getElementById("view-experiment");
  const step1ResultVisible = state.step === 1 && state.step1ResultVisible;
  const finalResultVisible = state.step === 2 && state.decisionSubmitted;
  const activeAction = step1ResultVisible
    ? state.initialAction
    : (finalResultVisible ? state.finalAction : null);

  state.glucoseFocusAction = activeAction || null;
  state.glucoseViewMode = activeAction ? "feedback" : "baseline";

  const chartSeries = activeAction ? (t.glucose_outcome_series[activeAction] || t.glucose_series) : t.glucose_series;
  const summary = activeAction ? t.glucose_outcome_summary[activeAction] : null;
  const visibleSeries = state.glucoseStreamingActive
    ? chartSeries.filter((point) => point.minute <= state.glucoseDisplayedUntil)
    : ((step1ResultVisible || finalResultVisible)
      ? chartSeries.filter((point) => point.minute <= 150)
      : chartSeries.filter((point) => point.minute <= 60));
  const topGlucosePoint = [...visibleSeries].reverse().find((point) => !isPredictionPoint(point)) || visibleSeries[visibleSeries.length - 1] || null;
  const topGlucoseValue = topGlucosePoint ? topGlucosePoint.value : t.trigger_glucose;
  const chartModeLabel = activeAction ? `${actionLabel(activeAction)} · 行为结果反馈` : `基础血糖曲线`;
  const chartMarkup = renderGlucoseChart(chartSeries, { ...t.glucose_axis, events: t.glucose_events }, chartModeLabel, summary);
  const baseSummary = {
    minute_30: { value: t.glucose_30, text: "基础预测" },
    minute_60: { value: t.glucose_60, text: "基础预测" },
    summary: "基础血糖预测，尚未切换到行为结果。",
  };
  const currentSummary = activeAction
    ? summary
    : (state.glucoseDisplayedUntil >= 60 ? baseSummary : null);
  const modeHint = step1ResultVisible
    ? `当前显示 ${actionLabel(state.initialAction)} 的 2 小时结果反馈。`
    : (finalResultVisible
      ? `当前显示 ${actionLabel(state.finalAction)} 的 2 小时结果反馈。`
      : (state.step === 2
        ? (state.glucoseStreamingActive
          ? "血糖曲线逐点展示中，建议将在更新完成后自动播放。"
          : "已展示到预测点，可继续选择决策。")
        : (state.glucoseStreamingActive
          ? "血糖曲线逐点展示中，基础预测会在更新完成后出现。"
          : "基础血糖曲线正在逐点展示。")));

  c.innerHTML = `
    <div class="exp-layout">
      <!-- 上半部分：血糖 + 建议 -->
      <div class="exp-top">
        <div class="panel">
          <div class="glucose-section">
            <div class="glucose-header">
              <div class="glucose-header-left">
                <div class="glucose-now">${topGlucoseValue.toFixed(1)}</div>
                <div class="glucose-unit">mmol/L</div>
                <div class="glucose-meta">${state.glucoseViewMode === "feedback" ? "结果反馈" : "基础血糖"} · ${modeHint}</div>
              </div>
              <div class="glucose-predictions">
                ${currentSummary ? `
                  <div class="pred-item">
                    <div class="pred-label">30分钟预测</div>
                    <div class="pred-value">${currentSummary.minute_30.value.toFixed(1)}</div>
                    <div class="glucose-summary-text">${currentSummary.minute_30.text}</div>
                  </div>
                  <div class="pred-item">
                    <div class="pred-label">60分钟预测</div>
                    <div class="pred-value">${currentSummary.minute_60.value.toFixed(1)}</div>
                    <div class="glucose-summary-text">${currentSummary.minute_60.text}</div>
                  </div>
                ` : `
                  <div class="pred-item" style="grid-column: 1 / -1;">
                    <div class="pred-label">预测值</div>
                    <div class="glucose-summary-text">曲线更新完成后显示基础预测</div>
                  </div>
                `}
              </div>
            </div>
            ${chartMarkup}
          </div>
        </div>

        <!-- advice panel -->
        <div class="panel advice-panel ${state.step === 2 ? 'visible' : ''}">
          ${state.step === 2 ? `
            <div class="advice-title">智能建议</div>
            <div class="audio-player">
              ${state.glucoseStreamingActive ? `<div class="advice-status">建议将在曲线更新完成后自动播放</div>` : ''}
              ${["audio", "voice"].includes(t.condition_media) && t.audio_url
                ? ((state.glucoseStreamingActive || finalResultVisible)
                  ? `<div class="speaker-icon-large locked">🔊</div><audio id="adviceAudio" src="${t.audio_url}" onerror="console.error('音频加载失败：', '${t.audio_url}'); alert('音频加载失败：${t.audio_url}');" preload="auto"></audio>`
                  : `<div class="speaker-icon-large" onclick="document.getElementById('adviceAudio').play();">🔊</div><audio id="adviceAudio" src="${t.audio_url}" onerror="console.error('音频加载失败：', '${t.audio_url}'); alert('音频加载失败：${t.audio_url}');" preload="auto"></audio>`)
                : (["audio", "voice"].includes(t.condition_media)
                  ? `<div style="padding:20px;color:red;text-align:center;"><strong>音频缺失</strong><br/>条件编号：${t.condition_id}</div>`
                  : "")}
              ${["avatar", "digital_human"].includes(t.condition_media) && t.video_url
                ? `<video class="video-player ${(state.glucoseStreamingActive || finalResultVisible) ? 'locked' : ''}" ${(state.glucoseStreamingActive || finalResultVisible) ? '' : 'controls'} src="${t.video_url}" onerror="console.error('视频加载失败：', '${t.video_url}'); alert('视频加载失败：${t.video_url}');"></video>`
                : (["avatar", "digital_human"].includes(t.condition_media)
                  ? `<div style="padding:20px;color:red;text-align:center;"><strong>视频缺失</strong><br/>条件编号：${t.condition_id}</div>`
                  : "")}
              <div class="advice-text">${t.advice_text}</div>
            </div>
          ` : ''}
        </div>
      </div>

      <!-- 下半部分：决策 -->
      <div class="decision-panel" id="decisionPanel"></div>
    </div>
  `;

  updateTopbar();
  renderDecisionPanel();
  
  // 为血糖图表添加拖动交互（防止动态渲染时显示问题）
  setTimeout(() => {
    const chartContainer = document.getElementById("glucoseChartContainer");
    if (chartContainer && chartContainer.querySelector("svg") && !state.glucoseChartPanBound) {
      state.glucoseChartPanBound = true;
      let isPanning = false;
      let startX = 0;
      let startOffset = state.glucoseChartPanOffset || 0;
      
      chartContainer.addEventListener("mousedown", (e) => {
        isPanning = true;
        startX = e.clientX;
        startOffset = state.glucoseChartPanOffset || 0;
        chartContainer.style.cursor = "grabbing";
      });
      
      document.addEventListener("mousemove", (e) => {
        const chartSvg = document.getElementById("glucoseChartContainer")?.querySelector("svg");
        if (isPanning && chartSvg) {
          const delta = e.clientX - startX;
          state.glucoseChartPanOffset = startOffset + delta;
          chartSvg.style.transform = `translateX(${state.glucoseChartPanOffset}px)`;
        }
      });
      
      document.addEventListener("mouseup", () => {
        isPanning = false;
        chartContainer.style.cursor = "grab";
      });
      
      // 触摸支持（移动设备）
      chartContainer.addEventListener("touchstart", (e) => {
        isPanning = true;
        startX = e.touches[0].clientX;
        startOffset = state.glucoseChartPanOffset || 0;
      });
      
      document.addEventListener("touchmove", (e) => {
        const chartSvg = document.getElementById("glucoseChartContainer")?.querySelector("svg");
        if (isPanning && chartSvg) {
          const delta = e.touches[0].clientX - startX;
          state.glucoseChartPanOffset = startOffset + delta;
          chartSvg.style.transform = `translateX(${state.glucoseChartPanOffset}px)`;
        }
      });
      
      document.addEventListener("touchend", () => {
        isPanning = false;
      });
    }
  }, 0);
  
  // 调试信息：输出当前试验的媒体配置
  console.log(`
╔════════════════════════════════════════════════════════╗
║          当前试验媒体信息（调试）                     ║
╠════════════════════════════════════════════════════════╣
║ 条件ID: ${t.condition_id}
║ 媒体类型: ${t.condition_media}
║ 音频URL: ${t.audio_url || "未配置"}
║ 视频URL: ${t.video_url || "未配置"}
║ 步骤: ${state.step}/2
╠════════════════════════════════════════════════════════╣
║ 建议：若媒体文件未加载，请：
║ 1. 按 F12 打开控制台，查看上述链接是否正确
║ 2. 访问 /api/debug/media 查看服务器可用的媒体文件
║ 3. 确认 backend/media/ 中的文件已更新
╚════════════════════════════════════════════════════════╝
  `);
}

function generateGlucoseCurve(glucoseSeries) {
  const minValue = Math.min(...glucoseSeries.map(p => p.value));
  const maxValue = Math.max(...glucoseSeries.map(p => p.value));
  const minMinute = Math.min(...glucoseSeries.map(p => p.minute));
  const maxMinute = Math.max(...glucoseSeries.map(p => p.minute));
  const minuteSpan = Math.max(maxMinute - minMinute, 1);
  const points = glucoseSeries.map((p) => {
    const x = 60 + ((p.minute - minMinute) / minuteSpan) * 720;
    const y = 200 - ((p.value - minValue) / (maxValue - minValue + 1.8)) * 170;
    return `${x},${y}`;
  });
  return points.join(' ');
}

function glucoseKindClass(kind) {
  if (kind === "meal") return "point-meal";
  if (kind === "decision") return "point-decision";
  if (kind === "outcome_30") return "point-outcome-30";
  if (kind === "outcome_60") return "point-outcome-60";
  if (kind === "future" || kind === "forecast") return "point-future";
  return "point-history";
}

function glucoseKindLabel(kind) {
  if (kind === "meal") return "进食";
  if (kind === "decision") return "决策";
  if (kind === "outcome_30") return "+30min";
  if (kind === "outcome_60") return "+60min";
  return "15min";
}

function isPredictionPoint(point) {
  return point?.kind === "future" || point?.kind === "forecast";
}

function glucoseMinuteLabel(minute) {
  if (minute === 0) return "0";
  if (minute > 0) return `+${minute}`;
  return `${minute}`;
}

function getGlucoseRegionBounds(series, axis) {
  const minMinute = axis?.min_minutes ?? Math.min(...series.map((point) => point.minute));
  const maxMinute = axis?.max_minutes ?? Math.max(...series.map((point) => point.minute));
  const decisionPoint = series.find((point) => point.kind === "decision") || series.find((point) => point.minute === 0) || null;
  const decisionMinute = decisionPoint?.minute ?? 0;
  let nearestStep = 15;

  for (let index = 1; index < series.length; index += 1) {
    const delta = Math.abs(series[index].minute - series[index - 1].minute);
    if (delta > 0 && delta < nearestStep) {
      nearestStep = delta;
    }
  }

  const halfBand = Math.max(nearestStep / 2, 7.5);

  return {
    minMinute,
    maxMinute,
    decisionMinute,
    decisionStart: decisionMinute - halfBand,
    decisionEnd: decisionMinute + halfBand,
  };
}

function glucosePointSymbol(point, x, y) {
  if (point.kind === "meal") {
    return `<polygon points="${x},${y - 7} ${x - 7},${y + 5} ${x + 7},${y + 5}" class="${glucoseKindClass(point.kind)}"/>`;
  }
  if (point.kind === "decision") {
    return `<rect x="${x - 6}" y="${y - 6}" width="12" height="12" rx="2" transform="rotate(45 ${x} ${y})" class="${glucoseKindClass(point.kind)}"/>`;
  }
  if (point.kind === "outcome_30") {
    return `<circle cx="${x}" cy="${y}" r="6.4" class="${glucoseKindClass(point.kind)}"/><circle cx="${x}" cy="${y}" r="3.2" fill="white" opacity="0.92"/>`;
  }
  if (point.kind === "outcome_60") {
    return `<rect x="${x - 5}" y="${y - 5}" width="10" height="10" rx="2" class="${glucoseKindClass(point.kind)}"/>`;
  }
  return `<circle cx="${x}" cy="${y}" r="${point.kind === 'future' ? 4 : 4.5}" class="${glucoseKindClass(point.kind)}"/>`;
}

function renderGlucoseChart(series, axis, modeLabel, summary) {
  const minValue = Math.min(...series.map(point => point.value));
  const maxValue = Math.max(...series.map(point => point.value));
  const minMinute = axis?.min_minutes ?? Math.min(...series.map(point => point.minute));
  const maxMinute = axis?.max_minutes ?? Math.max(...series.map(point => point.minute));
  const minuteSpan = Math.max(maxMinute - minMinute, 1);
  const valueSpan = Math.max(maxValue - minValue, 0.1);
  const yPadding = Math.max(valueSpan * 0.18, 0.4);
  const lower = minValue - yPadding;
  const upper = maxValue + yPadding;
  const xAt = (minute) => 72 + ((minute - minMinute) / minuteSpan) * 688;
  const yAt = (value) => 224 - ((value - lower) / (upper - lower)) * 174;
  const ticks = [lower, lower + (upper - lower) / 3, lower + ((upper - lower) * 2) / 3, upper];
  const timeMarks = axis?.time_marks || series.map(point => point.minute);
  const eventMap = new Map((axis?.events || []).map((event) => [event.minute, event]));
  const regionBounds = getGlucoseRegionBounds(series, axis);
  const regionTop = 30;
  const regionBottom = 224;
  const regionRect = (leftMinute, rightMinute, className) => {
    const left = Math.max(xAt(leftMinute), 72);
    const right = Math.min(xAt(rightMinute), 792);
    const width = Math.max(right - left, 0);
    return width > 0
      ? `<rect x="${left}" y="${regionTop}" width="${width}" height="${regionBottom - regionTop}" rx="16" class="glucose-region ${className}"/>`
      : "";
  };
  const summaryHtml = summary
    ? `
      <div class="glucose-summary-grid">
        <div class="glucose-summary-card">
          <div class="pred-value">${summary.minute_30.value.toFixed(1)}</div>
          <div class="glucose-summary-text">${summary.minute_30.text}</div>
          ${summary.minute_30.kind === "range" ? '<div class="glucose-badge">区间型结果</div>' : ''}
        </div>
        <div class="glucose-summary-card">
          <div class="pred-value">${summary.minute_60.value.toFixed(1)}</div>
          <div class="glucose-summary-text">${summary.minute_60.text}</div>
          ${summary.minute_60.kind === "range" ? '<div class="glucose-badge">区间型结果</div>' : ''}
        </div>
        <div class="glucose-summary-card accent-card">
          <div class="pred-label">结果判断</div>
          <div class="glucose-summary-text strong">${summary.summary}</div>
        </div>
      </div>
    `
    : `
      <div class="glucose-summary-grid">
        <div class="glucose-summary-card accent-card" style="grid-column: 1 / -1;">
          <div class="pred-label">预测值</div>
          <div class="glucose-summary-text strong">曲线更新完成后显示基础预测</div>
        </div>
      </div>
    `;

  // 根据流式加载状态过滤显示的数据点
  const displayedSeries = state.glucoseStreamingActive 
    ? series.filter(point => point.minute <= state.glucoseDisplayedUntil)
    : ((state.step1ResultVisible || state.decisionSubmitted) 
      ? series.filter(point => point.minute <= 150) // 提交后显示完整到+150min
      : series.filter(point => point.minute <= 60));

  // 构建SVG中要显示的点（含连线）
  const visiblePointsInChart = displayedSeries.map((point, idx) => {
    const x = xAt(point.minute);
    const y = yAt(point.value);
    const nextDisplayed = displayedSeries[idx + 1];
    
    // 线条颜色
    const lineColor = 'rgba(15, 23, 42, 0.58)';
    
    return {
      point,
      x,
      y,
      line: nextDisplayed ? `<line x1="${x}" y1="${y}" x2="${xAt(nextDisplayed.minute)}" y2="${yAt(nextDisplayed.value)}" stroke="${lineColor}" stroke-width="3" fill="none" opacity="0.95"/>` : '',
      symbol: glucosePointSymbol(point, x, y),
      labels: `
        <text x="${x}" y="${y - 16}" class="glucose-point-label" text-anchor="middle">${point.value.toFixed(1)}</text>
        ${point.kind === 'meal' || point.kind === 'decision' || point.kind.startsWith('outcome') ? `<text x="${x}" y="${y + 39}" class="glucose-point-state" text-anchor="middle">${glucoseKindLabel(point.kind)}</text>` : ''}
        ${eventMap.has(point.minute) ? `<text x="${x}" y="${y + 54}" class="glucose-point-state" text-anchor="middle">${eventMap.get(point.minute).label}</text>` : ''}
      `
    };
  });

  return `
    <div class="glucose-chart-shell">
      <div class="glucose-chart-header">
        <div>
          <div class="glucose-chart-title">${modeLabel}</div>
        </div>
        <div class="glucose-legend">
          <span><i class="legend-swatch region-history"></i>决策前</span>
          <span><i class="legend-swatch region-decision"></i>决策点</span>
          <span><i class="legend-swatch region-future"></i>决策后预测</span>
        </div>
      </div>
      <div class="glucose-chart-container" id="glucoseChartContainer" style="touch-action: pan-y; user-select: none;">
        <svg class="glucose-chart" viewBox="0 0 820 300" preserveAspectRatio="xMidYMid meet" style="cursor: grab; transition: transform 0.05s linear;">
          ${regionRect(minMinute, regionBounds.decisionStart, "glucose-region-history")}
          ${regionRect(regionBounds.decisionStart, regionBounds.decisionEnd, "glucose-region-decision")}
          ${regionRect(regionBounds.decisionEnd, maxMinute, "glucose-region-future")}

          <line x1="72" y1="30" x2="72" y2="225" stroke="var(--border)" stroke-width="2"/>
          <line x1="72" y1="224" x2="792" y2="224" stroke="var(--border)" stroke-width="2"/>
          <line x1="72" y1="${yAt(10.0)}" x2="792" y2="${yAt(10.0)}" stroke="var(--danger)" stroke-width="2" stroke-dasharray="8 6" opacity="0.78"/>
          <text x="788" y="${yAt(10.0) - 6}" font-size="12" text-anchor="end" fill="var(--danger)" font-weight="700">10.0 mmol/L</text>

          ${ticks.map((tick) => {
            const y = yAt(tick);
            return `
              <line x1="62" y1="${y}" x2="72" y2="${y}" stroke="var(--border)" stroke-width="1.2"/>
              <text x="56" y="${y + 4}" font-size="12" text-anchor="end" fill="var(--muted)">${tick.toFixed(1)}</text>
            `;
          }).join("")}

          <text x="28" y="126" font-size="12" font-weight="700" text-anchor="middle" fill="var(--muted)" transform="rotate(-90 28 126)">血糖值（mmol/L）</text>

          ${timeMarks.map((minute) => {
            const x = xAt(minute);
            const isHidden = state.glucoseStreamingActive && minute > state.glucoseDisplayedUntil;
            const opacity = isHidden ? 0.2 : 1;
            return `
              <line x1="${x}" y1="224" x2="${x}" y2="230" stroke="var(--border)" stroke-width="1" opacity="${opacity}"/>
              <text x="${x}" y="246" font-size="11" text-anchor="middle" fill="var(--muted)" opacity="${opacity}">${minute === 0 ? "0" : minute > 0 ? `+${minute}` : minute}</text>
            `;
          }).join("")}

          ${visiblePointsInChart.map(item => `
            ${item.line}
            <g>
              ${item.symbol}
              ${item.labels}
            </g>
          `).join("")}
        </svg>
      </div>
      ${summaryHtml}
    </div>
  `;
}

function renderDecisionPanel() {
  const t = state.trial;
  const root = document.getElementById("decisionPanel");
  const step1ResultVisible = state.step === 1 && state.step1ResultVisible;
  const finalResultVisible = state.step === 2 && state.decisionSubmitted;
  const selected = state.step === 1 ? state.initialAction : state.finalAction;
  const conf = state.step === 1 ? state.initialConfidence : state.finalConfidence;
  const isLocked = step1ResultVisible || finalResultVisible;

  const title = state.step === 1
    ? (step1ResultVisible ? "初始决策结果" : "初始决策")
    : (finalResultVisible ? "任务结果" : "最终决策");

  root.innerHTML = `
    <div class="decision-title">${title}</div>
    <div class="choice-grid ${isLocked ? 'locked' : ''}">
      ${t.action_options.map(opt => `
        <button class="choice-btn ${selected === opt.code ? 'active' : ''}" data-action="${opt.code}" ${isLocked ? 'disabled' : ''}>
          <div>${opt.label}</div>
        </button>
      `).join("")}
    </div>

    <div class="confidence-box">
      <div class="confidence-title">${state.step === 1 ? "您对刚才选择的运动方案，有多大把握认为它是正确的？" : "看到系统建议后，您对现在选择的运动方案，有多大把握认为它是正确的？"}</div>
      <div class="scale-hint">（1=完全没把握，5=非常有把握）</div>
      <div class="confidence-buttons">
        ${[1,2,3,4,5].map(n => `
          <button class="conf-btn ${conf === n ? 'active' : ''}" data-conf="${n}" ${isLocked ? 'disabled' : ''}>
            <div class="conf-value">${n}</div>
            <div class="conf-label">${['完全没把握', '较没把握', '一般', '较有把握', '非常有把握'][n-1]}</div>
          </button>
        `).join("")}
      </div>
    </div>

    ${isLocked ? `<div class="decision-locked-hint" style="padding:12px;background:rgba(16,185,129,0.1);border-radius:8px;color:var(--success);font-weight:600;">流式展示或结果展示中，当前已锁定</div>` : ''}

    <div class="button-group">
      ${state.step === 1
        ? (step1ResultVisible
          ? `<button class="btn-submit primary" id="toStep2">继续到决策2</button>`
          : `<button class="btn-submit primary" id="toStep1Result">提交初始决策</button>`)
        : (finalResultVisible
          ? `<button class="btn-submit primary" id="advanceTrial" ${state.postSubmitAdvance ? '' : 'disabled'}>继续下一个任务</button>`
          : `<button class="btn-submit primary" id="submitTrial">提交任务</button>`)}
    </div>
  `;

  root.querySelectorAll("button[data-action]:not([disabled])").forEach(btn => {
    btn.onclick = () => {
      const action = btn.dataset.action;
      if (state.step === 1) state.initialAction = action;
      else state.finalAction = action;
      renderDecisionPanel();
    };
  });

  root.querySelectorAll("button[data-conf]:not([disabled])").forEach(btn => {
    btn.onclick = () => {
      const conf = Number(btn.dataset.conf);
      if (state.step === 1) state.initialConfidence = conf;
      else state.finalConfidence = conf;
      renderDecisionPanel();
    };
  });

  if (state.step === 1 && !step1ResultVisible) {
    document.getElementById("toStep1Result").onclick = () => {
      if (!state.initialAction || !state.initialConfidence) {
        alert("请先选择行为和信心程度");
        return;
      }
      stopGlucoseStreaming();
      state.step1ResultVisible = true;
      state.glucoseViewMode = "feedback";
      state.glucoseFocusAction = state.initialAction;
      state.glucoseDisplayedUntil = 150;
      renderDecisionPanel();
      renderExperimentTrial();
    };
  } else if (state.step === 1 && step1ResultVisible) {
    document.getElementById("toStep2").onclick = () => {
      state.step = 2;
      state.step1ResultVisible = false;
      state.stepStartTs = Date.now();
      state.decisionSubmitted = false;
      state.glucoseViewMode = "baseline";
      state.glucoseFocusAction = null;
      state.glucoseDisplayedUntil = -30;
      renderExperimentTrial();
      startGlucoseStreaming(t.glucose_series, 60, () => {
        setTimeout(playAdviceMedia, 0);
      });
    };
  } else if (state.step === 2 && !finalResultVisible) {
    document.getElementById("submitTrial").onclick = submitTrial;
  } else if (state.step === 2 && finalResultVisible) {
    document.getElementById("advanceTrial").onclick = async () => {
      if (typeof state.postSubmitAdvance === "function") {
        await state.postSubmitAdvance();
      }
    };
  }
}

async function submitTrial() {
  if (!state.finalAction || !state.finalConfidence) {
    alert("请选择行为和信心程度");
    return;
  }

  state.decisionSubmitted = true;
  stopGlucoseStreaming();
  state.glucoseFocusAction = state.finalAction;
  state.glucoseViewMode = "feedback";
  state.glucoseDisplayedUntil = 150;
  renderExperimentTrial();

  // 保存日志到后端
  const responseTime = state.stepStartTs ? Date.now() - state.stepStartTs : 0;
  const payload = {
    subject_id: state.subject.subject_id,
    trial_index: state.trial.trial_index,
    initial_action: state.initialAction,
    initial_confidence: state.initialConfidence,
    final_action: state.finalAction,
    final_confidence: state.finalConfidence,
    response_time_ms: responseTime,
    advice_start_ts: state.stepStartTs,
    advice_end_ts: Date.now(),
  };

  try {
    const result = await api.logTrial(payload);
    state.trial.woa = result.woa;
    state.trial.woe = result.woe;
    state.postSubmitAdvance = async () => {
      if (result.experiment_complete) {
        await renderPostSurvey();
      } else if (result.rest_required) {
        state.subject = await api.getSubject(state.subject.subject_id);
        await renderRest();
      } else {
        await loadNextTrial();
      }
    };
    renderDecisionPanel();
  } catch (e) {
    alert(`提交失败: ${e.message}`);
    state.decisionSubmitted = false;
    state.postSubmitAdvance = null;
    stopGlucoseStreaming();
    state.glucoseViewMode = "baseline";
    renderDecisionPanel();
  }
}

async function loadNextTrial() {
  stopGlucoseStreaming();
  
  state.step = 1;
  state.initialAction = null;
  state.initialConfidence = null;
  state.finalAction = null;
  state.finalConfidence = null;
  state.stepStartTs = null;
  state.glucoseFocusAction = null;
  state.glucoseViewMode = "baseline";
  state.step1ResultVisible = false;
  state.decisionSubmitted = false;
  state.glucoseDisplayedUntil = 0;
  state.glucoseChartPanOffset = 0;
  state.postSubmitAdvance = null;

  state.subject = await api.getSubject(state.subject.subject_id);
  state.trial = await api.nextTrial(state.subject.subject_id);
  updateTopbar();
  renderExperimentTrial();
  setView("experiment");
  startGlucoseStreaming(state.trial.glucose_series, 60);
}

async function renderRest() {
  const container = document.getElementById("view-experiment");
  const startedAt = Date.now();
  let remaining = 300;
  container.innerHTML = `
    <div class="survey-layout">
      <div class="survey-header">
        <h2>第一阶段已完成，请休息片刻</h2>
        <div class="survey-section-marker">已完成轮次数：8/16</div>
      </div>
      <div class="survey-content">
        <div class="question-card">
          <div class="question-text">接下来您将体验另一种建议呈现方式，操作方法完全相同</div>
          <div class="scale-hint">建议休息时间：5分钟；准备好后也可以提前继续。</div>
        </div>
        <div class="rest-countdown" id="restCountdown">05:00</div>
      </div>
      <div class="survey-footer">
        <button class="primary" id="continueAfterRest">我已准备好，继续</button>
      </div>
    </div>
  `;
  const timer = setInterval(() => {
    remaining = Math.max(remaining - 1, 0);
    const mm = String(Math.floor(remaining / 60)).padStart(2, "0");
    const ss = String(remaining % 60).padStart(2, "0");
    const el = document.getElementById("restCountdown");
    if (el) el.textContent = `${mm}:${ss}`;
    if (remaining === 0) clearInterval(timer);
  }, 1000);
  document.getElementById("continueAfterRest").onclick = async () => {
    clearInterval(timer);
    const duration = Math.round((Date.now() - startedAt) / 1000);
    await api.completeRest(state.subject.subject_id, duration);
    await loadNextTrial();
  };
}

// ===== 后测渲染 =====
async function renderPostSurvey() {
  const scaleCfg = await api.getScales();
  state.scales = scaleCfg.scales;
  const post = state.scales.post;

  const container = document.getElementById("view-experiment");
  
  const sectionsHtml = post.sections.map((section, sIdx) => `
    <div class="survey-section">
      <div class="section-title">${section.name}</div>
      ${section.items.map((item, iIdx) => `
        <div class="question-card">
          <div class="question-text">${item}</div>
          <div class="scale-hint">1=非常不同意，5=完全同意</div>
          <div class="scale-buttons">
            ${[1,2,3,4,5].map(score => `
              <button class="scale-btn" data-post-section="${sIdx}" data-post-item="${iIdx}" data-score="${score}">
                <div class="score">${score}</div>
                <div class="meaning">${get5PointLabels()[score - 1]}</div>
              </button>
            `).join("")}
          </div>
        </div>
      `).join("")}
    </div>
  `).join("");

  container.innerHTML = `
    <div class="survey-layout">
      <div class="survey-header">
        <h2>${post.title}</h2>
        <div class="survey-section-marker">试验完成！请完成以下问卷</div>
      </div>
      <div class="survey-content">
        ${sectionsHtml}
      </div>
      <div class="survey-footer">
        <button class="primary" id="submitPost" style="min-width:200px;height:50px;">提交后测，完成实验</button>
      </div>
    </div>
  `;

  const responses = {};
  container.querySelectorAll(".scale-btn").forEach((btn) => {
    btn.onclick = () => {
      const sIdx = btn.dataset.postSection;
      const iIdx = btn.dataset.postItem;
      const score = btn.dataset.score;
      if (!responses[sIdx]) responses[sIdx] = {};
      responses[sIdx][iIdx] = score;
      
      container.querySelectorAll(`[data-post-section="${sIdx}"][data-post-item="${iIdx}"]`).forEach(b => {
        b.classList.remove("active");
      });
      btn.classList.add("active");
    };
  });

  document.getElementById("submitPost").onclick = async () => {
    const allScores = {};
    for (let s in responses) {
      for (let i in responses[s]) {
        allScores[`${s}_${i}`] = Number(responses[s][i]);
      }
    }
    await api.submitSurvey({
      subject_id: state.subject.subject_id,
      survey_type: "post",
      payload: { scale: "post_combined", answers: allScores },
    });
    state.subject = await api.getSubject(state.subject.subject_id);
    updateTopbar();
    alert("🎉 实验完成！感谢您的参与");
    renderHome();
    setView("home");
  };
}

// ===== 记录页面 =====
async function renderRecords() {
  const rows = await api.listSubjects();
  const dashboard = await api.getDashboard();
  const el = document.getElementById("view-records");
  el.innerHTML = `
  <div class="records-grid">
    <div class="card">
      <h3>实验进度看板</h3>
      <div class="dashboard-grid">
        <div class="dashboard-tile"><strong>${dashboard.completed_total}/${dashboard.target_total}</strong><span>已完成被试</span></div>
        <div class="dashboard-tile"><strong>${dashboard.today_completed}</strong><span>今日新增完成</span></div>
        <div class="dashboard-tile"><strong>${Math.round(dashboard.data_integrity_rate * 100)}%</strong><span>数据完整率</span></div>
      </div>
      <p class="muted">第1-4组完成人数：${[1,2,3,4].map(n => `第${n}组 ${dashboard.groups[String(n)] || 0}`).join(" / ")}</p>
      <p class="muted">媒介顺序：语音先 ${dashboard.media_order.voice_first || 0} / 数字人先 ${dashboard.media_order.digital_human_first || 0}</p>
      <a class="export-link" href="/api/export/all/summary.csv" target="_blank">导出全部被试汇总数据</a>
    </div>
    <div class="card">
    <h3>📋 被试记录</h3>
    ${rows.slice(0, 40).map(r => `
      <div style="padding:12px;border-bottom:2px solid var(--light);display:flex;justify-content:space-between;">
        <div>
          <div style="font-weight:600;font-size:18px;">${r.subject_id}</div>
          <div style="font-size:14px;color:var(--muted);">进度 ${r.current_trial_index}/${r.total_trials} | 第${r.latin_row}组 | ${r.media_order === "voice_first" ? "语音先" : "数字人先"}</div>
        </div>
        <div style="display:flex;gap:8px;">
          <button data-continue="${r.subject_id}" class="secondary">继续</button>
          <button data-manage="${r.subject_id}" class="secondary">顺序管理</button>
          <a href="/api/export/${r.subject_id}.csv" target="_blank" style="padding:10px 16px;border:2px solid var(--border);border-radius:8px;text-decoration:none;color:var(--primary);">导出</a>
        </div>
      </div>
    `).join("")}
    </div>
    <div class="card" id="sequenceManager"><h3>实验顺序管理</h3><p class="muted">从被试列表点击“顺序管理”查看和调整。</p></div>
  </div>`;

  el.querySelectorAll("[data-continue]").forEach(btn => {
    btn.onclick = async () => {
      state.subject = await api.getSubject(btn.dataset.continue);
      await openSubjectFlow();
    };
  });
  el.querySelectorAll("[data-manage]").forEach(btn => {
    btn.onclick = () => renderSequenceManager(btn.dataset.manage);
  });
}

async function renderSequenceManager(subjectId) {
  const [subject, sequence] = await Promise.all([api.getSubject(subjectId), api.getSequence(subjectId)]);
  const el = document.getElementById("sequenceManager");
  el.innerHTML = `
    <h3>实验顺序管理：${subjectId}</h3>
    ${subject.current_trial_index > 0 ? `<div class="admin-warning">该被试已完成${subject.current_trial_index}轮，修改将影响后续轮次的顺序，请确认</div>` : ""}
    <div class="admin-controls">
      <label>修改拉丁方分组</label>
      <select id="adminLatin">${[1,2,3,4].map(n => `<option value="${n}" ${subject.latin_row === n ? "selected" : ""}>第${n}组</option>`).join("")}</select>
      <button class="secondary" id="saveLatin">保存拉丁方分组</button>
      <label>修改媒介顺序</label>
      <select id="adminMedia">
        <option value="voice_first" ${subject.media_order === "voice_first" ? "selected" : ""}>语音先</option>
        <option value="digital_human_first" ${subject.media_order === "digital_human_first" ? "selected" : ""}>数字人先</option>
      </select>
      <button class="secondary" id="saveMedia">保存媒介顺序</button>
      <label>手动指定当前轮次</label>
      <input id="adminTrial" type="number" min="1" max="16" value="${subject.current_trial_index + 1}" />
      <button class="secondary" id="saveTrial">设置当前轮次</button>
    </div>
    <div class="sequence-table">
      <table>
        <thead><tr><th>轮次</th><th>模块</th><th>条件代码</th><th>场景类型</th><th>风格类型</th><th>媒介类型</th><th>实例编号</th><th>状态</th></tr></thead>
        <tbody>${sequence.rows.map(row => `<tr><td>${row.round}</td><td>${row.module}</td><td>${row.condition_code}</td><td>${row.scenario_type}</td><td>${row.style_type}</td><td>${row.media_type}</td><td>${row.instance_id}</td><td>${row.status}</td></tr>`).join("")}</tbody>
      </table>
    </div>
  `;
  const askReason = (message) => {
    if (!confirm(`${message}\n\n该操作会写入审计日志，是否继续？`)) return null;
    return prompt("请填写修改原因：");
  };
  document.getElementById("saveLatin").onclick = async () => {
    const reason = askReason("确认修改拉丁方分组？");
    if (!reason) return;
    await api.updateLatin(subjectId, Number(document.getElementById("adminLatin").value), reason);
    await renderSequenceManager(subjectId);
  };
  document.getElementById("saveMedia").onclick = async () => {
    const reason = askReason("确认修改媒介顺序？");
    if (!reason) return;
    await api.updateMediaOrder(subjectId, document.getElementById("adminMedia").value, reason);
    await renderSequenceManager(subjectId);
  };
  document.getElementById("saveTrial").onclick = async () => {
    const reason = askReason("确认修改当前轮次？");
    if (!reason) return;
    const result = await api.updateCurrentTrial(subjectId, Number(document.getElementById("adminTrial").value), reason);
    alert(result.message);
    await renderSequenceManager(subjectId);
  };
}

// ===== 量表编辑页面 =====
async function renderScales() {
  const cfg = await api.getScales();
  state.scales = normalizeScalesConfig(cfg.scales);
  cfg.scales = state.scales;
  let surveyPayload = { surveys: [] };
  try {
    surveyPayload = await api.listSurveys();
  } catch (e) {
    surveyPayload = { surveys: [] };
  }
  const el = document.getElementById("view-scales");
  const renderSectionEditor = (type, section, sIdx, total) => `
    <div class="section-editor" data-section-idx="${sIdx}" data-section-type="${type}">
      <div class="section-header">
        <input type="text" class="section-name" value="${section.name}" placeholder="量表名称"/>
        <input type="text" class="section-scale" value="${section.scale || '1-5'}" placeholder="量表刻度"/>
        <button class="btn-small danger" onclick="removeSection(this)">删除</button>
        <button class="btn-small secondary" onclick="moveSection(this, -1)" ${sIdx === 0 ? 'disabled' : ''}>↑</button>
        <button class="btn-small secondary" onclick="moveSection(this, 1)" ${sIdx === total - 1 ? 'disabled' : ''}>↓</button>
      </div>
      <div class="items-editor">
        ${section.items.map((item, iIdx) => `
          <div class="item-row">
            <input type="text" class="item-text" value="${item}" placeholder="题目"/>
            <button class="btn-small danger" onclick="removeItem(this)">删除</button>
          </div>
        `).join("")}
      </div>
      <button class="btn-small primary" onclick="addItem(this)">+ 添加题目</button>
    </div>
  `;

  const renderSurveyTab = () => {
    const grouped = surveyPayload.surveys.reduce((acc, survey) => {
      if (!acc[survey.subject_id]) {
        acc[survey.subject_id] = [];
      }
      acc[survey.subject_id].push(survey);
      return acc;
    }, {});
    const subjectIds = Object.keys(grouped);
    return `
      <div class="scale-surveys">
        <div class="scale-edit-box">
          <h3>提交记录查看</h3>
          <p class="muted">按被试查看前测、后测和任务量表的提交 JSON。</p>
          ${subjectIds.length === 0 ? '<div class="empty-state">暂无量表提交记录</div>' : subjectIds.map((subjectId) => `
            <details class="survey-record-card">
              <summary>${subjectId} · ${grouped[subjectId].length} 条记录</summary>
              <div class="survey-record-list">
                ${grouped[subjectId].map((survey) => `
                  <div class="survey-record-item">
                    <div class="survey-record-head">
                      <strong>${survey.survey_type}</strong>
                      <span>${survey.created_at}</span>
                    </div>
                    <pre>${JSON.stringify(survey.payload, null, 2)}</pre>
                  </div>
                `).join("")}
              </div>
            </details>
          `).join("")}
        </div>
      </div>
    `;
  };

  const renderEditor = () => {
    const pre = state.scales.pre;
    const post = state.scales.post;
    const task = state.scales.task_confidence || { title: "单任务信心量表", scale: "1-5", item: "您对刚才选择的运动方案，有多大把握认为它是正确的？" };

    el.innerHTML = `
      <div class="scales-container">
        <div class="scales-header">
          <h2>📊 量表管理</h2>
          <p>前测、后测、单任务信心和原始 JSON 同步管理</p>
        </div>

        <div class="scales-tabs">
          <button class="scale-tab-btn active" data-tab="pre">前测量表</button>
          <button class="scale-tab-btn" data-tab="post">后测量表</button>
          <button class="scale-tab-btn" data-tab="task">单任务信心</button>
          <button class="scale-tab-btn" data-tab="raw">原始JSON</button>
          <button class="scale-tab-btn" data-tab="surveys">提交记录</button>
        </div>

        <div class="scale-tab-content active" data-tab="pre">
          <div class="scale-edit-box">
            <h3>${pre.title}</h3>
            <div id="preScaleEditor" class="sections-editor">
              ${pre.sections.map((section, sIdx) => renderSectionEditor('pre', section, sIdx, pre.sections.length)).join("")}
            </div>
            <button class="primary" onclick="addSection('pre')" style="margin-top:16px;">+ 添加新量表</button>
          </div>
        </div>

        <div class="scale-tab-content" data-tab="post">
          <div class="scale-edit-box">
            <h3>${post.title}</h3>
            <div id="postScaleEditor" class="sections-editor">
              ${post.sections.map((section, sIdx) => renderSectionEditor('post', section, sIdx, post.sections.length)).join("")}
            </div>
            <button class="primary" onclick="addSection('post')" style="margin-top:16px;">+ 添加新量表</button>
          </div>
        </div>

        <div class="scale-tab-content" data-tab="task">
          <div class="scale-edit-box">
            <h3>单任务信心量表</h3>
            <div class="task-scale-editor">
              <label>标题</label>
              <input id="taskScaleTitle" type="text" value="${task.title}" />
              <label>刻度</label>
              <input id="taskScaleRange" type="text" value="${task.scale || '1-5'}" />
              <label>题目</label>
              <textarea id="taskScaleItem">${task.item || ''}</textarea>
            </div>
          </div>
        </div>

        <div class="scale-tab-content" data-tab="raw">
          <div class="scale-edit-box">
            <h3>原始 JSON</h3>
              <textarea id="scaleJsonEditor" class="scale-json-editor" spellcheck="false">${JSON.stringify(state.scales, null, 2)}</textarea>
            <div style="margin-top:12px; display:flex; gap:12px; flex-wrap:wrap;">
              <button class="secondary" id="importJsonBtn">从JSON导入</button>
              <button class="secondary" id="formatJsonBtn">格式化JSON</button>
            </div>
          </div>
        </div>

        <div class="scale-tab-content" data-tab="surveys">
          ${renderSurveyTab()}
        </div>

        <div class="scale-footer">
          <button class="primary" id="saveScalesBtn" style="min-width:200px;min-height:50px;font-size:18px;">💾 保存所有更改</button>
          <button class="secondary" id="resetScalesBtn" style="min-width:150px;min-height:50px;font-size:18px;">↻ 重置</button>
        </div>
      </div>
    `;

    el.querySelectorAll(".scale-tab-btn").forEach(btn => {
      btn.onclick = () => {
        const tabName = btn.dataset.tab;
        el.querySelectorAll(".scale-tab-btn").forEach(item => item.classList.remove("active"));
        el.querySelectorAll(".scale-tab-content").forEach(item => item.classList.remove("active"));
        btn.classList.add("active");
        el.querySelector(`[data-tab="${tabName}"]`).classList.add("active");
      };
    });

    const syncJsonEditorFromUI = () => {
      const jsonEditor = el.querySelector("#scaleJsonEditor");
      if (jsonEditor) {
        jsonEditor.value = JSON.stringify(collectScalesFromUI(), null, 2);
      }
    };

    if (!state.scalesEditorBound) {
      el.addEventListener("input", (event) => {
        if (!event.target.closest(".sections-editor, .task-scale-editor")) {
          return;
        }
        state.scales = collectScalesFromUI();
        syncJsonEditorFromUI();
      });
      state.scalesEditorBound = true;
    }

    el.querySelector("#saveScalesBtn").onclick = async () => {
      const updatedScales = collectScalesFromUI();
      try {
        await api.saveScales(updatedScales);
        state.scales = updatedScales;
        cfg.scales = updatedScales;
        alert("✅ 量表保存成功！");
        renderScales();
      } catch (e) {
        alert(`❌ 保存失败: ${e.message}`);
      }
    };

    el.querySelector("#resetScalesBtn").onclick = () => {
      state.scales = normalizeScalesConfig(cfg.scales);
      renderScales();
    };

    el.querySelector("#importJsonBtn").onclick = () => {
      try {
        const json = JSON.parse(el.querySelector("#scaleJsonEditor").value);
        state.scales = normalizeScalesConfig(json);
        cfg.scales = state.scales;
        renderScales();
      } catch (e) {
        alert(`JSON解析失败: ${e.message}`);
      }
    };

    el.querySelector("#formatJsonBtn").onclick = () => {
      try {
        const json = JSON.parse(el.querySelector("#scaleJsonEditor").value);
        el.querySelector("#scaleJsonEditor").value = JSON.stringify(json, null, 2);
      } catch (e) {
        alert(`JSON解析失败: ${e.message}`);
      }
    };

    syncJsonEditorFromUI();
  };

  renderEditor();
}

function collectScalesFromUI() {
  const el = document.getElementById("view-scales");
  const scales = JSON.parse(JSON.stringify(state.scales || {}));

  ["pre", "post"].forEach(type => {
    const editor = el.querySelector(`#${type}ScaleEditor`);
    if (!editor) {
      return;
    }
    const sections = editor.querySelectorAll(".section-editor");
    scales[type] = scales[type] || {};
    scales[type].title = type === "pre" ? (scales[type].title || "前测量表") : (scales[type].title || "后测量表");
    scales[type].sections = [];
    sections.forEach(section => {
      const name = section.querySelector(".section-name").value.trim();
      const scaleText = section.querySelector(".section-scale")?.value.trim() || "1-5";
      const items = Array.from(section.querySelectorAll(".item-text")).map(input => input.value.trim()).filter(Boolean);
      scales[type].sections.push({ name, items, scale: scaleText });
    });
  });

  const taskTitle = el.querySelector("#taskScaleTitle")?.value.trim();
  const taskScale = el.querySelector("#taskScaleRange")?.value.trim();
  const taskItem = el.querySelector("#taskScaleItem")?.value.trim();
  if (taskTitle || taskScale || taskItem) {
    scales.task_confidence = {
      title: taskTitle || "单任务信心量表",
      scale: taskScale || "1-5",
      item: taskItem || "您对刚才选择的运动方案，有多大把握认为它是正确的？",
    };
  }

  return scales;
}

function refreshScaleSectionControls(editor) {
  const sections = editor.querySelectorAll(".section-editor");
  sections.forEach((section, index) => {
    section.dataset.sectionIdx = String(index);
    const moveButtons = section.querySelectorAll(".section-header .btn-small.secondary");
    const upButton = moveButtons[0];
    const downButton = moveButtons[1];
    if (upButton) {
      upButton.disabled = index === 0;
    }
    if (downButton) {
      downButton.disabled = index === sections.length - 1;
    }
  });
}

function removeSection(button) {
  const el = document.getElementById("view-scales");
  const section = button.closest(".section-editor");
  const editor = button.closest(".sections-editor");
  if (section) section.remove();
  if (editor) refreshScaleSectionControls(editor);
  state.scales = collectScalesFromUI();
  const jsonEditor = el.querySelector("#scaleJsonEditor");
  if (jsonEditor) jsonEditor.value = JSON.stringify(state.scales, null, 2);
}

function addSection(type) {
  const el = document.getElementById("view-scales");
  const editor = el.querySelector(`#${type}ScaleEditor`);
  const newIdx = el.querySelectorAll(`#${type}ScaleEditor .section-editor`).length;
  const html = `
    <div class="section-editor" data-section-idx="${newIdx}">
      <div class="section-header">
        <input type="text" class="section-name" value="新量表" placeholder="量表名称"/>
        <input type="text" class="section-scale" value="1-5" placeholder="量表刻度"/>
        <button class="btn-small danger" onclick="removeSection(this)">删除</button>
      </div>
      <div class="items-editor">
        <div class="item-row">
          <input type="text" class="item-text" value="新题目" placeholder="题目"/>
          <button class="btn-small danger" onclick="removeItem(this)">删除</button>
        </div>
      </div>
      <button class="btn-small primary" onclick="addItem(this)">+ 添加题目</button>
    </div>
  `;
  editor.insertAdjacentHTML("beforeend", html);
  refreshScaleSectionControls(editor);
  state.scales = collectScalesFromUI();
  const jsonEditor = el.querySelector("#scaleJsonEditor");
  if (jsonEditor) jsonEditor.value = JSON.stringify(state.scales, null, 2);
}

function addItem(button) {
  const el = document.getElementById("view-scales");
  const section = button.closest(".section-editor");
  if (!section) return;
  const itemsEditor = section.querySelector(".items-editor");
  const html = `
    <div class="item-row">
      <input type="text" class="item-text" value="新题目" placeholder="题目"/>
      <button class="btn-small danger" onclick="removeItem(this)">删除</button>
    </div>
  `;
  itemsEditor.insertAdjacentHTML("beforeend", html);
  state.scales = collectScalesFromUI();
  const jsonEditor = el.querySelector("#scaleJsonEditor");
  if (jsonEditor) jsonEditor.value = JSON.stringify(state.scales, null, 2);
}

function removeItem(button) {
  const el = document.getElementById("view-scales");
  const itemRow = button.closest(".item-row");
  if (itemRow) itemRow.remove();
  state.scales = collectScalesFromUI();
  const jsonEditor = el.querySelector("#scaleJsonEditor");
  if (jsonEditor) jsonEditor.value = JSON.stringify(state.scales, null, 2);
}

function moveSection(button, direction) {
  const el = document.getElementById("view-scales");
  const editor = button.closest(".sections-editor");
  if (!editor) return;
  const sections = editor.querySelectorAll(".section-editor");
  const current = button.closest(".section-editor");
  if (!current) return;
  const idx = Array.from(sections).indexOf(current);
  const newIdx = idx + direction;
  if (newIdx >= 0 && newIdx < sections.length) {
    const target = sections[newIdx];
    if (direction > 0) {
      target.insertAdjacentElement("afterend", current);
    } else {
      target.insertAdjacentElement("beforebegin", current);
    }
    refreshScaleSectionControls(editor);
    state.scales = collectScalesFromUI();
    const jsonEditor = el.querySelector("#scaleJsonEditor");
    if (jsonEditor) jsonEditor.value = JSON.stringify(state.scales, null, 2);
  }
}

// ===== ?????? =====
function renderNotice() {
  const el = document.getElementById("view-notice");
  el.innerHTML = `
    <div class="card">
      <h3>????</h3>
      <p>?????????????????????????????????????????????????????????????????????????</p>

      <div class="training-callout">
        ?????????????????????????????????????????????????????????????????????
      </div>

      <div class="training-preview">
        <div class="training-card">
          <h4>????</h4>
          <div class="training-mini-flow">
            <div class="training-mini-step"><strong>1.</strong> ???????????????????</div>
            <div class="training-mini-step"><strong>2.</strong> ??????????????????????</div>
            <div class="training-mini-step"><strong>3.</strong> ?????????????????</div>
            <div class="training-mini-step"><strong>4.</strong> ????????????????????</div>
          </div>
        </div>
        <div class="training-card">
          <h4>?????</h4>
          <p>??????????????????????????????????????????????????????????????????????????????????????????</p>
        </div>
      </div>
    </div>
  `;
}


// ===== 选项卡绑定 =====
function bindTabs() {
  document.querySelectorAll(".tabs button").forEach(btn => {
    btn.onclick = async () => {
      const view = btn.dataset.view;
      if (view === "home") renderHome();
      else if (view === "records") await renderRecords();
      else if (view === "scales") await renderScales();
      else if (view === "notice") renderNotice();
      else if (view === "experiment" && state.subject) {
        if (state.subject.current_module === "DONE") alert("该被试已完成实验");
        else await openSubjectFlow();
      }
      setView(view);
    };
  });
}

// ===== 启动 =====
async function boot() {
  bindTabs();
  renderHome();
  renderNotice();
  await renderScales();
  await renderRecords();
  setView("home");
}

boot();


