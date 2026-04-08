## Why

SherpaNote 的核心功能 -- 音频录制与语音识别 -- 存在多个阻塞级问题：音频文件上传失败（System error）、拖拽上传交互异常（闪动 + 误开浏览器）、录制完成后音频未持久化且无法手动触发识别。此外，缺乏对 sherpa-onnx 引擎运行状态的可观测性，无法确认 ASR 调用是否正常工作，严重阻碍了开发调试和用户使用。

## What Changes

- **修复音频文件上传 Bug**：上传 MP3 等格式文件时出现 "Error opening: System error"，排查并修复文件打开/解码逻辑
- **修复拖拽上传交互 Bug**：拖拽文件到窗口后拖拽框持续闪动，松手后错误地打开默认浏览器而非处理文件
- **新增录制音频持久化功能**：录制完成后自动将音频保存到 `data/audio/` 目录，文件名记录到数据库，并在记录面板中添加手动触发音频识别的按钮
- **新增 sherpa-onnx 独立诊断工具**：创建可由用户操作的测试脚本，包含充足的日志输出，用于独立验证 sherpa-onnx 模型加载、推理和结果输出的正确性

## Capabilities

### New Capabilities
- `audio-persistence`: 录制音频自动保存到 data/audio 目录，文件路径写入数据库 records 表，记录面板支持手动触发识别
- `sherpa-diagnostics`: 独立的 sherpa-onnx 诊断测试脚本，支持用户交互操作，输出详细日志以验证模型加载、音频推理和识别结果

### Modified Capabilities
- `model-management-ui`: 无需修改（拖拽问题属于前端事件处理，不属于模型管理）

## Impact

- **后端 Python 代码**：`py/asr.py`（识别逻辑调试）、`py/storage.py`（数据库字段扩展）、`py/io.py`（音频文件处理/上传修复）
- **前端 Vue 代码**：录制组件（音频保存后处理）、记录面板（手动识别按钮）、拖拽事件处理（修复闪动和浏览器误开）
- **数据库**：`records` 表可能需要新增 `audio_path` 相关字段（如已有则复用）
- **新增文件**：`data/audio/` 目录结构、独立诊断测试脚本
- **依赖**：无新增外部依赖，使用已有的 sherpa-onnx、soundfile 等库
