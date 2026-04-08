# SherpaNote (雪豹笔记) 项目计划与详细设计

## 文档信息

| 项目 | 内容 |
|------|------|
| 产品名称 | SherpaNote（雪豹笔记） |
| 文档版本 | V1.0 |
| 制定日期 | 2026-04-07 |
| 技术栈 | PyWebVue (Vue 3 + pywebview) + DaisyUI 5 + Tailwind CSS 4 + sherpa-onnx + LLM |

---

## 一、项目现状分析

### 1.1 已有基础设施

项目已有完整的 PyWebVue 框架骨架，可直接在其上构建业务逻辑：

| 组件 | 文件 | 状态 | 说明 |
|------|------|------|------|
| 框架核心 | `pywebvue/` | 已完成 | Bridge 基类、App 类、@expose 装饰器 |
| 前端入口 | `frontend/src/main.ts` | 已完成 | Vue 3 启动 |
| Bridge 通信 | `frontend/src/bridge.ts` | 已完成 | call()、onEvent()、waitForPyWebView() |
| 构建系统 | `build.py` + `app.spec` | 已完成 | PyInstaller 打包（onedir/onefile/Android） |
| 开发脚本 | `dev.py` | 已完成 | 一键启动 Vite + App |
| Demo 应用 | `main.py` | 需替换 | 当前为 DemoApi，需替换为 SherpaNoteAPI |
| Demo 前端 | `frontend/src/App.vue` | 需替换 | 当前为 Demo UI，需替换为 SherpaNote UI |
| 设计系统 | `reference/DESIGN.md` | 已完成 | Notion 风格 DaisyUI 5 主题规范 |
| 需求文档 | `reference/Reference.md` | 已完成 | 完整 PRD |

### 1.2 待建设部分

```
py/                    # Python 业务逻辑（全部待建）
  asr.py              # sherpa-onnx 语音识别封装
  llm.py              # AI 大模型调用封装
  storage.py          # 数据持久化（SQLite + JSON）
  io.py               # 文件读写工具
  config.py           # 配置管理

frontend/src/         # Vue 前端（全部待建）
  views/              # 页面视图
    HomeView.vue      # 首页 - 稿件列表
    RecordView.vue    # 录音转写页
    EditorView.vue    # 逐字稿编辑页
  components/         # 可复用组件
    AudioRecorder.vue # 音频采集组件
    TranscriptPanel.vue # 转写文本面板
    AiProcessor.vue   # AI 处理面板
    ExportMenu.vue    # 导出菜单
    RecordCard.vue    # 稿件卡片
    SearchBar.vue     # 搜索筛选栏
    VersionHistory.vue # 版本历史侧边栏
    ThemeToggle.vue   # 深色/浅色主题切换
  composables/        # Vue 组合式函数
    useRecording.ts   # 录音逻辑
    useTranscript.ts  # 转写逻辑
    useAiProcess.ts   # AI 处理逻辑
    useStorage.ts     # 数据存取逻辑
  stores/             # 状态管理
    appStore.ts       # 全局应用状态
  types/              # TypeScript 类型定义
    index.ts          # 共享类型
  styles/             # 样式
    main.css          # 主样式（DaisyUI 主题 + Tailwind）
  router/             # 路由
    index.ts          # Vue Router 配置
```

---

## 二、系统架构设计

### 2.1 整体架构

```
+---------------------------------------------------------------+
|                     pywebview 桌面窗口                          |
|  +---------------------------+  +---------------------------+  |
|  |     Vue 3 前端            |  |     Python 后端            |  |
|  |                           |  |                           |  |
|  |  Views (页面)             |  |  Bridge (@expose API)     |  |
|  |    HomeView               |  |    init_model()           |  |
|  |    RecordView             |  |    start_streaming()      |  |
|  |    EditorView             |  |    feed_audio()           |  |
|  |                           |  |    transcribe_file()      |  |
|  |  Components (UI组件)      |  |    process_text()         |  |
|  |    AudioRecorder          |  |    save_record()          |  |
|  |    TranscriptPanel        |  |    list_records()         |  |
|  |    AiProcessor            |  |    export_record()        |  |
|  |    ...                    |  |    ...                    |  |
|  |                           |  |                           |  |
|  |  Composables (逻辑)       |  |  Services (业务)          |  |
|  |    useRecording           |  |    SherpaASR              |  |
|  |    useTranscript          |  |    AIProcessor            |  |
|  |    useAiProcess           |  |    Storage                |  |
|  |                           |  |                           |  |
|  +---------------------------+  +---------------------------+  |
|          |         ^                    ^         |             |
|          | call<T> |                    | _emit   |             |
|          +-------->    pywebview API    <--------+             |
|          |         <-------------------->         |             |
|          +--------+    CustomEvent      +---------+             |
+---------------------------------------------------------------+
|                sherpa-onnx (本地 ASR 引擎)                      |
|                SQLite (本地数据存储)                             |
|                LLM API / Ollama (AI 处理)                      |
+---------------------------------------------------------------+
```

### 2.2 通信机制

```
前端 -> 后端（请求-响应）:
  call<T>(method, ...args) --> @expose method() --> {"success": true, "data": ...}

后端 -> 前端（事件推送）:
  self._emit(event, data) --> CustomEvent("pywebvue:{event}") --> onEvent<T>(handler)
```

**关键约束**: 不使用 WebSocket，所有通信通过 pywebview 的 JS API 注入实现。

---

## 三、数据结构设计

### 3.1 核心数据模型

