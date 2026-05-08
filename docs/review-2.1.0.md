# Code Review: SherpaNote v2.1.0

**审查日期**: 2026-05-08
**审查范围**: 全量代码审查（Python 后端、Vue 前端、构建配置、文档）
**分支**: dev-2.1.0

---

## 审查摘要

| 严重度 | 数量 | 已修复 | 说明 |
|--------|------|--------|------|
| **必须修复（安全）** | 3 | 3/3 | 路径遍历、ZipSlip、XSS |
| **应当修复（可靠性）** | 8 | 7/8 | 静默吞错、内存泄漏、线程安全 |
| **建议改进（质量）** | 12 | 12/12 | 代码组织、类型安全、硬编码值 |
| **基础设施缺失** | 5 | 2/5 | I-04 lock 文件追踪、I-05 文档填充 |

---

## 一、安全问题（必须修复）

### S-01: 路径遍历攻击 -- open_file / open_folder [已修复]

- **文件**: `main.py:2189-2225`
- **严重度**: 高
- **描述**: `open_file(file_path)` 和 `open_folder(folder_path)` 直接将前端传入的路径传给 `os.startfile` / `subprocess.Popen`，没有任何路径验证。攻击者可以传入任意系统路径（如 `C:\Windows\System32\cmd.exe`）来执行程序或打开敏感文件。
- **修复**: 使用 `Path.resolve()` + `data_dir` 白名单校验，路径外则拒绝访问。与 `get_audio_base64` 方法保持一致的校验模式。

### S-02: ZipSlip 漏洞 -- 备份导入 [已修复]

- **文件**: `py/backup.py:344-358`
- **严重度**: 高
- **描述**: 备份导入时从 ZIP 文件提取音频文件使用 `info.filename` 构建目标路径。如果 ZIP 中的文件名包含 `../`（如 `audio/../../../etc/passwd`），可以写入任意位置。代码剥离了 `audio/` 前缀，但没有检查剩余部分是否包含路径遍历字符。
- **修复**: 提取前对 `dest` 做 `resolve()` 并校验是否在 `resolved_audio_dir` 内，检测到路径遍历则抛出 `ValueError`。

### S-03: XSS 风险 -- MarkdownRenderer [已修复]

- **文件**: `frontend/src/components/MarkdownRenderer.vue:199-218`
- **严重度**: 高
- **描述**: `v-html` 渲染 Markdown 时，`inlineFormat` 函数对普通文本段落未进行 HTML 转义。攻击者可通过以下方式注入：
  - 链接注入：`` `[xss](javascript:alert(1)) `` 转换为可执行的 `<a href="javascript:alert(1)">`
  - 直接 HTML 标签：LLM 输出中的 `<img onerror="...">` 或 `<script>` 会直接注入 DOM
- **修复**: 所有正则替换改用函数式替换并对捕获组调用 `escapeHtml`；链接 href 添加协议白名单校验（仅允许 `http/https/mailto/#/`），非法协议降级为纯文本输出。

---

## 二、可靠性问题（应当修复）

### R-01: @expose 装饰器静默吞没异常 [已修复]

- **文件**: `pywebvue/bridge.py:27-28`
- **严重度**: 高
- **描述**: `@expose` 装饰器捕获所有异常后仅返回错误字典，不记录日志。所有 60+ 个暴露给前端的方法如果发生异常，开发人员完全无法从日志中发现问题。
- **修复**: 在 except 块中添加 `logger.exception("Unhandled error in %s", func.__name__)`。

### R-02: AI 调用失败静默返回原文 [已修复]

- **文件**: `py/llm.py:302`
- **严重度**: 高
- **描述**: `restore_punctuation` 捕获 `Exception` 后静默返回原文 `return text`。用户完全无法感知 AI 处理失败（网络超时、API 密钥错误等），误以为处理成功。
- **修复**: 添加 `logger.warning("restore_punctuation failed, returning original text", exc_info=True)`，同时新增模块级 logger。

### R-03: 数据库操作静默吞错 [已修复]

