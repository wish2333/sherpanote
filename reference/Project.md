# SherpaNote 项目全记录

> 本文档完整记录 SherpaNote 从需求定义到功能成型的全过程，用于简历面试准备。

---

## 一、项目概述

| 维度 | 内容 |
|------|------|
| 产品名称 | SherpaNote（雪豹笔记） |
| 产品定位 | 面向学生、研究者、职场人士的本地优先 AI 语音学习助手 |
| 核心价值 | 隐私安全（本地ASR）、跨平台（Win/Mac）、从音频到结构化知识的一站式工作流 |
| 技术栈 | PyWebVue (Vue 3 + pywebview) + DaisyUI 5 + Tailwind CSS 4 + sherpa-onnx + SQLite + OpenAI API |
| 开发周期 | 2026-04-06 ~ 2026-04-15（3天核心开发 + 持续迭代） |
| 代码规模 | ~12,000+ 行（前端 + 后端），持续迭代中 |
| 角色定位 | 独立负责产品设计、架构设计、全栈开发 |

---

## 二、开发时间线

### Phase 0：需求定义与架构设计（2026-04-06 ~ 04-07）

**产出文档**：
- `reference/Reference.md` — 完整 PRD（17,926 字），涵盖产品定位、用户画像、功能需求（F101-F404）、技术架构、验收标准
- `reference/DESIGN.md` — UI 设计系统（29,519 字），基于 Notion 风格的 DaisyUI 5 主题规范
- `reference/daisy_llms.txt` — DaisyUI + Tailwind CSS 技术调研

**关键决策**：
1. **选型 PyWebVue 而非 Electron**：PyWebVue 用 pywebview 替代 Chromium，包体更小（~30MB vs ~200MB），Python 后端与前端零桥接成本
2. **选型 sherpa-onnx**：开源、本地运行、支持流式/离线、模型生态丰富（Paraformer/SenseVoice/Whisper/Qwen3-ASR 等）
3. **设计 Notion 风格 UI**：参考 Notion 的极简设计语言，用 DaisyUI 5 + Tailwind CSS 4 实现
4. **前后端通信架构**：PyWebVue 的 `@expose` + `_emit` + `onEvent` 模式，Python 方法直接暴露给前端调用，事件驱动推送结果

### Phase 1：框架搭建与核心功能（2026-04-08 09:00）

**commit**: `2e0c46d` feat: first commit

首个完整提交，实现从零到一的完整产品骨架：

- **后端**：`py/asr.py`（sherpa-onnx 流式/离线识别）、`py/storage.py`（SQLite 持久化 + WAL 模式）、`py/llm.py`（AI 流式处理）、`py/config.py`（配置管理）、`py/io.py`（音频 I/O）
- **前端**：5 个视图（HomeView / RecordView / EditorView / SettingsView / AudioManageView）、11 个组件、4 个 composables
- **核心链路跑通**：录音 -> 实时转录 -> 保存记录 -> AI 处理 -> 导出

**解决的问题**：
- 重新转录按钮未绑定功能 -> 实现 handleRetranscribe
- 音频播放 file:// 协议失败 -> 改用 base64 data URL
- 不同 ASR 模型运行方式差异（Paraformer vs SenseVoice）-> 改进模型检测逻辑
- 录音时切换页面状态丢失 -> 添加导航守卫
- 三语 Paraformer 模型加载崩溃（protobuf parsing failed）-> 修复模型类型判断
- 文件上传转录无进度条 -> 添加进度事件推送
- SQLite WAL 文件过大 -> 解释为正常机制

### Phase 2：UI 深度优化与 AI 处理增强（2026-04-08 10:57 ~ 22:32）

**commits**:
- `ec3bf60` feat(ui-audio): 全面优化音频管理、转录与用户界面
- `c947b01` chore(project): 更新项目名称为sherpanote并发布1.0.0版本
- `0351de4` feat(audio-ai): 全面升级音频转录与AI处理功能

**核心改进**：

1. **AI 预设系统**（settings > AI 处理选项卡）
   - API 预设管理：多供应商（OpenAI-compatible、OpenRouter），支持测试连接
   - 处理预设管理：用户自定义处理模板（名称、模式、提示词）
   - 转录后自动 AI 处理：可配置的自动执行链

2. **编辑器布局重构**
   - 从 Tab 切换改为垂直堆叠：Transcript + AI Result 上下排列
   - 左侧 1/3 控制面板（预设选择 + 已保存结果导航），右侧 2/3 内容区
   - Transcript 可折叠，AI Result 全尺寸展示

3. **输出截断防护**
   - `_estimate_max_tokens()` 根据输入长度动态估算
   - finish_reason 检测截断状态
   - "Continue" 按钮支持续写，追加而非重复