```python
# Record (转写记录) - 核心数据实体
@dataclass(frozen=True)
class Record:
    """一条完整的转写记录，使用不可变设计。
    更新时创建新实例而非修改原对象。
    """
    id: str                  # UUID，主键
    title: str               # 稿件标题（默认 "未命名录音"）
    audio_path: str | None   # 原始音频文件路径（None 表示实时录音未保存）
    transcript: str          # 完整逐字稿文本
    segments: list[Segment]  # 带时间戳的分段列表
    ai_results: dict[str, str]  # AI 处理结果 {"polish": "...", "note": "...", ...}
    category: str            # 分类标签
    tags: list[str]          # 用户标签
    duration_seconds: float  # 音频时长
    created_at: str          # ISO 8601 创建时间
    updated_at: str          # ISO 8601 最后修改时间
    version: int             # 当前版本号


# Segment (文本分段) - 逐字稿的原子单位
@dataclass(frozen=True)
class Segment:
    """逐字稿中的一个分段，包含时间戳。
    用于音频定位和播放同步。
    """
    index: int               # 段序号（从 0 开始）
    text: str                # 该段的转写文本
    start_time: float        # 起始时间（秒）
    end_time: float          # 结束时间（秒）
    speaker: str | None      # 说话人标识（可选，如 "Speaker 0"）
    is_final: bool           # 是否为定稿（流式转写中，非定稿可能被修正）


# Version (版本快照)
@dataclass(frozen=True)
class Version:
    """稿件的一个历史版本，支持版本回溯。"""
    record_id: str           # 关联的记录 ID
    version: int             # 版本号
    transcript: str          # 该版本的逐字稿快照
    ai_results: dict[str, str]  # 该版本的 AI 结果快照
    created_at: str          # 版本创建时间


# AiConfig (AI 模型配置)
@dataclass(frozen=True)
class AiConfig:
    """AI 模型配置，支持多种后端。"""
    provider: str            # "openai" | "anthropic" | "ollama" | "qwen"
    model: str               # 模型名称（如 "gpt-4o-mini", "qwen2.5:7b"）
    api_key: str | None      # API 密钥（本地模型为 None）
    base_url: str | None     # 自定义 API 端点（可选）
    temperature: float       # 生成温度（0.0 - 2.0）
    max_tokens: int          # 最大生成 token 数


# AsrConfig (ASR 模型配置)
@dataclass(frozen=True)
class AsrConfig:
    """语音识别引擎配置。"""
    model_dir: str           # 模型文件目录
    language: str            # 语言代码（"zh", "en", "auto"）
    sample_rate: int         # 采样率（默认 16000）
    use_gpu: bool            # 是否使用 GPU
```

### 3.2 SQLite 数据库 Schema

```sql
-- 稿件记录主表
CREATE TABLE IF NOT EXISTS records (
    id              TEXT PRIMARY KEY,           -- UUID
    title           TEXT NOT NULL DEFAULT '未命名录音',
    audio_path      TEXT,                       -- 原始音频路径
    transcript      TEXT NOT NULL DEFAULT '',   -- 完整逐字稿
    segments_json   TEXT NOT NULL DEFAULT '[]', -- 分段数据 JSON
    ai_results_json TEXT NOT NULL DEFAULT '{}', -- AI 结果 JSON
    category        TEXT NOT NULL DEFAULT '',   -- 分类
    tags_json       TEXT NOT NULL DEFAULT '[]', -- 标签 JSON
    duration_seconds REAL NOT NULL DEFAULT 0.0, -- 时长
    created_at      TEXT NOT NULL,              -- ISO 8601
    updated_at      TEXT NOT NULL               -- ISO 8601
);

-- 版本历史表
CREATE TABLE IF NOT EXISTS versions (
    record_id       TEXT NOT NULL,
    version         INTEGER NOT NULL,
    transcript      TEXT NOT NULL,
    ai_results_json TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL,
    PRIMARY KEY (record_id, version)
);

-- 应用配置表（KV 存储）
CREATE TABLE IF NOT EXISTS app_config (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);

-- 索引：按创建时间排序
CREATE INDEX IF NOT EXISTS idx_records_created ON records(created_at DESC);
-- 索引：按标题搜索
CREATE INDEX IF NOT EXISTS idx_records_title ON records(title);
-- 索引：全文搜索（使用 SQLite FTS5）
CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(
    title, transcript, content=records, content_rowid=rowid
);
```

---

## 四、详细模块设计

### 4.1 Phase 0: 项目基础设施搭建

**目标**: 建立 SherpaNote 的项目骨架，替换 Demo 代码。

#### 4.1.1 Python 依赖管理

更新 `pyproject.toml`，添加项目依赖（执行uv add添加依赖而非直接修改toml文件）：

```toml
[project]
name = "sherpanote"
version = "0.1.0"
description = "AI-powered voice learning assistant"
requires-python = ">=3.10"
dependencies = [
    "pywebview>=6.0",
    "sherpa-onnx>=1.10.0",    # 语音识别引擎
    "openai>=1.50.0",          # OpenAI/兼容 API 客户端
    "python-docx>=1.1.0",      # .docx 导出
]

[dependency-groups]
dev = [
    "pyinstaller>=6.19.0",
]
```

#### 4.1.2 前端依赖管理

更新 `frontend/package.json`，添加前端依赖：

```json
{
  "dependencies": {
    "vue": "^3.5.0",
    "vue-router": "^4.5.0",           // SPA 路由
    "pinia": "^2.3.0"                 // 状态管理
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.2.0",
    "typescript": "~5.7.0",
    "vite": "^6.0.0",
    "vue-tsc": "^2.2.0",
    "tailwindcss": "^4.0.0",           // Tailwind CSS 4
    "@tailwindcss/vite": "^4.0.0",     // Tailwind Vite 插件
    "daisyui": "^5.0.0"               // DaisyUI 5
  }
}
```