- **文件**: `py/storage.py:89`
- **严重度**: 高
- **描述**: 数据库迁移中 `ALTER TABLE` 捕获 `Exception` 后 `pass`。虽然预期是"列已存在"，但如果是权限不足、磁盘满等其他数据库错误也会被吞没，可能导致数据损坏。
- **修复**: 改为精确捕获 `sqlite3.OperationalError`，仅当错误信息包含 "duplicate column" 时忽略，其他错误重新抛出。

### R-04: 事件监听器未清理 -- AiProcessor [已修复]

- **文件**: `frontend/src/components/AiProcessor.vue:109-124`
- **严重度**: 高
- **描述**: `handleProcess` 中注册的 `offComplete` 和 `offError` 事件监听器是局部变量，未存储到 cleanup 数组。用户在 AI 处理期间离开页面时，监听器不会被清理，导致内存泄漏。组件没有 `onBeforeUnmount` 钩子来清理残留监听器。
- **修复**: 新增 `cleanupFns` 数组和 `onBeforeUnmount` 钩子，监听器注册时存入数组，事件触发时从数组移除，组件卸载时统一清理。重复点击 process 时先清理旧监听器。

### R-05: os.environ 线程不安全修改 [已修复]

- **文件**: `py/model_manager.py:183-229`
- **严重度**: 中
- **描述**: `download_from_huggingface` 直接修改 `os.environ`（HTTP_PROXY、HTTPS_PROXY 等），虽然有 try/finally 恢复，但 `os.environ` 是进程级全局状态。如果两个线程同时调用，会产生竞态条件。
- **修复**: 新增模块级 `_env_lock = threading.Lock()`，将整个环境变量修改 + 下载 + 恢复块包裹在 `with _env_lock:` 中。

### R-06: 数据冗余 -- SettingsView [保留]

- **文件**: `frontend/src/views/SettingsView.vue:40-45`
- **严重度**: 中
- **描述**: 从 store 复制了一份配置数据到本地 ref，`loadConfig()` 中手动双向同步（第 560-592 行），容易遗漏字段导致 store 与本地状态不同步。
- **状态**: 保留。这是表单编辑模式的常见做法（编辑副本而非直接修改 store），需要较大重构才能改为 `storeToRefs` 模式，风险收益比不高。

### R-07: Timer 未清理 [已修复]

- **文件**: `frontend/src/components/SearchBar.vue:30`, `frontend/src/views/SettingsView.vue:627`
- **严重度**: 中
- **描述**: `searchTimer` 和 `autoSaveTimer` 均未在组件卸载时清理。用户在 debounce 等待期间离开页面时，timer 回调仍会触发，可能导致对已卸载组件的操作。
- **修复**: SearchBar 新增 `onBeforeUnmount(() => clearTimeout(searchTimer))`；SettingsView 在已有的 `onUnmounted` 中添加 `if (autoSaveTimer) clearTimeout(autoSaveTimer)`。

### R-08: isLoading 状态未保护 [已修复]

- **文件**: `frontend/src/components/VersionHistory.vue:36-40`
- **严重度**: 中
- **描述**: `loadVersions` 中如果 `getVersions` 抛出异常，`isLoading` 永远为 `true`，UI 会一直显示加载中。
- **修复**: 将 `isLoading.value = false` 移入 `try/finally` 块，确保异常时也能重置。

---

## 三、代码质量问题（建议改进）

### Q-01: 上帝对象 -- main.py SherpaNoteAPI [已修复]

- **文件**: `main.py`（原 2343 行 -> 现 ~250 行），新增 `py/api/` 模块（6 个 mixin 文件）
- **严重度**: 中
- **描述**: `SherpaNoteAPI` 类承担了 ASR、OCR、AI 处理、配置管理、备份恢复、插件管理、文件管理等全部职责，是典型的上帝对象。
- **修复**: 按职责拆分为 6 个 mixin 类，通过多重继承组合：
  - `py/api/base.py` -- `ApiBase`，提供 `_api` 属性访问共享状态
  - `py/api/asr.py` -- `AsrMixin`，语音识别、whisper.cpp、依赖管理
  - `py/api/ai.py` -- `AiMixin`，AI 处理、预设管理
  - `py/api/storage.py` -- `StorageMixin`，记录 CRUD、版本历史、音频管理、导入导出
  - `py/api/models.py` -- `ModelsMixin`，ASR 模型管理
  - `py/api/ocr_plugin.py` -- `OcrPluginMixin`，OCR、插件后端、文档提取
  - `py/api/config_backup.py` -- `ConfigBackupMixin`，配置、备份恢复、文件选择器
  - `main.py` 仅保留 `__init__`、`dispatch_task` 和入口代码