4. **版本历史系统**
   - 手动保存版本（Save Version 按钮）
   - 内容差异脏检测（非布尔值，基于内容对比）
   - Restore 后正确更新 current 标识
   - 导航离开时自动保存脏记录版本
   - 可配置最大版本保留数

**解决的跨层 bug**：
- PyWebVue 桥接不支持 None 作为可选参数 -> 将参数改为单个 config 字典
- AI 结果未持久化 -> 在 ai_complete 事件后自动调用 autoSaveResult()
- Version History current 标识错误 -> 基于内容对比的脏检测替代布尔标记

### Phase 3：多源模型管理（2026-04-09）

**commit**: `e73881d` feat(model-management): 多镜像源支持与模型识别功能增强

这是技术上最复杂的阶段，涉及模型生态整合和自动检测：

1. **5 种下载源**
   - GitHub Releases（官方源）
   - HuggingFace（使用 huggingface_hub 库）
   - HF-Mirror（国内镜像，设置 endpoint）
   - GitHub Proxy（动态域名，用户可输入）
   - 魔搭社区（阿里系模型专属）

2. **模型自动分类**
   - 基于 `_classify_model_dir()` 的文件启发式规则：
     - joiner.onnx 存在 -> 流式（Transducer/Zipformer）
     - model.onnx 且无 encoder -> 离线（Paraformer/SenseVoice）
     - conv_frontend.onnx -> Qwen3-ASR
     - encoder_adaptor.onnx + llm.onnx -> FunASR Nano
   - 支持前缀文件名匹配（如 distil-large-v3.5-encoder.int8.onnx）

3. **6 个新模型集成**
   - Qwen3-ASR 0.6B/1.7B（SenseVoice API + monkey-patch 修复 hotwords bug）
   - FunASR Nano（4 文件：encoder_adaptor、llm、embedding、tokenizer/Qwen3-0.6B）
   - Whisper distil-large-v3/v3.5（encoder+decoder 模式，支持 language + task 参数）
   - 流式 Paraformer 中/粤/英三语版

4. **macOS 麦克风修复**（4 个 commits 迭代）
   - 根因：Info.plist 缺少 NSMicrophoneUsageDescription 声明
   - WKWebView 无法暴露 navigator.mediaDevices
   - 最终方案：在 app.spec BUNDLE 步骤生成包含权限声明的 .app 包

**设计思考**：模型下载源的选择反映了对中国用户网络环境的理解——GitHub 直连不稳定，HuggingFace 也有访问限制，需要提供多个备选源和代理配置。

### Phase 4：模拟流式识别与跨平台音频（2026-04-10）

**commits**:
- `4663141` feat(multilingual): 增强多语言支持并优化模型管理
- `1c17e4c` feat(asr): 实现模拟流式识别与 macOS 音频增强

**模拟流式识别**：

这是一个架构创新——许多高质量模型（SenseVoice、Qwen3-ASR、Cohere Transcribe）只有离线 API，但用户需要实时看到转录结果。

**方案**：VAD 分段 + 离线识别器管线
```
实时音频流 -> VAD 检测语音段 -> 段结束时送入 OfflineRecognizer -> 推送结果到前端
```

**关键设计**：
- 流式场景 VAD min_silence_duration 自动 x1.6（更长的静默等待，减少误切割）
- `_last_emitted_final_count` 计数器避免重复发射
- 段去重检测（相同内容不重复显示）
- 前端流式下拉框同时展示支持模拟流式的离线模型

**macOS 音频增强**：

- AudioContext sampleRate 不匹配（macOS 硬件 44100/48000Hz，后端期望 16000Hz）-> 前端重采样
- AudioContext suspended 状态 -> 最多 3 次重试
- 静音检测 -> 连续 3 秒 RMS < 0.01 触发警告
- 录音无语音时不再创建空记录 -> toast 提示

**VAD 参数可配置化**：

将 4 个 VAD 参数（threshold、min_silence_duration、min_speech_duration、max_speech_duration）暴露到设置界面，带 range slider + 中文说明。

**SenseVoice int8 Bug 修复**：

SenseVoice int8 模型使用 model.int8.onnx 而非 model.onnx，但代码只检测后者 -> 扩展文件匹配逻辑。

### Phase 5：模型精调与质量优化（2026-04-11）

**commits**:
- `aa6b048` fix(models, asr): 移除低质Whisper模型并修复冗余debug日志
- `9a464b3` fix(models): 添加更多 Whisper 模型并优化多文件 HF 下载

- 添加 Whisper 系列模型（distil-large-v3/v3.5/turbo/medium，各含 int8 和全量版本）
- 新增 `hf_files` 字段支持多文件 HF 下载（非 tar.bz2 包，而是散文件）
- 实测发现 ONNX-Whisper 模型质量不佳 -> 从模型管理器移除，保留执行代码供用户自行下载
- 减少切换录音/转录界面时的冗余 DEBUG 日志

