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
    setError("这台设备没有系统朗读。");
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
  zhToggle.setAttribute("aria-pressed", state.hideZh ? "true" : "false");
  zhToggle.textContent = state.hideZh ? "显示中文" : "隐藏中文";
  document.body.classList.toggle("hide-zh", state.hideZh);
}

function progress() {
  return state.lesson?.progress || null;
}

async function saveProgress(patch) {
  const current = progress();
  const body = {
    step: current?.step || "vocab",
    vocab_index: current?.vocab_index || 0,
    listen_index: current?.listen_index || 0,
    hide_zh: state.hideZh,
    question_results: current?.question_results || {},
    task_results: current?.task_results || {},
    expected_updated_at: current?.updated_at,
    ...patch,
  };
  try {
    const saved = await api(`/api/lessons/${state.lesson.id}/progress`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    state.lesson.progress = saved;
    return saved;
  } catch (error) {
    if (error.status === 409 && error.body?.detail?.progress) {
      state.lesson.progress = error.body.detail.progress;
      setError("另一端已经学到新的位置，已同步过来。");
      return state.lesson.progress;
    }
    setError(error.message);
    throw error;
  }
}

async function loadCore() {
  state.loading = true;
  state.error = "";
  render();
  try {
    state.today = await api("/api/today");
    state.lesson = await api(`/api/lessons/${state.today.lesson_id}`);
    state.hideZh = Boolean(state.lesson.progress.hide_zh);
    if (state.page === "talk") state.dialogue = await api(`/api/dialogue/${state.lesson.id}`);
    if (state.page === "progress") state.overview = await api("/api/progress");
    if (state.page === "today") state.due = (await api("/api/review/due")).items;
    if (state.page === "vocab" && state.library) await loadCatalog(true);
  } catch (error) {
    state.error = error.message;
  } finally {
    state.loading = false;
    render();
  }
}

async function loadCatalog(reset) {
  if (reset) {
    state.catalogOffset = 0;
    state.catalogItems = [];
  }
  try {
    state.catalog = await api("/api/catalog/status");
    if (!state.catalog.ready) return;
    const params = new URLSearchParams({
      books: state.catalogBook,
      q: state.catalogQ,
      offset: String(state.catalogOffset),
    });
    const data = await api(`/api/feed?${params}`);
    state.catalogItems = reset ? data.items : state.catalogItems.concat(data.items);
    state.catalogOffset += data.items.length;
    state.catalog.total = data.total;
  } catch (error) {
    state.catalog = { ready: false, hint: error.message };
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

function speakButton(text) {
  const wrap = document.createElement("div");
  wrap.className = "row";
  const button = document.createElement("button");
  button.type = "button";
  button.className = "speak";
  button.textContent = "朗读";
  button.addEventListener("click", () => speak(text));
  const tag = document.createElement("p");
  tag.className = "audio-tag";
  tag.textContent = "系统朗读";
  wrap.append(button, tag);
  return wrap;
}

function continueLesson() {
  const step = progress()?.step || "vocab";
  if (step === "listen") go("reading");
  else if (step === "talk") go("talk");
  else if (step === "recap") go("today");
  else if (step === "done") go("progress");
  else go("vocab");
}

function renderToday() {
  const root = document.createDocumentFragment();
  const due = state.due || [];
  if (due.length) {
    const card = state.flipped ? due[0] : due[0];
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
        button.addEventListener("click", async () => {
          await api(`/api/review/cards/${due[0].expression_id}/result`, {
            method: "POST",
            body: JSON.stringify({ result: id }),
          });
          state.flipped = false;
          await loadCore();
        });
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
    root.append(panel);
  }
  const lesson = document.createElement("section");
  lesson.className = "card";
  const kicker = document.createElement("p");
  kicker.className = "kicker";
  kicker.textContent = `${state.today.level} · 第一课`;
  const title = document.createElement("h1");
  title.textContent = state.today.title_zh;
  const source = document.createElement("p");
  source.className = "audio-tag";
  source.textContent = state.lesson?.source_note || "原创种子课。朗读为系统朗读。";
  const action = document.createElement("button");
  action.type = "button";
  action.className = "primary";
  action.textContent = state.today.action;
  action.addEventListener("click", continueLesson);
  lesson.append(kicker, title, source, action);
  root.append(lesson);
  if (progress()?.step === "recap" || progress()?.step === "done") root.append(renderRecap());
  return root;
}

function renderRecap() {
  const panel = document.createElement("section");
  panel.className = "card";
  panel.innerHTML = `<p class="kicker">复盘</p><h2>把一句加入复习</h2>`;
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
  const done = document.createElement("button");
  done.type = "button";
  done.className = "primary";
  done.textContent = progress()?.step === "done" ? "这一课已经完成" : "完成本课";
  done.disabled = progress()?.step === "done";
  done.addEventListener("click", async () => {
    await saveProgress({ step: "done" });
    go("progress");
  });
  panel.append(list, done);
  return panel;
}

function renderVocab() {
  const root = document.createDocumentFragment();
  const tabs = document.createElement("div");
  tabs.className = "row";
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
  const items = state.lesson.expressions;
  const index = Math.min(progress()?.vocab_index || 0, items.length - 1);
  const item = items[index];
  const card = document.createElement("section");
  card.className = "card";
  card.innerHTML = `<p class="kicker">词汇 ${index + 1}/${items.length}</p>`;
  const english = document.createElement("p");
  english.className = "english";
  english.textContent = item.english;
  const zh = document.createElement("p");
  zh.className = "zh can-hide";
  zh.textContent = item.chinese;
  card.append(english, zh, speakButton(item.english));
  const next = document.createElement("button");
  next.type = "button";
  next.className = "primary";
  next.textContent = index + 1 >= items.length ? "去听读" : "下一个";
  next.addEventListener("click", async () => {
    if (index + 1 >= items.length) {
      await saveProgress({ step: "listen", vocab_index: index });
      go("reading");
    } else {
      await saveProgress({ step: "vocab", vocab_index: index + 1 });
      render();
    }
  });
  card.append(next);
  root.append(card);
  return root;
}

function renderLibrary() {
  const panel = document.createElement("section");
  panel.className = "card";
  if (!state.catalog) return banner("loading", "正在打开词句库…");
  if (!state.catalog.ready) {
    const empty = banner("empty", state.catalog.hint || "还没有词库。");
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

function renderReading() {
  const root = document.createDocumentFragment();
  const card = document.createElement("section");
  card.className = "card";
  card.innerHTML = `<p class="kicker">听读</p><h1>短对话</h1>`;
  state.lesson.dialogue.forEach((line) => {
    const block = document.createElement("div");
    block.className = "script";
    const who = document.createElement("p");
    who.className = "kicker";
    who.textContent = line.speaker_zh;
    const en = document.createElement("p");
    en.className = "english";
    en.style.fontSize = "1.25rem";
    en.textContent = line.english;
    const zh = document.createElement("p");
    zh.className = "zh can-hide";
    zh.textContent = line.chinese;
    block.append(who, en, zh, speakButton(line.english));
    card.append(block);
  });
  root.append(card);
  const quiz = document.createElement("section");
  quiz.className = "card";
  quiz.innerHTML = `<p class="kicker">理解题</p>`;
  const results = { ...(progress()?.question_results || {}) };
  state.lesson.questions.forEach((question) => {
    const wrap = document.createElement("div");
    const prompt = document.createElement("h2");
    prompt.textContent = question.prompt_en;
    const zh = document.createElement("p");
    zh.className = "zh can-hide";
    zh.textContent = question.prompt_zh;
    wrap.append(prompt, zh);
    question.options.forEach((option) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "choice";
      const saved = results[question.id];
      if (saved?.choice === option.id) {
        button.classList.add(saved.correct ? "ok" : "bad", "is-on");
      }
      button.replaceChildren();
      const en = document.createElement("span");
      en.textContent = option.en;
      button.append(en);
      if (option.zh) {
        const zhOpt = document.createElement("span");
        zhOpt.className = "zh can-hide";
        zhOpt.textContent = " · " + option.zh;
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
  const next = document.createElement("button");
  next.type = "button";
  next.className = "primary";
  next.textContent = "去对话";
  next.addEventListener("click", async () => {
    await saveProgress({ step: "talk" });
    go("talk");
  });
  quiz.append(next);
  root.append(quiz);
  return root;
}

function renderTalk() {
  const session = state.dialogue;
  const root = document.createDocumentFragment();
  const card = document.createElement("section");
  card.className = "card";
  const kicker = document.createElement("p");
  kicker.className = "kicker";
  kicker.textContent = session?.mode_zh || "脚本练习";
  const title = document.createElement("h1");
  title.textContent = "点一杯咖啡";
  const note = document.createElement("p");
  note.className = "audio-tag";
  note.textContent = "这一步是脚本练习，还不是语音，也不是 AI 对话。";
  card.append(kicker, title, note);
  (state.lesson.dialogue || []).forEach((line) => {
    const block = document.createElement("div");
    block.className = "script";
    const who = document.createElement("p");
    who.className = "kicker";
    who.textContent = line.speaker_zh;
    const en = document.createElement("p");
    en.className = "english";
    en.style.fontSize = "1.2rem";
    en.textContent = line.english;
    const zh = document.createElement("p");
    zh.className = "zh can-hide";
    zh.textContent = line.chinese;
    block.append(who, en, zh);
    card.append(block);
  });
  const area = document.createElement("textarea");
  area.placeholder = "用英文写出你的点单，例如 I would like a cup of coffee, please.";
  area.value = session?.order_text || "";
  const hint = document.createElement("button");
  hint.type = "button";
  hint.className = "ghost";
  hint.textContent = "看提示";
  hint.addEventListener("click", async () => {
    state.dialogue = await api(`/api/dialogue/${state.lesson.id}/hint`, { method: "POST" });
    render();
  });
  if (session?.hint) {
    const box = document.createElement("p");
    box.className = "zh";
    box.textContent = `提示：${session.hint.english} / ${session.hint.chinese}`;
    card.append(box);
  }
  const submit = document.createElement("button");
  submit.type = "button";
  submit.className = "primary";
  submit.textContent = "提交订单";
  submit.addEventListener("click", async () => {
    try {
      state.dialogue = await api(`/api/dialogue/${state.lesson.id}/order`, {
        method: "POST",
        body: JSON.stringify({ text: area.value }),
      });
      const done = {};
      state.dialogue.goals.forEach((goal) => {
        done[goal.id] = goal.done;
      });
      await saveProgress({ step: "talk", task_results: done });
      render();
    } catch (error) {
      setError(error.message);
    }
  });
  const goals = document.createElement("ul");
  goals.className = "list";
  (session?.goals || []).forEach((goal) => {
    const item = document.createElement("li");
    item.className = "goal" + (goal.done ? " done" : "");
    item.textContent = (goal.done ? "已完成 · " : "未完成 · ") + goal.label_zh;
    goals.append(item);
  });
  const recap = document.createElement("button");
  recap.type = "button";
  recap.className = "ghost";
  recap.textContent = "去复盘";
  recap.addEventListener("click", async () => {
    await saveProgress({ step: "recap" });
    go("today");
  });
  card.append(area, hint, submit, goals, recap);
  root.append(card);
  return root;
}

function renderProgress() {
  const data = state.overview;
  if (!data) return banner("empty", "进度还没加载出来。");
  const root = document.createDocumentFragment();
  const summary = document.createElement("section");
  summary.className = "card";
  summary.innerHTML = `<p class="kicker">进度</p><h1>半年路线</h1>
    <p>完成课程 ${data.completed_lessons.length} · 复习卡 ${data.card_count} · 到期 ${data.due_count}</p>`;
  root.append(summary);
  const done = document.createElement("section");
  done.className = "card";
  done.innerHTML = "<h2>已完成课程</h2>";
  if (!data.completed_lessons.length) done.append(banner("empty", "还没有完成的课。先把咖啡店点餐走完。"));
  else {
    const list = document.createElement("ul");
    list.className = "list";
    data.completed_lessons.forEach((item) => {
      const row = document.createElement("li");
      row.textContent = `${item.title_zh} · ${item.at}`;
      list.append(row);
    });
    done.append(list);
  }
  root.append(done);
  const log = document.createElement("section");
  log.className = "card";
  log.innerHTML = "<h2>复习记录</h2>";
  if (!data.review_log.length) log.append(banner("empty", "还没有复习记录。"));
  else {
    const list = document.createElement("ul");
    list.className = "list";
    data.review_log.forEach((item) => {
      const row = document.createElement("li");
      const names = { forgot: "忘了", fuzzy: "模糊", remembered: "记得" };
      row.textContent = `${item.english} · ${names[item.result] || item.result} · 下次 ${item.due_at}`;
      list.append(row);
    });
    log.append(list);
  }
  root.append(log);
  const map = document.createElement("section");
  map.className = "card";
  map.innerHTML = "<h2>半年路线图</h2>";
  const list = document.createElement("ul");
  list.className = "list roadmap";
  data.roadmap.forEach((item) => {
    const row = document.createElement("li");
    row.innerHTML = `第 ${item.month} 月 ${item.title_zh} <span>${item.label}</span>`;
    list.append(row);
  });
  map.append(list);
  root.append(map);
  return root;
}

function render() {
  const route = pageId();
  state.page = route.page;
  state.library = route.page === "vocab" ? state.library : false;
  const active = document.activeElement;
  const keepSearch = active && active.classList.contains("search");
  const cursor = keepSearch ? active.selectionStart : null;
  paintNav();
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
  if (route.library) state.library = true;
  loadCore();
});

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/static/sw.js").catch(() => {});
}

state.page = pageId().page;
loadCore();