### Q-02: 超标文件 [已修复]

| 文件 | 原始行数 | 修复后 | 标准 | 修复方式 |
|------|----------|--------|------|----------|
| `main.py` | 2343 | ~250 | 800 | Q-01 拆分为 6 个 mixin 类 |
| `py/asr.py` | 1077 | 651 | 800 | 提取 `py/file_matcher.py`（模型文件匹配）+ `py/asr_recognizer.py`（识别器工厂函数） |
| `py/model_manager.py` | 862 | 797 | 800 | Q-03 共享 `py/file_matcher.py`，简化分隔注释 |
| `frontend/src/views/SettingsView.vue` | 931脚本 | 626脚本 | 400 | 提取 `useAiPresets.ts`、`useProcessingPresets.ts`、`useBackup.ts` |
| `frontend/src/views/EditorView.vue` | 495脚本 | 394脚本 | 400 | 提取 `useAudioPlayback.ts`、`useVersionManagement.ts` |

### Q-03: 重复代码 [已修复]

- **文件**: `py/asr.py:96-140` 与 `py/model_manager.py:420-460`
- **描述**: `_find_file` 和 `_match_model_file` 逻辑几乎完全相同，应提取到公共工具模块。
- **修复**: 提取 `py/file_matcher.py`（194 行），包含 `match_model_file()`、`find_file()`、`is_simulated_streaming_model()`、`is_sense_voice_dir()`、`find_tokenizer_dir()`、`has_model_files()`、`classify_model_dir()`。`py/asr.py` 和 `py/model_manager.py` 均改为 `from py.file_matcher import ...`。

### Q-04: 调试 print 残留 [已修复]

| 文件 | 行号 | 内容 |
|------|------|------|
| `pywebvue/app.py` | 139 | `print("DEBUG: ...")` 改为 `logger.debug(...)` |
| `py/document_extractor.py` | 39 | docstring 示例，非实际代码 |
| `py/ocr.py` | 182 | docstring 示例，非实际代码 |

### Q-05: TypeScript 类型安全 [已修复]

| 文件 | 行号 | 问题 | 状态 |
|------|------|------|------|
| `bridge.ts` | 70 | 添加 `isApiResponse<T>` 类型守卫，替代 `as` 断言 | [已修复] |
| `OcrView.vue` | 146 | `(window as any)` 改为使用 `call()` 桥接调用 | [已修复] |
| `OcrView.vue` | 171 | `catch (e: any)` 改为 `catch (e: unknown)` + `instanceof Error` | [已修复] |
| `SettingsView.vue` | 883-901 | 大量 `as` 类型断言，应定义 `ConfigResponse` 接口 | [保留] |

### Q-06: 魔法数字 [已修复]

| 文件 | 原始值 | 常量名 |
|------|--------|--------|
| `py/asr.py:404` | `num_threads = 2` | `_STREAMING_NUM_THREADS` |
| `py/asr.py:868` | `num_threads = 4` | `_OFFLINE_NUM_THREADS` |
| `py/llm.py:320-328` | `500, 3000, 10000` | `_TOKEN_THRESHOLD_SHORT/MEDIUM/LONG` |
| `py/llm.py:320-328` | `3, 2, 1.5` | `_TOKEN_MULTIPLIER_SHORT/MEDIUM/LONG` |
| `py/llm.py:332` | `2048` | `_TOKEN_MIN_AUTO` |
| `py/llm.py:298` | `200, 4096` | `_PUNCT_EXTRA_TOKENS`, `_PUNCT_MAX_TOKENS` |
| `py/io.py:140` | `32767` | `np.iinfo(np.int16).max` |
| `py/whispercpp.py:122` | `timeout=3600` | `_WHISPER_SUBPROCESS_TIMEOUT` |
| `py/video_downloader.py:129` | `"192"` | `_DEFAULT_AUDIO_QUALITY` |
| `pywebvue/app.py:124-128` | `50, 100` | `_EVENT_FLUSH_INTERVAL_MS`, `_TASK_EXECUTOR_INTERVAL_MS` |