#### 4.1.3 DaisyUI 主题配置

创建 `frontend/src/styles/main.css`，配置 Notion 风格双主题：

```css
@import "tailwindcss";
@plugin "daisyui";

/* 浅色主题 */
@plugin "daisyui/theme" {
  name: "sherpanote-light";
  default: true;
  color-scheme: light;
  --color-base-100: #ffffff;
  --color-base-200: #f6f5f4;
  --color-base-300: #e8e7e6;
  --color-base-content: rgba(0,0,0,0.95);
  --color-primary: #0075de;
  --color-primary-content: #ffffff;
  --color-secondary: #213183;
  --color-secondary-content: #ffffff;
  --color-accent: #097fe8;
  --color-accent-content: #ffffff;
  --color-neutral: #31302e;
  --color-neutral-content: #ffffff;
  --color-info: #097fe8;
  --color-info-content: #ffffff;
  --color-success: #2a9d99;
  --color-success-content: #ffffff;
  --color-warning: #dd5b00;
  --color-warning-content: #ffffff;
  --color-error: #e53e3e;
  --color-error-content: #ffffff;
  --radius-selector: 9999px;
  --radius-field: 0.25rem;
  --radius-box: 0.75rem;
  --depth: 1;
}

/* 深色主题 */
@plugin "daisyui/theme" {
  name: "sherpanote-dark";
  prefersdark: true;
  color-scheme: dark;
  --color-base-100: #191919;
  --color-base-200: #1e1e1e;
  --color-base-300: #2a2a2a;
  --color-base-content: rgba(255,255,255,0.92);
  --color-primary: #4da3f0;
  --color-primary-content: #191919;
  --color-secondary: #6878c8;
  --color-secondary-content: #ffffff;
  --color-accent: #5aacf5;
  --color-accent-content: #191919;
  --color-neutral: #d4d3d1;
  --color-neutral-content: #191919;
  --color-info: #5aacf5;
  --color-info-content: #191919;
  --color-success: #3dbdb9;
  --color-success-content: #191919;
  --color-warning: #f07020;
  --color-warning-content: #191919;
  --color-error: #f56565;
  --color-error-content: #ffffff;
  --radius-selector: 9999px;
  --radius-field: 0.25rem;
  --radius-box: 0.75rem;
  --depth: 1;
}

/* NotionInter 字体（Inter 变体） */
@font-face {
  font-family: "NotionInter";
  src: local("Inter"), local("Inter-Regular");
}
```

#### 4.1.4 目录结构创建

创建所有业务目录（py/、views/、components/ 等），确保目录骨架完整。

---

### 4.2 Phase 1: Python 后端核心模块

**目标**: 实现所有 Python 业务逻辑，提供完整的 Bridge API。

#### 4.2.1 py/config.py - 配置管理

**功能**:
- 管理应用全局配置（数据目录、AI 配置、ASR 配置）
- 配置持久化到 SQLite app_config 表
- 提供默认配置和配置校验

**关键设计点**:
- 使用不可变 dataclass 作为配置载体
- 配置变更返回新实例（immutability 原则）
- 首次运行时创建默认配置

**Bridge API**:
```python
@expose
def get_config(self) -> dict:
    """获取当前配置"""

@expose
def update_config(self, config: dict) -> dict:
    """更新配置，返回新配置"""
```

#### 4.2.2 py/asr.py - sherpa-onnx 语音识别封装

**功能**:
- 封装 sherpa-onnx OnlineRecognizer（流式识别）和 OfflineRecognizer（文件转写）
- 管理模型加载/卸载生命周期
- 音频预处理（重采样到 16kHz 单声道 PCM）
- VAD（语音活动检测）静音切分
- 通过回调函数推送识别结果

**关键设计点**:
- 模型懒加载：首次使用时才加载模型，避免启动延迟
- 线程安全：流式识别运行在独立线程中，通过事件推送结果
- 音频格式转换：Web Audio API 输出 float32，需转为 sherpa-onnx 需要的 int16 PCM
- 资源管理：提供 cleanup() 方法释放模型内存

**核心类**:
```python
class SherpaASR:
    """sherpa-onnx 语音识别引擎封装。

    管理在线（流式）和离线（文件）两种识别模式。
    模型在首次使用时懒加载，通过 _emit 推送识别结果。
    """

    def __init__(self, config: AsrConfig) -> None: ...

    # --- 流式识别 ---
    def start_streaming(self) -> None:
        """初始化 OnlineRecognizer，准备接收音频流。"""

    def feed_audio(self, float32_samples: bytes) -> dict:
        """处理一段音频数据，返回中间/定稿结果。
        float32_samples: 前端传来的 16kHz 单声道 float32 PCM 字节流。
        返回: {"partial": "...", "final": "...", "timestamp": [...]}
        """

    def stop_streaming(self) -> dict:
        """结束流式识别，返回最终定稿结果。"""

    # --- 文件转写 ---
    def transcribe_file(self, path: str, on_progress: Callable) -> list[Segment]:
        """转写完整音频文件，通过 on_progress 回调推送进度。
        支持 mp3/wav/m4a/flac 等格式（通过 soundfile 或 ffmpeg 解码）。
        返回带时间戳的 Segment 列表。
        """

    # --- 资源管理 ---
    def cleanup(self) -> None:
        """释放模型资源，回收内存。"""
```

