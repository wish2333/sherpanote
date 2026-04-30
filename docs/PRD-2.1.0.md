# OCR 系统升级 v2.1.0（修订版）产品需求文档

**版本**：2.1.0-rev1  
**状态**：草案  
**最后更新**：2026-04-29  

---

## 1. 修订历史

| 版本       | 日期       | 作者       | 变更说明                                                     |
| ---------- | ---------- | ---------- | ------------------------------------------------------------ |
| 2.1.0-rev1 | 2026-04-29 | 审计后修订 | 集成审计意见，重写插件运行时架构、完善文本检测、扩充无文本层处理、强化 Java 检测、改进 UI 与输出标准化 |

---

## 2. 目标与背景

### 2.1 目标
将现有单一 PP-OCR 引擎升级为**多后端、带决策树的智能文档提取系统**：
- 图像：保持 PP-OCR (RapidOCR)
- PDF：自动检测文本层，提供默认轻量方案与可选高级引擎
- Office 文档：新支持 DOCX/PPTX/XLSX，通过轻量级规则引擎提取

同时确保桌面应用打包体积可控、运行时环境封闭、依赖隔离，且所有后端均可按需安装，无需用户手动配置 Python 环境。

### 2.2 关键驱动
- 原系统对文本型 PDF 仍执行 OCR，效率低、质量差
- 缺乏 Office 文档直接提取能力
- 用户希望按需选用高质量布局/表格提取（opendataloader-pdf, docling），但不强制打包
- 需要解决插件运行时 Python 解释器来源、依赖隔离和跨平台一致性

---

## 3. 核心决策树（修订版）

```
[输入文件]
  |-- 图像 (PNG/JPG/BMP/TIFF/WebP) --> PP-OCR (不变)
  |
  |-- Office (DOCX/PPTX/XLSX) --> markitdown (原生支持)
  |
  |-- PDF
        |
        +-- 文本层检测* (见4.1)
              |
              +-- [无文本层] (扫描件/纯图 PDF)
              |     |-- 默认: PP-OCR (PDF 转图像 → OCR)
              |     +-- 可选: docling (如已安装，且启用其 OCR 后端)
              |
              +-- [有文本层]
                    |-- 默认: markitdown (纯 Python，无模型)
                    |-- 可选: opendataloader-pdf (需 Java 11+)
                    |-- 可选: docling (布局/表格增强)
                    +-- 回退: PP-OCR (始终可用)
```

*\* 文本层检测使用 pdfplumber 提取前 3 页文本，累积字符数 > 50（可配置），并提供用户手动覆写入口。*

**关键变更**：
- 无文本层 PDF 增加 docling 作为可选后端，以利用其 OCR 与布局能力
- 文本层检测改用 pdfplumber（MIT 协议），放弃 PyMuPDF，规避 AGPL 风险
- 检测算法增强：多页累计判断，支持手动标记

---

## 4. 详细功能需求

### 4.1 文本层检测（新设计）

**实现方式**：使用 `pdfplumber`（markitdown 的现有依赖）逐页提取文本，计算前 N 页（默认 3，可配置）的累积可见字符数。

**判定规则**：
- 累计字符数 ≤ 阈值（默认 50）：判定为**无文本层**
- 累计字符数 > 阈值：判定为**有文本层**

**特殊处理**：
- 全部页面字符数极少但文件嵌入了字体/文字编码，可能是文本型但内容被误判，用户可在设置中强制指定“有文本层”
- 旋转文字、多栏仍可能提取出部分字符，阈值足够低可容错
- 若 pdfplumber 无法打开文件，回退为“无文本层”并提示用户

**UI 交互**：
- 文档处理前自动检测，结果记录于日志
- 在“文档信息”面板显示检测结果，并提供“手动覆写”开关（强制有/无文本层）

### 4.2 各后端能力与使用条件

| 后端                   | 处理范围                               | 默认/可选 | 环境要求                       | 输出         |
| ---------------------- | -------------------------------------- | --------- | ------------------------------ | ------------ |
| **PP-OCR (RapidOCR)**  | 图像、无文本层 PDF（扫描件）           | 默认      | 已有模型（~200MB）             | 统一中间格式 |
| **markitdown**         | 有文本层 PDF、Office 文档              | 默认      | 纯 Python，0 模型              | 统一中间格式 |
| **opendataloader-pdf** | 有文本层 PDF                           | 可选      | Java 11+，插件 venv            | 统一中间格式 |
| **docling**            | 有文本层 PDF、无文本层 PDF（OCR 模式） | 可选      | 插件 venv，首次下载模型 ~1.5GB | 统一中间格式 |

### 4.3 输出标准化
所有后端产生的原始结果（markdown、JSON、文本）必须经过适配器转换为**统一中间结构**：