### Q-07: 硬编码 URL 重复 [已修复]

HuggingFace / hf-mirror / ModelScope 的 base URL 在 `py/model_registry.py` 和 `py/model_manager.py` 中多处重复硬编码。
- **修复**: 在 `model_registry.py` 新增 `HUGGINGFACE_BASE_URL`、`HF_MIRROR_BASE_URL`、`MODELSCOPE_API_BASE_URL` 常量，`model_manager.py` 导入并使用这些常量。`get_download_url` 中的 `ghproxy` 分支也改用已有的 `GITHUB_BASE_URL`。

### Q-08: processText 未检查返回值 [已修复]

- **文件**: `frontend/src/composables/useAiProcess.ts:61-77`
- **描述**: `processText` 调用 `call()` 后未检查 `success` 字段。如果失败，`isProcessing` 会一直为 `true`。
- **修复**: 检查 `res.success`，失败时重置 `isProcessing` 并显示错误提示。

### Q-09: clipboard API 未处理异常 [已修复]

- **文件**: `frontend/src/composables/useAiProcess.ts:103-108`
- **描述**: `navigator.clipboard.writeText` 返回 Promise 但未 await 也未 catch，在非安全上下文下会静默失败。
- **修复**: `copyResult` 改为 `async`，添加 `try/catch`，失败时显示错误提示。

### Q-10: OCR 引擎延迟初始化无锁 [已修复]

- **文件**: `py/ocr.py:200`
- **描述**: `_engine` 是可变实例变量，延迟初始化时没有锁保护。如果两个请求同时触发初始化，可能创建多个引擎实例。
- **修复**: 新增 `self._init_lock = threading.Lock()`，`initialize()` 使用双重检查锁定模式。

### Q-11: 缺少返回类型注解 [已修复]

- **文件**: `py/document_extractor.py:69-99`
- **描述**: `_get_ppocr_adapter()` 等 4 个方法缺少返回类型注解。
- **修复**: 添加返回类型注解 `-> PpocrAdapter`、`-> MarkitdownAdapter`、`-> DoclingAdapter | None`、`-> OpendataAdapter | None`。

### Q-12: 错误信息泄露系统路径 [已修复]

- **文件**: `main.py:2199, 2213`
- **描述**: `open_file` 和 `open_folder` 将 `str(e)` 直接返回前端，可能泄露系统路径等敏感信息。
- **修复**: 返回通用错误消息 "Failed to open file/folder"，详细异常通过 `logger.exception` 记录到服务端日志。

---

## 四、基础设施缺失

### I-01: 自动化测试完全缺失

- **严重度**: 高
- **描述**: 项目没有任何可执行的自动化测试。`pyproject.toml` 无 pytest 依赖，`package.json` 无 vitest/jest。仅有 6 份手动测试计划文档（`tests/2.1.0-test_plans/`）。
- **建议**: 至少为核心模块（`storage.py`、`config.py`、`llm.py`）添加单元测试，前端至少覆盖 composable 层。

### I-02: CI/CD 完全缺失

- **严重度**: 高
- **描述**: 无 `.github/`、`.gitlab-ci.yml`、`Dockerfile` 等任何 CI/CD 配置。发布流程为纯手动。
- **建议**: 至少添加 GitHub Actions 进行 lint + type check + 前端 build 验证。

### I-03: 开发工具链缺失

- **严重度**: 中
- **描述**: Python 端缺少 pytest、mypy、ruff、bandit；前端缺少 eslint、vitest。
- **建议**: 在 `pyproject.toml` 和 `package.json` 中添加 dev 依赖。

### I-04: 前端依赖未精确锁定 (RESOLVED)