### Phase 6：GPU 加速、Whisper.cpp 集成与转录体验升级（2026-04-13 ~ 04-15）

**核心新增**：

1. **GPU 加速支持**
   - `py/gpu_detect.py`：自动检测 NVIDIA GPU、CUDA 版本、验证 sherpa-onnx CUDA 构建版本
   - `build.py` CUDA 构建流程：隔离 `_cuda_build_venv` 避免影响开发环境，支持 `--cuda` 和 `--cuda-variant`（CUDA 11.8 / CUDA 12+cuDNN 9）两种变体
   - 设置界面 GPU 开关：实时显示 GPU 名称、CUDA 版本，不可用时显示原因
   - ASR 引擎通过 `provider="cuda"` 参数启用 CUDA 加速，经 nvidia-smi 验证 GPU 确实参与计算

2. **Whisper.cpp 集成**
   - `py/whispercpp.py`：可选的 ASR 后端，通过 whisper-cli.exe 进行转录
   - `py/whispercpp_registry.py`：Whisper.cpp 模型注册表，支持 cpu/blas/cuda 变体
   - 二进制分发管理：下载、安装、依赖文件（libggml 等）自动提取
   - 录音/转录界面支持引擎动态切换，模型选择器自动过滤

3. **转录体验升级**
   - 进度条实时显示段落数量（如"42% (15/30)"）
   - 音频元数据管理：支持显示视频标题或原文件名
   - 智能文件检测：导入音频时自动避免重复复制
   - 音频格式优化：WAV 转 MP3，文件大小减少 90% 以上

**解决的工程问题**：
- `uv run` 会重新同步 `.venv` 导致 CUDA 包被替换 -> 创建隔离的临时 venv 用于 CUDA 构建
- PyInstaller 无法自动收集 `onnxruntime_providers_cuda.dll` -> 在 app.spec 中手动收集 sherpa-onnx lib/ 下的所有 DLL
- `import onnxruntime` 失败（sherpa-onnx 内部捆绑）-> 改为检查 `sherpa_onnx.__version__` 中的 `+cuda` 后缀
- Whisper.exe 已弃用 -> 切换到 whisper-cli.exe
- Whisper.cpp 模型下载临时文件扩展名兼容性 -> 统一处理

---

## 三、关键架构决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 桌面框架 | PyWebVue (pywebview) vs Electron | 包体小 5x+，Python 原生调用无 IPC 开销 |
| ASR 引擎 | sherpa-onnx | 本地运行、模型丰富、支持流式/离线、社区活跃 |
| UI 框架 | DaisyUI 5 + Tailwind CSS 4 | 组件丰富、主题灵活、开发效率高 |
| 数据库 | SQLite WAL 模式 | 零配置、事务安全、并发读性能好 |
| 前后端通信 | @expose + _emit 事件驱动 | PyWebVue 原生机制，无需 WebSocket |
| 模型检测 | 文件启发式规则 | 支持任意模型，不限于预设目录名 |
| 模拟流式 | VAD + OfflineRecognizer | 用离线模型实现类流式体验，扩展可用模型范围 |
| GPU 构建 | 隔离临时 venv | 避免 CUDA 包污染开发环境，保持 dev/build 分离 |
| 版本控制 | 内容差异脏检测 | 避免无修改也创建版本，减少版本噪音 |

---

## 四、技术亮点总结

1. **模型生态整合能力**：对接 5 种下载源、10+ ASR 模型、多种模型架构（Transducer/Paraformer/SenseVoice/Whisper/Qwen3-ASR/FunASR Nano/Cohere Transcribe），基于文件启发式自动分类
2. **模拟流式架构创新**：VAD + OfflineRecognizer 管线，让离线模型也能提供实时转录体验
3. **GPU 加速构建体系**：隔离临时 venv 避免 CUDA 包污染开发环境，支持 CUDA 11.8 和 12.x 两种变体，自动检测 GPU 并验证 sherpa-onnx CUDA 构建
4. **Whisper.cpp 双引擎架构**：sherpa-onnx + whisper.cpp 双 ASR 后端，用户可按需切换，模型选择器自动过滤
5. **跨平台音频处理**：macOS AudioContext 兼容（重采样、suspended 重试、静音检测）
6. **多供应商 AI 集成**：OpenAI-compatible + OpenRouter，预设管理，流式输出，截断恢复
7. **端到端数据安全**：ASR 全程本地运行，SQLite WAL 持久化，版本历史可追溯
8. **快速迭代能力**：3 天从 PRD 到可用产品，持续迭代至 v1.3.0
