# SherpaNote v2.2.0 修改记录

> **基线提交**：`2cec805` — feat(docs): 更新文档以反映v2.1.1版本的架构重构、安全性修复和可靠性改进（2026-05-08）
> **首次提交**：`c656e01` — chore(init): v2.2.0 版本初始化与文档结构整理（2026-05-09 → 2026-06-26）
> **记录日期**：2026-06-26
> **当前分支**：`dev-2.2.0`

---

## 一、概述

自 v2.1.1 发布（提交 `2cec805`）以来，启动了 v2.2.0 开发周期。本阶段主要完成版本号升级、开发环境配置调整、文档结构整理，并为 v2.2.0 引入参考资料目录。尚未涉及功能性代码变更。

---

## 二、变更详情

### 0. 修复 Bilibili 视频下载 412 报错（yt-dlp）

**问题**：从 B 站 URL 下载音频时报 `HTTP Error 412: Precondition Failed`，导致下载转录功能不可用。

**根因**：B 站对其 WBI 签名的 playurl 接口（`api.bilibili.com/x/player/wbi/playurl`）加了风控——当请求缺少特定 cookie（未登录态）时返回 412。yt-dlp 内置的 Bilibili 提取器在未提供登录 cookie 时会命中此风控；旧版 yt-dlp（2026.3.17）甚至在网页抓取阶段就被拦截。

**修复**：
1. 升级 yt-dlp `2026.3.17` → `2026.6.9`（新版改进了网页阶段的请求，能通过网页抓取）。
2. 在 `py/video_downloader.py` 导入时对 yt-dlp 的 `BilibiliBaseIE._download_playinfo` 打补丁，将播放地址请求从风控接口 `/x/player/wbi/playurl` 改写为 legacy 接口 `/x/player/playurl`（后者未启用 412 风控校验）。补丁幂等、带防御性跳过，未来 yt-dlp 上游修复或移除该方法时自动失效。

**验证**：用测试视频 `BV14p7G6dEBZ` 端到端验证——元数据获取、音频下载（26.99MiB）、MP3 提取（37.5MB）、进度回调均正常，临时文件已清理。

| 文件 | 变更 |
|------|------|
| `pyproject.toml` | `yt-dlp==2026.3.17` → `yt-dlp==2026.6.9` |
| `py/video_downloader.py` | 新增 `_apply_bilibili_playurl_patch()`，导入时自动应用 |

> **注意**：此补丁为针对 B 站风控的临时 workaround。若 yt-dlp 后续版本上游修复了该问题，可在升级版本后移除补丁；补丁逻辑本身对已修复版本无副作用（legacy 端点始终可用）。

### 1. 版本号升级（2.1.0 → 2.2.0）

统一升级前后端版本号至 `2.2.0`，标志新开发周期正式启动。

| 文件 | 变更 |
|------|------|
| `pyproject.toml` | `version = "2.1.0"` → `2.2.0` |
| `frontend/package.json` | `"version": "2.1.0"` → `"2.2.0"` |

### 2. Vite 开发服务器端口调整（5173 → 5200）

将前端开发服务器默认端口由 `5173` 改为 `5200`，避免与其他常用服务端口冲突。涉及配置与提示文案的同步更新。

| 文件 | 行号 | 变更 |
|------|------|------|
| `frontend/vite.config.ts` | `server.port` | `5173` → `5200` |
| `pywebvue/app.py` | `App.__init__` 参数 `dev_url` 默认值 | `http://localhost:5173` → `http://localhost:5200` |
| `dev.py` | 注释及 `_start_vite` 提示文案 | `:5173` → `:5200`（含模块 docstring 与运行时日志） |

> **注意**：`dev.py` 中的 CLAUDE.md 仍记载端口为 `5173`，如需保持一致，后续应同步更新 CLAUDE.md 中的相关命令说明。

### 3. 文档结构整理

#### 3.1 删除过时文档

清理 v2.1.x 周期遗留的冗余文档，统一归并至 `docs/archived/` 与版本化目录。

| 已删除文件 | 说明 |
|------------|------|
| `docs/PRD-2.1.0.md` | v2.1.0 OCR 升级 PRD（已归档至 `docs/2.0.0/PRD-2.1.0.md`） |
| `docs/PRD.md` | 通用 PRD（内容已整合到版本化文档体系） |
| `docs/review-2.1.0.md` | v2.1.0 代码审计报告（已归档至 `docs/2.0.0/`） |

#### 3.2 新增参考资料目录 `reference/`

引入独立的参考资料目录，存放外部参考实现与 PRD 草案，与项目自有文档隔离。

| 新增文件 | 说明 |
|----------|------|
| `reference/Reference-2.2.0.md` | v2.2.0 参考资料 |
| `reference/Reference-2.2.0-PRD.md` | v2.2.0 PRD 参考草案 |

#### 3.3 新增会话恢复与项目文档

| 新增文件 | 说明 |
|----------|------|
| `docs/Resume.md` | 开发会话恢复文档，用于跨会话上下文延续 |

### 4. 工具配置（未纳入版本控制）

以下为开发工具相关变更，属本地工作区状态，**不视为产品代码变更**：

| 路径 | 说明 |
|------|------|
| `.reasonix/` | Reasonix 工具本地配置目录（新增） |
| `.claude/SKILLS/resume-project-doc/` | 会话恢复相关 Skill 定义（新增） |

---

## 三、变更统计

```
 dev.py                  |   4 +-
 docs/PRD-2.1.0.md       | 307 ------------------------------------------
 docs/PRD.md             | 248 ----------------------------------
 docs/review-2.1.0.md    | 350 ------------------------------------------------
 frontend/package.json   |   2 +-
 frontend/vite.config.ts |   2 +-
 pyproject.toml          |   2 +-
 pywebvue/app.py         |   2 +-
 8 files changed, 6 insertions(+), 911 deletions(-)
```

**已跟踪文件**：8 个（4 修改 + 3 删除，另含 2 个新文件待加入版本控制）
**代码净变化**：+6 / -911（主要为文档删除）

---

## 四、未完成事项与后续计划

1. **CLAUDE.md 端口同步**：CLAUDE.md 中仍多处记载 Vite 端口为 `5173`，需同步更新为 `5200`。
2. **v2.2.0 功能开发**：本阶段仅完成版本元数据与开发环境配置，v2.2.0 的功能性需求尚未开始实现，待 `reference/Reference-2.2.0-PRD.md` 评审确定后启动。
3. **文档纳入版本控制**：`docs/Resume.md`、`reference/Reference-2.2.0*.md` 当前为未跟踪状态，待确认是否提交。
