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
  readings: [],
  reading: null,
  readingIndex: 0,
  readingArticleId: "",
  vocabQueue: [],
  talkTopics: [],
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
  grammarExplain: {},
  vocabIndex: 0,
  vocabPhase: "learn",
};

const view = document.querySelector("#view");
const zhToggle = document.querySelector("#zh-toggle");

function pageId() {
  const raw = (location.hash || "#/today").replace(/^#\/?/, "");
  const [page, extra] = raw.split("/");
  return {
    page: PAGES.some((item) => item.id === page) ? page : "today",
    library: extra === "library",
    itemId: extra && extra !== "library" ? extra : "",
  };
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

let spokenUtterance = null;
let speakTimer = 0;
let cachedVoices = [];

function refreshVoices() {
  if (!window.speechSynthesis || typeof window.speechSynthesis.getVoices !== "function") return [];
  cachedVoices = window.speechSynthesis.getVoices() || [];
  return cachedVoices;
}

function englishVoice() {
  const voices = cachedVoices.length ? cachedVoices : refreshVoices();
  const english = voices.filter((voice) => /^en\b/i.test(voice.lang) || /english/i.test(voice.name));
  return (
    english.find((voice) => /en-US/i.test(voice.lang)) ||
    english.find((voice) => /en-GB/i.test(voice.lang)) ||
    english[0] ||
    null
  );
}

function canSpeak() {
  return Boolean(window.speechSynthesis);
}

function speakHint() {
  if (!window.speechSynthesis) return "这台设备没有系统朗读。英文仍可以看、可以练。";
  if (cachedVoices.length && !englishVoice()) {
    return "手机里还没有英文语音。打开系统设置里的「文字转语音」，选用 Google 文字转语音并下载英语，媒体音量也要打开。页面上的英文仍可以看、可以练。";
  }
  return "现在读不出来。把媒体音量打开，并在系统设置里确认文字转语音可用。英文仍可以看、可以练。";
}

function speak(text) {
  const clean = String(text || "").replace(/\s+/g, " ").trim();
  if (!clean) return;
  if (!window.speechSynthesis) {
    setError(speakHint());
    return;
  }
  refreshVoices();
  window.clearTimeout(speakTimer);
  try {
    window.speechSynthesis.resume();
    window.speechSynthesis.cancel();
  } catch {
    setError(speakHint());
    return;
  }
  const utterance = new SpeechSynthesisUtterance(clean);
  const voice = englishVoice();
  utterance.lang = voice && voice.lang ? voice.lang : "en-US";
  utterance.rate = 0.84;
  if (voice) utterance.voice = voice;
  utterance.onerror = (event) => {
    if (event.error === "interrupted" || event.error === "canceled") return;
    setError(speakHint());
  };
  spokenUtterance = utterance;
  const start = () => {
    try {
      window.speechSynthesis.resume();
      window.speechSynthesis.speak(utterance);
    } catch {
      setError(speakHint());
    }
  };
  if (window.speechSynthesis.speaking || window.speechSynthesis.pending) {
    speakTimer = window.setTimeout(start, 80);
  } else {
    start();
  }
}

if (window.speechSynthesis) {
  refreshVoices();
  window.speechSynthesis.addEventListener("voiceschanged", refreshVoices);
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
    const route = pageId();
    const today = await api("/api/today");
    const overview = page === "progress" ? await api("/api/progress") : null;
    const due = page === "today" ? (await api("/api/review/due")).items : [];
    const readings = page === "reading" || page === "today" ? (await api("/api/readings")).items : state.readings;
    const vocabQueue = page === "vocab" && !state.library ? (await api("/api/vocab/queue")).items : [];
    const talkTopics = page === "talk" ? (await api("/api/talk/topics")).items : [];
    const itemId = route.itemId || "";
    let lesson = state.lesson;
    let dialogue = null;
    let reading = null;
    if (page === "talk" && itemId) {
      lesson = await api(`/api/lessons/${itemId}`);
      dialogue = await api(`/api/dialogue/${itemId}`);
    } else if (page === "reading" && itemId) {
      reading = await api(`/api/readings/${itemId}`);
      lesson = reading;
    } else if (today.lesson_id) {
      try {
        lesson = await api(`/api/lessons/${state.openLessonId || today.lesson_id}`);
      } catch (error) {
        lesson = lesson || null;
      }
    }
    if (request !== coreRequest) return;
    const sameLesson = state.lesson?.id === lesson?.id;
    const localRev = sameLesson ? currentRevision() : 0;
    const remoteRev = Number(lesson?.progress?.revision);
    if (lesson && sameLesson && Number.isFinite(remoteRev) && localRev > remoteRev) {
      lesson.progress = state.lesson.progress;
    }
    Object.assign(state, {
      today, lesson, dialogue, overview, due, readings, reading, vocabQueue, talkTopics,
      hideZh: Boolean(lesson?.progress?.hide_zh),
    });
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

function markIcon(kind) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.classList.add("teach-mark-icon");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", "currentColor");
  path.setAttribute("stroke-width", "2.6");
  path.setAttribute("stroke-linecap", "round");
  path.setAttribute("stroke-linejoin", "round");
  path.setAttribute("d", kind === "yes" ? "M5 12.5 10 17.5 19 7" : "M7 7l10 10M17 7 7 17");
  svg.append(path);
  return svg;
}

function replyMarkKind(zh) {
  if (zh === "是") return "yes";
  if (zh === "不是") return "no";
  return "";
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

function strokeIcon(pathD) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.classList.add("teach-ai-icon");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", "currentColor");
  path.setAttribute("stroke-width", "2");
  path.setAttribute("stroke-linecap", "round");
  path.setAttribute("stroke-linejoin", "round");
  path.setAttribute("d", pathD);
  svg.append(path);
  return svg;
}

function speakButton(text) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "speak";
  const available = canSpeak();
  button.setAttribute("aria-label", available ? "用设备语音朗读" : "这台设备不能朗读");
  button.title = available
    ? "用这台设备的系统语音朗读，不是录音"
    : "这台设备没有系统朗读。英文仍可以看、可以练。";
  if (!available) button.disabled = true;
  button.append(speakIcon());
  button.dataset.speak = text;
  button.addEventListener("click", () => speak(button.dataset.speak || text));
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
  const kind = document.createElement("p");
  kind.className = "kicker";
  kind.textContent = mark.kind === "grammar" ? "语法" : mark.kind === "phrase" ? "短句" : "词汇";
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
  speakBtn.setAttribute("aria-label", canSpeak() ? "朗读" : "这台设备不能朗读");
  speakBtn.title = canSpeak()
    ? "用这台设备的系统语音朗读，不是录音"
    : "这台设备没有系统朗读。英文仍可以看、可以练。";
  if (!canSpeak()) speakBtn.disabled = true;
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
  const actions = document.createElement("div");
  actions.className = "gloss-mark-actions";
  appendKnowButtons(actions, mark.status, async (result) => {
    try {
      await api(`/api/headwords/${encodeURIComponent(mark.headword || mark.headword_id || "")}/mark`, {
        method: "POST",
        body: JSON.stringify({ result }),
      });
      closeGloss();
      const articleId = state.reading?.id;
      if (articleId && state.page === "reading" && pageId().itemId === articleId) {
        await refreshReadingInPlace(articleId);
      }
    } catch (error) {
      setError(error.message);
    }
  });
  card.append(kind, word, row, meta, actions);
  document.body.append(backdrop, card);
  if (mobile) backdrop.addEventListener("click", closeGloss);
  else {
    placeGlossCard(anchor, card);
    document.addEventListener("pointerdown", onGlossPointer, true);
  }
  document.addEventListener("keydown", onGlossKey);
  window.addEventListener("resize", closeGloss);
  gloss = { anchor, card, backdrop };
  requestAnimationFrame(() => {
    if (gloss?.anchor === anchor) window.addEventListener("scroll", closeGloss, true);
  });
}

async function refreshReadingInPlace(articleId) {
  const current = state.reading;
  const updated = await api(`/api/readings/${encodeURIComponent(articleId)}`);
  if (
    current !== state.reading ||
    state.page !== "reading" ||
    pageId().itemId !== articleId ||
    !updated.passage
  ) return;

  current.passage = updated.passage;
  if (state.lesson === current) state.lesson.passage = updated.passage;
  const paragraphs = current.passage.paragraphs || [];
  if (!paragraphs.length) return;
  const index = Math.min(Math.max(0, state.readingIndex || 0), paragraphs.length - 1);
  state.readingIndex = index;
  const sentence = view.querySelector(".passage-card .passage-block .sentence");
  if (sentence) {
    const para = paragraphs[index];
    sentence.replaceWith(renderAnnotated(para.english, para.marks, "english sentence"));
  }
}

function appendKnowButtons(root, status, onPick) {
  const known = status === "known" || status === "due";
  const buttons = [["会", "known"]];
  if (known) buttons.push(["还不会", "unknown"]);
  buttons.forEach(([label, result]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "gloss-mark-btn" + (result === "known" && known ? " is-on" : "");
    if (result === "known") button.classList.add("is-know");
    button.textContent = label;
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      onPick(result);
    });
    root.append(button);
  });
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
    if (item.kind !== "vocab" && item.kind !== "grammar" && item.kind !== "phrase") return;
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
    const kindLabel = mark.kind === "grammar" ? "语法" : mark.kind === "phrase" ? "短句" : "生词";
    button.setAttribute("aria-label", `${kindLabel} ${mark.headword || button.textContent}`);
    if (mark.status === "due") button.classList.add("is-due");
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
  go("reading", state.today?.lesson_id);
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
    ? `${state.lesson.level || "CET-4"} · 回去看`
    : `${state.today.level} · 第 ${state.today.lesson_no} 篇`;
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
  const queue = state.today.lessons || [];
  if (queue.length) {
    const month = document.createElement("section");
    month.className = "card";
    const monthTitle = document.createElement("h2");
    monthTitle.textContent = "阅读";
    const monthHelp = document.createElement("p");
    monthHelp.className = "audio-tag";
    monthHelp.textContent = "每篇都是完整短文。点开就能读，不必按顺序。";
    const list = document.createElement("ul");
    list.className = "list";
    queue.forEach((item) => {
      const row = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "today-lesson-btn is-" + item.status;
      const name = document.createElement("p");
      name.className = "english";
      name.style.fontSize = "1.05rem";
      name.textContent = `${item.lesson_no}. ${item.title_zh}`;
      const status = document.createElement("p");
      status.className = "audio-tag";
      status.textContent = item.status === "done" ? "已读完 · 点这里再看" : "点这里阅读";
      btn.append(name, status);
      btn.addEventListener("click", () => go("reading", item.id));
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
    ["lesson", "待复习"],
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
  root.append(tabs);
  if (state.library) {
    root.append(renderLibrary());
    return root;
  }
  const items = state.vocabQueue || [];
  if (!items.length) {
    root.append(banner("empty", "这些词都标过会了。到期漏出时会再出现。"));
    return root;
  }
  const index = Math.min(Math.max(0, state.vocabIndex || 0), items.length - 1);
  state.vocabIndex = index;
  const item = items[index];
  const card = renderTeachCard(item, index, items.length);
  root.append(cardDeck(card, index, items.length, async next => {
    state.vocabIndex = next;
    state.flipped = false;
    render();
  }, "生词"));
  return root;
}

async function markQueueItem(item, result) {
  try {
    await api(`/api/headwords/${encodeURIComponent(item.headword_id || item.english)}/mark`, {
      method: "POST",
      body: JSON.stringify({ result }),
    });
    state.flipped = false;
    await loadCore();
  } catch (error) {
    setError(error.message);
  }
}

function vocabDots(index, total) {
  const bar = document.createElement("div");
  bar.className = "vocab-bar";
  bar.setAttribute("aria-hidden", "true");
  const fill = document.createElement("span");
  fill.className = "vocab-bar-fill";
  fill.style.width = `${total ? Math.max(8, ((index + 1) / total) * 100) : 0}%`;
  bar.append(fill);
  return bar;
}

async function showVocabCard(index, phase) {
  state.flipped = false;
  state.vocabIndex = index;
  state.vocabPhase = phase || "learn";
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

function hasGrammarTeach(item) {
  const teach = item && item.teach;
  if (!teach) return false;
  return Boolean(
    teach.ask ||
    teach.ask_en ||
    (teach.replies && teach.replies.length) ||
    (teach.swaps && teach.swaps.length) ||
    teach.why_title
  );
}

function fillAsk(template, fallback, swap) {
  if (!template) return fallback || "";
  if (!swap) return fallback || template.replaceAll("{en}", "").replaceAll("{zh}", "").trim();
  return template.replaceAll("{en}", swap.en || "").replaceAll("{zh}", swap.zh || "");
}

function teachLabel(text) {
  const label = document.createElement("p");
  label.className = "teach-label";
  label.textContent = text;
  return label;
}

function renderGrammarTeach(item) {
  const teach = item.teach || {};
  const block = document.createElement("div");
  block.className = "teach-block grammar-teach";
  const swaps = teach.swaps || [];
  let selected = swaps.find((itemSwap) => item.example_en && item.example_en.includes(itemSwap.en)) || swaps[0] || null;

  const askEn = () => fillAsk(teach.ask_en, item.example_en, selected);
  const askZh = () => fillAsk(teach.ask_zh, item.example_zh, selected);

  const ask = document.createElement("section");
  ask.className = "teach-section";
  const line = document.createElement("div");
  line.className = "teach-ask-line";
  const en = document.createElement("p");
  en.className = "teach-example";
  const zh = document.createElement("p");
  zh.className = "zh can-hide";
  const speak = speakButton(askEn());
  line.append(en, speak);
  ask.append(teachLabel(teach.ask || "怎么问"), line, zh);

  const replyBox = document.createElement("section");
  replyBox.className = "teach-section";
  if (teach.replies && teach.replies.length) {
    replyBox.append(teachLabel("怎么回答"));
    teach.replies.forEach((reply) => {
      const row = document.createElement("p");
      row.className = "teach-reply";
      const label = document.createElement("span");
      const mark = replyMarkKind(reply.zh);
      if (mark) {
        label.className = "teach-reply-mark teach-reply-mark-" + mark;
        label.setAttribute("aria-label", reply.zh);
        label.append(markIcon(mark));
      } else {
        label.className = "teach-reply-zh can-hide";
        label.textContent = reply.zh;
      }
      const english = document.createElement("span");
      english.className = "teach-reply-en";
      english.textContent = reply.en;
      row.append(label, english);
      replyBox.append(row);
    });
  }

  const swapBox = document.createElement("section");
  swapBox.className = "teach-section";
  const swapButtons = [];
  if (swaps.length) {
    swapBox.append(teachLabel("换个词试试"));
    const row = document.createElement("div");
    row.className = "teach-swaps";
    swaps.forEach((swap) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "teach-swap";
      button.dataset.en = swap.en;
      const zhPart = document.createElement("span");
      zhPart.className = "can-hide";
      zhPart.textContent = swap.zh;
      const enPart = document.createElement("span");
      enPart.textContent = swap.en;
      button.append(zhPart, enPart);
      button.addEventListener("click", () => {
        selected = swap;
        refreshAsk();
      });
      swapButtons.push(button);
      row.append(button);
    });
    swapBox.append(row);
  }

  function refreshAsk() {
    const english = askEn();
    en.textContent = english;
    zh.textContent = askZh();
    speak.dataset.speak = english;
    swapButtons.forEach((button) => {
      const on = button.dataset.en === (selected && selected.en);
      button.classList.toggle("is-on", on);
      button.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }
  refreshAsk();

  block.append(ask);
  if (teach.replies && teach.replies.length) block.append(replyBox);
  if (swaps.length) block.append(swapBox);
  if (teach.why_title || (teach.why_lines && teach.why_lines.length)) {
    const details = document.createElement("details");
    details.className = "teach-why";
    const summary = document.createElement("summary");
    summary.textContent = teach.why_title || "为什么？";
    details.append(summary);
    (teach.why_lines || []).forEach((lineText) => {
      const p = document.createElement("p");
      p.className = "teach-why-line";
      p.textContent = lineText;
      details.append(p);
    });
    details.addEventListener("toggle", () => {
      if (details.open) details.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
    block.append(details);
  }
  block.append(renderGrammarMore(item));
  return block;
}

function grammarExplainEntry(id) {
  return state.grammarExplain[id] || { status: "", text: "", message: "", question: "" };
}

function renderGrammarMore(item) {
  const box = document.createElement("div");
  box.className = "teach-more";
  const start = document.createElement("button");
  start.type = "button";
  start.className = "teach-more-btn";
  const out = document.createElement("div");
  let askOpen = false;

  function paint() {
    const current = grammarExplainEntry(item.id);
    const busy = current.status === "loading";
    out.replaceChildren();
    start.hidden = Boolean(current.text);
    start.disabled = busy;
    start.textContent = busy && !current.text ? "正在请 DeepSeek 讲…" : "更详细一点";
    if (current.text) {
      out.append(renderAiPanel(item, current, busy));
    }
    if (current.status === "error") {
      out.append(
        banner("empty", current.message || "讲解失败。", () => {
          requestExplain(current.question || "");
        })
      );
    }
  }

  function renderAiPanel(card, current, busy) {
    const panel = document.createElement("section");
    panel.className = "teach-ai";
    const kicker = document.createElement("p");
    kicker.className = "kicker";
    kicker.textContent = "DeepSeek 讲解";
    const note = document.createElement("p");
    note.className = "teach-explain";
    note.textContent = current.text;
    if (current.question) {
      const asked = document.createElement("p");
      asked.className = "teach-ask-q";
      asked.textContent = "问：" + current.question;
      panel.append(kicker, asked, note);
    } else {
      panel.append(kicker, note);
    }
    const foot = document.createElement("div");
    foot.className = "teach-ai-foot";
    const askBtn = document.createElement("button");
    askBtn.type = "button";
    askBtn.className = "teach-ai-tool";
    askBtn.setAttribute("aria-expanded", askOpen ? "true" : "false");
    askBtn.setAttribute("aria-label", "问 DeepSeek");
    askBtn.title = "问一句";
    askBtn.disabled = busy;
    askBtn.append(strokeIcon("M21 15a2 2 0 0 1-2 2H8l-4 4V5a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2z"));
    askBtn.addEventListener("click", () => {
      askOpen = !askOpen;
      paint();
      if (askOpen) {
        const field = box.querySelector(".teach-ask-input");
        field?.focus();
      }
    });
    const refresh = document.createElement("button");
    refresh.type = "button";
    refresh.className = "teach-ai-tool";
    refresh.setAttribute("aria-label", "重新讲解");
    refresh.title = "重新讲解";
    refresh.disabled = busy;
    refresh.append(strokeIcon("M21 12a9 9 0 1 1-3-6.7M21 3v6h-6"));
    refresh.addEventListener("click", () => {
      askOpen = false;
      requestExplain("").catch(() => {});
    });
    foot.append(askBtn, refresh);
    if (askOpen) {
      const form = document.createElement("form");
      form.className = "teach-ask";
      const field = document.createElement("input");
      field.className = "teach-ask-input";
      field.type = "text";
      field.maxLength = 200;
      field.setAttribute("aria-label", "向 DeepSeek 提问");
      field.placeholder = "例如：为什么不能说 Yes, I'm?";
      const send = document.createElement("button");
      send.type = "submit";
      send.className = "ghost";
      send.textContent = "问";
      send.disabled = busy;
      form.append(field, send);
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const question = field.value.trim();
        if (!question) {
          field.focus();
          return;
        }
        askOpen = false;
        requestExplain(question).catch(() => {});
      });
      panel.append(form);
    }
    panel.append(foot);
    return panel;
  }

  async function requestExplain(question) {
    const lessonId = item.lesson_id || state.lesson?.id;
    if (!item.id || !lessonId) return;
    const previous = grammarExplainEntry(item.id);
    state.grammarExplain[item.id] = {
      status: "loading",
      text: previous.text || "",
      message: "",
      question: question || "",
    };
    paint();
    try {
      const result = await api(
        `/api/lessons/${encodeURIComponent(lessonId)}/expressions/${encodeURIComponent(item.id)}/explain`,
        { method: "POST", body: JSON.stringify({ question: question || "" }) }
      );
      state.grammarExplain[item.id] = {
        status: "ok",
        text: result.explain_zh || "这一条暂时没有更多说明。",
        message: "",
        question: question || "",
      };
    } catch (error) {
      state.grammarExplain[item.id] = {
        status: "error",
        text: previous.text || "",
        message: error.message,
        question: question || "",
      };
    }
    paint();
    const target = box.querySelector(".teach-ai") || box;
    target.scrollIntoView({ block: "end", behavior: "smooth" });
  }

  start.addEventListener("click", () => {
    requestExplain("").catch(() => {});
  });
  const row = document.createElement("div");
  row.className = "teach-more-row";
  row.append(start, speakButton(item.english));
  box.append(row, out);
  paint();
  return box;
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
  if (hasGrammarTeach(item)) {
    face.append(renderGrammarTeach(item));
  } else {
    if (item.note_zh) {
      const note = document.createElement("div");
      note.className = "teach-block";
      const title = document.createElement("p");
      title.className = "kicker";
      title.textContent = item.kind === "grammar" ? "语法" : "怎么记";
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
    face.append(renderGrammarMore(item));
  }
  const actions = document.createElement("div");
  actions.className = "vocab-actions";
  if (item.headword_id) {
    const grades = document.createElement("div");
    grades.className = "vocab-grades is-single";
    appendKnowButtons(grades, item.status, (result) => markQueueItem(item, result));
    actions.append(grades);
  }
  if (!item.headword_id && index + 1 === total) {
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
  if (index !== progress()?.vocab_index) {
    const resume = document.createElement("button");
    resume.type = "button";
    resume.className = "primary";
    resume.textContent = "返回待评分词卡";
    resume.onclick = () => { recallPreview = null; state.flipped = false; render(); };
    actions.append(resume);
  } else if (state.flipped) {
    if (item.headword_id) {
      const row = document.createElement("div");
      row.className = "vocab-toolbar";
      appendKnowButtons(row, item.status, (result) => markQueueItem(item, result));
      row.append(speakButton(item.english));
      actions.append(row);
    } else {
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
  }
  card.append(vocabHead("回忆", index, total), face, actions);
  return card;
}

function renderLibrary() {
  const panel = document.createElement("section");
  panel.className = "card library-card";
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
  list.className = "list library-list";
  state.catalogItems.forEach((item) => {
    const row = document.createElement("li");
    const en = document.createElement("p");
    en.className = "english";
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

function renderReadingList() {
  const root = document.createDocumentFragment();
  const card = document.createElement("section");
  card.className = "card";
  const kicker = document.createElement("p");
  kicker.className = "kicker";
  kicker.textContent = "阅读";
  const title = document.createElement("h1");
  title.textContent = "长篇精读";
  const help = document.createElement("p");
  help.className = "audio-tag";
  help.textContent = "每篇是完整短文。浅蓝虚线是词汇，紫色实线是语法，短句另有划线。没标的都按不会。会了的下一篇不再划出，到期会再漏出来。";
  card.append(kicker, title, help);
  const list = document.createElement("ul");
  list.className = "list";
  (state.readings || []).forEach((item, index) => {
    const row = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "today-lesson-btn is-" + (item.done ? "done" : "unread");
    const name = document.createElement("p");
    name.className = "english";
    name.style.fontSize = "1.05rem";
    name.textContent = `${index + 1}. ${item.title_zh}`;
    const meta = document.createElement("p");
    meta.className = "audio-tag";
    meta.textContent = `${item.word_count} 词 · 还剩 ${item.mark_visible} 处划线`;
    btn.append(name, meta);
    btn.addEventListener("click", () => go("reading", item.id));
    row.append(btn);
    list.append(row);
  });
  if (!(state.readings || []).length) card.append(banner("empty", "还没有文章。"));
  else card.append(list);
  root.append(card);
  return root;
}

function renderReadingArticle(article) {
  const root = document.createDocumentFragment();
  const passage = article.passage || {};
  const card = document.createElement("section");
  card.className = "card passage-card";
  const back = document.createElement("button");
  back.type = "button";
  back.className = "ghost";
  back.textContent = "返回文章列表";
  back.addEventListener("click", () => go("reading"));
  const kicker = document.createElement("p");
  kicker.className = "kicker";
  const words = (passage.paragraphs || []).reduce((sum, para) => sum + (para.english || "").split(/\s+/).filter(Boolean).length, 0);
  kicker.textContent = `阅读 · ${article.level || "CET-4"} · 约 ${words} 词`;
  const title = document.createElement("h1");
  title.textContent = passage.title_zh || article.title_zh || "短文";
  const help = document.createElement("p");
  help.className = "audio-tag";
  help.textContent = "浅蓝虚线是词汇，紫色实线是语法，短句也有划线。没标的都按不会，点开标会即可。朗读是这台设备的系统语音，不是录音。";
  const paragraphs = passage.paragraphs || [];
  const articleId = article.id || passage.title_zh || article.title_zh || "reading";
  if (state.readingArticleId !== articleId) {
    state.readingArticleId = articleId;
    state.readingIndex = 0;
  }
  card.append(back, kicker, title, help);
  if (!paragraphs.length) {
    card.append(banner("empty", "这篇短文还没有正文。"));
    root.append(card);
  } else {
    const index = Math.min(Math.max(0, state.readingIndex || 0), paragraphs.length - 1);
    state.readingIndex = index;
    const para = paragraphs[index];
    const block = document.createElement("div");
    block.className = "passage-block";
    block.append(
      renderAnnotated(para.english, para.marks, "english sentence"),
      Object.assign(document.createElement("p"), { className: "zh can-hide", textContent: para.chinese }),
      speakButton(para.english)
    );
    card.append(block);
    root.append(cardDeck(card, index, paragraphs.length, next => {
      state.readingIndex = next;
      render();
      view.querySelector(".study-deck")?.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
        block: "start",
      });
    }, "阅读"));
  }
  const quiz = document.createElement("section");
  quiz.className = "card quiz-card";
  const quizKicker = document.createElement("p");
  quizKicker.className = "kicker";
  quizKicker.textContent = "理解题";
  const quizTitle = document.createElement("h1");
  quizTitle.textContent = "读完选一选";
  const quizHelp = document.createElement("p");
  quizHelp.className = "audio-tag";
  quizHelp.textContent = "对照上面的文章。选错了可以再选。";
  quiz.append(quizKicker, quizTitle, quizHelp);
  const results = { ...(progress()?.question_results || {}) };
  const letters = "ABCDE";
  (article.questions || []).forEach((question, index) => {
    const wrap = document.createElement("div");
    wrap.className = "quiz-block";
    const num = document.createElement("p");
    num.className = "quiz-num";
    num.textContent = `第 ${index + 1} 题 · 共 ${article.questions.length} 题`;
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
  const doneWrap = document.createElement("div");
  doneWrap.className = "talk-actions";
  const done = document.createElement("button");
  done.type = "button";
  const already = article.progress?.step === "done";
  done.className = already ? "ghost" : "primary";
  done.textContent = already ? "已经读完" : "读完了";
  if (!already) {
    done.addEventListener("click", async () => {
      try {
        await saveProgress({ step: "done" });
        render();
      } catch (error) {
        setError(error.message);
      }
    });
  }
  doneWrap.append(done);
  quiz.append(doneWrap);
  root.append(quiz);
  return root;
}

function renderReading() {
  const article = state.reading;
  if (article?.passage) return renderReadingArticle(article);
  return renderReadingList();
}

function renderTalkTopics() {
  const root = document.createDocumentFragment();
  const card = document.createElement("section");
  card.className = "card";
  const kicker = document.createElement("p");
  kicker.className = "kicker";
  kicker.textContent = "对话";
  const title = document.createElement("h1");
  title.textContent = "选一个话题";
  const help = document.createElement("p");
  help.className = "audio-tag";
  help.textContent = "和阅读分开。点进一题，用英文写出你的话。";
  card.append(kicker, title, help);
  const list = document.createElement("ul");
  list.className = "list";
  (state.talkTopics || []).forEach((item, index) => {
    const row = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "today-lesson-btn is-unread";
    const name = document.createElement("p");
    name.className = "english";
    name.style.fontSize = "1.05rem";
    name.textContent = `${index + 1}. ${item.title_zh}`;
    btn.append(name);
    btn.addEventListener("click", () => go("talk", item.id));
    row.append(btn);
    list.append(row);
  });
  if (!(state.talkTopics || []).length) card.append(banner("empty", "还没有话题。"));
  else card.append(list);
  root.append(card);
  return root;
}

function renderTalk() {
  if (!pageId().itemId) return renderTalkTopics();
  if (!state.lesson) {
    const root = document.createDocumentFragment();
    root.append(banner("empty", "打不开这个话题。"));
    return root;
  }
  const session = state.dialogue;
  const task = state.lesson?.task || {};
  const root = document.createDocumentFragment();
  const backWrap = document.createElement("p");
  const back = document.createElement("button");
  back.type = "button";
  back.className = "ghost";
  back.textContent = "返回话题列表";
  back.addEventListener("click", () => go("talk"));
  backWrap.append(back);
  root.append(backWrap);

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
  kicker.textContent = session?.mode_zh || "你的回复";
  const title = document.createElement("h1");
  title.textContent = task.title_zh || "写出你的英文";
  const brief = document.createElement("p");
  brief.className = "talk-brief";
  brief.textContent = task.brief_zh || "先看对方说了什么，再自己用英文写回复。";
  turn.append(kicker, title, brief);
  if (session?.degraded) {
    turn.append(banner("empty", session.coach_zh || "DeepSeek 暂时不可用，已改回关键词检查。"));
  }

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

  if (session?.reply_en) {
    const reply = document.createElement("div");
    reply.className = "teach-block";
    const replyKicker = document.createElement("p");
    replyKicker.className = "kicker";
    replyKicker.textContent = "对方说";
    const replyEn = document.createElement("p");
    replyEn.className = "teach-example";
    replyEn.textContent = session.reply_en;
    reply.append(replyKicker, replyEn, speakButton(session.reply_en));
    turn.append(reply);
  }
  if (session?.coach_zh && !session.degraded) {
    const coach = document.createElement("p");
    coach.className = "talk-coach";
    coach.textContent = session.coach_zh;
    turn.append(coach);
  }
  if (allDone) {
    const ok = document.createElement("p");
    ok.className = "talk-ok";
    ok.textContent = "这几项都说到了。";
    turn.append(ok);
  }
  if (session?.hint) {
    const box = document.createElement("div");
    box.className = "teach-block";
    const hintKicker = document.createElement("p");
    hintKicker.className = "kicker";
    hintKicker.textContent = "提示";
    const hintLine = (state.lesson.dialogue || []).find((line) => line.id === session.hint.id);
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
    submit.textContent = session?.chat?.available ? "正在请 DeepSeek 看…" : "正在检查…";
    try {
      state.talkDraft = area.value;
      state.dialogue = await api(`/api/dialogue/${state.lesson.id}/order`, {
        method: "POST",
        body: JSON.stringify({ text: area.value, expected_revision: progress()?.revision }),
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
  const voice = document.createElement("button");
  voice.type = "button";
  voice.className = "ghost";
  voice.disabled = true;
  voice.textContent = session?.voice?.label_zh || "实时语音还没接入";
  voice.setAttribute("aria-disabled", "true");

  const actions = document.createElement("div");
  actions.className = "talk-actions";
  const secondary = document.createElement("div");
  secondary.className = "talk-actions-row";
  if (allDone) {
    secondary.append(hint, voice);
    actions.append(submit, secondary);
  } else {
    secondary.append(hint, voice);
    actions.append(submit, secondary);
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
  const lessonTotal = data.lesson_total || (data.lessons || []).length || 1;
  const monthDone = data.month_done || 0;
  const monthTotal = data.month_total || 6;
  const currentMonth = (data.roadmap || []).find((item) => item.status === "in_progress")
    || [...(data.roadmap || [])].reverse().find((item) => item.status === "done")
    || (data.roadmap || [])[0];

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
  const monthNumber = currentMonth?.month || 1;
  monthTitle.textContent = `第 ${monthNumber} 月课程`;
  month.append(monthTitle);
  const monthLessons = (data.lessons || []).filter((item) => item.month === monthNumber);
  const lessonItems = (monthLessons.length ? monthLessons : data.lessons || []).map((item) => {
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
  if (!state.today && state.page !== "progress" && state.page !== "reading" && state.page !== "vocab" && state.page !== "talk") {
    if (!state.error) view.append(banner("empty", "还没有内容。"));
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
