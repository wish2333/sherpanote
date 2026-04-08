Sherpa文档：https://k2-fsa.github.io/sherpa/onnx/python/index.html

# SherpaNote（雪豹笔记）PRD 需求文档
基于 PyWebVue 框架与 sherpa-onnx 的 AI 语音学习软件

## 文档基础信息
| 项目         | 内容                                   |
|--------------|----------------------------------------|
| 产品名称     | SherpaNote（雪豹笔记）                 |
| 文档版本     | V1.1                                   |
| 制定日期     | 2026-04-06                             |
| 最后修订     | 2026-04-07                             |
| 技术栈       | PyWebVue (Vue 3 + pywebview) + DaisyUI + Tailwind CSS + sherpa-onnx + 本地/云端 LLM |
| 核心目标     | 构建一款跨平台（Mac/Windows）、注重隐私、高效的课程录音转写与 AI 知识整理工具 |

---

## 一、产品概述
### 1.1 产品定位
SherpaNote 是一款面向学生、研究者及职场人士的**本地优先 AI 学习助手**。它集成了业界顶尖的 sherpa-onnx 语音识别引擎，能够在无网络环境下实时将课程、会议语音转为高精度文字稿，并通过 AI 大模型一键生成结构化笔记、思维导图、知识点摘要及互动式点评。

### 1.2 核心价值
1.  **极致隐私**：语音转写（sherpa-onnx）全程本地运行，音频数据不上云，杜绝课程/会议内容泄露。
2.  **跨端一致**：基于 PyWebVue 框架，实现 Mac/Windows 桌面端的核心代码复用与体验统一。
3.  **知识生产效率**：从”原始音频”到”结构化知识”的一站式 workflow。
4.  **数据持久化**：本地自动保存所有转写记录与笔记，支持多格式导出，断电/崩溃不丢失数据。

---

## 二、核心目标（MVP 版本）
1.  **跑通核心链路**：实现基于 sherpa-onnx 的实时录音转写与文件上传转写。
2.  **落地 PyWebVue 架构**：充分利用框架的 `Bridge` 机制（`@expose` + `_emit` + `onEvent`），实现 Python 后端（语音处理、文件 IO）与 Vue 前端（UI、交互）的高效通信。
3.  **AI 赋能内容**：对接 AI 大模型（支持本地 LLM 或云端 API），完成逐字稿的修订、笔记生成与要点提炼。
4.  **数据持久化**：实现转写记录的自动保存、历史管理、版本追溯与多格式导出。
5.  **基础工程化**：利用 PyWebVue 的打包能力（PyInstaller），生成可分发的 Mac/Windows 安装包。

---

## 三、用户画像
| 用户类型       | 核心痛点                                                                 | 核心诉求                                                                 |
|----------------|--------------------------------------------------------------------------|--------------------------------------------------------------------------|
| 高校学生       | 上课记笔记跟不上，课后整理录音耗时巨大；复习时找不到重点。             | 实时出稿，自动提取重点，生成便于复习的笔记。                           |
| 研究员/博主   | 访谈录音转写成本高，人工整理逐字稿效率低；需要从素材中快速找灵感。     | 高精度转写，说话人分离，AI 辅助生成“脑洞”和观点。                     |
| 职场人士       | 会议信息量大，会后遗忘关键决策；需要快速生成会议纪要。                 | 语音实时转文字，AI 自动生成待办事项与会议摘要。                         |

---

## 四、功能需求
### 4.1 核心功能模块
基于 PyWebVue 的架构特性，功能分为**前端交互层（Vue）**和**后端能力层（Python via Bridge）**。

