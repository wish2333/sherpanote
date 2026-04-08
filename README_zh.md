# SherpaNote - AI驱动的语音学习助手

![SherpaNote 截图](reference/preview.png)

[English README](README.md)

SherpaNote 是一款智能语音学习助手，结合了实时语音识别与AI驱动的文本处理功能。录制您的想法、讲座或对话，让 SherpaNote 自动转录并利用AI润色、笔记整理、思维导图和头脑风暴等功能来增强您的内容。

基于 **PyWebVue** 框架构建，SherpaNote 在 Windows、macOS 和 Linux 上提供无缝的桌面体验，同时利用现代 Web 技术为用户界面提供强大支持。

## 🌟 功能特性

### 🎙️ 语音识别
- **实时流式转录**：支持实时部分结果显示
- **离线音频文件转录**：带进度跟踪的完整音频处理
- **多语言支持**：中文、英文及自动检测
- **GPU加速**：支持更快的处理速度
- **多种ASR模型**：包括 Paraformer 和 Whisper 等变体

### 🤖 AI处理
- **文本润色**：优化和改进转录文本
- **智能笔记**：将原始转录转换为结构化笔记
- **思维导图**：从内容生成可视化思维导图
- **头脑风暴**：通过AI生成建议扩展思路
- **流式响应**：实时AI令牌流式传输，即时反馈

### 💾 数据管理
- **持久化存储**：所有记录通过SQLite数据库本地保存
- **版本历史**：跟踪变更并恢复历史版本
- **音频持久化**：录制的音频文件存储在结构化目录中
- **搜索功能**：通过标题或转录文本中的关键词查找记录
- **导入/导出**：支持Markdown、TXT、DOCX和SRT格式

### 🔧 模型管理
- **模型注册表**：浏览可用的ASR模型及详细信息
- **一键安装**：直接从应用内下载和安装模型
- **自定义镜像**：配置自定义下载源以获得更快访问
- **模型验证**：安装后验证模型完整性
- **活跃模型选择**：选择用于流式/离线识别的模型

### 🎨 用户体验
- **响应式设计**：基于Vue 3和Tailwind CSS的美观现代界面
- **深色/浅色模式**：自动主题切换，支持系统偏好检测
- **原生文件对话框**：平台原生的文件和文件夹选择器
- **拖拽操作**：通过拖拽轻松导入音频文件
- **键盘快捷键**：高效的键盘导航工作流

## 🛠️ 技术栈

### 后端 (Python)
- **Python 3.10+**：核心应用逻辑
- **sherpa-onnx**：离线语音识别引擎
- **OpenAI API**：AI文本处理和生成
- **pywebview**：原生桌面窗口管理
- **SQLite**：本地数据持久化
- **uv**：快速的Python包管理和执行工具

### 前端 (Vue.js)
- **Vue 3**：响应式用户界面框架
- **TypeScript**：类型安全的JavaScript开发
- **Vite**：极速开发服务器和构建工具
- **Tailwind CSS**：实用优先的CSS框架
- **DaisyUI**：带有内置主题的美观组件库
- **Pinia**：Vue应用程序的状态管理

### 构建与部署
- **PyInstaller**：桌面应用程序打包
- **Buildozer**：Android APK生成（仅限macOS/Linux）
- **跨平台**：单一代码库支持Windows、macOS、Linux和Android

## 🚀 快速开始

