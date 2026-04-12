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