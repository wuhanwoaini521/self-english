# Pixel Book Deck Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有学习界面改为像素粒子背景与有景深的书本堆叠卡片，并为词汇和阅读提供手机滑动、PC 按钮与键盘翻页。

**Architecture:** 沿用单页原生 JavaScript 渲染，扩展现有 `cardDeck` 作为唯一翻页组件；阅读文章每次渲染一个段落，理解题独立于段落分页。CSS 负责静态像素背景、纸张层叠和响应式景深，不新增运行时依赖。

**Tech Stack:** HTML、CSS、原生 JavaScript、Python unittest、Playwright 1.62、FastAPI 现有测试服务。

**Spec:** `docs/superpowers/specs/2026-11-27-pixel-book-deck-design.md`

## Global Constraints

- 不迁移框架，不引入 Canvas 动画、3D 引擎或新依赖。
- 不修改后端 API、课程内容、学习数据库、复习排期或评分规则。
- 翻页只改变当前页展示，不自动标会、不自动评分、不自动完成课程。
- 手机也保留翻页按钮；PC 保留按钮和左右方向键。
- 顶层正文始终清晰，尊重 `prefers-reduced-motion`，不依赖悬停，不产生横向页面滚动。
- 保留工作区已有修改，只提交当前任务所需文件；未经用户明确要求不创建 git commit。

## Review Focus

- 垂直手势必须继续滚动页面，不能误翻页：Task 1 的手机垂直滑动测试。
- 点词、朗读、输入和按钮不能被 deck 的滑动手势截获：Task 1 的点词与朗读不翻页测试。
- 首页和末页不能越界，重复点击 / 滑动不能跳过页：Task 1 的边界与页码测试。
- 阅读分页不能隐藏理解题、完成阅读和跨端学习记录：Task 1 保留并完成现有阅读流程测试。
- 粒子、景深和过渡不能造成横向溢出或妨碍减少动态效果用户：Task 2 的桌面 / 手机溢出与 reduced-motion 检查。

---

### Task 1: 统一词汇与阅读的书本翻页

**Files:**
- Modify: `app/static/app.js:9-38`（阅读页面临时状态）
- Modify: `app/static/app.js:1024-1085`（通用 `cardDeck`）
- Modify: `app/static/app.js:1668-1784`（阅读文章逐段渲染）
- Test: `tests/browser_learning.py:32-64`

**Interfaces:**
- Consumes: 现有 `renderTeachCard(item, index, total)`、`renderAnnotated(english, marks, className)`、`speakButton(text)`、`saveProgress(patch)`。
- Produces: `cardDeck(card, index, total, changePage, label)` 保持现有签名，供词汇和阅读共用；`state.readingIndex: number` 与 `state.readingArticleId: string` 仅保存当前前端文章页码；每个阅读 `.study-deck` 的 aria-label 包含 `阅读，第 N 页，共 M 页`。

- [ ] **Step 1: 写失败的浏览器翻页测试**

在 `exercise` 打开第一篇文章后，将原先 `.passage-block` 数量为 3 的断言改为分页行为：
- 初始只有 1 个 `.passage-card .passage-block` 和 1 个阅读 `.study-deck`。
- 记录第一段英文；点击 `.study-deck .deck-arrow.next` 后英文改变，aria-label 为第 2/3 页，再点击“上一页”恢复第一段。
- 第一段“上一页”禁用；到第三段后“下一页”禁用，连续点击不能产生第 4 页。
- 在 deck 获得焦点时按 `ArrowRight` / `ArrowLeft`，与按钮行为一致。
- 手机在阅读 deck 上派发 primary touch pointer 的水平 swipe（`dx=-120, dy=0`）后进入第 2 页；垂直 swipe（`dx=0, dy=120`）不改变页码。
- 点击当前页 `.speak` 与 `.mark` 不改变页码，点词弹层和“会”仍按原流程工作。

- [ ] **Step 2: 运行测试并确认因阅读尚未分页而失败**

Run: `uv run --with playwright==1.62 python -m tests.browser_learning`
Expected: FAIL；初始 `.passage-block` 为 3，或找不到阅读 `.study-deck`。若测试被当前工作区已有错误阻断，记录实际错误，不把它写成分页测试通过。

- [ ] **Step 3: 实现阅读页码状态和逐段渲染**

在 `state` 添加 `readingIndex: 0`、`readingArticleId: ""`。`renderReadingArticle(article)` 在文章 ID 改变时归零，将索引夹到 `0..paragraphs.length-1`；创建含返回、标题、帮助和当前 `.passage-block` 的 `.passage-card`，交给 `cardDeck`。`changePage(next)` 只更新 `readingIndex` 并 `render()`。空段落文章保留明确空状态，不构造 `total=0` 的可翻页 deck。理解题和完成按钮继续作为 deck 之后的独立内容。

- [ ] **Step 4: 收紧通用 deck 的交互而不改变学习提交**