**Bridge API**:
```python
@expose
def init_model(self, language: str = "auto") -> dict:
    """初始化 ASR 模型。language: 'zh' | 'en' | 'auto'"""

@expose
def start_streaming(self) -> dict:
    """启动流式识别会话"""

@expose
def feed_audio(self, base64_data: str) -> dict:
    """接收 Base64 编码的音频数据，推送识别结果。
    注意: pywebview JS API 不直接支持 bytes 传输，
    因此前端将 float32 PCM 编码为 Base64 字符串传输。
    """

@expose
def stop_streaming(self) -> dict:
    """结束流式识别，返回最终文本"""

@expose
def transcribe_file(self, file_path: str) -> dict:
    """转写音频文件，通过 _emit("transcribe_progress") 推送进度"""
```

**技术难点**:
1. **音频数据传输**: pywebview JS API 不支持直接传输二进制数据。解决方案：前端将 PCM 音频编码为 Base64 字符串，后端解码后送入 sherpa-onnx。这会增加约 33% 的数据量，但保证兼容性。
2. **流式识别线程**: sherpa-onnx OnlineRecognizer.decode() 是阻塞调用。需要在独立线程中运行，通过 queue 接收音频数据，通过事件推送结果。
3. **模型文件管理**: sherpa-onnx 需要模型文件（通常 100MB+）。需要在首次使用时自动下载并缓存，或在安装时打包。

#### 4.2.3 py/llm.py - AI 大模型封装

**功能**:
- 统一封装多种 LLM 后端（OpenAI / Anthropic / Ollama / Qwen）
- 提供文本处理的四种模式：修订润色、课堂笔记、思维导图、脑洞点评
- 流式输出支持（SSE 风格，通过 _emit 推送）
- 错误重试和超时处理

**关键设计点**:
- 统一接口：无论使用哪个 LLM 后端，对外暴露相同的 process() 方法
- 使用 OpenAI Python SDK 作为统一客户端（兼容 OpenAI、Ollama、Qwen 等）
- 流式输出：使用 stream=True，逐 token 推送到前端
- Prompt 模板管理：每种处理模式对应一个精心设计的 prompt 模板

**核心类**:
```python
class AIProcessor:
    """AI 文本处理器，支持多种 LLM 后端。

    通过统一的 process() 接口处理文本，
    内部根据配置选择不同的 LLM 后端。
    支持流式输出，通过 _emit 逐 token 推送结果。
    """

    def __init__(self, config: AiConfig) -> None: ...

    def process(self, text: str, mode: str) -> str:
        """处理文本，mode: polish/note/mindmap/brainstorm。
        返回处理后的完整文本（非流式模式）。
        """

    def process_stream(self, text: str, mode: str) -> None:
        """流式处理文本，通过 _emit("ai_token") 逐 token 推送。
        完成时推送 _emit("ai_complete", {"result": full_text})。
        """
```

**Prompt 模板**:
```
# 修订润色 (polish)
你是专业的文本编辑。请将以下语音转写稿修订为通顺的书面稿：
- 修正口语化表达和语病
- 去除废话和重复内容
- 保留原意不变
- 输出纯文本，不需要额外说明

# 课堂笔记 (note)
你是高效的学习助手。请将以下课堂内容整理为结构化笔记：
- 提取核心知识点
- 按层级组织（一、二、三级标题）
- 标注重点内容
- 使用 Markdown 格式

# 思维导图 (mindmap)
请将以下内容生成 Markmap 格式的思维导图：
- 以中心主题开始
- 层级展开关键概念
- 使用 Markdown 标题层级表示层级关系

# 脑洞点评 (brainstorm)
你是批判性思维导师。请基于以下内容：
- 提出 3-5 个延伸性问题
- 指出内容的不足之处
- 提供相关背景补充
- 建议进一步探索的方向
```

**Bridge API**:
```python
@expose
def process_text(self, text: str, mode: str) -> dict:
    """非流式处理文本"""

@expose
def process_text_stream(self, text: str, mode: str) -> dict:
    """流式处理文本，结果通过 _emit 推送"""

@expose
def get_ai_config(self) -> dict:
    """获取当前 AI 配置"""

@expose
def update_ai_config(self, config: dict) -> dict:
    """更新 AI 配置"""
```

#### 4.2.4 py/storage.py - 数据持久化

**功能**:
- SQLite 数据库初始化和迁移
- Record / Version 的 CRUD 操作
- 全文搜索（FTS5）
- 版本历史管理
- 多格式导出（.md / .txt / .docx / .srt）

**关键设计点**:
- WAL 模式：启用 SQLite WAL 日志模式，支持并发读写
- 原子写入：所有写操作在事务中完成，确保数据一致性
- 不可变数据：Record 使用 frozen dataclass，更新时创建新实例
- 版本管理：每次保存自动创建版本快照，保留最近 N 个版本
- FTS5 全文搜索：对标题和逐字稿内容建立全文索引

