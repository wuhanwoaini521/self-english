const PAGES = [
  { id: "today", label: "今天" },
  { id: "vocab", label: "词汇" },
  { id: "reading", label: "阅读" },
  { id: "talk", label: "对话" },
  { id: "progress", label: "进度" },
];

const state = {
  page: "today",
  library: false,
  loading: true,
  error: "",
  today: null,
  lesson: null,
  dialogue: null,
  overview: null,
  due: [],
  catalog: null,
  catalogBook: "travel",
  catalogQ: "",
  catalogOffset: 0,
  catalogItems: [],
  flipped: false,
  hideZh: false,
  talkDraft: "",
  talkLessonId: "",
  talkJustSubmitted: false,
  openLessonId: "",
  aimRecap: false,
};

const view = document.querySelector("#view");
const zhToggle = document.querySelector("#zh-toggle");

function pageId() {
  const raw = (location.hash || "#/today").replace(/^#\/?/, "");
  const [page, extra] = raw.split("/");
  return { page: PAGES.some((item) => item.id === page) ? page : "today", library: extra === "library" };
}

function go(page, extra) {
  location.hash = extra ? `#/${page}/${extra}` : `#/${page}`;
}

function setError(message) {
  state.error = message || "";
  render();
}

async function api(path, options) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail;
    const message = typeof detail === "string" ? detail : detail?.message || "请求失败。";
    const error = new Error(message);
    error.status = response.status;
    error.body = body;
    throw error;
  }
  return body;
}

function speak(text) {
  if (!window.speechSynthesis) {
    setError("这台设备现在不能朗读。");
    return;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-US";
  utterance.rate = 0.84;
  window.speechSynthesis.speak(utterance);
}

function paintNav() {
  document.querySelectorAll("[data-nav]").forEach((root) => {
    root.replaceChildren(
      ...PAGES.map((item) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "nav-btn" + (item.id === state.page ? " is-on" : "");
        button.textContent = item.label;
        button.addEventListener("click", () => go(item.id));
        return button;
      })
    );
  });
  zhToggle.setAttribute("aria-checked", state.hideZh ? "false" : "true");
  document.body.classList.toggle("hide-zh", state.hideZh);
}

function progress() {
  return state.lesson?.progress || null;
}

function applyProgress(saved) {
  if (!state.lesson || !saved) return;
  if (saved.lesson_id && saved.lesson_id !== state.lesson.id) return;
  const incoming = Number(saved.revision);
  const current = Number(state.lesson.progress?.revision);
  if (Number.isFinite(incoming) && Number.isFinite(current) && incoming < current) return;
  state.lesson.progress = saved;
  state.hideZh = Boolean(saved.hide_zh);
}

function sameProgressValue(left, right) {
  if (Object.is(left, right)) return true;
  if (typeof left === "boolean" || typeof right === "boolean") return Boolean(left) === Boolean(right);
  if (typeof left === "number" || typeof right === "number") return Number(left) === Number(right);
  return JSON.stringify(left) === JSON.stringify(right);
}

function progressMatches(remote, patch) {
  return Object.entries(patch).every(([key, value]) => {
    if (key === "expected_revision") return true;
    if (!Object.prototype.hasOwnProperty.call(remote, key)) return true;
    return sameProgressValue(remote[key], value);
  });
}

function currentRevision() {
  const value = Number(state.lesson?.progress?.revision);
  return Number.isFinite(value) ? value : 0;
}

let progressTail = Promise.resolve();

function enqueueProgress(task) {
  const run = progressTail.then(task, task);
  progressTail = run.then(() => {}, () => {});
  return run;
}

async function saveProgress(patch) {
  return enqueueProgress(() => saveProgressNow(patch));
}

async function saveProgressNow(patch) {
  const lessonId = state.lesson?.id;
  if (!lessonId) throw new Error("还没有课程。");
  const body = { ...patch, expected_revision: currentRevision() };
  try {
    const saved = await api(`/api/lessons/${lessonId}/progress`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    applyProgress(saved);
    if (state.error) {
      state.error = "";
      render();
    }
    return saved;
  } catch (error) {
    const remote = error.status === 409 ? error.body?.detail?.progress : null;
    if (remote) {
      state.flipped = false;
      applyProgress(remote);
      if (progressMatches(remote, patch)) {
        if (state.error) state.error = "";
        render();
        return remote;
      }
      error.message = "另一端已经更新，已同步学习位置。请重新确认本次操作。";
    }
    setError(error.message);
    throw error;
  }
}

let coreRequest = 0;
async function loadCore() {
  const request = ++coreRequest;
  const page = state.page;
  state.loading = true;
  state.error = "";
  render();
  try {
    const today = await api("/api/today");
    const lessonId = state.openLessonId || today.lesson_id;
    const lesson = await api(`/api/lessons/${lessonId}`);
    const dialogue = page === "talk" ? await api(`/api/dialogue/${lessonId}`) : null;
    const overview = page === "progress" ? await api("/api/progress") : null;
    const due = page === "today" ? (await api("/api/review/due")).items : [];
    if (request !== coreRequest) return;
    const sameLesson = state.lesson?.id === lesson.id;
    const localRev = sameLesson ? currentRevision() : 0;
    const remoteRev = Number(lesson.progress?.revision);
    if (sameLesson && Number.isFinite(remoteRev) && localRev > remoteRev) {
      lesson.progress = state.lesson.progress;
    }
    Object.assign(state, { today, lesson, dialogue, overview, due, hideZh: Boolean(lesson.progress.hide_zh) });
    if (page === "vocab" && state.library) await loadCatalog(true);
  } catch (error) {
    if (request === coreRequest) state.error = error.message;
  } finally {
    if (request === coreRequest) {
      state.loading = false;
      render();
    }
  }
}

let catalogRequest = 0;
let catalogBusy = false;

async function loadCatalog(reset) {
  if (!reset && catalogBusy) return;
  const request = ++catalogRequest;
  catalogBusy = true;
  const offset = reset ? 0 : state.catalogOffset;
  const params = new URLSearchParams({ books: state.catalogBook, q: state.catalogQ, offset });
  if (reset) {
    state.catalogOffset = 0;
    state.catalogItems = [];
  }
  try {
    const status = await api("/api/catalog/status");
    if (request !== catalogRequest) return;
    state.catalog = status;
    if (!status.ready) return;
    const data = await api(`/api/feed?${params}`);
    if (request !== catalogRequest) return;
    state.catalogItems = reset ? data.items : state.catalogItems.concat(data.items);
    state.catalogOffset = offset + data.items.length;
    state.catalog.total = data.total;
  } catch (error) {
    if (request === catalogRequest) state.catalog = { ready: false, hint: error.message, failed: true };
  } finally {
    if (request === catalogRequest) catalogBusy = false;
  }
}

let grading = false;
async function submitGrade(card, result, patch) {
  if (grading) return;
  grading = true;
  try {
    await enqueueProgress(() => submitGradeNow(card, result, patch));
  } finally {
    grading = false;
  }
}

async function submitGradeNow(card, result, patch) {
  const lesson = state.lesson;
  const expressionId = card.expression_id || card.id;
  const version = patch ? currentRevision() : card.due_at;
  const key = `grade:${expressionId}:${version}`;
  try {
    let body = JSON.parse(sessionStorage.getItem(key) || "null");
    if (body && body.result !== result) {
      const names = { forgot: "忘了", fuzzy: "模糊", remembered: "记得" };
      setError(`上次“${names[body.result]}”的保存结果待确认，请再次点击该评分。`);
      return;
    }
    if (!body) {
      const operationId = Array.from(crypto.getRandomValues(new Uint32Array(4))).join("-");
      body = { operation_id: operationId, result };
      if (patch) body.progress = { ...patch, expected_revision: version };
      else body.expected_due = version;
      sessionStorage.setItem(key, JSON.stringify(body));
    }
    view.querySelectorAll("button.grade").forEach(button => {
      button.disabled = true;
      if (button.classList.contains(result)) button.textContent = "保存中…";
    });
    const saved = await api(`/api/review/cards/${expressionId}/result`, {
      method: "POST", body: JSON.stringify(body),
    });
    sessionStorage.removeItem(key);
    if (lesson !== state.lesson) return;
    state.error = "";
    state.flipped = false;
    if (saved.progress) {
      applyProgress(saved.progress);
      render();
    } else await loadCore();
  } catch (error) {
    if (error.status === 409) {
      sessionStorage.removeItem(key);
      await loadCore();
    }
    setError(error.message);
  }
}

function banner(kind, text, retry) {
  const box = document.createElement("div");
  box.className = kind;
  box.textContent = text;
  if (retry) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost";
    button.textContent = "重试";
    button.style.marginTop = "0.7rem";
    button.addEventListener("click", retry);
    box.append(document.createElement("br"), button);
  }
  return box;
}

