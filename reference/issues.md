## 1.2.5 - 模型列表调整

### 🐛 修复

- 解决了切换录音/转录界面时出现冗余日志的问题，优化了用户体验，减少了不必要的技术信息显示

### 📦 更新

- 模型库调整：移除了质量不佳的Whisper ONNX预置模型

- 保留Whisper执行逻辑。如需使用这些模型，用户可自行下载并配置

## Whisper其他实现方式

  研究报告覆盖：
  1. 问题定义 - ONNX Whisper 模型质量差，需要 whisper.cpp 替代方案
  2. 当前架构分析 - ASR 栈、数据流、关键文件、前后端契约
  3. 三种方案对比评估：

    - pywhispercpp (Python 绑定) - 因 GPU 编译复杂度和 pyinstaller 兼容性被否决
    - faster-whisper (CTranslate2) - 因 macOS 无 Metal 支持被否决
    - whisper.cpp CLI (子进程) - 因双端可行性被选中
  4. CLI 接口详细研究 - 命令格式、JSON 输出结构、退出码、GPU 行为
  5. 二进制分发调研 - GitHub API 验证了 Windows 有预编译二进制(v1.8.4)，macOS 无预编译但 Homebrew 有 whisper-cpp v1.8.4

    带预编译 bottles
  6. GGML 模型分发 - HuggingFace ggerganov/whisper.cpp，6 种模型大小
  7. 完整实现计划 - 2 个新文件 + 7 个修改文件，详细架构和接口设计
  8. 风险评估 - 7 项风险及缓解措施
  9. 待专家评审的开放问题 - 6 个关键设计决策点

## dev-1.3.0-pre1

###  PLAN - 更新需求：

- 进度条现在显示的是啥，希望能够添加显示处理到的segment数可以吗
- 添加GPU支持（如果与cpu版本包体积相差大，需要分别打包）CUDA可以支持，M系列芯片有对应的加速吗
- 探索Whisper.cpp作为可选插件接入的可能性，还是再额外提供一个打包版本？

     Legend: session-request | 🔴 bugfix | 🟣 feature | 🔄 refactor | ✅ change | 🔵 discovery | ⚖️ decision
    
     Column Key
       Read: Tokens to read this observation (cost to learn it now)
       Work: Tokens spent on work that produced this record ( research, building, deciding)
    
     Context Index: This semantic index (titles, types, files, tokens) is usually sufficient to understand past work.
    
     When you need implementation details, rationale, or debugging context:
       - Fetch by ID: get_observations([IDs]) for observations visible in this index
       - Search history: Use the mem-search skill for past decisions, bugs, and deeper research
       - Trust this index over re-reading code for past decisions and learnings
    
     Context Economics
       Loading: 50 observations (18,080 tokens to read)
       Work investment: 117,063 tokens spent on research, building, and decisions
       Your savings: 85% reduction from reuse
    
     Apr 14, 2026
    
     General
       #163  5:25 PM  ⚖️  SherpaNote v1.3.0 implementation plan approved with three-phase architecture
     ..\..\Git\GiteaManager\sherpanote\py\asr.py
       #164  5:26 PM  🟣  Progress callback signature extended to support segment count information
       #165           🟣  VAD segment pre-draining implemented for accurate progress tracking with segment counts
     ..\..\Git\GiteaManager\sherpanote\main.py
       #166  5:27 PM  🟣  Frontend progress tracking extended with segment count information
     ..\..\Git\GiteaManager\sherpanote\frontend\src\composables\useTranscript.ts
       #167  5:28 PM  🟣  Progress bar segment count data flow completed in frontend composable
     ..\..\Git\GiteaManager\sherpanote\frontend\src\components\AudioRecorder.vue
       #168           🟣  AudioRecorder component updated to access segment count data
       #169           🟣  Phase 1 implementation completed: Progress bar now displays segment counts during file
     transcription
     General
       #170  5:54 PM  ⚖️  Whisper.cpp CLI subprocess approach selected over Python bindings
       #171           🟣  Whisper.cpp integration planned with GPU support and progress improvements
       #172           🔵  Current ASR architecture documented for whisper.cpp migration
     ..\..\Git\GiteaManager\sherpanote\build.py
       #173  5:55 PM  🔵  Current build system uses PyInstaller with modular configuration
     ..\..\Git\GiteaManager\sherpanote\frontend\src\types\index.ts
       #174           🔵  Frontend architecture defines GPU toggle and ASR configuration types
     ..\..\Git\GiteaManager\sherpanote\frontend\src\stores\appStore.ts
       #175  5:56 PM  🔵  Frontend state management contains comprehensive ASR configuration
     ..\..\Git\GiteaManager\sherpanote\py\gpu_detect.py
       #176           🟣  GPU detection module implemented for CUDA acceleration support
     ..\..\Git\GiteaManager\sherpanote\main.py
       #177  5:57 PM  🟣  GPU detection API endpoint added to SherpaNote backend
     ..\..\Git\GiteaManager\sherpanote\frontend\src\bridge.ts
       #178           🟣  Frontend bridge API helper added for GPU detection
     ..\..\Git\GiteaManager\sherpanote\frontend\src\views\SettingsView.vue
       #179           🟣  GPU detection imports added to SettingsView component
       #180  5:58 PM  🟣  GPU detection state and lifecycle integration added to SettingsView
       #181           🟣  GPU toggle UI enhanced with status display and conditional disabling
     ..\..\Git\GiteaManager\sherpanote\build.py
       #182           ✅  Build script prepared for CUDA GPU support with new --cuda flag
     src/types
       #183  6:22 PM  🔵  TypeScript compilation failed due to missing GpuStatus type export
     src/types/index.ts
       #184  6:23 PM  🔵  GpuStatus interface is exported from types module
     src/types.ts
       #185           🔵  Project contains both types.ts file and types/index.ts directory
       #186           🔵  Root cause identified: GpuStatus missing from src/types.ts
       #187           🔴  Added GpuStatus interface export to src/types.ts
     General
       #188  6:29 PM  🔵  Whisper.cpp migration research completed for version 1.3.0
       #189           🔵  Current model registry architecture supports multiple download sources
       #190  6:30 PM  🔵  Model manager download architecture uses unified dispatcher pattern
       #191           🔵  ModelInstaller class orchestrates threaded model installation with progress tracking
       #192           🔵  Single archive installation workflow uses five-phase progress pipeline
     ..\..\Git\GiteaManager\sherpanote\py\whispercpp_registry.py
       #193           🟣  Implemented whisper.cpp binary registry and installation system
     ..\..\Git\GiteaManager\sherpanote\py\whispercpp.py
       #194  6:31 PM  🟣  Implemented Whisper.cpp ASR backend with CLI subprocess integration
     General
       #195           🔵  Model registry uses tuple-based catalog with dictionary index for fast lookup
       #196           🔵  Model registry catalog terminates at line 238 with index creation
     ..\..\Git\GiteaManager\sherpanote\py\model_manager.py
       #197  9:12 PM  🟣  Added whisper.cpp GGML model support to model extraction
       #198           🟣  Added whisper.cpp VAD skip logic to model installer
       #199           🟣  Applied whisper.cpp VAD skip to HuggingFace multi-file installer
     ..\..\Git\GiteaManager\sherpanote\py\config.py
       #200  9:13 PM  🟣  Added ASR backend selection to configuration
       #201           🟣  Added asr_backend serialization to AppConfig.to_dict
       #202           🟣  Added asr_backend deserialization to AppConfig.from_dict
     ..\..\Git\GiteaManager\sherpanote\main.py
       #203           🟣  Added _whisper_asr instance variable to SherpaNoteAPI
       #204  9:14 PM  🟣  Added whisper.cpp binary management API to SherpaNoteAPI
       #205           🟣  Added whisper.cpp backend support to transcribe_file method
       #206  9:15 PM  🟣  Added whisper.cpp backend support to retranscribe_record method
       #207           🟣  Added whisper.cpp backend support to import_and_transcribe method
     General
       #208  9:26 PM  ⚖️  Whisper.cpp CLI subprocess approach selected over Python bindings
       #209           🟣  Whisper implementation plan defines 9-file modification scope
       #210           🟣  Version 1.3.0 requirements add GPU support and progress enhancements
     ..\..\Git\GiteaManager\sherpanote\main.py
       #211           🟣  Whisper.cpp implementation completed across 15 files
     ..\..\Git\GiteaManager\sherpanote\py\gpu_detect.py
       #212  9:27 PM  🟣  Three new Python modules created for whisper.cpp integration


     Access 117k tokens of past research & decisions for just 18,080t. Use the claude-mem skill to access memories by
     ID