- **严重度**: 中
- **描述**: 前端 `package.json` 使用 caret 范围（`^`），未确认 bun.lockb 是否提交到仓库。
- **建议**: 确保 lock 文件提交，或改用精确版本锁定。
- **修复**: 从 `.gitignore` 移除 `bun.lock` 忽略规则，使 `frontend/bun.lock` 可被 git 追踪。Caret 范围配合 lock 文件是 JS 生态标准做法，lock 文件保证可复现构建。

### I-05: 文档空壳 (RESOLVED)

- **严重度**: 低
- **描述**: `docs/dev_guide.md` 和 `docs/changelog.md` 仅有标题，内容未填充。
- **建议**: 补充开发指南和变更日志内容。
- **修复**: 已填充 `dev_guide.md`（249行，含架构、模块、约定、构建、调试等10个章节）和 `changelog.md`（152行，含v1.0.0~v2.1.0共6个版本的完整变更记录）。

---

## 五、良好实践（值得保持）

| 方面 | 说明 |
|------|------|
| **Python 依赖锁定** | 全部使用 `==` 精确锁定，良好实践 |
| **Immutable configs** | 所有配置使用 frozen dataclass，避免意外修改 |
| **SQLite WAL 模式** | 正确使用 WAL 提升并发读写性能 |
| **Composables 职责分离** | useRecording / useTranscript / useAiProcess / useStorage / usePlugin / useDragDrop 按领域分离 |
| **Pinia Composition API** | 使用 setup 函数风格，符合 Vue 3 推荐 |
| **桥接层设计** | PyWebVue bridge 正确处理线程安全和事件队列 |
| **文档体系** | PRD、设计文档、流程文档、业务规则分层清晰 |
| **模型下载多源** | 支持 GitHub、HuggingFace、HF-Mirror、GitHub Proxy、ModelScope 五种下载源 |
| **事件监听清理** | 多数 composables 在 `onBeforeUnmount` 中正确清理（useRecording、useTranscript、usePlugin 等） |
| **导航守卫** | 录音中正确阻止路由跳转，防止状态丢失 |

---

## 六、优先修复建议

### 第一优先级（安全） -- 全部已修复

1. **S-01** [已修复]: `main.py` open_file/open_folder 添加路径白名单验证
2. **S-02** [已修复]: `py/backup.py` ZIP 导入添加路径遍历检查
3. **S-03** [已修复]: `MarkdownRenderer.vue` inlineFormat 入口添加 HTML 转义 + 链接协议白名单

### 第二优先级（可靠性） -- 7/8 已修复

4. **R-01** [已修复]: `pywebvue/bridge.py` @expose 装饰器添加日志记录
5. **R-02** [已修复]: `py/llm.py` restore_punctuation 失败时记录日志
6. **R-03** [已修复]: `py/storage.py` 精确捕获 "column already exists" 异常
7. **R-04** [已修复]: `AiProcessor.vue` 事件监听器添加 onBeforeUnmount 清理
8. **R-05** [已修复]: `py/model_manager.py` os.environ 修改添加线程锁
9. **R-06** [保留]: `SettingsView.vue` store 数据冗余（表单编辑模式，暂不重构）
10. **R-07** [已修复]: SearchBar / SettingsView Timer 未清理
11. **R-08** [已修复]: VersionHistory loadVersions 添加 try/finally

### 第三优先级（质量） -- 12/12 已修复

12. **Q-04** [已修复]: 移除调试 print 语句（app.py 改为 logger.debug）
13. **Q-05** [已修复]: TypeScript 类型安全（bridge.ts 类型守卫、OcrView 去除 any）
14. **Q-06** [已修复]: 魔法数字提取为命名常量（6 个文件共 10+ 个常量）
15. **Q-07** [已修复]: 硬编码 URL 提取到 model_registry.py 常量（HUGGINGFACE_BASE_URL 等）
16. **Q-08** [已修复]: processText 检查返回值，失败时重置 isProcessing
17. **Q-09** [已修复]: clipboard API 添加 try/catch
18. **Q-10** [已修复]: OCR 引擎延迟初始化添加 threading.Lock
19. **Q-11** [已修复]: document_extractor 添加返回类型注解
20. **Q-12** [已修复]: open_file/open_folder 错误消息不再泄露系统路径
21. **Q-01** [已修复]: 上帝对象拆分为 6 个 mixin 类（py/api/ 模块），main.py 从 2343 行缩减至 ~250 行
22. **Q-02** [已修复]: 超标文件（提取 composables + 公共模块，所有文件降至标准以下）
23. **Q-03** [已修复]: 重复代码（提取 `py/file_matcher.py` 共享模块）