function speakIcon() {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.classList.add("speak-icon");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("fill", "currentColor");
  path.setAttribute(
    "d",
    "M3.4 9h3.3L11 5.1v13.8L6.7 15H3.4V9zm9.8.2v5.6c1-.6 1.6-1.7 1.6-2.8s-.6-2.2-1.6-2.8zM11.5 4.3v2.1c2.4.8 4.1 3.1 4.1 5.6s-1.7 4.8-4.1 5.6v2.1c3.6-.9 6.2-4.1 6.2-7.7s-2.6-6.8-6.2-7.7z"
  );
  svg.append(path);
  return svg;
}

function speakButton(text) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "speak";
  button.setAttribute("aria-label", "用设备语音朗读");
  button.append(speakIcon());
  button.addEventListener("click", () => speak(text));
  return button;
}

let gloss = null;

function closeGloss() {
  if (!gloss) return;
  document.removeEventListener("keydown", onGlossKey);
  document.removeEventListener("pointerdown", onGlossPointer, true);
  window.removeEventListener("resize", closeGloss);
  window.removeEventListener("scroll", closeGloss, true);
  gloss.anchor.classList.remove("is-open");
  gloss.anchor.setAttribute("aria-expanded", "false");
  gloss.backdrop.remove();
  gloss.card.remove();
  gloss = null;
}

function onGlossKey(event) {
  if (event.key === "Escape") closeGloss();
}

function onGlossPointer(event) {
  if (!gloss) return;
  if (gloss.card.contains(event.target) || gloss.anchor.contains(event.target)) return;
  closeGloss();
}

function placeGlossCard(anchor, card) {
  const rect = anchor.getBoundingClientRect();
  const pad = 12;
  const width = card.offsetWidth;
  const height = card.offsetHeight;
  let left = rect.left;
  let top = rect.bottom + 8;
  if (left + width > window.innerWidth - pad) left = window.innerWidth - pad - width;
  if (left < pad) left = pad;
  if (top + height > window.innerHeight - pad) top = rect.top - 8 - height;
  if (top < pad) top = pad;
  card.style.left = `${Math.round(left)}px`;
  card.style.top = `${Math.round(top)}px`;
}

function openGloss(anchor, mark) {
  if (gloss && gloss.anchor === anchor) {
    closeGloss();
    return;
  }
  closeGloss();
  anchor.classList.add("is-open");
  anchor.setAttribute("aria-expanded", "true");
  const mobile = window.matchMedia("(max-width: 859px)").matches;
  const backdrop = document.createElement("div");
  backdrop.className = "gloss-backdrop" + (mobile ? " is-center" : "");
  const card = document.createElement("div");
  card.className = "gloss-card" + (mobile ? " is-center" : "");
  card.setAttribute("role", "dialog");
  card.setAttribute("aria-label", mark.headword || "词卡");
  const word = document.createElement("p");
  word.className = "gloss-word";
  word.textContent = mark.headword || "";
  const row = document.createElement("div");
  row.className = "gloss-phonetic";
  if (mark.phonetic) {
    const ipa = document.createElement("span");
    ipa.className = "gloss-ipa";
    ipa.textContent = mark.phonetic;
    row.append(ipa);
  }
  const speakBtn = document.createElement("button");
  speakBtn.type = "button";
  speakBtn.className = "gloss-speak";
  speakBtn.setAttribute("aria-label", "朗读");
  speakBtn.append(speakIcon());
  speakBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    speak(mark.headword || anchor.textContent);
  });
  row.append(speakBtn);
  const meta = document.createElement("div");
  meta.className = "gloss-meta";
  if (mark.pos) {
    const pos = document.createElement("span");
    pos.className = "gloss-pos " + glossPosClass(mark.pos);
    pos.textContent = mark.pos;
    meta.append(pos);
  }
  if (mark.sense_zh) {
    const meaning = document.createElement("p");
    meaning.className = "gloss-meaning";
    meaning.textContent = mark.sense_zh;
    meta.append(meaning);
  }
  card.append(word, row, meta);
  document.body.append(backdrop, card);
  if (mobile) backdrop.addEventListener("click", closeGloss);
  else {
    placeGlossCard(anchor, card);
    document.addEventListener("pointerdown", onGlossPointer, true);
  }
  document.addEventListener("keydown", onGlossKey);
  window.addEventListener("resize", closeGloss);
  window.addEventListener("scroll", closeGloss, true);
  gloss = { anchor, card, backdrop };
}

function glossPosClass(pos) {
  if (pos === "名词") return "is-noun";
  if (pos === "动词" || pos === "助动词" || pos === "动词短语") return "is-verb";
  if (pos === "短语") return "is-phrase";
  if (pos === "副词") return "is-adverb";
  return "is-grammar";
}

function usableMarks(english, marks) {
  if (!english || !marks || !marks.length) return [];
  const out = [];
  let lastEnd = 0;
  marks.forEach((item) => {
    const start = Number(item.start);
    const end = Number(item.end);
    if (!Number.isInteger(start) || !Number.isInteger(end)) return;
    if (start < lastEnd || end <= start || end > english.length) return;
    if (item.kind !== "vocab" && item.kind !== "grammar") return;
    out.push(item);
    lastEnd = end;
  });
  return out;
}