```python
@dataclass
class ExtractedDocument:
    markdown: str              # 主文本内容 (GFM)
    metadata: dict             # 页数、作者、创建日期等
    tables: list[Table]        # 表格结构化数据（可选）
    images: list[ImageRef]     # 内嵌图片引用（可选）
    raw_format: str            # 原始格式标识（用于问题复现）
```

下游 UI/导出模块仅消费 `ExtractedDocument`，实现后端完全解耦。

---

## 5. 插件运行时架构（核心解决审计问题）

### 5.1 总体原则
- **子进程隔离**：所有可选后端运行在独立 Python 子进程中，通过 stdin/stdout/stderr 交换 JSON，杜绝依赖冲突
- **嵌入式 Python 解释器**：应用包内携带 Python 独立构建版（如 `python-build-standalone`），用于创建插件 venv，无需用户安装 Python
- **统一 venv 管理**：所有可选后端共用同一个插件 venv，按需安装包

### 5.2 运行时目录布局

```
app_dir/
  SherpaNote.exe             # 主应用入口
  _internal/                 # PyInstaller frozen 环境（主应用依赖）
  uv                         # 捆绑的 uv 独立二进制
  python/                    # 捆绑的 Python 独立构建版
    python.exe               # python-build-standalone 提供
    ...                      # 相关 so/dll
  data/
    plugins/
      .venv/                 # 由捆绑 python 创建的虚拟环境
        bin/
            python           # 插件解释器
        lib/site-packages/
            docling/         # 按需安装
            opendataloader-pdf/
```

**关键决定**：
- `python-build-standalone` 大小约 30 MB，随应用分发，保证创建 venv 时 Python 版本与主应用一致
- 开发环境也可使用系统 Python，但打包后必须依赖捆绑版本

### 5.3 插件子进程通信协议
插件后端以 CLI 形式提供，每个后端实现一个简单的入口脚本（由应用生成或后端自身提供封装）。

**调用示例（docling）**：
```bash
# 激活 venv，运行标准化包装器
./data/plugins/.venv/bin/python -m sherpanote.plugins.docling_runner \
    --input "file.pdf" \
    --method "text_layer" \      # 或 "ocr"
    --output-json "result.json"
```

**包装器职责**：
- 接收参数，调用真实后端 API
- 输出标准 JSON `{"success": true, "result": ExtractedDocument_as_dict}`
- 错误时输出 `{"success": false, "error": "...", "traceback": "..."}`

主进程解析 JSON，转换为 `ExtractedDocument`。超时、异常均可捕获。

### 5.4 插件安装与检测流程

```
用户选择“启用 docling”
  → 检查插件 venv 是否存在？ 否 → 使用捆绑 python 创建 venv
  → 检查包是否已安装 (uv pip list)
    否 → 显示对话框“需下载 ~500MB 包 + ~1.5GB 模型，继续？”
        确认 → 进度条显示 uv pip install 输出
            安装后 → 询问是否立即下载模型（可选预下载）
  → 安装完成，设置状态为已启用
  → 后续处理直接调用子进程
```

**卸载**：移除 venv 中对应包；全部可选后端停用后，可清空整个插件 venv。

### 5.5 Java 运行时检测 (opendataloader-pdf)
**增强检测逻辑**：
1. 检查环境变量 `JAVA_HOME` → 找到 `java` 二进制
2. 检查系统 PATH 中的 `java`
3. 搜索常见安装路径（Windows: `Program Files\Java`, `Program Files\Eclipse Adoptium` 等；macOS: `/Library/Java/JavaVirtualMachines`；Linux: `/usr/lib/jvm`）
4. 用户可在设置界面手动指定 `java` 可执行文件完整路径

**版本校验**：执行 `java -version` 解析输出，要求大版本 >= 11。格式：`"11.0.20"` → 提取首数字。

**未检测到时的 UI**：
- 设置项灰显，提示“未检测到 Java 11+，请安装或指定路径”
- 提供下载指引链接（Adoptium 等）

### 5.6 PPP-OCR 模型管理（不变）
现有 `py/ocr.py` 的 RapidOCR 模型管理保持不变。docling 自带的 OCR 后端可能需要单独模型，但可尝试配置 docling 使用已有的 RapidOCR 模型目录，以避免重复下载。此优化作为可选项，第一版允许 docling 自行管理。

---

## 6. 用户界面（UI/UX）设计

### 6.1 设置界面扩展
在“OCR / 文档提取”设置面板中增加：

**PDF 处理方式** 区域：
- **文本层 PDF 默认引擎**：下拉选择（markitdown / opendataloader-pdf / docling / PP-OCR），每个选项标注所需环境
- **无文本层 PDF 默认引擎**：下拉选择（PP-OCR / docling），docling 灰显若未安装
- **可选后端管理** 板块：
  - 每行一个后端，显示安装状态（未安装 / 已安装 / 下载中），版本信息
  - 按钮：安装 / 卸载 / 更新
  - 点击安装弹出详情对话框（所需磁盘空间、网络要求）