### 先决条件
- **Python 3.10 或更高版本**
- **uv** 包管理器：[安装 uv](https://docs.astral.sh/uv/getting-started/installation/)
- **bun**、**npm** 或 **yarn** 用于前端依赖

### 安装
```bash
# 克隆仓库
git clone https://github.com/your-username/sherpanote.git
cd sherpanote

# 安装依赖并启动开发服务器
uv run dev.py
```

### 开发命令
```bash
# 启动开发环境（Vite + Python 应用）
uv run dev.py

# 仅安装依赖（不启动应用）
uv run dev.py --setup

# 从构建的前端加载（生产预览）
uv run dev.py --no-vite
```

## 📦 构建与打包

### 桌面应用程序
```bash
# 构建目录型应用程序（推荐）
uv run build.py

# 构建单个可执行文件
uv run build.py --onefile

# 构建时捆绑ASR模型（仅目录模式）
uv run build.py --with-models sherpa-onnx-paraformer-zh-small-2024-03-09

# 清理构建产物
uv run build.py --clean
```

### Android APK（仅限macOS/Linux）
```bash
# 构建Android APK
uv run build.py --android
```

> **注意**：Android构建需要macOS或Linux系统。Windows用户可以使用WSL或Docker。

## 🎯 使用指南

### 录制音频
1. 点击主界面中的**录制**按钮
2. 自然说话 - 您将看到实时转录更新
3. 完成后点击**停止**
4. 您的录音将自动保存，包含音频文件和转录文本

### AI处理
1. 从列表中选择任意记录
2. 选择AI模式：**润色**、**笔记**、**思维导图**或**头脑风暴**
3. 点击**处理**以增强您的内容
4. 实时查看AI令牌流式传输的结果

### 管理模型
1. 进入**设置** → **ASR引擎**
2. 在**模型管理**部分浏览可用模型
3. 点击**下载**安装模型
4. 使用下拉菜单设置活跃的流式和离线模型

### 导入与导出
- **导入**：拖拽 `.md` 或 `.txt` 文件，或使用导入按钮
- **导出**：右键点击任意记录并选择导出格式（MD、TXT、DOCX、SRT）

## 📁 项目结构

```
sherpanote/
├── frontend/           # Vue.js 前端应用程序
│   ├── src/            # 源代码
│   │   ├── components/ # Vue 组件
│   │   ├── views/      # 页面视图
│   │   ├── composables/# Vue 组合式函数
│   │   └── stores/     # Pinia 状态存储
├── py/                 # Python 后端模块
│   ├── asr.py          # 语音识别逻辑
│   ├── llm.py          # AI 处理逻辑
│   ├── storage.py      # 数据持久化
│   └── model_manager.py # 模型管理
├── pywebvue/           # PyWebVue 框架核心
├── main.py             # 应用程序入口点
├── dev.py              # 开发启动脚本
├── build.py            # 构建和打包脚本
└── app.spec            # PyInstaller 配置
```

## ⚙️ 配置

SherpaNote 使用存储在SQLite中的持久化配置系统。关键配置选项包括：

- **数据目录**：音频文件和数据库的存储位置
- **ASR设置**：模型目录、采样率、GPU使用、镜像URL
- **AI设置**：OpenAI API密钥、模型选择、温度参数
- **UI偏好**：主题、语言、默认视图

配置可以通过**设置**界面或通过API以编程方式修改。

## 🤝 贡献指南

我们欢迎贡献！以下是参与步骤：

1. **Fork** 仓库
2. **创建**功能分支 (`git checkout -b feature/amazing-feature`)
3. **提交**您的更改 (`git commit -m '添加神奇功能'`)
4. **推送**到分支 (`git push origin feature/amazing-feature`)
5. **打开**拉取请求

### 开发准则
- 遵循现有的代码风格和模式
- 编写有意义的提交消息
- 在可能的情况下为新功能包含测试
- 为新功能更新文档
- 确保跨平台兼容性

### 报告问题
报告bug或请求功能时，请包含：
- 您的操作系统及版本
- Python版本
- 复现问题的步骤
- 期望行为 vs 实际行为
- 任何错误消息或日志

## 📄 许可证

本项目采用MIT许可证 - 详情请参阅 [LICENSE](LICENSE) 文件。

## 🙏 致谢

- **[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)**：离线语音识别工具包
- **[pywebview](https://github.com/r0x0r/pywebview)**：跨平台原生GUI库
- **[Vue.js](https://vuejs.org/)**：渐进式JavaScript框架
- **[Tailwind CSS](https://tailwindcss.com/)**：实用优先的CSS框架
- **[DaisyUI](https://daisyui.com/)**：Tailwind CSS的组件库

---

由 SherpaNote 团队用心打造。快乐学习！