function renderAnnotated(english, marks, className) {
  const line = document.createElement("p");
  line.className = className || "english";
  const list = usableMarks(english, marks);
  if (!list.length) {
    line.textContent = english;
    return line;
  }
  let cursor = 0;
  list.forEach((mark) => {
    if (mark.start > cursor) line.append(english.slice(cursor, mark.start));
    const button = document.createElement("button");
    button.type = "button";
    button.className = "mark mark-" + mark.kind;
    button.textContent = english.slice(mark.start, mark.end);
    button.setAttribute("aria-expanded", "false");
    button.setAttribute("aria-haspopup", "dialog");
    button.setAttribute("aria-label", `${mark.kind === "grammar" ? "语法" : "生词"} ${mark.headword || button.textContent}`);
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      openGloss(button, mark);
    });
    line.append(button);
    cursor = mark.end;
  });
  if (cursor < english.length) line.append(english.slice(cursor));
  return line;
}

function renderScriptLine(line) {
  const block = document.createElement("div");
  block.className = "script";
  const who = document.createElement("p");
  who.className = "kicker";
  who.textContent = line.speaker_zh;
  const en = renderAnnotated(line.english, line.marks, "english sentence");
  const zh = document.createElement("p");
  zh.className = "zh can-hide";
  zh.textContent = line.chinese;
  block.append(who, en, zh, speakButton(line.english));
  return block;
}

const STEP_ORDER = ["vocab", "listen", "talk", "recap", "done"];

function stepIndex(step) {
  const index = STEP_ORDER.indexOf(step || "vocab");
  return index < 0 ? 0 : index;
}

function reached(step) {
  return stepIndex(progress()?.step) >= stepIndex(step);
}

function visitStep(step) {
  if (step === "listen") go("reading");
  else if (step === "talk") go("talk");
  else if (step === "recap" || step === "done") {
    state.aimRecap = true;
    if (state.page === "today") {
      render();
    } else go("today");
  } else go("vocab");
}

async function advanceTo(step) {
  if (!reached(step)) await saveProgress({ step });
  visitStep(step);
}

async function finishLesson() {
  if (progress()?.step === "done") {
    state.openLessonId = "";
    await loadCore();
    return;
  }
  await saveProgress({ step: "done" });
  state.openLessonId = "";
  await loadCore();
}

function continueLesson() {
  const step = progress()?.step || "vocab";
  if (step === "recap") visitStep("recap");
  else if (step === "done") go("progress");
  else visitStep(step);
}

async function openLesson(lessonId) {
  state.openLessonId = lessonId;
  state.flipped = false;
  try {
    state.lesson = await api(`/api/lessons/${lessonId}`);
    if (state.page === "talk") state.dialogue = await api(`/api/dialogue/${lessonId}`);
    visitStep(progress()?.step || "vocab");
    if (state.page === "today") render();
  } catch (error) {
    setError(error.message);
  }
}

function renderStepNav() {
  const nav = document.createElement("nav");
  nav.className = "step-nav";
  nav.setAttribute("aria-label", "本课步骤");
  const recapOn = state.page === "today" && reached("recap");
  [
    { id: "vocab", page: "vocab", label: "词汇" },
    { id: "listen", page: "reading", label: "听读" },
    { id: "talk", page: "talk", label: "对话" },
    { id: "recap", page: "today", label: "复盘" },
  ].forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    const isOn = item.id === "recap" ? recapOn : state.page === item.page;
    button.className = "step-nav-btn" + (isOn ? " is-on" : "");
    button.textContent = item.label;
    if (!reached(item.id)) {
      button.disabled = true;
      button.title = "还没走到这一步";
    } else {
      button.addEventListener("click", () => visitStep(item.id));
    }
    nav.append(button);
  });
  return nav;
}

function renderToday() {
  const root = document.createDocumentFragment();
  if (state.lesson) root.append(renderStepNav());
  const due = state.due || [];
  let reviewPanel;
  if (due.length) {
    const card = due[0];
    const panel = document.createElement("section");
    panel.className = "card";
    panel.innerHTML = `<p class="kicker">到期复习</p>`;
    const english = document.createElement("p");
    english.className = "english";
    english.textContent = due[0].english;
    panel.append(english);
    if (state.flipped) {
      const zh = document.createElement("p");
      zh.className = "zh";
      zh.textContent = due[0].chinese;
      panel.append(zh);
      const row = document.createElement("div");
      row.className = "row";
      [
        ["forgot", "忘了"],
        ["fuzzy", "模糊"],
        ["remembered", "记得"],
      ].forEach(([id, label]) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "grade " + id;
        button.textContent = label;
        button.addEventListener("click", () => submitGrade(card, id));
        row.append(button);
      });
      panel.append(row);
    } else {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "primary";
      button.textContent = "翻开";
      button.addEventListener("click", () => {
        state.flipped = true;
        render();
      });
      panel.append(button);
    }
    reviewPanel = panel;
  }
  const lesson = document.createElement("section");
  lesson.className = "card today-task";
  const viewingOther = Boolean(state.lesson && state.lesson.id !== state.today.lesson_id);
  const kicker = document.createElement("p");
  kicker.className = "kicker";
  kicker.textContent = viewingOther
    ? `${state.lesson.level || "A1"} · 回去看`
    : `${state.today.level} · 第 ${state.today.lesson_no} 课`;
  const title = document.createElement("h1");
  title.textContent = viewingOther ? state.lesson.title_zh : state.today.title_zh;
  const source = document.createElement("p");
  source.className = "audio-tag";
  source.textContent = state.lesson?.source_note || "原创种子课。朗读为系统朗读。";
  const action = document.createElement("button");
  action.type = "button";
  action.className = "primary";
  if (viewingOther) {
    action.textContent = "回到正在学的课";
    action.addEventListener("click", async () => {
      state.openLessonId = "";
      await loadCore();
    });
  } else {
    action.textContent = state.today.action;
    action.addEventListener("click", continueLesson);
  }
  const note = document.createElement("p");
  note.className = "audio-tag";
  note.textContent = due.length ? `今天有 ${due.length} 张卡待复习` : "今天没有到期复习卡";
  lesson.append(kicker, title, source, note, action);
  root.append(lesson);
  if (reviewPanel) root.append(reviewPanel);
  if (reached("recap")) root.append(renderRecap());
  const queue = state.today.lessons || [];
  if (queue.length) {
    const month = document.createElement("section");
    month.className = "card";
    const monthTitle = document.createElement("h2");
    monthTitle.textContent = "这个月";
    const monthHelp = document.createElement("p");
    monthHelp.className = "audio-tag";
    monthHelp.textContent = "点已学过的课可以回去看。同一天可以连续学完。";
    const list = document.createElement("ul");
    list.className = "list";
    queue.forEach((item) => {
      const row = document.createElement("li");
      const locked = item.status === "upcoming";
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "today-lesson-btn is-" + item.status;
      btn.disabled = locked;
      const name = document.createElement("p");
      name.className = "english";
      name.style.fontSize = "1.05rem";
      name.textContent = `${item.lesson_no}. ${item.title_zh}`;
      const status = document.createElement("p");
      status.className = "audio-tag";
      status.textContent = locked
        ? item.label
        : item.status === "current"
          ? `正在学 · ${item.label} · 点这里继续`
          : "已完成 · 点这里回去看";
      btn.append(name, status);
      if (!locked) btn.addEventListener("click", () => openLesson(item.id));
      row.append(btn);
      list.append(row);
    });
    month.append(monthTitle, monthHelp, list);
    root.append(month);
  }
  return root;
}

