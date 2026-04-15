## dev-1.3.1-pre1

- 功能
  - 目前插件化的whispercpp在win上如何打开cuda支持？
- 优化
  - 如果已经用其他途径安装了ffmpeg，static-ffmpeg按钮无需隐藏，但是点击后需要再确认后才下载并将其路径自动填入自定义路径并保存配置
  - yt-dlp cookie文件下方的文字未设置为小标题而戳出去了
  - 现在llm功能的预设功能的提示词和自定义功能的提示词分别都写在哪里？
  - whispercpp的模型还有什么可选，我希望选择一下，在模型管理器中添加

```
- whisper.cpp 在 Windows 上的 CUDA 支持：目前 whispercpp_registry.py 已经在 BINARIES 中注册了 cuda-11.8 变体（第61-66行），但存在两个问题：1. 安装时无法选择变体 - handleInstallWhisper() 调用 installWhisperBinary() 不传参数，所以默认安装 BLAS  版本（get_default_binary() 优先选 BLAS）  2. whisper.cpp 的 CUDA 二进制会自动使用 GPU不需要额外命令行参数（跟 sherpa-onnx 不同）要启用 CUDA，用户需要安装 cuda-11.8 变体的二进制。目前 UI 没有变体选择器，需要添加。我会在下面一起改。
- LLM 提示词位置
  - 预设功能提示词: py/llm.py 第21-64行的 _PROMPTS 字典（polish/note/mindmap/brainstorm），以及
  _PUNCT_PROMPT（标点恢复）
  - 自定义功能提示词: 通过 py/processing_presets.py 的 ProcessingPresetStore 管理，存储在 SQLite 数据库 data/data.db 的
  ai_processing_presets 表中，前端在设置页的 AI 选项卡下管理
```

  1. whisper.cpp CUDA 支持 (功能)

   功能：whisper.cpp CUDA 支持 + 多版本共存

  - py/whispercpp_registry.py - 重构为多版本架构：
    - 每个变体存储在独立子目录 (data/whisper.cpp/<variant>/)
    - 切换已下载版本时只更新 _active_variant.txt 指针文件，无需重新下载
    - 自动迁移旧的扁平安装到变体目录结构
    - uninstall_binary() 支持删除单个变体或全部
    - get_status() 返回 installed_variants 列表
  - frontend/src/views/SettingsView.vue - 添加变体选择器 UI：
    - 下拉框显示所有可用变体，已下载的标记 [已下载]
    - 安装/切换时区分"下载新版本"和"切换已有版本"，提示语不同
    - 卸载按钮保留
  - frontend/src/types.ts - WhisperBinaryStatus 新增 installed_variants 字段
  - frontend/src/bridge.ts - installWhisperBinary 添加返回类型声明
  - main.py - install_whisper_binary 响应包装为 {success, data} 格式

  优化：static-ffmpeg 按钮逻辑

  - frontend/src/views/SettingsView.vue - 按钮始终可见，已安装时点击需 confirm 确认，下载成功后自动填入路径并保存

  优化：yt-dlp Cookie 描述样式

  - frontend/src/views/SettingsView.vue - <label class="label"> 改为 <p> 修复溢出

  信息：LLM 提示词位置

  - 预设：py/llm.py 的 _PROMPTS 字典

  - 自定义：SQLite ai_processing_presets 表，通过 py/processing_presets.py 管理

  - 修复完成。改动在 frontend/src/components/AiProcessor.vue:52-68：

      - getCustomPrompt() — 当 mode 是内置模式（如 polish）时，也去 processingPresets 中查找 builtin_{mode} 对应的 preset
        并返回其 prompt
      - getPresetId() — 内置模式也返回对应的 builtin_{mode} ID

    这样设置界面编辑内置模式的 prompt 后，AI 处理时就会用编辑后的 prompt，而不是 _PROMPTS 字典的硬编码默认值。

      问题根因： 默认 prompt 存在两处且互相独立 — llm.py 的 _PROMPTS 和 processing_presets.py 的 _BUILTIN_PRESETS。preset 被
       SQLite seed 后即使修改 _PROMPTS 也不会生效。

      修复内容：

      1. py/processing_presets.py — 删除硬编码的 _BUILTIN_PRESETS，改为从 llm._PROMPTS 动态生成默认值（单一来源），新增
        reset_builtins() 方法将所有内置 preset 的 prompt 重置为 _PROMPTS 的当前值
      2. py/main.py — 新增 reset_builtin_presets API 端点
      3. frontend/src/views/SettingsView.vue — 新增"恢复内置默认"按钮和 resetBuiltinPresets() 函数

      现在修改 _PROMPTS 后，点"恢复内置默认"按钮就能把所有内置预设同步到最新硬编码值。

  新增：whisper.cpp 模型

  - py/model_registry.py - 新增 whisper-ggml-large-v3-turbo (1550MB) 和 whisper-ggml-large-v3-turbo-q5_0 (548MB)

### 📝 Commit Message

```
feat(whisper): 添加CUDA支持并实现多版本共存

- 重构whispercpp_registry.py支持多版本架构
- 每个变体存储在独立子目录(data/whisper.cpp/<variant>/)
- 实现变体选择器UI，显示可用变体并标记已下载版本
- 优化安装/切换逻辑，支持下载新版本或切换已有版本
- 添加自动迁移旧版安装到新目录结构的功能
- 修复uninstall_binary()支持删除单个变体或全部
```

### 🚀 Release Notes

```
## 2026-04-15 - 多平台性能优化与界面改进

### ✨ 新增
- Whisper.cpp CUDA支持：Windows用户现在可启用GPU加速大幅提升转写速度
- Whisper.cpp模型选择：支持多个模型版本，可根据需求选择大小和精度
- LLM提示词统一管理：内置提示词可通过设置界面编辑，支持一键恢复默认

### 🐛 修复
- 修复静态FFmpeg按钮在已有安装时不可见的问题
- 修复yt-dlp Cookie描述文本界面溢出显示问题

### ⚡ 优化
- Whispercpp支持多版本共存，安装/切换版本无需重复下载
- AI处理内置模式提示词现在可通过设置界面自定义
```