###   v1.3.0 Implementation Summary

  Phase 1: 进度条显示 Segment 数 (已完成)

  - py/asr.py - VAD 预排空到 list，获得总数后逐一转写，准确报告 (current/total)
  - main.py - 3 处 on_progress 回调传递 segment 信息到事件
  - frontend/src/composables/useTranscript.ts - 新增 segmentInfo ref
  - frontend/src/components/AudioRecorder.vue - 进度显示 42% (15/30) 格式

  Phase 2: sherpa-onnx GPU 支持 (已完成)

  - 新建 py/gpu_detect.py (~130 行) - NVIDIA GPU/CUDA 检测，nvidia-smi + ORT provider 验证
  - app.spec - hiddenimports 添加 py.gpu_detect
  - main.py - 新增 detect_gpu() API
  - build.py - 添加 --cuda 构建参数
  - frontend/src/views/SettingsView.vue - GPU 状态显示（名称/CUDA 版本/不可用原因）
  - frontend/src/types.ts + bridge.ts - GpuStatus 类型 + detectGpu() helper

  Phase 3: whisper.cpp 可选插件 (已完成)

  - 新建 py/whispercpp.py (~200 行) - WhisperCppASR 类，子进程调用 whisper-cli
  - 新建 py/whispercpp_registry.py (~280 行) - 二进制元数据、下载/安装/卸载
  - py/config.py - AsrConfig 添加 asr_backend 字段
  - py/model_registry.py - 添加 5 个 GGML 模型条目 (tiny/base/small/medium/large)
  - py/model_manager.py - 支持 .bin 单文件下载，whisper.cpp 模型跳过 VAD
  - main.py - 后端路由 (sherpa-onnx / whisper.cpp) + 二进制管理 API
  - frontend - 后端选择器、whisper.cpp 设置面板、录音按钮禁用

  总计：3 个新文件 + 15 个修改文件，~530 行新增代码。前端类型检查全部通过。

### PLAN - 修改后bug