function renderRecap() {
  const panel = document.createElement("section");
  panel.className = "card";
  panel.id = "lesson-recap";
  const kicker = document.createElement("p");
  kicker.className = "kicker";
  kicker.textContent = "复盘";
  const title = document.createElement("h2");
  title.textContent = "本课表达";
  const help = document.createElement("p");
  help.className = "audio-tag";
  help.textContent = "对照一下刚学的词。学词汇时评过的已经在复习里。要回去改对话，点返回。";
  const list = document.createElement("ul");
  list.className = "list";
  (state.lesson.expressions || []).forEach((item) => {
    const row = document.createElement("li");
    const en = document.createElement("p");
    en.className = "english";
    en.style.fontSize = "1.2rem";
    en.textContent = item.english;
    const zh = document.createElement("p");
    zh.className = "zh can-hide";
    zh.textContent = item.chinese;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost";
    button.textContent = "加入复习";
    button.addEventListener("click", async () => {
      const card = await api("/api/review/cards", {
        method: "POST",
        body: JSON.stringify({ expression_id: item.id }),
      });
      button.textContent = card.created ? "已加入" : "已有这张卡";
    });
    row.append(en, zh, button);
    list.append(row);
  });
  const actions = document.createElement("div");
  actions.className = "talk-actions";
  const back = document.createElement("button");
  back.type = "button";
  back.className = "ghost";
  back.textContent = "返回对话";
  back.addEventListener("click", () => visitStep("talk"));
  const done = document.createElement("button");
  done.type = "button";
  done.className = "primary";
  const already = progress()?.step === "done";
  const viewingOther = Boolean(state.openLessonId && state.openLessonId !== state.today.lesson_id);
  const hasNext = Boolean(state.today?.has_next);
  if (already) {
    done.textContent = viewingOther ? "回到正在学的课" : "这一课已经完成";
    done.disabled = !viewingOther;
    if (viewingOther) {
      done.addEventListener("click", async () => {
        state.openLessonId = "";
        await loadCore();
      });
    }
  } else {
    done.textContent = hasNext ? "完成本课，接着下一课" : "完成本课";
    done.addEventListener("click", () => finishLesson());
  }
  actions.append(back, done);
  panel.append(kicker, title, help, list, actions);
  return panel;
}

function renderVocab() {
  const root = document.createDocumentFragment();
  const tabs = document.createElement("div");
  tabs.className = "row vocab-tabs";
  [
    ["lesson", "本课词汇"],
    ["library", "词句库"],
  ].forEach(([id, label]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip" + ((id === "library") === state.library ? " is-on" : "");
    button.textContent = label;
    button.addEventListener("click", () => {
      state.library = id === "library";
      state.flipped = false;
      if (state.library) loadCatalog(true).then(render);
      else render();
    });
    tabs.append(button);
  });
  if (!state.library) root.append(renderStepNav());
  root.append(tabs);
  if (state.library) {
    root.append(renderLibrary());
    return root;
  }
  const items = state.lesson.expressions;
  const phase = progress()?.vocab_phase || "learn";
  if (phase === "done") {
    root.append(renderVocabDone(items.length));
    return root;
  }
  const currentIndex = Math.min(progress()?.vocab_index || 0, items.length - 1);
  const preview = phase === "recall" && recallPreview?.lesson === state.lesson.id && recallPreview.revision === progress().revision;
  const index = preview ? recallPreview.index : currentIndex;
  const item = items[index];
  const card = phase === "recall" ? renderRecallCard(item, index, items.length) : renderTeachCard(item, index, items.length);
  root.append(cardDeck(card, index, items.length, async next => {
    if (phase === "learn") await showVocabCard(next, phase);
    else {
      recallPreview = { lesson: state.lesson.id, revision: progress().revision, index: next };
      state.flipped = false;
      render();
    }
  }, "本课词卡"));
  return root;
}

function renderVocabDone(total) {
  const card = document.createElement("section");
  card.className = "card vocab-card";
  const kicker = document.createElement("p");
  kicker.className = "kicker";
  kicker.textContent = "本课词汇";
  const title = document.createElement("h1");
  title.textContent = `${total} 个词评完了`;
  const brief = document.createElement("p");
  brief.className = "talk-brief";
  brief.textContent = "评分只决定复习间隔，不会把你扔去下一页。下一步是听读短对话，你点了才过去。";
  const actions = document.createElement("div");
  actions.className = "vocab-actions";
  const next = document.createElement("button");
  next.type = "button";
  next.className = "primary";
  next.textContent = "去听读";
  next.addEventListener("click", () => advanceTo("listen"));
  const again = document.createElement("button");
  again.type = "button";
  again.className = "ghost";
  again.textContent = "再看一遍";
  again.addEventListener("click", async () => {
    await saveProgress({
      step: progress()?.step || "vocab",
      vocab_index: 0,
      vocab_phase: "learn",
    });
    state.flipped = false;
    render();
  });
  actions.append(next, again);
  card.append(kicker, title, brief, actions);
  return card;
}

function vocabDots(index, total) {
  const dots = document.createElement("div");
  dots.className = "vocab-dots";
  dots.setAttribute("aria-hidden", "true");
  for (let i = 0; i < total; i += 1) {
    const dot = document.createElement("span");
    dot.className = "vocab-dot" + (i === index ? " is-on" : i < index ? " is-done" : "");
    dots.append(dot);
  }
  return dots;
}

async function showVocabCard(index, phase) {
  state.flipped = false;
  const current = progress() || {};
  const step = current.step || "vocab";
  if (current.vocab_index === index && current.vocab_phase === phase) {
    render();
    return;
  }
  await saveProgress({
    step,
    vocab_index: index,
    vocab_phase: phase,
  });
  render();
}

let recallPreview = null;