**核心类**:
```python
class Storage:
    """本地数据持久化层。

    使用 SQLite WAL 模式存储所有数据。
    所有写操作在事务中完成，确保原子性。
    Record 使用不可变设计，更新时返回新实例。
    """

    def __init__(self, db_path: str | None = None) -> None:
        """初始化数据库。默认路径: ~/sherpanote/data.db"""

    # --- Record CRUD ---
    def save(self, record: Record) -> Record:
        """保存记录（新增或更新）。
        自动更新 updated_at 时间戳。
        更新时自动创建版本快照。
        返回新的 Record 实例。
        """

    def get(self, record_id: str) -> Record | None:
        """根据 ID 获取记录"""

    def list(self, filter: dict | None = None) -> list[Record]:
        """获取记录列表。
        filter: {"category": "...", "keyword": "...", "sort_by": "..."}
        支持 FTS5 全文搜索和分类筛选。
        """

    def delete(self, record_id: str) -> bool:
        """删除记录及其所有版本"""

    # --- 版本管理 ---
    def get_versions(self, record_id: str) -> list[Version]:
        """获取记录的所有版本"""

    def restore_version(self, record_id: str, version: int) -> Record:
        """回退到指定版本，创建新版本记录"""

    # --- 导出 ---
    def export(self, record: Record, fmt: str, output_dir: str) -> str:
        """导出记录为指定格式。
        fmt: "md" | "txt" | "docx" | "srt"
        返回导出文件的完整路径。
        """

    # --- 搜索 ---
    def search(self, keyword: str, limit: int = 50) -> list[Record]:
        """全文搜索，使用 FTS5"""
```

**导出格式实现**:
```
.md:  直接使用 Markdown 格式，包含标题、时间戳、逐字稿、AI 结果
.txt: 纯文本，去除所有格式标记
.docx: 使用 python-docx 库生成 Word 文档
.srt:  SRT 字幕格式，使用 Segment 的时间戳
```

**Bridge API**:
```python
@expose
def save_record(self, data: dict) -> dict:
    """保存/更新转写记录"""

@expose
def get_record(self, record_id: str) -> dict:
    """获取单条记录"""

@expose
def list_records(self, filter: dict = None) -> dict:
    """获取记录列表"""

@expose
def delete_record(self, record_id: str) -> dict:
    """删除记录"""

@expose
def search_records(self, keyword: str) -> dict:
    """全文搜索"""

@expose
def get_version_history(self, record_id: str) -> dict:
    """获取版本历史"""

@expose
def restore_version(self, record_id: str, version: int) -> dict:
    """回退到指定版本"""

@expose
def export_record(self, record_id: str, fmt: str) -> dict:
    """导出记录。返回文件路径。"""

@expose
def import_file(self, file_path: str) -> dict:
    """导入 .md / .txt 文件为记录"""
```

#### 4.2.5 py/io.py - 文件读写工具

**功能**:
- 音频文件格式检测和验证
- 音频文件元数据提取（时长、采样率、通道数）
- 文件拖拽处理（复用 Bridge.get_dropped_files）
- 数据目录管理（创建、清理临时文件）

#### 4.2.6 main.py - 主入口 Bridge API

将所有模块组合到 `SherpaNoteAPI` 类中：

```python
class SherpaNoteAPI(Bridge):
    """SherpaNote 主 API，组合所有业务模块。

    通过 PyWebVue Bridge 暴露给前端。
    所有公开方法使用 @expose 装饰器，遵循 {"success": bool, "data": ...} 响应规范。
    后端主动推送使用 self._emit(event, data)。
    """

    def __init__(self):
        super().__init__()
        self._config = AppConfig.default()
        self._storage = Storage(self._config.data_dir)
        self._asr: SherpaASR | None = None      # 懒加载
        self._ai: AIProcessor | None = None      # 懒加载
```

---

### 4.3 Phase 2: 前端核心页面与组件

**目标**: 实现完整的 Vue 3 前端 UI。

#### 4.3.1 路由设计

```
/                   -> HomeView        (稿件列表)
/record             -> RecordView      (录音转写)
/editor/:id         -> EditorView      (逐字稿编辑 + AI 处理)
/settings           -> SettingsView    (配置页)
```

#### 4.3.2 状态管理 (Pinia)

```typescript
// appStore.ts - 全局状态
interface AppState {
  ready: boolean;            // Bridge 是否就绪
  darkMode: boolean;         // 深色模式
  records: Record[];         // 稿件列表缓存
  currentRecord: Record | null;  // 当前编辑的稿件
  isRecording: boolean;      // 是否正在录音
  isTranscribing: boolean;   // 是否正在转写
  isAiProcessing: boolean;   // AI 是否正在处理
}
```

#### 4.3.3 HomeView - 稿件列表页

**布局**:
```
+----------------------------------------------------------+
| [navbar]  Logo  |  [搜索框]  |  [+ 新建]  [导出] [主题]   |
+----------------------------------------------------------+
| [sidebar]  |  [main content area]                        |
|  全部记录   |  +----------------------------------------+ |
|  课程       |  | RecordCard                              | |
|  会议       |  |   标题 | 时长 | 创建时间 | 状态          | |
|  访谈       |  +----------------------------------------+ |
|  (分类)     |  | RecordCard                              | |
|             |  +----------------------------------------+ |
|             |  | ...                                     | |
|             |  +----------------------------------------+ |
+----------------------------------------------------------+
```

**组件**:
- `SearchBar`: 搜索框 + 筛选器（DaisyUI input + select）
- `RecordCard`: 稿件卡片（DaisyUI card），显示标题、时长、时间、分类标签
- `ExportMenu`: 导出下拉菜单（DaisyUI dropdown）
- `ThemeToggle`: 深色/浅色切换（DaisyUI toggle）

**交互逻辑**:
1. 页面加载时调用 `list_records()` 获取稿件列表
2. 搜索框输入时防抖调用 `search_records(keyword)`
3. 点击卡片跳转到 `/editor/:id`
4. 点击"新建"跳转到 `/record` 开始录音
5. 拖拽音频文件到页面触发文件上传转写

#### 4.3.4 RecordView - 录音转写页

