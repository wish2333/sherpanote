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

- Whisper模型输出格式需要与我们当前的适配（识别时间戳并按照软件当前的格式把时间戳及其对应内容显示出来）

  - 22:30:08 [WARNING] py.whispercpp: Failed to parse whisper.cpp JSON output. Raw output:

    [00:00:00.000 --> 00:00:05.260]  好 现在我们来测试一下测试 测试一条 测试
    [00:00:05.260 --> 00:00:08.640]  对对对

- 添加视频下载转录功能（yt-dlp，优先适配bilibili）