function cardDeck(card, index, total, changePage, label) {
  const deck = document.createElement("section");
  deck.className = "study-deck";
  deck.tabIndex = 0;
  deck.setAttribute("aria-label", `${label}，第 ${index + 1} 页，共 ${total} 页`);
  deck.append(card);
  let busy = false;
  async function move(delta) {
    if (busy || index + delta < 0 || index + delta >= total) return;
    busy = true;
    const keepFocus = deck.contains(document.activeElement);
    try {
      await changePage(index + delta);
      const next = view.querySelector(".study-deck");
      if (next && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        next.firstElementChild.animate([{ transform: `translateX(${delta * 12}px)`, opacity: .85 }, {}], { duration: 160 });
      }
      if (keepFocus) next?.focus({ preventScroll: true });
    } catch (error) {
      setError(error.message);
    } finally {
      busy = false;
    }
  }
  for (const delta of [-1, 1]) {
    const arrow = document.createElement("button");
    arrow.type = "button";
    arrow.className = "deck-arrow " + (delta < 0 ? "prev" : "next");
    arrow.setAttribute("aria-label", delta < 0 ? "上一页" : "下一页");
    arrow.textContent = delta < 0 ? "‹" : "›";
    arrow.disabled = index + delta < 0 || index + delta >= total;
    arrow.onclick = () => move(delta);
    deck.append(arrow);
  }
  deck.onkeydown = event => {
    if (!["ArrowLeft", "ArrowRight"].includes(event.key) || event.altKey || event.ctrlKey || event.shiftKey) return;
    event.preventDefault();
    move(event.key === "ArrowRight" ? 1 : -1);
  };
  let start = null;
  let suppressClick = false;
  deck.onpointerdown = event => {
    start = null;
    suppressClick = false;
    if (!event.isPrimary || event.button !== 0 || event.target.closest("button:not(.vocab-flip), input, textarea, a")) return;
    start = { x: event.clientX, y: event.clientY, id: event.pointerId };
  };
  deck.onpointercancel = () => { start = null; };
  deck.onpointerup = event => {
    if (!start || start.id !== event.pointerId) return;
    const dx = event.clientX - start.x;
    const dy = event.clientY - start.y;
    start = null;
    if (Math.abs(dx) < 42 || Math.abs(dx) < Math.abs(dy) * 1.5 || window.getSelection()?.toString()) return;
    suppressClick = true;
    move(dx < 0 ? 1 : -1);
  };
  deck.addEventListener("click", event => {
    if (suppressClick) { event.preventDefault(); event.stopPropagation(); }
  }, true);
  return deck;
}

function vocabHead(label, index, total) {
  const head = document.createElement("div");
  head.className = "vocab-head";
  const kicker = document.createElement("p");
  kicker.className = "kicker";
  kicker.textContent = `${label} ${index + 1}/${total}`;
  head.append(kicker, vocabDots(index, total));
  return head;
}

function renderTeachCard(item, index, total) {
  const card = document.createElement("section");
  card.className = "card vocab-card teach-card";
  const face = document.createElement("div");
  face.className = "vocab-face";
  const visual = document.createElement("div");
  visual.className = "teach-visual";
  visual.setAttribute("aria-hidden", "true");
  visual.textContent = item.mark || "📝";
  const english = document.createElement("p");
  english.className = "english vocab-word";
  english.textContent = item.english;
  const meaning = document.createElement("p");
  meaning.className = "teach-meaning";
  meaning.textContent = item.chinese;
  face.append(visual, english);
  if (item.phonetic) {
    const ipa = document.createElement("p");
    ipa.className = "teach-ipa";
    ipa.textContent = item.phonetic;
    face.append(ipa);
  }
  face.append(meaning);
  if (item.note_zh) {
    const note = document.createElement("div");
    note.className = "teach-block";
    const title = document.createElement("p");
    title.className = "kicker";
    title.textContent = "怎么记";
    const body = document.createElement("p");
    body.className = "teach-note";
    body.textContent = item.note_zh;
    note.append(title, body);
    face.append(note);
  }
  if (item.example_en) {
    const example = document.createElement("div");
    example.className = "teach-block";
    const title = document.createElement("p");
    title.className = "kicker";
    title.textContent = "例句";
    const en = document.createElement("p");
    en.className = "teach-example";
    en.textContent = item.example_en;
    example.append(title, en);
    if (item.example_zh) {
      const zh = document.createElement("p");
      zh.className = "zh can-hide";
      zh.textContent = item.example_zh;
      example.append(zh);
    }
    face.append(example);
  }
  const actions = document.createElement("div");
  actions.className = "vocab-actions";
  const nav = document.createElement("div");
  nav.className = "vocab-nav";
  nav.append(speakButton(item.english));
  actions.append(nav);
  if (index + 1 === total) {
    const next = document.createElement("button");
    next.type = "button";
    next.className = "primary";
    next.textContent = "去回忆这些词";
    next.onclick = () => showVocabCard(0, "recall").catch(error => setError(error.message));
    actions.append(next);
  }
  card.append(vocabHead("认识", index, total), face, actions);
  return card;
}

function renderRecallCard(item, index, total) {
  const card = document.createElement("section");
  card.className = "card vocab-card recall-card" + (state.flipped ? " is-back" : " is-front");
  const face = state.flipped ? document.createElement("div") : document.createElement("button");
  face.className = "vocab-face";
  if (!state.flipped) {
    face.type = "button";
    face.classList.add("vocab-flip");
    face.setAttribute("aria-label", "翻开看中文");
    face.addEventListener("click", () => {
      state.flipped = true;
      render();
    });
  }
  const english = document.createElement("p");
  english.className = "english vocab-word";
  english.textContent = item.english;
  face.append(english);
  if (state.flipped) {
    if (item.phonetic) {
      const ipa = document.createElement("p");
      ipa.className = "teach-ipa";
      ipa.textContent = item.phonetic;
      face.append(ipa);
    }
    const meaning = document.createElement("p");
    meaning.className = "teach-meaning";
    meaning.textContent = item.chinese;
    face.append(meaning);
    if (item.example_en) {
      const example = document.createElement("div");
      example.className = "teach-block";
      const title = document.createElement("p");
      title.className = "kicker";
      title.textContent = "例句";
      const en = document.createElement("p");
      en.className = "teach-example";
      en.textContent = item.example_en;
      example.append(title, en);
      if (item.example_zh) {
        const zh = document.createElement("p");
        zh.className = "zh can-hide";
        zh.textContent = item.example_zh;
        example.append(zh);
      }
      face.append(example);
    }
  } else {
    const hint = document.createElement("p");
    hint.className = "vocab-hint";
    hint.textContent = "先想意思，再点这张卡片翻开";
    face.append(hint);
  }
  const actions = document.createElement("div");
  actions.className = "vocab-actions";
  const nav = document.createElement("div");
  nav.className = "vocab-nav";
  nav.append(speakButton(item.english));
  actions.append(nav);
  if (index !== progress().vocab_index) {
    const resume = document.createElement("button");
    resume.type = "button";
    resume.className = "primary";
    resume.textContent = "返回待评分词卡";
    resume.onclick = () => { recallPreview = null; state.flipped = false; render(); };
    actions.append(resume);
  } else if (state.flipped) {
    const grades = document.createElement("div");
    grades.className = "vocab-grades";
    [
      ["forgot", "忘了"],
      ["fuzzy", "模糊"],
      ["remembered", "记得"],
    ].forEach(([id, label]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "grade " + id;
      button.textContent = label;
      button.addEventListener("click", () => submitGrade(item, id, {
        vocab_index: Math.min(index + 1, total - 1),
        vocab_phase: index + 1 === total ? "done" : "recall",
      }));
      grades.append(button);
    });
    actions.append(grades);
  }
  card.append(vocabHead("回忆", index, total), face, actions);
  return card;
}

