## Context

SherpaNote 是基于 PyWebVue 的桌面应用，Python 后端封装 sherpa-onnx ASR 引擎，Vue 3 前端提供录制/上传 UI。当前存在四个阻塞级问题需要解决：

1. **上传 MP3 文件报错** "Error opening: System error" — `py/io.py` 中的 `read_audio_as_mono_16k` 使用 `soundfile.read()` 打开文件，soundfile 依赖 libsndfile，对 MP3 格式支持取决于编译时是否启用了 MPG123 编解码器。Windows 上预编译的 pysoundfile 包通常不包含 MP3 支持。
2. **拖拽框闪动 + 误开浏览器** — `dragover`/`dragleave` 事件在子元素间冒泡导致 `isDraggingOver` 状态在 true/false 间快速切换。pywebview 的拖放机制可能在 drop 未能正确拦截时将文件交给操作系统默认处理（打开浏览器）。
3. **录制音频未持久化** — `PcmRecorder.close()` 将 WAV 保存到 `data/temp/`，但 `stop_streaming` 返回的 `audio_path` 没有被存入数据库的 `records.audio_path` 字段。RecordView 中 `handleRecordingComplete` 调用 `saveAsRecord` 时虽然传入了 `audio_path`，但目标目录应为 `data/audio/` 而非 `data/temp/`。
4. **sherpa-onnx 缺乏可观测性** — ASR 引擎的加载、推理、结果输出没有任何面向用户的日志或状态反馈，无法判断 sherpa-onnx 是否真正工作。

## Goals / Non-Goals

**Goals:**
- 修复 MP3 等格式的音频文件上传，使用 audioread 或 ffmpeg 作为 soundfile 的备选解码方案
- 修复拖拽交互：消除子元素冒泡导致的闪动，确保 pywebview 正确拦截拖放事件
- 录制完成后音频自动保存到 `data/audio/`，路径写入数据库，记录面板添加手动识别按钮
- 创建独立的 sherpa-onnx 诊断脚本，验证模型加载、音频推理和结果输出

**Non-Goals:**
- 不修改 AI 处理模块（py/llm.py）
- 不修改模型下载/管理逻辑
- 不新增音频格式支持（仍使用已有的支持列表）
- 不重构数据库 schema（`audio_path` 字段已存在）

## Decisions

### 1. 音频解码方案：引入 audioread 作为 soundfile 的 fallback

**选择**: `audioread` + `soundfile` 双路径方案
**理由**: `soundfile` 不支持 MP3 是 pysoundfile 在 Windows 上的已知限制。`audioread` 库会自动检测并调用系统安装的 ffmpeg、GStreamer 或 Media Foundation 作为后端。这比在 Windows 上安装特定版本的 libsndfile + MPG123 更可靠。
**备选方案**:
- 直接调用 ffmpeg subprocess — 更可控但增加了外部依赖
- 使用 pydub — 额外引入了大量不必要的依赖

**实现**: 在 `read_audio_as_mono_16k` 中，先用 `soundfile` 尝试，失败后 fallback 到 `audioread`。audioread 返回 int16 PCM，需转换为 float32。

### 2. 拖拽闪动修复：使用 drag counter 替代布尔标志

**选择**: 引入 `dragCounter` 整数计数器，`dragenter` +1、`dragleave` -1，仅在 counter > 0 时显示覆盖层
**理由**: 这是 Web 拖拽事件冒泡问题的标准解决方案。当鼠标从父元素移入子元素时，会先触发父元素的 `dragleave` 再触发子元素的 `dragenter`，导致布尔标志闪烁。
**备选方案**:
- CSS `pointer-events: none` 在覆盖层上 — 简单但可能影响用户体验
- 使用 `relatedTarget` 判断 — 在复杂 DOM 中不可靠

**实现**: 在 HomeView.vue 和 RecordView.vue 中将 `isDraggingOver: ref(false)` 替换为 `dragCounter: ref(0)` + computed `isDraggingOver`。

### 3. pywebview 拖放误开浏览器：在 window 级别拦截 dragover

**选择**: 在 `mounted` 时添加 `window.addEventListener('dragover', ...)` 和 `window.addEventListener('drop', ...)` 防止 pywebview/webview 将文件交给系统处理
**理由**: pywebview 基于系统 webview（Windows 上是 Edge WebView2），如果 JavaScript 没有在 window 级别拦截 dragover 和 drop 事件，浏览器引擎会将文件拖放当作导航处理（打开文件）。
**实现**: 创建 `useDragDrop` composable，在 mount 时注册全局事件监听器，在 unmount 时清理。

### 4. 录制音频持久化：修改 PcmRecorder 输出目录为 data/audio/

**选择**: `PcmRecorder` 构造时传入 `output_dir=data/audio/`，并在 `stop_streaming` 中将 `audio_path` 确保写入数据库
**理由**: `PcmRecorder` 已支持 `output_dir` 参数。`data/temp/` 目录用于临时文件，录制完成的正式音频应存放到 `data/audio/`。数据库 `records.audio_path` 字段已存在，只需确保 save 时正确传入。
**实现**: 在 `SherpaASR.start_streaming()` 中，设置 `PcmRecorder(output_dir=str(Path(data_dir) / "audio"))`。前端 `handleRecordingComplete` 已传入 `audio_path`，无需修改。

### 5. 手动识别按钮：在记录列表的 RecordCard 和编辑器页面添加

**选择**: 在 RecordCard.vue 中添加"识别"按钮，调用新增的 `retranscribe_record` API
**理由**: 用户需要能对已有音频记录重新触发识别。需要一个后端 API 读取 `audio_path` 并调用 `transcribe_file`，然后更新记录。
**实现**: 后端新增 `retranscribe_record(record_id)` 方法；前端在 RecordCard 中添加按钮。

### 6. sherpa-onnx 诊断脚本：独立的 CLI 工具

**选择**: 创建 `scripts/test_sherpa.py`，使用 `uv run --script` 运行
**理由**: 独立于主应用运行，避免 PyWebVue/webview 的干扰。用户可以直接在终端运行，看到完整的日志输出。
**实现**: 脚本包含以下测试步骤：
1. 检测 sherpa_onnx 是否可导入
2. 扫描模型目录
3. 加载在线/离线识别器
4. 使用内置测试音频或用户指定音频文件进行推理
5. 输出详细的日志信息（模型路径、加载时间、推理时间、识别结果）

## Risks / Trade-offs

- **[audioread 依赖系统解码器]** → 需要在 README 中注明用户需安装 ffmpeg。可在诊断脚本中检测并提示。
- **[拖拽修复可能影响其他拖拽功能]** → 全局事件拦截需要谨慎，仅拦截文件类型拖拽（检查 `dataTransfer.types`）。
- **[录制音频保存到 data/audio/ 会占用磁盘空间]** → 可在后续版本中添加清理功能，当前不在范围内。
- **[手动识别是耗时操作]** → 需要明确的进度反馈，复用已有的 `transcribe_progress` 事件机制。