#### 模块一：音频采集与 sherpa-onnx 转写（核心壁垒）
| 需求ID | 需求描述                                                                 | 详细规格与技术实现                                                                 |
|--------|--------------------------------------------------------------------------|--------------------------------------------------------------------------|
| F101   | 实时麦克风流式转写                                                     | **前端（Vue）**：<br>1. 调用浏览器 Web Audio API 采集麦克风音频；<br>2. 将音频流（16kHz, 单声道, PCM）分片通过 PyWebVue Bridge 的 `call()` 方法发送至 Python 后端；<br>3. 通过 `onEvent("partial_result", handler)` 监听实时识别结果，通过 `onEvent("final_result", handler)` 监听定稿结果。<br><br>**后端（Python）**：<br>1. `@expose` 暴露 `start_streaming()` 和 `feed_audio(data)` 方法；<br>2. 集成 sherpa-onnx `OnlineRecognizer`；<br>3. 通过 `self._emit("partial_result", {"text": "..."})` 推送中间结果；<br>4. 通过 `self._emit("final_result", {"text": "...", "timestamp": ...})` 推送定稿结果。 |
| F102   | 音频文件上传转写                                                         | **前端（Vue）**：<br>1. 支持拖拽上传 mp3/wav/m4a 等常见格式（利用 PyWebVue 内置 `Bridge.get_dropped_files()`）；<br>2. 通过 `onEvent("transcribe_progress", handler)` 监听转写进度。<br><br>**后端（Python）**：<br>1. `@expose` 暴露 `transcribe_file(path)` 方法；<br>2. 集成 sherpa-onnx `OfflineRecognizer`；<br>3. 支持 VAD（语音活动检测），自动切分静音片段；<br>4. 通过 `self._emit("transcribe_progress", {"percent": 30})` 推送进度；<br>5. 返回带时间戳的完整逐字稿 `{"success": True, "data": ...}`。 |
| F103   | 说话人分离（可选）                                                       | 后端集成 sherpa-onnx 说话人分离模型，在逐字稿中标注 [Speaker 0], [Speaker 1]。 |

#### 模块二：文本编辑器与稿件管理
| 需求ID | 需求描述                                                                 | 详细规格                                                                 |
|--------|--------------------------------------------------------------------------|--------------------------------------------------------------------------|
| F201   | 智能逐字稿编辑器                                                         | 1. 前端使用 TipTap 富文本编辑器，UI 组件基于 DaisyUI + Tailwind CSS 构建；<br>2. 支持播放原音频，点击文字自动定位音频播放位置（基于时间戳）；<br>3. 支持手动修改、高亮、批注。 |
| F202   | 稿件库管理                                                               | 1. 支持按课程/项目分类；<br>2. 列表视图展示：标题、时长、创建时间、转写状态；<br>3. 支持导出为 .md, .txt, .docx 格式（详见 F401）。 |

#### 模块三：AI 知识加工（大脑）
| 需求ID | 需求描述                                                                 | 详细规格与交互逻辑                                                                 |
|--------|--------------------------------------------------------------------------|--------------------------------------------------------------------------|
| F301   | 一键 AI 加工                                                             | 前端提供“魔法按钮”，用户点击后选择以下模式之一发送给后端：<br>1. **修订润色**：修正口语化表达、去除废话，形成通顺的书面稿。<br>2. **课堂笔记**：提取知识点，按层级（一、二、三级标题）重新排版。<br>3. **思维导图/大纲**：生成 Markmap 或 Mermaid 格式的思维导图。<br>4. **脑洞/点评**：基于内容提出延伸性问题、批判性思考或相关背景补充。 |
| F302   | AI 模型配置                                                             | **后端（Python）**：<br>1. 封装 LLM 调用接口；<br>2. 支持配置：<br>   - 云端 API（OpenAI/Anthropic/Qwen 等）；<br>   - 本地 LLM（通过 Ollama 或 Llama.cpp 集成）。 |