function renderLibrary() {
  const panel = document.createElement("section");
  panel.className = "card";
  if (!state.catalog) return banner("loading", "正在打开词句库…");
  if (!state.catalog.ready) {
    const empty = banner("empty", state.catalog.hint || "还没有词库。", state.catalog.failed && (() => loadCatalog(true).then(render)));
    return empty;
  }
  const search = document.createElement("input");
  search.className = "search";
  search.type = "search";
  search.placeholder = "搜英文或中文";
  search.value = state.catalogQ;
  search.addEventListener("input", () => {
    state.catalogQ = search.value;
    loadCatalog(true).then(render);
  });
  const books = document.createElement("div");
  books.className = "row";
  ["travel", "business", "reading"].forEach((id) => {
    const names = { travel: "旅行", business: "商务", reading: "阅读" };
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip" + (state.catalogBook === id ? " is-on" : "");
    button.textContent = names[id];
    button.addEventListener("click", () => {
      state.catalogBook = id;
      loadCatalog(true).then(render);
    });
    books.append(button);
  });
  const list = document.createElement("ul");
  list.className = "list";
  state.catalogItems.forEach((item) => {
    const row = document.createElement("li");
    const en = document.createElement("p");
    en.className = "english";
    en.style.fontSize = "1.25rem";
    en.textContent = item.english;
    const zh = document.createElement("p");
    zh.className = "zh can-hide";
    zh.textContent = item.chinese;
    row.append(en, zh);
    if (item.phonetic || item.pos) {
      const meta = document.createElement("p");
      meta.className = "kicker";
      meta.textContent = [item.phonetic, item.pos].filter(Boolean).join("  ");
      row.append(meta);
    }
    row.append(speakButton(item.english));
    list.append(row);
  });
  panel.append(search, books, list);
  if (!state.catalogItems.length && !catalogBusy) panel.append(banner("empty", "没有匹配的词句，试试其他关键词。"));
  if (state.catalogItems.length < (state.catalog.total || 0)) {
    const more = document.createElement("button");
    more.type = "button";
    more.className = "ghost";
    more.textContent = "再看 7 条";
    more.addEventListener("click", () => loadCatalog(false).then(render));
    panel.append(more);
  }
  return panel;
}

function renderPassage(passage, index) {
  const card = document.createElement("section");
  card.className = "card passage-card";
  const kicker = document.createElement("p");
  kicker.className = "kicker";
  const title = document.createElement("h1");
  title.textContent = passage.title_zh || "短文";
  const help = document.createElement("p");
  help.className = "audio-tag";
  help.textContent = "浅蓝虚线是生词，紫色实线是语法。点喇叭，用这台设备的声音读出来，不是录音。";
  card.append(kicker, title, help);
  const total = passage.paragraphs.length;
  kicker.textContent = `短文 · 第 ${index + 1} / ${total} 段`;
  const para = passage.paragraphs[index];
  const block = document.createElement("div");
  block.className = "passage-block";
  block.append(
    renderAnnotated(para.english, para.marks, "english sentence"),
    Object.assign(document.createElement("p"), { className: "zh can-hide", textContent: para.chinese }),
    speakButton(para.english)
  );
  card.append(block);
  return card;
}

function renderReading() {
  const root = document.createDocumentFragment();
  root.append(renderStepNav());
  const passage = state.lesson.passage;
  const paragraphs = passage?.paragraphs?.length || 0;
  const index = Math.min(progress().listen_index, paragraphs);
  const changePage = async next => {
    await saveProgress({ listen_index: next });
    render();
  };
  if (index < paragraphs) {
    root.append(cardDeck(renderPassage(passage, index), index, paragraphs + 1, changePage, "听读"));
    return root;
  }
  const card = document.createElement("section");
  card.className = "card";
  const listenKicker = document.createElement("p");
  listenKicker.className = "kicker";
  listenKicker.textContent = `听读 · 第 ${index + 1} / ${paragraphs + 1} 页`;
  const listenTitle = document.createElement("h1");
  listenTitle.textContent = "短对话";
  const listenHelp = document.createElement("p");
  listenHelp.className = "audio-tag";
  listenHelp.textContent = "点喇叭，用这台设备的声音读出来。";
  card.append(listenKicker, listenTitle, listenHelp);
  state.lesson.dialogue.forEach((line) => card.append(renderScriptLine(line)));
  root.append(cardDeck(card, index, paragraphs + 1, changePage, "听读"));
  const quiz = document.createElement("section");
  quiz.className = "card quiz-card";
  const quizKicker = document.createElement("p");
  quizKicker.className = "kicker";
  quizKicker.textContent = "理解题";
  const quizTitle = document.createElement("h1");
  quizTitle.textContent = "听完选一选";
  const quizHelp = document.createElement("p");
  quizHelp.className = "audio-tag";
  quizHelp.textContent = "对照上面的对话。选错了可以再选。";
  quiz.append(quizKicker, quizTitle, quizHelp);
  const results = { ...(progress()?.question_results || {}) };
  const letters = "ABCDE";
  state.lesson.questions.forEach((question, index) => {
    const wrap = document.createElement("div");
    wrap.className = "quiz-block";
    const num = document.createElement("p");
    num.className = "quiz-num";
    num.textContent = `第 ${index + 1} 题 · 共 ${state.lesson.questions.length} 题`;
    const prompt = document.createElement("h2");
    prompt.textContent = question.prompt_en;
    const zh = document.createElement("p");
    zh.className = "zh can-hide";
    zh.textContent = question.prompt_zh;
    wrap.append(num, prompt, zh);
    question.options.forEach((option, optionIndex) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "choice";
      const saved = results[question.id];
      if (saved?.choice === option.id) {
        button.classList.add(saved.correct ? "ok" : "bad", "is-on");
      }
      const key = document.createElement("span");
      key.className = "choice-key";
      key.textContent = letters[optionIndex] || String(optionIndex + 1);
      const en = document.createElement("span");
      en.className = "choice-en";
      en.textContent = option.en;
      button.append(key, en);
      if (option.zh) {
        const zhOpt = document.createElement("span");
        zhOpt.className = "zh can-hide choice-zh";
        zhOpt.textContent = option.zh;
        button.append(zhOpt);
      }
      button.addEventListener("click", async () => {
        results[question.id] = {
          choice: option.id,
          correct: option.id === question.answer_id,
        };
        await saveProgress({ step: "listen", question_results: results });
        render();
      });
      wrap.append(button);
    });
    quiz.append(wrap);
  });
  const actions = document.createElement("div");
  actions.className = "talk-actions";
  const back = document.createElement("button");
  back.type = "button";
  back.className = "ghost";
  back.textContent = "返回词汇";
  back.addEventListener("click", () => visitStep("vocab"));
  const next = document.createElement("button");
  next.type = "button";
  next.className = "primary";
  next.textContent = "去对话";
  next.addEventListener("click", () => advanceTo("talk"));
  actions.append(back, next);
  quiz.append(actions);
  root.append(quiz);
  return root;
}