**布局**:
```
+----------------------------------------------------------+
| [navbar]  <- 返回  |  实时转写  |  [停止录音] [保存]      |
+----------------------------------------------------------+
|                                                          |
|  +----------------------------------------------------+  |
|  | 录音状态指示器                                      |  |
|  |   [波形动画]  正在录音 00:05:32                      |  |
|  +----------------------------------------------------+  |
|                                                          |
|  +----------------------------------------------------+  |
|  | 转写结果面板 (TranscriptPanel)                      |  |
|  |                                                    |  |
|  |   [partial result 灰色斜体]                         |  |
|  |   [final result 正常文本，带时间戳]                   |  |
|  |   [final result 正常文本，带时间戳]                   |  |
|  |   [partial result 灰色斜体]                         |  |
|  |   ...                                              |  |
|  +----------------------------------------------------+  |
|                                                          |
|  也支持拖拽文件上传：                                     |
|  +----------------------------------------------------+  |
|  | 拖拽音频文件到此处，或点击上传                        |  |
|  |   [进度条] 转写进度 45%                               |  |
|  +----------------------------------------------------+  |
+----------------------------------------------------------+
```

**组件**:
- `AudioRecorder`: 麦克风录音控制组件
- `TranscriptPanel`: 转写结果实时显示面板

**关键交互逻辑**:
```typescript
// useRecording.ts - 录音组合式函数

// 1. 请求麦克风权限
const stream = await navigator.mediaDevices.getUserMedia({
  audio: {
    sampleRate: 16000,
    channelCount: 1,
    echoCancellation: true,
  }
});

// 2. 创建 AudioContext 和 ScriptProcessorNode
//    将 MediaStream 转为 16kHz 单声道 float32 PCM
const audioCtx = new AudioContext({ sampleRate: 16000 });
const source = audioCtx.createMediaStreamSource(stream);
const processor = audioCtx.createScriptProcessor(4096, 1, 1);

processor.onaudioprocess = (e) => {
  const float32Data = e.inputBuffer.getChannelData(0);
  // 编码为 Base64，发送到 Python 后端
  const base64 = float32ToBase64(float32Data);
  call("feed_audio", base64);
};

// 3. 监听 Python 推送的识别结果
onEvent<{ text: string }>("partial_result", ({ text }) => {
  partialText.value = text;  // 灰色斜体显示
});

onEvent<{ text: string; timestamp: number[] }>("final_result", ({ text, timestamp }) => {
  segments.value.push({ text, timestamp });
  partialText.value = "";    // 清空中间结果
});

// 4. 停止录音
await call("stop_streaming");
stream.getTracks().forEach(t => t.stop());
```

**技术难点**:
1. **音频重采样**: 浏览器 MediaStream 采样率可能是 44100Hz 或 48000Hz，需要通过 AudioContext 重采样到 16000Hz。
2. **Base64 编码开销**: float32 PCM 每 4096 帧（约 256ms@16kHz）编码为 Base64 约为 22KB。这个数据量在本地 pywebview 环境下没有性能问题。
3. **ScriptProcessorNode 废弃**: 标准推荐使用 AudioWorklet，但 pywebview 环境中 ScriptProcessorNode 更简单可靠。如果需要迁移到 AudioWorklet，需要单独的 worklet 文件。

#### 4.3.5 EditorView - 逐字稿编辑页

**布局**:
```
+----------------------------------------------------------+
| [navbar]  <- 返回  |  稿件标题  |  [导出v] [保存状态]     |
+----------------------------------------------------------+
|               |                    |                      |
| [版本历史]     | [逐字稿编辑区]       | [AI 处理面板]          |
|               |                    |                      |
| v2 (当前)     |  TipTap 富文本编辑器  | [魔法按钮]            |
| v1            |                    |  - 修订润色            |
| v3 (草稿)     |  支持播放同步：       |  - 课堂笔记            |
|               |  点击文字 ->         |  - 思维导图            |
|               |  音频跳转到该位置     |  - 脑洞点评            |
|               |                    |                      |
|               |                    | [AI 输出区域]          |
|               |                    |  流式显示 AI 结果       |
|               |                    |                      |
+----------------------------------------------------------+
| [音频播放控制条]  <<  00:05:32  >>  音量                   |
+----------------------------------------------------------+
```

**组件**:
- TipTap 富文本编辑器（替代方案：contenteditable + 自定义处理）
- `VersionHistory`: 版本历史侧边栏（DaisyUI drawer）
- `AiProcessor`: AI 处理面板

**TipTap 集成**（可选方案，视复杂度决定）:
TipTap 是基于 ProseMirror 的 Vue 富文本编辑器。如果 TipTap 集成过于复杂，MVP 阶段可以使用简单的 `<textarea>` + Markdown 预览替代。

**音频同步播放逻辑**:
```typescript
// 点击逐字稿中的某个 Segment，音频跳转到对应时间戳
function seekToSegment(segment: Segment) {
  if (audioElement.value) {
    audioElement.value.currentTime = segment.start_time;
    audioElement.value.play();
  }
}

// 音频播放时，高亮当前正在播放的 Segment
function onTimeUpdate() {
  const current = audioElement.value.currentTime;
  const activeSegment = segments.value.find(
    s => s.start_time <= current && s.end_time > current
  );
  activeSegmentIndex.value = activeSegment?.index ?? -1;
}
```