#### 模块四：数据持久化与历史记录
| 需求ID | 需求描述                                                                 | 详细规格                                                                 |
|--------|--------------------------------------------------------------------------|--------------------------------------------------------------------------|
| F401   | 多格式导出                                                               | **后端（Python）**：<br>1. `@expose` 暴露 `export_record(record_id, format)` 方法；<br>2. 支持导出格式：`.md`（Markdown）、`.txt`（纯文本）、`.docx`（Word）、`.srt`（字幕）；<br>3. 导出内容包括：逐字稿、AI 生成的笔记/摘要、时间戳信息。<br><br>**前端（Vue）**：<br>1. 在稿件详情页提供"导出"下拉菜单（DaisyUI dropdown 组件）；<br>2. 导出时弹出系统文件保存对话框。 |
| F402   | 自动保存与版本历史                                                       | **后端（Python）**：<br>1. 每次转写完成或用户编辑后自动保存到本地 JSON/SQLite 存储；<br>2. `@expose` 暴露 `save_record(data)` 方法；<br>3. 维护编辑版本历史（保留最近 N 次修改），支持版本回溯。<br>4. `@expose` 暴露 `get_version_history(record_id)` 方法。<br><br>**前端（Vue）**：<br>1. 编辑器自动保存指示器（显示"已保存"/"保存中"状态）；<br>2. 提供版本历史侧边栏，可查看/对比/恢复历史版本。 |
| F403   | 稿件历史记录与搜索                                                       | **后端（Python）**：<br>1. `@expose` 暴露 `list_records(filter)` 方法，支持按标题、日期、标签筛选；<br>2. `@expose` 暴露 `search_records(keyword)` 方法，支持全文检索逐字稿内容；<br>3. `@expose` 暴露 `delete_record(record_id)` 方法。<br><br>**前端（Vue）**：<br>1. 首页稿件列表支持搜索框与筛选器（DaisyUI input + select 组件）；<br>2. 支持批量选择与批量删除；<br>3. 列表支持排序（按创建时间、最近编辑时间、标题）。 |
| F404   | 数据导入                                                                 | **后端（Python）**：<br>1. `@expose` 暴露 `import_file(path)` 方法；<br>2. 支持导入之前导出的 `.md`、`.txt` 格式文件，自动识别并恢复为稿件记录。<br><br>**前端（Vue）**：<br>1. 在稿件列表页提供"导入"按钮，支持文件选择对话框。 |

---

## 五、技术架构与 PyWebVue 集成方案
这是本项目的关键，需严格遵循 PyWebVue 的框架规范（详见 `docs/` 目录下的 api.md、development.md、building.md）。

### 5.1 目录结构映射
直接利用 PyWebVue 的标准结构进行开发：
```text
SherpaNote/
  main.py            # 入口，初始化 App，定义 Bridge 子类
  pywebvue/          # 框架核心（不动）
    ├── app.py       # App 类：窗口创建、dev/prod URL 解析、生命周期管理
    ├── bridge.py    # Bridge 基类 + @expose 装饰器
    └── __init__.py  # 导出：App, Bridge, expose
  py/                # 我们的 Python 业务逻辑
    ├── asr.py       # sherpa-onnx 封装
    ├── llm.py       # AI 大模型封装
    ├── storage.py   # 数据持久化（保存/加载/导出/导入）
    └── io.py        # 文件读写工具
  frontend/           # Vue 前端
    ├── src/
    │   ├── main.ts       # Vue 启动入口
    │   ├── App.vue       # 根组件
    │   ├── bridge.ts     # 框架桥接：call(), onEvent(), waitForPyWebView()
    │   ├── env.d.ts      # pywebview 类型声明
    │   └── views/        # 录音页、编辑页、列表页
    ├── index.html        # Vite 入口
    ├── tailwind.config.ts # Tailwind CSS 配置（含 DaisyUI 插件）
    └── package.json
  dev.py             # 开发启动脚本（uv sync + npm install + Vite + Python app）
  build.py           # 打包脚本（PyInstaller 桌面端）
  app.spec           # PyInstaller 打包配置
```

### 5.2 前端 UI 框架
前端使用 **DaisyUI + Tailwind CSS** 作为 UI 组件库与样式方案：
- **Tailwind CSS**：原子化 CSS 框架，用于快速构建自定义布局与样式。
- **DaisyUI**：基于 Tailwind CSS 的组件库，提供 Button、Modal、Drawer、Dropdown、Table、Toast 等开箱即用的组件，减少重复 UI 开发。
- 在 `tailwind.config.ts` 中配置 DaisyUI 插件与主题。

### 5.3 核心 Bridge 设计（Python 端）
在 `main.py` 中定义核心 API 类，这是前后端通信的唯一桥梁。

> **通信机制说明**：PyWebVue 的前后端通信通过 `window.pywebview.api`（JS API 注入）实现，**不使用 WebSocket**。
> - **前端 -> 后端**：通过 `call<T>(method, ...args)` 调用 `@expose` 装饰的 Python 方法，返回 `Promise<ApiResponse<T>>`。
> - **后端 -> 前端**：通过 `self._emit(event, data)` 推送 `CustomEvent("pywebvue:{event}")`，前端通过 `onEvent<T>(name, handler)` 监听。