function renderTalk() {
  const session = state.dialogue;
  const task = state.lesson?.task || {};
  const root = document.createDocumentFragment();
  root.append(renderStepNav());

  const heard = document.createElement("section");
  heard.className = "card";
  const heardKicker = document.createElement("p");
  heardKicker.className = "kicker";
  heardKicker.textContent = task.hear_label_zh || "对方刚才说";
  heard.append(heardKicker);
  const dialogue = state.lesson.dialogue || [];
  const firstYou = dialogue.findIndex((line) => line.speaker === "you");
  const cueLines = dialogue
    .slice(0, firstYou === -1 ? dialogue.length : firstYou)
    .filter((line) => line.speaker !== "you");
  if (!cueLines.length) {
    heard.append(banner("empty", "这一课还没有对方的开场白。"));
  } else {
    cueLines.forEach((line) => heard.append(renderScriptLine(line)));
  }
  root.append(heard);

  const turn = document.createElement("section");
  turn.className = "card";
  const kicker = document.createElement("p");
  kicker.className = "kicker";
  kicker.textContent = "你的回复";
  const title = document.createElement("h1");
  title.textContent = task.title_zh || "写出你的英文";
  const brief = document.createElement("p");
  brief.className = "talk-brief";
  brief.textContent = task.brief_zh || "先看对方说了什么，再自己用英文写回复。";
  turn.append(kicker, title, brief);

  const goalList = session?.goals || [];
  const allDone = goalList.length > 0 && goalList.every((goal) => goal.done);
  if (goalList.length) {
    const checkLabel = document.createElement("p");
    checkLabel.className = "kicker";
    checkLabel.textContent = "要说到";
    const checks = document.createElement("ul");
    checks.className = "talk-checks";
    goalList.forEach((goal) => {
      const item = document.createElement("li");
      item.className = "check" + (goal.done ? " is-done" : "");
      item.textContent = goal.label_zh;
      checks.append(item);
    });
    turn.append(checkLabel, checks);
  }

  const areaLabel = document.createElement("label");
  areaLabel.className = "kicker";
  areaLabel.setAttribute("for", "talk-input");
  areaLabel.textContent = "你要说的话";
  const area = document.createElement("textarea");
  area.id = "talk-input";
  area.setAttribute("aria-label", "你要说的英文");
  area.placeholder = task.placeholder || "用英文写你要说的话。";
  if (state.talkLessonId !== state.lesson.id) {
    state.talkLessonId = state.lesson.id;
    state.talkDraft = session?.order_text || "";
  } else if (!state.talkDraft) {
    state.talkDraft = session?.order_text || "";
  }
  area.value = state.talkDraft;
  area.addEventListener("input", () => {
    state.talkDraft = area.value;
  });
  turn.append(areaLabel, area);

  if (allDone) {
    const ok = document.createElement("p");
    ok.className = "talk-ok";
    ok.textContent = "这几项都说到了。可以去做复盘。";
    turn.append(ok);
  }
  if (session?.hint) {
    const box = document.createElement("div");
    box.className = "teach-block";
    const hintKicker = document.createElement("p");
    hintKicker.className = "kicker";
    hintKicker.textContent = "提示";
    const hintLine = state.lesson.dialogue.find((line) => line.id === session.hint.id);
    const en = hintLine
      ? renderAnnotated(hintLine.english, hintLine.marks, "teach-example")
      : Object.assign(document.createElement("p"), { className: "teach-example", textContent: session.hint.english });
    const zh = document.createElement("p");
    zh.className = "zh can-hide";
    zh.textContent = session.hint.chinese;
    box.append(hintKicker, en, zh);
    turn.append(box);
  }

  const hint = document.createElement("button");
  hint.type = "button";
  hint.className = "ghost";
  hint.textContent = "看一句提示";
  hint.addEventListener("click", async () => {
    state.talkDraft = area.value;
    state.dialogue = await api(`/api/dialogue/${state.lesson.id}/hint`, { method: "POST" });
    render();
  });
  const submit = document.createElement("button");
  submit.type = "button";
  submit.className = allDone ? "ghost" : "primary";
  submit.textContent = allDone ? "再交一次" : task.submit_label || "提交我的话";
  submit.addEventListener("click", async () => {
    const previous = submit.textContent;
    submit.disabled = true;
    submit.textContent = "正在检查…";
    try {
      state.talkDraft = area.value;
      state.dialogue = await api(`/api/dialogue/${state.lesson.id}/order`, {
        method: "POST",
        body: JSON.stringify({ text: area.value, expected_revision: progress().revision }),
      });
      state.lesson.progress = state.dialogue.progress;
      state.talkJustSubmitted = true;
      render();
    } catch (error) {
      if (error.body?.detail?.progress) state.lesson.progress = error.body.detail.progress;
      submit.disabled = false;
      submit.textContent = previous;
      setError(error.message);
    }
  });
  const recap = document.createElement("button");
  recap.type = "button";
  recap.className = allDone ? "primary" : "talk-skip";
  recap.textContent = allDone ? "去做复盘" : "先去做复盘";
  recap.addEventListener("click", async () => {
    recap.disabled = true;
    try {
      await advanceTo("recap");
    } catch (error) {
      recap.disabled = false;
      setError(error.message);
    }
  });
  const back = document.createElement("button");
  back.type = "button";
  back.className = "ghost";
  back.textContent = "返回听读";
  back.addEventListener("click", () => visitStep("listen"));

  const actions = document.createElement("div");
  actions.className = "talk-actions";
  const secondary = document.createElement("div");
  secondary.className = "talk-actions-row";
  if (allDone) {
    secondary.append(submit, back);
    actions.append(recap, secondary);
  } else {
    secondary.append(hint, back);
    actions.append(submit, secondary, recap);
  }
  turn.append(actions);
  root.append(turn);
  return root;
}

function localWhen(isoStamp) {
  if (!isoStamp) return "";
  const date = new Date(isoStamp);
  if (Number.isNaN(date.getTime())) return isoStamp;
  return date.toLocaleString("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function svgEl(name, attrs) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)));
  return node;
}

function ringChart(value, total, caption) {
  const wrap = document.createElement("div");
  wrap.className = "ring";
  const safeTotal = total || 1;
  const pct = Math.max(0, Math.min(1, (value || 0) / safeTotal));
  const radius = 42;
  const circ = 2 * Math.PI * radius;
  const svg = svgEl("svg", {
    viewBox: "0 0 108 108",
    class: "ring-svg",
    "aria-hidden": "true",
  });
  svg.append(
    svgEl("circle", {
      cx: 54,
      cy: 54,
      r: radius,
      fill: "none",
      stroke: "#d2d2d0",
      "stroke-width": 10,
    })
  );
  if (pct > 0) {
    svg.append(
      svgEl("circle", {
        cx: 54,
        cy: 54,
        r: radius,
        fill: "none",
        stroke: "#111111",
        "stroke-width": 10,
        "stroke-linecap": "round",
        "stroke-dasharray": `${circ * pct} ${circ}`,
        transform: "rotate(-90 54 54)",
      })
    );
  }
  const valueEl = document.createElement("p");
  valueEl.className = "ring-value";
  valueEl.textContent = `${value || 0}/${total || 0}`;
  const cap = document.createElement("p");
  cap.className = "ring-cap";
  cap.textContent = caption;
  wrap.append(svg, valueEl, cap);
  wrap.setAttribute("role", "img");
  wrap.setAttribute("aria-label", `${caption} ${value || 0} 共 ${total || 0}`);
  return wrap;
}

function barChart(items, tone, maxValue) {
  const max = maxValue || Math.max(1, ...items.map((item) => item.count || 0));
  const list = document.createElement("div");
  list.className = "hbar-list";
  items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "hbar";
    const label = document.createElement("p");
    label.className = "hbar-label";
    label.textContent = item.label_zh;
    const count = document.createElement("p");
    count.className = "hbar-count";
    count.textContent = item.display != null ? item.display : String(item.count || 0);
    const track = document.createElement("div");
    track.className = "hbar-track";
    const fill = document.createElement("div");
    fill.className = "hbar-fill" + (tone === "result" ? " is-" + item.id : "");
    fill.style.width = `${((item.count || 0) / max) * 100}%`;
    track.append(fill);
    row.append(label, count, track);
    if (item.hint_zh) {
      row.title = item.hint_zh;
    }
    list.append(row);
  });
  return list;
}