保留现有点按钮、键盘和 pointer 判断；确保每次渲染从闭包中的固定 `index` 计算目标页，`busy` 期间忽略重复移动，边界按钮禁用。水平手势阈值保持 42px 且横向位移至少为纵向 1.5 倍；interactive 控件、文字选择和取消的 pointer 不触发翻页。不要为“翻开看中文”或“会 / 不会”绑定滑动手势。

- [ ] **Step 5: 运行分页与原有学习流程测试**

Run: `uv run --with playwright==1.62 python -m tests.browser_learning`
Expected: PASS，包括点词标会、手机同步、词句库筛选 / 搜索 / 分页、对话、理解题和“读完了”。

### Task 2: 像素粒子背景与书本景深视觉

**Files:**
- Modify: `app/static/app.css:1-56`（色板、静态像素粒子背景）
- Modify: `app/static/app.css:329-334`、`698-735`、`784-830`（统一纸张、控件与步骤导航）
- Modify: `app/static/app.css:1362-1578`（响应式书本堆叠、景深和 reduced-motion）
- Modify: `app/static/index.html:6,14,34`（主题色与静态资源版本）
- Modify: `app/static/manifest.webmanifest:5-7`（与页面一致的背景 / 主题色）
- Test: `tests/browser_learning.py`

**Interfaces:**
- Consumes: Task 1 的 `.study-deck > .card`、`.deck-arrow.prev/.next`、`.passage-card`、`.script`、`.teach-block`。
- Produces: 全站 CSS 色板与纸张层级；`.study-deck::before/::after` 为无交互的装饰后层；`.study-deck > .card` 为始终清晰的顶层；`.book-page` 不作为必需接口，避免额外 DOM 包装。

- [ ] **Step 1: 写失败的视觉与可访问性断言**

在桌面和手机浏览器回归中加入：
- `body` 的计算 `backgroundImage` 含 `linear-gradient`，`body::before` 或 `::after` 有非 `none` 的像素层。
- `.study-deck::before` 和 `::after` 的 `transform` 均非 `none`，顶层卡片 `boxShadow` 非 `none`，顶层 `filter` 为 `none`。
- 两个 `.deck-arrow` 在手机仍可见，命中区域至少 44×44px；PC 翻页按钮同样存在。
- 词汇、阅读、对话、进度和今天页面均满足 `document.documentElement.scrollWidth <= innerWidth`。
- `page.emulate_media(reduced_motion="reduce")` 后，装饰层无动画 / 过渡，且按钮翻页仍有效。

- [ ] **Step 2: 运行测试并确认旧视觉断言失败**

Run: `uv run --with playwright==1.62 python -m tests.browser_learning`
Expected: Task 1 行为保持通过，新增顶层景深 / 像素层等视觉断言至少一项失败。

- [ ] **Step 3: 实现静态右下至左上像素粒子渐变**

用 `body` 多层 `linear-gradient` 建立从右下到左上的明度 / 色彩变化，用固定定位伪元素和平铺小方形渐变建立不同密度的像素粒子。粒子层 `pointer-events: none`，内容层保持更高 z-index；不使用持续动画。导航与底部栏采用足够不透明的背景，保证文字对比度。

- [ ] **Step 4: 实现书本堆叠和景深**

用 `.study-deck::before/::after` 形成两层错位、缩放的后页，顶层卡片加柔和多层投影；装饰层可降低对比度，但不得模糊顶层正文。桌面增强层间距，手机缩小错位并保留 44px 翻页命中区。让 `.script`、`.teach-block`、`.passage-block` 使用一致的纸张边缘 / 书页线风格，不给每句额外创建会干扰阅读的全尺寸 deck。

- [ ] **Step 5: 完成响应式与减少动态效果样式**

为通用过渡添加 `@media (prefers-reduced-motion: reduce)` 覆盖；检查长词、长段、中文开关、评分按钮和底部导航。更新 `index.html` 静态资源查询版本及主题色，并同步 manifest，避免旧 CSS 缓存与浏览器主题色不一致。

- [ ] **Step 6: 运行完整针对性验证**

Run: `node --check app/static/app.js`
Expected: PASS，无 JavaScript 语法错误。

Run: `uv run python -m unittest tests.test_learning tests.test_ai -v`
Expected: 全部 PASS；若有失败，报告实际失败，不以视觉改动为由跳过。

Run: `uv run --with playwright==1.62 python -m tests.browser_learning`
Expected: 全部 PASS，桌面与 393×852 手机视口无横向溢出，按钮 / 键盘 / 手机滑动翻页及原学习流程通过。

- [ ] **Step 7: 人工检查浏览器截图并记录边界**

分别截取桌面词汇、手机词汇、桌面阅读、手机阅读，确认像素方向、书页层次、正文清晰和按钮可达。说明这是浏览器视口验证，不声称真机验证；若无法截图或检查，明确列为未验证事项。