### 第四优先级（基础设施） -- 2/5 已修复

24. **I-04** [已修复]: `.gitignore` 移除 `bun.lock` 忽略规则，`frontend/bun.lock` 可被 git 追踪
25. **I-05** [已修复]: 填充 `dev_guide.md`（249行，10章节）和 `changelog.md`（152行，6个版本）
26. **I-01** [未修复]: 自动化测试完全缺失（需长期投入）
27. **I-02** [未修复]: CI/CD 完全缺失（需长期投入）
28. **I-03** [未修复]: 开发工具链缺失（需长期投入）

| 编号 | 文件 | 修复内容 |
|------|------|----------|
| S-01 | main.py:2189-2225 | open_file / open_folder 添加 Path.resolve() + data_dir 白名单校验，路径外则拒绝访问 |
| S-02 | py/backup.py:344-358 | ZIP 导入时对 audio/ 下的文件路径做 resolve() 后校验是否在 audio_dir 内，检测到路径遍历则抛出 ValueError |
| S-03 | MarkdownRenderer.vue:199-218 | inlineFormat 所有正则替换改用函数式替换并对捕获组调用 escapeHtml；链接 href 添加协议白名单校验（仅允许 http/https/mailto/#/），非法协议降级为纯文本输出 |
| R-01 | pywebvue/bridge.py:27 | @expose 装饰器 except 块添加 logger.exception |
| R-02 | py/llm.py:305 | restore_punctuation 失败时记录 logger.warning + exc_info |
| R-03 | py/storage.py:89 | 改为精确捕获 sqlite3.OperationalError，仅 "duplicate column" 时忽略，其他重新抛出 |
| R-04 | AiProcessor.vue:35-40,110-135 | 新增 cleanupFns 数组 + onBeforeUnmount，监听器存入数组，事件触发时移除，卸载时统一清理 |
| R-05 | py/model_manager.py:14,185 | 新增 _env_lock = threading.Lock()，环境变量修改 + 下载 + 恢复块包裹在 with _env_lock 中 |
| R-07 | SearchBar.vue:8,31 | 新增 onBeforeUnmount 清理 searchTimer |
| R-07 | SettingsView.vue:922 | onUnmounted 中添加 autoSaveTimer 清理 |
| R-08 | VersionHistory.vue:36-40 | loadVersions 添加 try/finally 保护 isLoading 状态 |
| Q-04 | pywebvue/app.py:139 | `print("DEBUG: ...")` 改为 `logger.debug(...)`，新增 logger |
| Q-05 | bridge.ts:67-78 | 添加 `isApiResponse<T>` 类型守卫函数，替代 `as ApiResponse<T>` 断言 |
| Q-05 | OcrView.vue:146 | `(window as any).pywebview?.api?.get_file_size` 改为 `call<number>("get_file_size", p)` |
| Q-05 | OcrView.vue:171 | `catch (e: any)` 改为 `catch (e: unknown)` + `instanceof Error` 窄化 |
| Q-08 | useAiProcess.ts:76-81 | 检查 `call()` 返回的 `res.success`，失败时重置 `isProcessing` 并显示错误 |
| Q-09 | useAiProcess.ts:103-108 | `copyResult` 改为 async，`clipboard.writeText` 添加 try/catch |
| Q-10 | py/ocr.py:200-206 | 新增 `self._init_lock = threading.Lock()`，`initialize()` 使用双重检查锁定 |
| Q-11 | py/document_extractor.py:69-99 | 4 个 adapter getter 添加返回类型注解 |
| Q-12 | main.py:2203-2204,2221-2222 | 错误消息改为通用文本，异常详情通过 logger.exception 记录到服务端 |
| Q-06 | py/asr.py:404,868 | `num_threads` 提取为 `_STREAMING_NUM_THREADS`、`_OFFLINE_NUM_THREADS` |
| Q-06 | py/llm.py:298,320-332 | token 阈值/乘数提取为 `_TOKEN_THRESHOLD_*`、`_TOKEN_MULTIPLIER_*`、`_TOKEN_MIN_AUTO`、`_PUNCT_*` |
| Q-06 | py/io.py:140 | `32767` 改为 `np.iinfo(np.int16).max` |
| Q-06 | py/whispercpp.py:122 | `timeout=3600` 提取为 `_WHISPER_SUBPROCESS_TIMEOUT` |
| Q-06 | py/video_downloader.py:129 | `"192"` 提取为 `_DEFAULT_AUDIO_QUALITY` |
| Q-06 | pywebvue/app.py:124-128 | `50, 100` 提取为 `_EVENT_FLUSH_INTERVAL_MS`、`_TASK_EXECUTOR_INTERVAL_MS` |
| Q-07 | py/model_registry.py | 新增 `HUGGINGFACE_BASE_URL`、`HF_MIRROR_BASE_URL`、`MODELSCOPE_API_BASE_URL` 常量，`get_download_url` 和 ghproxy 分支改用常量 |
| Q-07 | py/model_manager.py | 导入并使用 `HUGGINGFACE_BASE_URL`、`HF_MIRROR_BASE_URL`，替换 2 处硬编码 URL |
| Q-01 | main.py | SherpaNoteAPI 拆分为 6 个 mixin 类（AsrMixin、AiMixin、StorageMixin、ModelsMixin、OcrPluginMixin、ConfigBackupMixin），main.py 从 2343 行缩减至 ~250 行 |
| Q-01 | py/api/__init__.py | 新模块，导出所有 mixin 类 |
| Q-01 | py/api/base.py | ApiBase 基类，提供 `_api` 属性访问共享 SherpaNoteAPI 实例 |
| Q-01 | py/api/asr.py | AsrMixin：语音识别、whisper.cpp、依赖管理（15 个 @expose 方法） |
| Q-01 | py/api/ai.py | AiMixin：AI 处理、预设 CRUD（17 个 @expose 方法） |
| Q-01 | py/api/storage.py | StorageMixin：记录 CRUD、版本历史、音频管理、导入导出（20 个 @expose 方法） |
| Q-01 | py/api/models.py | ModelsMixin：ASR 模型管理（7 个 @expose 方法） |
| Q-01 | py/api/ocr_plugin.py | OcrPluginMixin：OCR、插件后端、文档提取（16 个 @expose 方法） |
| Q-01 | py/api/config_backup.py | ConfigBackupMixin：配置、备份恢复、文件选择器（8 个 @expose 方法） |
| Q-02 | py/asr.py | 提取 `py/file_matcher.py`（7 个模型文件匹配函数）+ `py/asr_recognizer.py`（3 个识别器工厂函数），1081→651 行 |
| Q-02 | py/model_manager.py | 共享 `py/file_matcher.py`，简化分隔注释，803→797 行 |
| Q-02 | SettingsView.vue | 提取 `useAiPresets.ts`（165 行）、`useProcessingPresets.ts`（131 行）、`useBackup.ts`（105 行），脚本 931→626 行 |
| Q-02 | EditorView.vue | 提取 `useAudioPlayback.ts`（83 行）、`useVersionManagement.ts`（52 行），脚本 495→394 行 |
| Q-03 | py/file_matcher.py | 新建共享模块（194 行），包含 `match_model_file()`、`find_file()` 等 7 个函数，消除 asr.py 与 model_manager.py 的重复代码 |
| I-04 | .gitignore:180 | 移除 `bun.lock` 忽略规则，使 `frontend/bun.lock` 可被 git 追踪，保证可复现的前端依赖构建 |
| I-05 | docs/dev_guide.md | 填充开发指南文档（249行）：环境搭建、项目架构、后端/前端布局、技术决策、数据目录、命名规范、构建命令、插件开发、调试技巧共 10 个章节 |
| I-05 | docs/changelog.md | 填充变更日志（152行）：v1.0.0 ~ v2.1.0 共 6 个版本的完整变更记录，包含 Added/Fixed/Changed 分类 |