function renderProgress() {
  const data = state.overview;
  if (!data) return banner("empty", "进度还没加载出来。");
  const root = document.createDocumentFragment();
  const doneCount = (data.completed_lessons || []).length;
  const lessonTotal = data.lesson_total || 3;
  const monthDone = data.month_done || 0;
  const monthTotal = data.month_total || 6;
  const currentMonth = (data.roadmap || []).find((item) => item.status === "in_progress") || (data.roadmap || [])[0];

  const summary = document.createElement("section");
  summary.className = "card";
  const kicker = document.createElement("p");
  kicker.className = "kicker";
  kicker.textContent = "进度";
  const title = document.createElement("h1");
  title.textContent = "半年路线";
  const rings = document.createElement("div");
  rings.className = "chart-rings";
  rings.append(
    ringChart(doneCount, lessonTotal, "已完成课程"),
    ringChart(monthDone, monthTotal, "已完成月份")
  );
  const stats = document.createElement("p");
  stats.className = "chart-stats";
  stats.textContent = `复习卡 ${data.card_count || 0} · 今天到期 ${data.due_count || 0}`;
  summary.append(kicker, title, rings, stats);
  root.append(summary);

  const map = document.createElement("section");
  map.className = "card";
  const mapTitle = document.createElement("h2");
  mapTitle.textContent = "六个月";
  const track = document.createElement("div");
  track.className = "month-track";
  track.setAttribute("role", "list");
  (data.roadmap || []).forEach((item) => {
    const cell = document.createElement("div");
    cell.className = "month-cell is-" + item.status;
    cell.setAttribute("role", "listitem");
    const num = document.createElement("span");
    num.className = "month-n";
    num.textContent = String(item.month);
    cell.append(num);
    cell.title = `第 ${item.month} 月 ${item.title_zh} · ${item.label}`;
    track.append(cell);
  });
  const mapNote = document.createElement("p");
  mapNote.className = "audio-tag";
  mapNote.textContent = currentMonth
    ? `当前第 ${currentMonth.month} 月 · ${currentMonth.title_zh} · ${currentMonth.label}`
    : "路线还没有排出来。";
  map.append(mapTitle, track, mapNote);
  root.append(map);

  const month = document.createElement("section");
  month.className = "card";
  const monthTitle = document.createElement("h2");
  monthTitle.textContent = "本月三课";
  month.append(monthTitle);
  const lessonItems = (data.lessons || []).map((item) => {
    const pct = { idle: 0, vocab: 0.2, listen: 0.4, talk: 0.6, recap: 0.8, done: 1 }[item.step] ?? 0;
    return {
      label_zh: item.title_zh,
      count: Math.round(pct * 100),
      display: item.step_zh,
      hint_zh: item.step_zh,
    };
  });
  if (!lessonItems.length) month.append(banner("empty", "还没有排课。"));
  else month.append(barChart(lessonItems, "", 100));
  root.append(month);

  const boxes = document.createElement("section");
  boxes.className = "card";
  const boxesTitle = document.createElement("h2");
  boxesTitle.textContent = "复习卡在哪一格";
  const boxesHelp = document.createElement("p");
  boxesHelp.className = "audio-tag";
  boxesHelp.textContent = "格子越大，下次隔得越久。这是复习间隔，不是口语分数。";
  boxes.append(boxesTitle, boxesHelp, barChart(data.boxes || []));
  if (!(data.card_count > 0)) {
    const note = document.createElement("p");
    note.className = "audio-tag";
    note.textContent = "词汇评分后，卡片会进格子。";
    boxes.append(note);
  }
  root.append(boxes);

  const results = document.createElement("section");
  results.className = "card";
  const resultsTitle = document.createElement("h2");
  resultsTitle.textContent = "最近怎么评";
  results.append(resultsTitle, barChart(data.results || [], "result"));
  const resultTotal = (data.results || []).reduce((sum, item) => sum + (item.count || 0), 0);
  if (!resultTotal) {
    const note = document.createElement("p");
    note.className = "audio-tag";
    note.textContent = "还没有评分。翻卡选忘了、模糊或记得之后会出现。";
    results.append(note);
  }
  root.append(results);

  const log = document.createElement("section");
  log.className = "card";
  const logTitle = document.createElement("h2");
  logTitle.textContent = "最近复习";
  log.append(logTitle);
  if (!(data.review_log || []).length) log.append(banner("empty", "还没有复习记录。"));
  else {
    const list = document.createElement("ul");
    list.className = "list";
    const names = { forgot: "忘了", fuzzy: "模糊", remembered: "记得" };
    data.review_log.forEach((item) => {
      const row = document.createElement("li");
      row.textContent = `${item.english} · ${names[item.result] || item.result} · 下次 ${localWhen(item.due_at)}`;
      list.append(row);
    });
    log.append(list);
  }
  root.append(log);
  return root;
}

function render() {
  closeGloss();
  const route = pageId();
  state.page = route.page;
  state.library = route.page === "vocab" ? state.library : false;
  const active = document.activeElement;
  const keepSearch = active && active.classList.contains("search");
  const cursor = keepSearch ? active.selectionStart : null;
  paintNav();
  view.classList.toggle("is-vocab", state.page === "vocab" && !state.library);
  view.replaceChildren();
  if (state.loading) {
    view.append(banner("loading", "正在打开…"));
    return;
  }
  if (state.error) view.append(banner("error", state.error, loadCore));
  if (!state.lesson && state.page !== "progress") {
    if (!state.error) view.append(banner("empty", "还没有课程。"));
    return;
  }
  const page = {
    today: renderToday,
    vocab: renderVocab,
    reading: renderReading,
    talk: renderTalk,
    progress: renderProgress,
  }[state.page];
  view.append(page());
  if (state.aimRecap && !state.loading) {
    const recap = document.getElementById("lesson-recap");
    if (recap) {
      state.aimRecap = false;
      recap.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }
  if (keepSearch) {
    const search = view.querySelector(".search");
    if (search) {
      search.focus();
      if (cursor != null) search.setSelectionRange(cursor, cursor);
    }
  }
}

zhToggle.addEventListener("click", async () => {
  state.hideZh = !state.hideZh;
  paintNav();
  render();
  if (state.lesson) {
    try {
      await saveProgress({ hide_zh: state.hideZh });
    } catch {
      /* keep the toggle; retry is on screen if save failed */
    }
  }
});

window.addEventListener("hashchange", () => {
  const route = pageId();
  state.page = route.page;
  state.flipped = false;
  if (route.library) state.library = true;
  loadCore();
});

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/static/sw.js").catch(() => {});
}

{
  const route = pageId();
  state.page = route.page;
  state.library = route.library;
  loadCore();
}