**自动保存逻辑**:
```typescript
// 编辑器内容变化时，防抖 2 秒自动保存
const saveTimer = ref<ReturnType<typeof setTimeout>>();

watch(editorContent, () => {
  saveStatus.value = "editing";
  clearTimeout(saveTimer.value);
  saveTimer.value = setTimeout(async () => {
    saveStatus.value = "saving";
    await call("save_record", { ...currentRecord, transcript: editorContent.value });
    saveStatus.value = "saved";
  }, 2000);
});
```

---

### 4.4 Phase 3: AI 知识加工

**目标**: 实现 AI 文本处理的完整链路。

#### 4.4.1 AI 处理流程

```
用户点击"魔法按钮"
  -> 选择处理模式 (polish/note/mindmap/brainstorm)
  -> 前端调用 call("process_text_stream", text, mode)
  -> 后端 AIProcessor.process_stream() 启动
  -> 后端逐 token 通过 _emit("ai_token", {text: "..."}) 推送
  -> 前端 onEvent("ai_token") 实时渲染
  -> 后端完成时 _emit("ai_complete", {result: full_text})
  -> 前端将结果保存到 record.ai_results[mode]
  -> 前端触发自动保存
```

#### 4.4.2 流式渲染

```typescript
// 前端流式接收 AI 结果
const aiResult = ref("");
let fullText = "";

onEvent<{ text: string }>("ai_token", ({ text }) => {
  fullText += text;
  aiResult.value = fullText;
  isAiProcessing.value = true;
});

onEvent<{ result: string }>("ai_complete", ({ result }) => {
  isAiProcessing.value = false;
  // 保存到当前记录
  currentRecord.value = {
    ...currentRecord.value,
    ai_results: {
      ...currentRecord.value.ai_results,
      [currentMode.value]: result,
    }
  };
  call("save_record", currentRecord.value);
});
```

---

### 4.5 Phase 4: 打包与分发

**目标**: 生成可直接运行的桌面应用。

#### 4.5.1 PyInstaller 配置更新

更新 `app.spec`：
- 修改 APP_NAME 为 "SherpaNote"
- 添加 sherpa-onnx 模型文件到 datas
- 添加 SQLite 数据库文件处理

#### 4.5.2 模型文件打包策略

sherpa-onnx 模型文件较大（通常 100MB+），有以下几种打包策略：

| 策略 | 优点 | 缺点 |
|------|------|------|
| 内嵌到 exe | 开箱即用 | 安装包大（500MB+） |
| 首次运行下载 | 安装包小 | 需要网络，用户体验差 |
| 独立下载 | 灵活 | 需要额外下载步骤 |

**推荐方案**: 使用独立模型目录，安装后在首次启动时提示用户选择/下载模型。

---

## 五、关键技术点总结

### 5.1 pywebview 二进制数据传输

**问题**: pywebview JS API 的 `window.pywebview.api` 方法调用只支持 JSON 可序列化的参数（字符串、数字、布尔、数组、对象），不支持直接传输 ArrayBuffer 或 Blob。

**解决方案**: 音频 PCM 数据使用 Base64 编码传输。

```typescript
// 前端：float32 -> Base64
function float32ToBase64(float32Array: Float32Array): string {
  const bytes = new Uint8Array(float32Array.buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

// Python 后端：Base64 -> float32
import base64
def decode_audio(base64_data: str) -> numpy.ndarray:
    raw = base64.b64decode(base64_data)
    return numpy.frombuffer(raw, dtype=numpy.float32)
```

### 5.2 sherpa-onnx 模型管理

**模型类型**: sherpa-onnx 支持多种模型格式。推荐使用：
- **流式模型**: Paraformer-zipformer（中文效果最佳）或 Whisper-streaming
- **离线模型**: Paraformer（中文）或 Whisper（多语言）
- **说话人分离**: 3D-Speaker 或 pyannote（可选功能）

**模型文件结构**:
```
models/
  sherpa-onnx-streaming/
    tokens.txt
    encoder-epoch-xx.onnx
    decoder-epoch-xx.onnx
    joiner-epoch-xx.onnx
  sherpa-onnx-offline/
    tokens.txt
    model.onnx
```

### 5.3 SQLite FTS5 全文搜索

```sql
-- 建立全文搜索虚拟表
CREATE VIRTUAL TABLE records_fts USING fts5(title, transcript, content=records);

-- 同步触发器（自动保持 FTS 索引与主表一致）
CREATE TRIGGER records_ai AFTER INSERT ON records BEGIN
    INSERT INTO records_fts(rowid, title, transcript) VALUES (new.rowid, new.title, new.transcript);
END;

CREATE TRIGGER records_ad AFTER DELETE ON records BEGIN
    INSERT INTO records_fts(records_fts, rowid, title, transcript) VALUES('delete', old.rowid, old.title, old.transcript);
END;

CREATE TRIGGER records_au AFTER UPDATE ON records BEGIN
    INSERT INTO records_fts(records_fts, rowid, title, transcript) VALUES('delete', old.rowid, old.title, old.transcript);
    INSERT INTO records_fts(rowid, title, transcript) VALUES (new.rowid, new.title, new.transcript);
END;

-- 搜索查询
SELECT r.* FROM records r
JOIN records_fts f ON r.rowid = f.rowid
WHERE records_fts MATCH ?
ORDER BY rank
LIMIT ?;
```

### 5.4 音频格式兼容

用户可能上传多种音频格式。处理方案：

| 格式 | 处理方式 |
|------|---------|
| WAV (PCM) | 直接读取，确认采样率和通道数 |
| MP3 | 通过 soundfile 或 miniaudio 解码 |
| M4A/AAC | 通过 soundfile 或 miniaudio 解码 |
| FLAC | 通过 soundfile 解码 |
| 其他 | 提示用户转换为支持的格式 |