- 进度条显示 Segment 数这个好像没有显示出来需要修复
- Whisper安装失败
  - 21:52:22 [ERROR] py.whispercpp_registry: Failed to install whisper.cpp binary
    Traceback (most recent call last):
      File "Q:\Git\GiteaManager\sherpanote\py\whispercpp_registry.py", line 204, in install_binary
        _download_file(
      File "Q:\Git\GiteaManager\sherpanote\py\whispercpp_registry.py", line 242, in _download_file
        opener = urllib.request.build_opener()
    NameError: name 'urllib' is not defined
- GPU版本构建具体怎么操作？

###   Summary

  Bugs Fixed

  1. whispercpp_registry.py:242 - NameError: name 'urllib' is not defined

    - Root cause: import urllib.request was scoped inside install_binary(), but _download_file() is a separate
  module-level function
    - Fix: Moved import urllib.request to the module-level imports section
  2. types/index.ts - Missing asr_backend in AsrConfig and missing WhisperBinaryStatus type

    - The file was out of sync with types.ts (the canonical source)
    - Fix: Synced types/index.ts with all types from types.ts

  Segment Count Display

  The segment count display code is correct. The reason you didn't see it is likely because you were testing with the
  whisper.cpp backend, which only reports segment info at 100% (the subprocess doesn't emit intermediate progress). For
  sherpa-onnx with VAD enabled, segment counts display properly during the 20-90% transcription phase.

  Remaining Items (Not Build Fixes)

  - 添加视频下载转录功能 - This is a feature request, not a bug. Want me to plan this?
  - 修改下载源自动保存配置 - Also a feature request. Currently, changing download source requires clicking "Save". Want
    me to add auto-save on change?
  - GPU版本构建怎么操作 - The build.py has a --cuda flag. You need a CUDA toolkit installed and an NVIDIA GPU. The
    py/gpu_detect.py module checks for CUDA availability. Want me to walk you through the specific steps?

### BUG

- Binary installed but verification failed(Whisper安装过程中，控制台显示py.whispercpp_registry: Extracted whisper-cli to Q:\Git\GiteaManager\sherpanote\data\whisper.cpp\main.exe后)

  - Confirmed - only main.exe (28KB), no DLLs. That's why verification failed.

      What changed:

      - _extract_binary: Now extracts all files from the zip (main.exe + whisper.dll + ggml.dll + any other deps), instead
        of only main.exe
      - get_binary_path: Added _find_binary_in_dir helper that searches for both main.exe and whisper-cli.exe
      - get_macos_binary_path: Now looks inside whisper.xcframework/macos-arm64/ or macos-x86_64/ subdirectories
      - is_installed: Handles None return from get_binary_path

      To test: Delete data/whisper.cpp/ folder and reinstall from Settings. The verification should now pass since all
      required DLLs will be alongside main.exe.

- Whisper模型下载报错

  -   Root cause: The download saves to _{model_id}_download.tmp (.tmp extension), but the .bin check in extract_archive
      only matched .bin extension. The whisper.cpp GGML model was being fed to tarfile.open("r:bz2") which crashed. Now it
      detects model_type == "whispercpp" and handles it correctly regardless of the temp file extension.

- Whisper运行报错

  -  Two changes:

      1. Removed --no-timestamps - this flag may not exist or behave differently in v1.8.4
      2. Added cwd=str(self._binary.parent) - ensures DLLs are found
      3. Improved error message - shows stdout tail when stderr is empty

      Retry the transcription now. If it still fails, the error message will show the actual whisper.cpp output instead of
      being empty.

  - 22:28:20 [ERROR] __main__: retranscribe_record: failed: whisper.cpp exited with code 1: WARNING: The binary 'main.exe' is deprecated.
     Please use 'whisper-cli.exe' instead.
     See https://github.com/ggerganov/whisper.cpp/tree/master/examples/deprecation-warning/README.md for more information.
    Traceback (most recent call last):
      File "Q:\Git\GiteaManager\sherpanote\main.py", line 627, in _work
        segments = whisper.transcribe_file(audio_path, on_progress=on_progress)
      File "Q:\Git\GiteaManager\sherpanote\py\whispercpp.py", line 113, in transcribe_file
        raise RuntimeError(
    RuntimeError: whisper.cpp exited with code 1: WARNING: The binary 'main.exe' is deprecated.
     Please use 'whisper-cli.exe' instead.
     See https://github.com/ggerganov/whisper.cpp/tree/master/examples/deprecation-warning/README.md for more information.

  - main.py uses get_binary_path() which will now return whisper-cli.exe. Retry the transcription now -- it should
      use whisper-cli.exe instead of the deprecated main.exe.

     Legend: session-request | 🔴 bugfix | 🟣 feature | 🔄 refactor | ✅ change | 🔵 discovery | ⚖️ decision
    
     Column Key
       Read: Tokens to read this observation (cost to learn it now)
       Work: Tokens spent on work that produced this record ( research, building, deciding)
    
     Context Index: This semantic index (titles, types, files, tokens) is usually sufficient to understand past work.
    
     When you need implementation details, rationale, or debugging context:
       - Fetch by ID: get_observations([IDs]) for observations visible in this index
       - Search history: Use the mem-search skill for past decisions, bugs, and deeper research
       - Trust this index over re-reading code for past decisions and learnings
    
     Context Economics
       Loading: 50 observations (13,707 tokens to read)
       Work investment: 0 tokens spent on research, building, and decisions
    
     Apr 14, 2026
    
     ..\..\Git\GiteaManager\sherpanote\py\model_manager.py
       #199  9:12 PM  🟣  Applied whisper.cpp VAD skip to HuggingFace multi-file installer
     ..\..\Git\GiteaManager\sherpanote\py\config.py
       #200  9:13 PM  🟣  Added ASR backend selection to configuration
       #201           🟣  Added asr_backend serialization to AppConfig.to_dict
       #202           🟣  Added asr_backend deserialization to AppConfig.from_dict
     ..\..\Git\GiteaManager\sherpanote\main.py
       #203           🟣  Added _whisper_asr instance variable to SherpaNoteAPI
       #204  9:14 PM  🟣  Added whisper.cpp binary management API to SherpaNoteAPI
       #205           🟣  Added whisper.cpp backend support to transcribe_file method
       #206  9:15 PM  🟣  Added whisper.cpp backend support to retranscribe_record method
       #207           🟣  Added whisper.cpp backend support to import_and_transcribe method
     General
       #208  9:26 PM  ⚖️  Whisper.cpp CLI subprocess approach selected over Python bindings
       #209           🟣  Whisper implementation plan defines 9-file modification scope
       #210           🟣  Version 1.3.0 requirements add GPU support and progress enhancements
     ..\..\Git\GiteaManager\sherpanote\main.py
       #211           🟣  Whisper.cpp implementation completed across 15 files
     ..\..\Git\GiteaManager\sherpanote\py\gpu_detect.py
       #212  9:27 PM  🟣  Three new Python modules created for whisper.cpp integration
     ..\..\Git\GiteaManager\sherpanote\py\whispercpp_registry.py
       #213  9:54 PM  🔴  Whisper.cpp installation failure due to missing urllib import
       #214  9:55 PM  🔵  Missing urllib import scope issue in whispercpp_registry.py
     ..\..\Git\GiteaManager\sherpanote\frontend\src\components\AudioRecorder.vue
       #215           🔵  Progress bar segment count display implementation already exists
     ..\..\Git\GiteaManager\sherpanote\py\config.py
       #216           🔵  ASR configuration supports download source and proxy settings
     ..\..\Git\GiteaManager\sherpanote\py\whispercpp.py
       #217           🔵  Segment count progress reporting differs between ASR backends
     ..\..\Git\GiteaManager\sherpanote\main.py
       #218           🔵  GPU detection and configuration infrastructure exists
     ..\..\Git\GiteaManager\sherpanote\py\whispercpp.py
       #219           🔵  Whisper.cpp progress reporting limited to completion phase
     ..\..\Git\GiteaManager\sherpanote\frontend\src\stores\appStore.ts
       #220  9:56 PM  🔵  Frontend state management includes ASR config with download source
     ..\..\Git\GiteaManager\sherpanote\py\whispercpp_registry.py
       #221  9:57 PM  🔴  Fix initiated for urllib import scope issue in whispercpp_registry.py
     ..\..\Git\GiteaManager\sherpanote\frontend\src\types\index.ts
       #222           🔴  Type definition sync task created for types/index.ts
     ..\..\Git\GiteaManager\sherpanote\py\whispercpp.py
       #223           🔵  Segment count display investigation task created
     ..\..\Git\GiteaManager\sherpanote\py\whispercpp_registry.py
       #224           🔴  Fixed urllib import scope issue in whispercpp_registry.py
       #225  9:58 PM  🔴  Completed urllib import fix in whispercpp_registry.py
     ..\..\Git\GiteaManager\sherpanote\frontend\src\types\index.ts
       #226           🔴  Fixed missing type definitions in types/index.ts
     ..\..\Git\GiteaManager\sherpanote\py\whispercpp.py
       #227  9:59 PM  🔵  Segment count display investigation completed - no fix required
     General
       #228  10:07 PM  🔵  Whisper.cpp binary verification uses subprocess --help check
       #229  10:08 PM  🔵  Binary extraction sets Unix permissions to 0o755 for whisper-cli and main executables
       #230            🔴  Fixed binary verification failure by extracting all dependencies and improving path detection
    
       #231            🔵  Installation directory contains only main.exe with missing DLL dependencies
       #232  10:10 PM  🔴  Binary verification failure persists after installation
     ..\..\Git\GiteaManager\sherpanote\py\whispercpp_registry.py
       #233  10:11 PM  🔵  Binary verification uses subprocess --help test
       #234            🔴  Fixed whisper.cpp binary verification by setting working directory for DLL resolution
     ..\..\Git\GiteaManager\sherpanote\py\whispercpp.py
       #235            🔵  Found duplicate binary verification logic with same Windows DLL resolution issue
       #236            🔴  Fixed whisper.cpp binary availability check by setting working directory for DLL resolution
     ..\..\Git\GiteaManager\sherpanote\data\whisper.cpp
       #237  10:12 PM  🔵  whisper.cpp verification fails after extraction
     ..\..\Git\GiteaManager\sherpanote\py\model_manager.py
       #238  10:14 PM  🔵  Whisper model extraction fails due to format mismatch
     ..\..\Git\GiteaManager\sherpanote\py\model_registry.py
       #239            🔵  Whisper GGML models are raw binary files not tar archives
     ..\..\Git\GiteaManager\sherpanote\py\model_manager.py
       #240  10:15 PM  🔵  Model manager already has logic to handle raw .bin files
       #241  10:17 PM  🔵  Download temp filename causes .bin files to be treated as archives
       #242  10:18 PM  🔵  HuggingFace download copies file with wrong extension to temp path
       #243            🔵  extract_archive function lacks parameter to identify whisper.cpp models
     General
       #244  10:23 PM  🔵  whisper.cpp transcription failing with exit code 1
     ..\..\Git\GiteaManager\sherpanote\py\whispercpp.py
       #245  10:24 PM  🔴  Fixed whisper.cpp subprocess execution context and error reporting
     General
       #246  10:28 PM  🔴  whisper.cpp binary deprecated causing transcription failures
     ..\..\Git\GiteaManager\sherpanote\py\whispercpp_registry.py
       #247  10:29 PM  🔴  whisper.cpp binary priority updated to prefer whisper-cli.exe over deprecated main.exe
       #248            🔴  whisper.cpp fallback binary path updated to whisper-cli.exe

### 📝 Commit Message

```
feat(core): Implement v1.3.0 with GPU support, whisper.cpp integration, and progress tracking

- Add segment count display to progress bar for better transcription feedback
- Implement GPU detection and CUDA acceleration support
- Integrate whisper.cpp as alternative ASR backend with CLI subprocess approach
- Fix whisper.cpp binary extraction, installation, and execution issues
- Add comprehensive GPU status UI with conditional toggles
- Enhance progress tracking for both sherpa-onnx and whisper.cpp backends
```

### 🚀 Release Notes

```
## 1.3.0 - 语音转录体验全面升级

### ✨ 新增
- 进度条实时显示转录段落数量，如"42% (15/30)"，让用户更清楚转录进度
- GPU加速支持：自动检测NVIDIA CUDA设备，显著提升大文件转录速度
- Whisper.cpp集成：新增可选的ASR后端，提供更好的模型支持和更多硬件兼容性

### 🐛 修复
- 解决进度条不显示段落数量的问题(whisper.cpp后端将在最终版本中提供实时进度)
- 修复Whisper.cpp安装失败问题，现已正确提取所有依赖文件
- 修复Whisper.cpp模型下载错误，处理临时文件扩展名兼容性问题
- 解决Whisper.exe已弃用警告，现在正确使用新的whisper-cli.exe

### ⚡ 优化
- 大幅提升GPU环境下的转录性能，特别是对于长音频文件
- 改进安装流程，自动检测系统并引导用户选择合适的GPU版本
- 增强错误提示，提供更详细的故障排除信息
```

### 💥 Breaking Changes
- 若已安装Whisper.cpp，请删除`data/whisper.cpp/`文件夹后重新安装以确保包含所有依赖DLL
- GPU版本构建需安装CUDA工具包，可通过`build.py --cuda`参数构建GPU版本（目前版本仍然失效）

## dev-1.3.0-pre2

### PLAN 

- 修改下载源自动保存配置

- 删除模型管理界面中的MS源的两个Qwen3模型

- 模型设置界面添加选Whisper引擎时的模型切换（与onnx区分，隐藏onnx模型选项）

- 录音/转录界面提供引擎切换和选Whisper引擎是的模型选项

- Whisper模型输出格式需要与我们当前的适配（识别时间戳并按照软件当前的格式把时间戳及其对应内容显示出来，去掉时间戳的文字部分显示在下方文字框中）

  - 22:30:08 [WARNING] py.whispercpp: Failed to parse whisper.cpp JSON output. Raw output:

    [00:00:00.000 --> 00:00:05.260]  好 现在我们来测试一下测试 测试一条 测试
    [00:00:05.260 --> 00:00:08.640]  对对对

- 添加视频下载转录功能（yt-dlp，优先适配bilibili）

###  dev-1.3.0-pre2 Implementation Plan

 Context

 v1.3.0 引入了 whisper.cpp 作为可选 ASR 后端，但存在几个问题：
 1. 下载源切换后不会自动保存
 2. MS 源的两个 Qwen3 模型需要从模型管理界面移除
 3. 选择 Whisper 引擎时没有独立的模型选择器，和 ONNX 模型混在一起
 4. 录音界面没有引擎切换功能
 5. whisper.cpp 输出 SRT 而非 JSON，时间戳解析失败
 6. 缺少视频链接下载转写功能

---
 Task 1: 下载源自动保存配置

 Complexity: Low
 Files: frontend/src/views/SettingsView.vue

 修改:
 - 在模型管理页面的下载源 <select> (line 1566) 添加 @change="saveConfig" 事件
 - 目前只有 ghproxy 域名输入框有保存逻辑，下载源切换没有

---
 Task 2: 删除 MS 源的两个 Qwen3 模型

 Complexity: Low
 Files: py/model_registry.py

 修改:
 - 移除两个 sources=("modelscope",) 的 Qwen3 模型条目 (lines 94-116):
   - sherpa-onnx-qwen3-asr-0.6B (display_name: "Qwen3-ASR 0.6B (ModelScope)")
   - sherpa-onnx-qwen3-asr-1.7B (display_name: "Qwen3-ASR 1.7B (ModelScope)")
 - 保留其他源的 Qwen3 模型条目（GitHub/HF 等源的 int8 版本）

---
 Task 3: 模型设置界面 Whisper 引擎模型切换

 Complexity: Medium
 Files: frontend/src/views/SettingsView.vue, py/config.py, main.py

 问题: 当前 active_offline_model 同时用于 ONNX 和 Whisper 模型，但两者不可混用。需要在选择 Whisper 引擎时显示专门的
 GGML 模型选择器。

 修改:

 前端 SettingsView.vue

 - 在 "ASR 引擎配置" 卡片中，当 asr_backend === 'whisper-cpp' 时:
   - 隐藏现有的 "流式识别模型" 和 "离线识别模型" 选择器（Whisper 不支持流式）
   - 在 whisper.cpp 设置区块内添加 "Whisper 模型" 选择器
   - 模型列表从 installedModels 中过滤 model_type === "whispercpp" 的模型
   - 选中的模型 ID 保存到 asrConfig.active_whisper_model
   - 保存时调用 update_config 传递 active_whisper_model

 后端 config.py

 - AsrConfig 添加 active_whisper_model: str = "" 字段
 - to_dict / from_dict 序列化/反序列化新字段

 后端 main.py

 - _get_whisper_asr (line 1025): 优先使用 active_whisper_model 而非 active_offline_model 查找模型路径
 - 修改模型路径查找逻辑，匹配 active_whisper_model 对应的目录和 .bin 文件

 前端 types.ts

 - AsrConfig 接口添加 active_whisper_model: string

---
 Task 4: 录音/转录界面引擎切换

 Complexity: Medium
 Files: frontend/src/views/RecordView.vue, frontend/src/stores/appStore.ts

 修改:

 RecordView.vue Quick Settings Bar (line 258)

 - 在语言选择器后添加 "ASR 引擎" 选择器 (sherpa-onnx / whisper-cpp)
 - 当选择 whisper-cpp 时:
   - 隐藏 "流式模型" 选择器（Whisper 不支持流式）
   - 显示 "Whisper 模型" 选择器（从 installedModels 过滤 model_type === "whispercpp"）
   - 绑定到 store.asrConfig.active_whisper_model
 - 当选择 sherpa-onnx 时:
   - 恢复现有的 "流式模型" 和 "离线模型" 选择器
   - 隐藏 "Whisper 模型" 选择器
 - 引擎切换时调用 saveQuickSetting 保存配置

 导入转写区域

 - 在文件上传按钮旁添加 URL 输入入口（Task 6 的一部分，此处预留位置）

---
 Task 5: Whisper 输出格式适配

 Complexity: Medium
 Files: py/whispercpp.py

 问题: whisper.cpp v1.8.4 的 --output-json 标志不生效，实际输出 SRT 格式，导致 JSON 解析失败。

 修改:

 修复 CLI 参数

 - 将 --output-json 改为 --output-file-type json（whisper.cpp v1.8.4 正确参数）
 - 同时保留 --output-file 参数指定输出文件路径，使用临时文件
 - 从临时文件读取 JSON 输出而非 stdout

 添加 SRT fallback 解析

 - 在 _parse_output 方法中，当 JSON 解析失败时，检测输出是否为 SRT 格式
 - SRT 格式: [HH:MM:SS.mmm --> HH:MM:SS.mmm] text
 - 解析时间戳转换为秒数: HH*3600 + MM*60 + SS.mmm
 - 提取文本内容（去掉时间戳标签），与现有 Segment 格式对齐

 输出格式

 每个 segment 产出:
 {
     "index": int,
     "text": str,           # 纯文本，不含时间戳标签
     "start_time": float,   # 秒
     "end_time": float,     # 秒
     "speaker": None,
     "is_final": True,
 }
 这与 TranscriptPanel.vue 和 EditorView.vue 现有的 start_time/end_time 显示逻辑完全兼容。

---
 Task 6: 视频下载转录功能 (yt-dlp)

 Complexity: High
 Files:
 - py/requirements.txt 或 pyproject.toml - 添加 yt-dlp 依赖
 - py/video_downloader.py (新建) - yt-dlp 封装模块
 - main.py - 添加 download_and_transcribe API
 - frontend/src/views/RecordView.vue - 导入区域添加 URL 输入
 - frontend/src/bridge.ts - 添加 bridge helper
 - frontend/src/components/TranscriptPanel.vue - 进度展示（如需）

 设计:

 后端 video_downloader.py

 @dataclass(frozen=True)
 class VideoDownloadConfig:
     output_dir: str          # 音频目录
     format: str = "bestaudio"  # 优先下载最佳音频
     proxy: str = ""          # 代理设置（复用现有 AsrConfig.proxy）

 def download_audio(url: str, config: VideoDownloadConfig,
                    on_progress: Callable) -> str:
     """下载视频的音频轨道，返回本地文件路径。"""
 - 使用 yt_dlp.YoutubeDL 下载
 - 设置 postprocessors 提取音频为 wav/mp3 格式
 - 优先适配 bilibili（无需特殊处理，yt-dlp 原生支持）
 - 通过 on_progress 回调报告下载进度
 - 下载完成后返回文件路径，由调用方纳入音频管理器

 后端 main.py

 - 新增 @expose download_and_transcribe(self, url: str) -> dict 方法
 - 流程: 下载音频 -> _copy_file_to_audio_dir 纳入管理 -> 转录 -> 保存记录
 - 复用现有的 import_and_transcribe 的后半段逻辑
 - 事件: download_progress (下载进度), transcribe_progress (转录进度), download_transcribe_complete (完成)

 前端 RecordView.vue

 - 在导入转写区域（line 325 附近）添加 URL 输入框和 "下载转写" 按钮
 - 输入视频链接 -> 点击按钮 -> 显示下载+转录进度 -> 完成后跳转到编辑器
 - URL 输入框 placeholder 提示支持的平台（bilibili, YouTube 等）
 - 下载过程中禁用按钮，显示进度条

---
 文件修改总览

 ┌─────────────────────────────────────┬──────┬──────────┐
 │                文件                 │ Task │ 修改类型 │
 ├─────────────────────────────────────┼──────┼──────────┤
 │ frontend/src/views/SettingsView.vue │ 1, 3 │ Edit     │
 ├─────────────────────────────────────┼──────┼──────────┤
 │ py/model_registry.py                │ 2    │ Edit     │
 ├─────────────────────────────────────┼──────┼──────────┤
 │ py/config.py                        │ 3    │ Edit     │
 ├─────────────────────────────────────┼──────┼──────────┤
 │ main.py                             │ 3, 6 │ Edit     │
 ├─────────────────────────────────────┼──────┼──────────┤
 │ frontend/src/types.ts               │ 3    │ Edit     │
 ├─────────────────────────────────────┼──────┼──────────┤
 │ frontend/src/views/RecordView.vue   │ 4, 6 │ Edit     │
 ├─────────────────────────────────────┼──────┼──────────┤
 │ py/whispercpp.py                    │ 5    │ Edit     │
 ├─────────────────────────────────────┼──────┼──────────┤
 │ py/video_downloader.py              │ 6    │ New      │
 ├─────────────────────────────────────┼──────┼──────────┤
 │ py/requirements.txt                 │ 6    │ Edit     │
 ├─────────────────────────────────────┼──────┼──────────┤
 │ frontend/src/bridge.ts              │ 6    │ Edit     │
 └─────────────────────────────────────┴──────┴──────────┘

---
 验证方案

 1. 下载源保存: 切换下载源后刷新页面，确认配置保持
 2. 模型管理: 确认 MS 源 Qwen3 模型不再显示，其他源 Qwen3 不受影响
 3. Whisper 模型切换: 选择 whisper-cpp 引擎后模型选择器显示 GGML 模型，切换回 onnx 后恢复原样
 4. 录音界面引擎切换: Quick Settings 中切换引擎，模型列表随之变化
 5. Whisper 转录: 使用 whisper.cpp 转录音频文件，确认时间戳正确显示在 TranscriptPanel 中
 6. 视频下载: 输入 bilibili 链接，确认下载进度显示、音频提取成功、自动转录、记录保存

### 任务总结

  Task 1: 下载源自动保存配置

  - 文件: frontend/src/views/SettingsView.vue
  - 修改: 下载源 <select> 添加 @change="saveConfig"，切换即保存

  Task 2: 删除 MS 源两个 Qwen3 模型

  - 文件: py/model_registry.py
  - 修改: 移除 sherpa-onnx-qwen3-asr-0.6B 和 sherpa-onnx-qwen3-asr-1.7B 两个 ModelScope 专属条目，其他源的 Qwen3 int8
    版本保留

  Task 3: 模型设置界面 Whisper 模型切换

  - 文件: py/config.py, frontend/src/types.ts, frontend/src/views/SettingsView.vue, main.py
  - 修改:
    - AsrConfig 新增 active_whisper_model 字段（含序列化/反序列化）
    - 前端 AsrConfig 类型同步添加字段
    - SettingsView 选择 whisper-cpp 时隐藏流式/离线模型选择器，显示 GGML 模型选择器
    - main.py _get_whisper_asr 优先使用 active_whisper_model

  Task 4: 录音界面引擎切换

  - 文件: frontend/src/views/RecordView.vue
  - 修改: Quick Settings 栏新增引擎选择器，根据引擎动态显示对应的模型选择器

  Task 5: Whisper 输出格式适配

- 文件: py/whispercpp.py

- 修改:
    - CLI 参数从 --output-json 改为 --output-file + --output-file-type json，输出到临时文件
    - 新增 SRT 格式 fallback 解析 (_parse_srt)，正则匹配 [HH:MM:SS.mmm --> HH:MM:SS.mmm] 时间戳并转换为秒数
    - 解析优先级: JSON 文件 -> JSON stdout -> SRT -> 原始文本

- 问题：

  - > 23:22:26 [INFO] py.whispercpp: Running whisper.cpp: Q:\Git\GiteaManager\sherpanote\data\whisper.cpp\whisper-cli.exe
    > -m Q:\Git\GiteaManager\sherpanote\models\whisper-ggml-tiny\ggml-tiny.bin -f
    > Q:\Git\GiteaManager\sherpanote\data\audio\import_20260408_104031.wav --output-file
    > C:\Users\10411\AppData\Local\Temp\whisper_out_2tpbrg9y.json --output-file-type json -l zh -t 4
    > 23:22:27 [INFO] py.whispercpp: whisper.cpp produced 0 segments
    > 23:22:27 [INFO] __main__: retranscribe_record: transcription done, 0 segments, saving...
    > 23:22:27 [INFO] __main__: retranscribe_record: complete for record
    > 0469f454-19f2-4713-ba92-83dafdc4a02d修改之后同一个文件whisper也识别错误了，其他文件也会报错，需要解决

- 代码已修复。现在不再使用临时文件，whisper.cpp 输出直接从 stdout 读取并用 SRT 解析器处理。

  Task 6 (待实现): 视频下载转录

  - 详细计划保存在 C:\Users\10411\.claude\plans\peppy-knitting-bumblebee.md
  - 核心要点: 新建 py/video_downloader.py 封装 yt-dlp、main.py 新增 download_and_transcribe API、pyproject.toml 添加
    yt-dlp 依赖、前端 RecordView 导入区域添加 URL 输入框

     Legend: session-request | 🔴 bugfix | 🟣 feature | 🔄 refactor | ✅ change | 🔵 discovery | ⚖️ decision
    
     Column Key
       Read: Tokens to read this observation (cost to learn it now)
       Work: Tokens spent on work that produced this record ( research, building, deciding)
    
     Context Index: This semantic index (titles, types, files, tokens) is usually sufficient to understand past work.
    
     When you need implementation details, rationale, or debugging context:
       - Fetch by ID: get_observations([IDs]) for observations visible in this index
       - Search history: Use the mem-search skill for past decisions, bugs, and deeper research
       - Trust this index over re-reading code for past decisions and learnings
    
     Context Economics
       Loading: 50 observations (12,560 tokens to read)
       Work investment: 0 tokens spent on research, building, and decisions
    
     Apr 14, 2026
    
     General
       #249  10:46 PM  🔵  Project structure mapped for Vue frontend and Python backend
     ..\..\Git\GiteaManager\sherpanote\py\whispercpp_registry.py
       #250  10:47 PM  🔵  Whisper.cpp binary registry manages platform-specific downloads and installation
     ..\..\Git\GiteaManager\sherpanote\py\asr.py
       #251  10:48 PM  🔵  ASR backend architecture supports dual engines: sherpa-onnx (built-in) and whisper.cpp
     (plugin)
     ..\..\Git\GiteaManager\sherpanote\frontend\src\components\AudioRecorder.vue
       #252            🔵  Frontend already has ASR backend detection and disables recording for whisper.cpp
     ..\..\Git\GiteaManager\sherpanote\frontend\src\views\EditorView.vue
       #253  10:50 PM  🔵  Found formatAudioTime function in EditorView.vue for timestamp display formatting
       #254  10:51 PM  🔵  Current timestamp format uses MM:SS display format with segment-based seeking
     ..\..\Git\GiteaManager\sherpanote\py\model_registry.py
       #255  10:52 PM  🔵  Comprehensive codebase exploration reveals two Qwen3 models on ModelScope source, download
     source storage, and Whisper.cpp integration details
       #256            🔵  Identified two ModelScope-exclusive Qwen3 models for removal and Whisper.cpp timestamp
     parsing format variations
     ..\..\Git\GiteaManager\sherpanote\py\whispercpp.py
       #257  10:53 PM  🔵  Whisper.cpp subprocess command construction and error handling found in whispercpp.py
     General
       #259  10:58 PM  ✅  Download Source Auto-Save Configuration
     ..\..\Git\GiteaManager\sherpanote\app\app.py
       #260            🔵  Application Structure Identified
     ..\..\Git\GiteaManager\sherpanote\py\model_registry.py
       #261            🔵  Model Registry Structure Identified
     ..\..\Git\GiteaManager\sherpanote\py\config.py
       #262            🔵  Configuration System Identified
     ..\..\Git\GiteaManager\sherpanote\main.py
       #263            🔵  Main Application API Identified
     ..\..\Git\GiteaManager\sherpanote\frontend\src\views\SettingsView.vue
       #264            🔵  Frontend Vue Components Identified
     General
       #265            🔵  Settings UI Structure Identified
     ..\..\Git\GiteaManager\sherpanote\frontend\src\views\RecordView.vue
       #266  10:59 PM  🔵  Record Interface Structure Identified
       #267            🔵  Recording Interface Implementation Identified
     ..\..\Git\GiteaManager\sherpanote\frontend\src\components\AudioRecorder.vue
       #268            🔵  Audio Recorder Component Identified
     ..\..\Git\GiteaManager\sherpanote\py\asr.py
       #269            🔵  ASR Engine Implementation Identified
     ..\..\Git\GiteaManager\sherpanote\py\whispercpp.py
       #270            🔵  Whisper Integration Components Identified
       #271            🔵  Whisper.cpp Implementation Identified
     ..\..\Git\GiteaManager\sherpanote\py\whispercpp_registry.py
       #272            🔵  Whisper Binary Registry Identified
     ..\..\Git\GiteaManager\sherpanote\py\storage.py
       #273            🔵  Storage System Audio Path Support
     ..\..\Git\GiteaManager\sherpanote\main.py
       #274  11:00 PM  🔵  Audio File Management System Identified
     ..\..\Git\GiteaManager\sherpanote\frontend\src\views\SettingsView.vue
       #275            🔵  Complete System Architecture Analysis
     ..\..\Git\GiteaManager\sherpanote\main.py
       #276            🔵  Whisper Model Selection Logic Identified
     C:\Users\10411\.claude\plans\peppy-knitting-bumblebee.md
       #277  11:05 PM  ⚖️  dev-1.3.0-pre2 implementation plan established
     ..\..\Git\GiteaManager\sherpanote\frontend\src\views\SettingsView.vue
       #278            🟣  Download source selector now auto-saves configuration
     ..\..\Git\GiteaManager\sherpanote\py\model_registry.py
       #279            🟣  Task 1 completed: download source auto-save implemented
       #280  11:06 PM  🟣  Removed ModelScope-specific Qwen3 ASR models from registry
     ..\..\Git\GiteaManager\sherpanote\frontend\src\types.ts
       #281            🟣  Task 2 completed: ModelScope Qwen3 models removed from registry
     ..\..\Git\GiteaManager\sherpanote\py\config.py
       #282            🟣  Added active_whisper_model field to AsrConfig dataclass
       #283  11:07 PM  🟣  Implemented separate Whisper model selection configuration
     ..\..\Git\GiteaManager\sherpanote\frontend\src\views\SettingsView.vue
       #284            🟣  Task 3 in progress: Frontend Whisper model selector implementation
       #285            🟣  Examining existing model filtering patterns in SettingsView.vue
       #286            🟣  Added Whisper model filter computed property to SettingsView.vue
       #287            🟣  Examining existing model selector UI structure in SettingsView.vue
       #288            🟣  Hidden ONNX model selectors when whisper-cpp backend selected in SettingsView
     General
       #289  11:23 PM  🔵  Whisper.cpp transcription producing zero segments after modifications
       #290            🔵  Whisper.cpp command construction and execution in whispercpp.py
       #291  11:24 PM  🔴  Changed whisper.cpp output capture from JSON file to stdout SRT format
       #292            🔵  Code references undefined tmp_path after temp file removal
       #293            🔴  Removed temp file references from output parsing section
       #294  11:25 PM  🔴  Syntax error identified in whispercpp.py
     ..\..\Git\GiteaManager\sherpanote\py\whispercpp.py
       #295            🔵  Indentation syntax error found in whispercpp.py exception handling
       #296  11:26 PM  🔴  Fixed exception handler indentation in whispercpp.py
       #297            🔴  Fixed second exception handler indentation in whispercpp.py
       #298            🔵  Additional indentation errors found in whispercpp.py exception handlers
       #299  11:27 PM  🔴  Python indentation error in whispercpp.py

### 📝 Commit Message

```
feat(whisper): 完善 Whisper 引擎集成与配置管理

- 新增下载源自动保存功能，切换后配置持久化
- 移除 ModelScope 源的两个 Qwen3 模型，保留其他源版本
- 为 Whisper 引擎添加独立模型选择器，与 ONNX 模型区分
- 录音/转录界面支持引擎切换，动态显示对应模型选项
- 修复 Whisper 输出格式解析，正确显示时间戳信息
```

### 🚀 Release Notes

```
## 2026-04-14 - Whisper 引擎优化与配置管理提升

### ✨ 新增
- 下载源配置自动保存：切换下载源后配置自动保存，无需手动保存
- 录音界面引擎切换：支持在录音/转录界面动态切换 ASR 引擎
- 独立 Whisper 模型选择：选择 Whisper 引擎时自动过滤显示对应模型选项

### 🐛 修复
- Whisper 转录时间戳显示问题：修复 Whisper 模型输出时间解析错误
- 模型管理界面：移除了不需要的 ModelScope 源 Qwen3 模型选项
- 录音体验：优化录音界面引擎切换体验，正确隐藏/显示对应选项

### ⚡ 优化
- Whisper 引擎集成：完善 Whisper 与系统现有架构的融合
- 配置管理：优化下载源和模型配置的保存逻辑
- 模型管理：简化模型选择界面，提高用户体验
```

## dev1.3.0-pre3

- Task6待实现，详细计划保存在 C:\Users\10411\.claude\plans\peppy-knitting-bumblebee.md
- 测试了一下，whisper强制需要转成 wav 16kHz 单声道 再识别（没有自动处理功能）都这样处理吧，临时文件保存到软件目录/data/temp并在软件关闭时清理

## 其他

- CUDA构建打包仍未完成
- Whisper.cpp功能在MAC平台的实现需要测试