- **Java 路径**：文本框 + 浏览按钮，用于 opendataloader-pdf
- **docling 模型目录**：可指定自定义 `artifacts_path`，支持离线模型包
- **文本层检测** 高级选项：累积页数、字符阈值

### 6.2 主界面 OCR 视图
- 文件类型图标显示识别出的文档类型（PDF-文本层、PDF-扫描件、Office）
- 处理方法提示（如“使用 markitdown 提取”或“使用 docling 增强表格”）
- 处理进度条（特别在 docling 首次下载模型时，显示“正在准备 AI 模型…”及下载进度）

### 6.3 错误与状态提示
- 后端不可用时，在设置中明确说明原因并指导解决
- 处理失败时，提供详细错误日志，并建议切换回默认引擎
- 网络断开时，docling 插件安装或模型下载自动中止并给出离线使用指引

---

## 7. 技术实现与组件化

### 7.1 核心模块拆分
```
py/
  document_extractor.py    # 主入口，决策树，插件子进程调度
  text_detector.py         # pdfplumber 文本层检测逻辑
  adapters/
      markitdown_adapter.py
      opendata_adapter.py
      docling_adapter.py
      ppocr_adapter.py
  plugins/
      manager.py           # 插件 venv 生命周期、安装、检测
      runner.py            # 子进程调用封装，JSON 通信
  outputs/
      unified_document.py  # 统一数据类定义
```

### 7.2 依赖与许可证
**核心依赖（打包）**：
- `markitdown[all]` (MIT 兼容) → 包含 pdfplumber, mammoth 等
- `pypdfium2` (BSD) → 替代 PyMuPDF，用于扫描 PDF 转图像
- `rapidocr-onnxruntime` → PP-OCR 引擎
- 移除 PyMuPDF（AGPL 高风险）

**可选后端（插件 venv 按需安装）**：
- `opendataloader-pdf` (Apache 2.0)
- `docling` (MIT)

**捆绑**：
- `uv` 独立二进制
- `python-build-standalone` (Apache 2.0) 提供的 Python 运行时

### 7.3 文本层检测实现细节
- 使用 `pdfplumber.open(pdf_path)` 打开文件
- 遍历前 `detect_pages` 页，每页调用 `page.extract_text()`
- 统计 `len(re.sub(r'\s', '', text))` 非空白字符
- 若累计 ≥ 阈值，返回 `True`

### 7.4 docling 的 OCR 模式配置
docling 无文本层 PDF 处理时，需设置其 pipeline 使用 OCR 后端。我们配置其使用 **RapidOCR**（通过 `docling` 选项 `ocr_engine="rapidocr"`），以尽可能复用小部分模型。若 docling 的 RapidOCR 需要独立下载模型，则其自行管理，但可尝试通过环境变量或配置指向我们已有的 RapidOCR 模型目录。细节在实现时由 docling_adapter 处理。

---

## 8. 构建与打包 (PyInstaller)

### 8.1 构建脚本增强
- 下载指定版本的 `uv` 独立二进制，按平台/架构命名
- 下载对应平台的 `python-build-standalone` (基于 `opython` 打包的独立 Python)，解压至构建目录的 `python` 文件夹
- PyInstaller 配置中：
  - 添加 `--add-binary` 将 `uv` 和 `python/*` 文件复制到最终包
  - 主应用依赖仅包含核心依赖，不包含 docling/opendataloader-pdf
  - 保留 `_internal` 标准结构

### 8.2 最终包体预估
- 核心依赖（RapidOCR, markitdown, pypdfium2 等）：~230 MB
- 捆绑 Python 独立版：~30 MB
- 捆绑 uv：~20 MB
- 主应用及资源：~15 MB  
**总计**：~295 MB（较之前略有增加但换来完全自包含的插件环境）

---

## 9. 测试计划（要点）

- 文本层检测：多页、单页、空白 PDF、加密 PDF、扫描件混合
- 插件安装流程：在线、离线、空间不足、权限错误
- 后端切换：动态切换引擎处理同一文档，输出标准化比对
- Java 检测：各平台常见路径，用户手动指定
- docling 下载模型：进度显示，取消，离线使用 `artifacts_path`
- 子进程异常：超时、崩溃、返回非法 JSON 时的恢复

---

## 10. 实施路线图

**Phase 1**：核心重构 + markitdown 集成 + 新文本层检测 + 输出标准化 (DONE)
**Phase 2**：插件运行时架构（捆绑 Python + uv 子进程） + docling 和 opendataloader-pdf 适配器 (DONE)
**Phase 3**：设置 UI、安装流程、卸载、Java 检测、离线模型指引 (DONE)
**Phase 4**：全面测试、许可证审查、性能调优、文档 (DONE)

---

本文档已综合审计反馈的所有关键点，并提供了具体、可落地的技术方案。可作为下一阶段开发与评审的基准。