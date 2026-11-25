# self-english

一人用的英语学习应用。电脑跑服务，手机和平板用浏览器打开同一套页面。第一个月是三课原创 A1：咖啡店点餐、问候、请对方再说一次。

五个页面：今天、词汇、阅读、对话、进度。桌面左侧导航，手机底部导航。进度页用图表看半年路线、本月课程、复习格子和评分，时间按本地日期显示。

## 启动

词库不是课程的前置条件。没有 `data/app.db` 时，首页和第一个月三课仍可学；词句库会提示如何构建。

```powershell
git clone https://github.com/wuhanwoaini521/self-english.git
cd self-english
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

这台电脑打开 http://127.0.0.1:8000 。同一局域网的手机用这台电脑的地址，端口 8000。若手机打不开，在 Windows 防火墙里允许 Python 访问专用网络。

可选：下载公开词表并生成词句库（不影响学习进度）。家里电脑会收录 CEFR-J 的 A1–B1 词，以及最多约 4000 条短句：

```powershell
uv run python scripts\download_sources.py
uv run python scripts\build_catalog.py
```

## 数据

- `data/app.db`：可重建的词句目录。`scripts/build_catalog.py` 会删掉再生成它。
- `data/learning.db`：课程进度、复习卡、对话记录。不进 git。重建词库不会改这份文件。
- `data/raw/`：下载的词典和句对，不进 git。

来源和许可见 `data/SOURCES.txt`。咖啡店点餐是原创种子，朗读标为「系统朗读」。

## 第一课怎么走

今天开始 → 词汇先看完整词卡（音标、意思、怎么记、例句），认完后再翻卡回忆并评分 → 听读对话和两道理解题 → 对话里用英文提交点单 → 复盘确认复习卡 → 完成本课。每一步顶部可以返回已走过的词汇 / 听读 / 对话 / 复盘。没有每天上限，第一课完成后首页会立刻接着「问候」和「请对方再说一次」，同一天可以连续学。已完成的课可以在首页点回去看。词汇评分会直接进入复习。词句库随时可以多看。

复习规则：先看英文，翻开后再选忘了（盒子回到 1，1 天后）、模糊（盒子不变，2 天后）、记得（盒子加 1，最高 4；下次分别等 3 / 7 / 14 天，满级仍是 14 天）。同一表达重复加入只会有一张卡。

## 检查

```powershell
uv run python -m unittest tests.test_learning -v
```