```python
from pywebvue import App, Bridge, expose
from py.asr import SherpaASR
from py.llm import AIProcessor
from py.storage import Storage

class SherpaNoteAPI(Bridge):
    def __init__(self):
        super().__init__()
        # 初始化模型（懒加载或启动时加载）
        self.asr_engine = SherpaASR()
        self.ai_processor = AIProcessor()
        self.storage = Storage()

    # === 语音转写相关 ===
    @expose
    def init_model(self, model_type: str = "online") -> dict:
        """初始化 sherpa-onnx 模型，加载到内存"""
        return {"success": True, "data": {"model_type": model_type}}

    @expose
    def start_streaming(self) -> dict:
        """启动实时流式识别"""
        return {"success": True, "data": {"status": "streaming"}}

    @expose
    def feed_audio(self, data: bytes) -> dict:
        """处理实时音频流分片，通过 _emit 推送识别结果"""
        result = self.asr_engine.decode(data)
        # 通过事件推送中间结果到前端
        self._emit("partial_result", {"text": result["partial"]})
        self._emit("final_result", {"text": result["final"], "timestamp": result["ts"]})
        return {"success": True, "data": {"length": len(data)}}

    @expose
    def transcribe_file(self, file_path: str) -> dict:
        """处理完整音频文件，通过 _emit 推送进度"""
        def _on_progress(percent: int):
            self._emit("transcribe_progress", {"percent": percent})

        result = self.asr_engine.decode_file(file_path, on_progress=_on_progress)
        return {"success": True, "data": result}

    # === AI 处理相关 ===
    @expose
    def process_text(self, text: str, mode: str) -> dict:
        """mode: polish/note/mindmap/brainstorm"""
        result = self.ai_processor.run(text, mode)
        return {"success": True, "data": result}

    # === 数据持久化相关 ===
    @expose
    def save_record(self, data: dict) -> dict:
        """保存转写记录"""
        record_id = self.storage.save(data)
        return {"success": True, "data": {"record_id": record_id}}

    @expose
    def list_records(self, filter: dict = None) -> dict:
        """获取记录列表"""
        records = self.storage.list(filter)
        return {"success": True, "data": records}

    @expose
    def export_record(self, record_id: str, format: str) -> dict:
        """导出记录为指定格式"""
        file_path = self.storage.export(record_id, format)
        return {"success": True, "data": {"file_path": file_path}}

# 启动应用
if __name__ == "__main__":
    api = SherpaNoteAPI()
    app = App(api, title="SherpaNote", frontend_dir="frontend_dist")
    app.run()  # auto-detect: dev when not frozen, prod when frozen
```

---

## 六、非功能需求
### 6.1 性能与体验
1.  **转写延迟**：实时流式转写的首字延迟 < 500ms，句尾延迟 < 1s。
2.  **资源占用**：sherpa-onnx 模型加载后，内存占用控制在 500MB 以内（CPU 模式）。
3.  **启动速度**：利用 PyWebVue 启动，从点击图标到界面可交互 < 3s。

### 6.2 兼容性
1.  **桌面端**：完美支持 Windows 10/11，macOS 12+（Intel & Apple Silicon）。

### 6.3 安全性
1.  **本地优先**：默认所有处理（ASR）在本地完成，用户不主动开启 AI 功能则不联网。
2.  **数据隔离**：每个项目的数据存储在独立的沙箱目录中。

---

## 七、验收标准
1.  **工程化验收**：
    *   能够通过 `cd frontend && npm run build && uv run build.py` 成功生成 Mac/Windows 的可执行文件，且双击即可运行，无需安装 Python 环境。
    *   前端构建使用 DaisyUI + Tailwind CSS 组件库。
2.  **功能验收**：
    *   对着麦克风说话，界面上实时出现文字（通过 `_emit` / `onEvent` 实时推送）。
    *   上传一段 10 分钟的课程录音，能生成带时间戳的逐字稿，并显示进度条。
    *   点击”生成笔记”，能调用 AI 返回结构化内容。
    *   转写记录自动保存，关闭后重新打开数据不丢失。
    *   支持将逐字稿和笔记导出为 .md / .txt / .docx 格式。
    *   在历史列表中能搜索和筛选已保存的记录。
3.  **技术栈验收**：
    *   代码中必须明确集成 `sherpa-onnx` 库。
    *   使用 PyWebVue 的 `@expose` 装饰器进行通信，遵循 `{“success”: True, “data”: ...}` 响应规范。
    *   实时推送使用 `Bridge._emit()` + 前端 `onEvent()` 事件机制。
    *   前端 UI 基于 DaisyUI + Tailwind CSS 构建。