推荐使用 `soundfile` 库（基于 libsndfile），它支持大多数常见音频格式。

### 5.5 性能优化策略

1. **模型懒加载**: ASR 模型在首次使用时才加载，减少启动时间
2. **音频分片**: 4096 帧/片（约 256ms@16kHz），平衡延迟和传输开销
3. **防抖搜索**: 搜索输入 300ms 防抖，避免频繁查询
4. **虚拟列表**: 稿件列表超过 100 条时使用虚拟滚动
5. **SQLite WAL**: Write-Ahead Logging 模式，支持并发读写
6. **自动保存防抖**: 编辑器内容变化 2 秒后才触发保存

---

## 六、实施阶段划分

### Phase 0: 基础设施搭建
- 更新 pyproject.toml 和 package.json 依赖
- 创建目录结构
- 配置 DaisyUI 主题和 Tailwind CSS
- 设置 Vue Router 和 Pinia
- 替换 main.py 中的 DemoApi 为 SherpaNoteAPI 骨架

### Phase 1: Python 后端核心
- 实现 py/config.py（配置管理）
- 实现 py/storage.py（数据持久化 + SQLite）
- 实现 py/io.py（文件工具）
- 实现 py/llm.py（AI 大模型封装）
- 实现 py/asr.py（sherpa-onnx 封装）
- 组装 main.py 中的完整 Bridge API

### Phase 2: 前端核心页面
- 实现 HomeView（稿件列表 + 搜索 + 导入）
- 实现 RecordView（录音 + 文件上传转写）
- 实现 EditorView（逐字稿编辑 + 音频播放同步）
- 实现 AudioRecorder 组件（Web Audio API）
- 实现 TranscriptPanel 组件（实时转写显示）

### Phase 3: AI 知识加工
- 实现 AiProcessor 组件（魔法按钮 + 模式选择）
- 实现流式 AI 结果渲染
- 实现 AI 结果保存和版本管理
- 实现思维导图预览（Markmap/Mermaid 渲染）

### Phase 4: 导出与打包
- 实现多格式导出（.md / .txt / .docx / .srt）
- 实现版本历史 UI
- 更新 PyInstaller 打包配置
- 生成 Windows/macOS 安装包

---

## 七、风险评估

| 风险 | 等级 | 说明 | 缓解措施 |
|------|------|------|---------|
| sherpa-onnx 模型体积 | HIGH | 模型文件 100MB+，影响分发 | 首次运行下载 / 独立模型包 |
| Web Audio API 兼容性 | MEDIUM | pywebview 内嵌浏览器可能限制部分 API | 提前验证 pywebview 的 AudioContext 支持 |
| Base64 音频传输性能 | MEDIUM | 数据量增大约 33% | 本地 pywebview 环境下影响可忽略 |
| TipTap 集成复杂度 | MEDIUM | 富文本编辑器集成工作量大 | MVP 阶段使用 textarea 替代 |
| LLM API 稳定性 | LOW | 网络波动导致请求失败 | 实现重试机制 + 错误提示 |
| SQLite 并发 | LOW | WAL 模式支持并发读，写操作串行 | 所有写操作在事务中完成 |

---

## 八、手动测试指南

> 注意：按照项目约定，不编写自动化测试，而是提供手动测试项。

### 8.1 Bridge 通信测试
- [x] 启动应用，检查前端能否成功调用 `waitForPyWebView()`
- [x] 在控制台输入 `window.pywebview.api`，确认 API 已注入
- [x] 调用 `call("get_config")` 确认 Python 端响应正常

### 8.2 ASR 转写测试
- [x] 点击录音按钮，确认麦克风权限请求正常弹出
- [ ] 对着麦克风说话，确认界面上实时显示识别文字
- [ ] 说话停止后，确认 final_result 正确推送
- [ ] 上传一段 1 分钟的音频文件，确认进度条正常推进
- [ ] 确认转写完成后逐字稿包含正确的时间戳

### 8.3 数据持久化测试
- [ ] 录制一段音频并转写，关闭应用
- [ ] 重新打开应用，确认稿件出现在列表中
- [ ] 编辑逐字稿内容，确认 2 秒后自动保存指示器显示"已保存"
- [ ] 查看版本历史，确认每次保存创建了新版本
- [ ] 回退到旧版本，确认内容正确恢复

### 8.4 AI 处理测试
- [ ] 配置 AI API（如 OpenAI API Key）
- [ ] 点击"修订润色"，确认流式输出正常显示
- [ ] 点击"课堂笔记"，确认输出为结构化 Markdown
- [ ] 点击"思维导图"，确认输出为 Markmap 格式
- [ ] 断开网络后点击 AI 处理，确认错误提示正常

### 8.5 导出测试
- [ ] 导出为 .md 格式，用文本编辑器打开确认内容正确
- [ ] 导出为 .txt 格式，确认纯文本无格式标记
- [ ] 导出为 .docx 格式，用 Word 打开确认排版正确
- [ ] 导出为 .srt 格式，确认时间戳格式正确

### 8.6 深色模式测试
- [ ] 点击主题切换按钮，确认深色模式正常切换
- [ ] 确认所有 DaisyUI 组件在深色模式下显示正确
- [ ] 关闭应用重新打开，确认主题偏好已持久化

### 8.7 打包测试
- [ ] 运行 `cd frontend && npm run build && cd .. && uv run build.py`
- [ ] 在 `dist/` 目录找到生成的可执行文件
- [ ] 双击运行，确认应用正常启动
- [ ] 确认不需要安装 Python 环境即可运行
