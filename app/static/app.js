const NAMES = { travel: "旅行", business: "商务", reading: "阅读" };
const state = { books: new Set(["travel"]), q: "", offset: 0, total: 0 };
let requestId = 0;
let loading = false;
let userMoved = false;

const summary = document.querySelector("#summary");
const list = document.querySelector("#list");
const status = document.querySelector("#status");
const hint = document.querySelector("#more-hint");
const search = document.querySelector("#q");
const hideButton = document.querySelector("#hide-zh");

function setStatus(message) {
  status.hidden = !message;
  status.textContent = message || "";
}

function bookQuery() {
  return [...state.books].join(",");
}

function endpoint() {
  const params = new URLSearchParams({
    books: bookQuery(),
    q: state.q,
    offset: String(state.offset),
  });
  return `/api/feed?${params}`;
}

function renderItem(item) {
  const entry = document.createElement("li");
  entry.className = "entry";
  const english = document.createElement("p");
  english.className = "english";
  english.textContent = item.english;
  const speak = document.createElement("button");
  speak.type = "button";
  speak.className = "speak";
  speak.textContent = "听";
  speak.setAttribute("aria-label", `朗读 ${item.english}`);
  speak.addEventListener("click", () => speakEnglish(item.english));
  const meta = document.createElement("p");
  meta.className = "meta";
  if (item.kind === "word") {
    const bits = [];
    if (item.phonetic) bits.push(item.phonetic);
    if (item.pos) bits.push(item.pos);
    meta.textContent = bits.join("  ");
    meta.hidden = bits.length === 0;
  } else {
    meta.hidden = true;
  }
  const chinese = document.createElement("p");
  chinese.className = "zh";
  chinese.textContent = item.chinese;
  entry.append(english, speak, meta, chinese);
  return entry;
}

function paintBooks() {
  document.querySelectorAll(".book").forEach((button) => {
    const on = state.books.has(button.dataset.book);
    button.classList.toggle("is-on", on);
    button.setAttribute("aria-pressed", on ? "true" : "false");
  });
  const label = [...state.books].map((id) => NAMES[id]).join(" + ");
  summary.textContent = state.total
    ? `${label} · ${state.total} 条，一次 7 条`
    : label;
}

async function loadPage(reset) {
  if (loading) return;
  const current = ++requestId;
  loading = true;
  if (reset) {
    state.offset = 0;
    userMoved = false;
    list.replaceChildren();
  }
  setStatus("");
  hint.hidden = true;
  let response;
  try {
    response = await fetch(endpoint());
  } catch {
    if (current === requestId) setStatus("页面连不上这台电脑上的服务。");
    loading = false;
    return;
  }
  if (current !== requestId) {
    loading = false;
    return;
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    setStatus(body.detail || "词库读取失败。");
    loading = false;
    return;
  }
  const data = await response.json();
  state.total = data.total;
  for (const item of data.items) list.append(renderItem(item));
  state.offset += data.items.length;
  hint.hidden = state.offset >= data.total;
  if (!data.total) setStatus(state.q ? "没有找到。" : "这本词书还是空的。");
  paintBooks();
  loading = false;
}

function maybeMore() {
  if (!userMoved || loading || state.offset >= state.total) return;
  const gap = document.documentElement.scrollHeight - window.scrollY - window.innerHeight;
  const shortPage = document.documentElement.scrollHeight <= window.innerHeight + 4;
  if (gap < 160 || shortPage) loadPage(false);
}

function speakEnglish(text) {
  if (!window.speechSynthesis) {
    setStatus("这台设备没有朗读。");
    return;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-US";
  utterance.rate = 0.82;
  window.speechSynthesis.speak(utterance);
}

document.querySelectorAll(".book").forEach((button) => {
  button.addEventListener("click", () => {
    const id = button.dataset.book;
    if (state.books.has(id)) {
      if (state.books.size === 1) return;
      state.books.delete(id);
    } else {
      state.books.add(id);
    }
    paintBooks();
    loadPage(true);
  });
});

let searchTimer = 0;
search.addEventListener("input", () => {
  state.q = search.value;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadPage(true), 180);
});

window.addEventListener("scroll", () => {
  if (window.scrollY > 8) userMoved = true;
  maybeMore();
}, { passive: true });

window.addEventListener("wheel", (event) => {
  if (event.deltaY > 0) {
    userMoved = true;
    maybeMore();
  }
}, { passive: true });

window.addEventListener("touchmove", () => {
  userMoved = true;
  maybeMore();
}, { passive: true });

hideButton.addEventListener("click", () => {
  const hidden = document.body.classList.toggle("hide-zh");
  hideButton.setAttribute("aria-pressed", hidden ? "true" : "false");
  hideButton.textContent = hidden ? "显示中文" : "盖住中文";
});

list.addEventListener("click", (event) => {
  const line = event.target.closest(".zh");
  if (line && document.body.classList.contains("hide-zh")) line.classList.toggle("shown");
});

loadPage(true);
