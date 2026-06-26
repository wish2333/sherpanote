# SherpaNote v2.2.0 产品需求文档

**版本**: 2.2.0
**状态**: 草案
**最后更新**: 2026-05-08

---

## 1. 修订历史

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|----------|
| 2.2.0-draft | 2026-05-08 | PRD | 初稿，基于外部评估报告与 v2.1.0 审查遗留问题制定 |

---

## 2. 目标与背景

### 2.1 目标

将 SherpaNote 的插件系统从"硬编码的可选后端管理器"升级为**可扩展、安全、跨平台兼容的插件架构**，同时补齐 v2.1.0 审查中遗留的基础设施短板。

核心目标：

1. **插件架构升级** -- 从共享 venv + 硬编码后端，演进为独立隔离 + manifest 驱动的可扩展插件系统
2. **开发基础设施补齐** -- 建立自动化测试、开发工具链、基础 CI 验证
3. **跨平台兼容性加固** -- 修复插件目录权限问题，改进健康检查

### 2.2 关键驱动

- **外部评估结论**: 当前方案作为"可选后端管理器"评分 8/10，但作为"通用插件系统"仅 5.5/10
- **扩展瓶颈**: 共享 venv 在新增插件时会产生依赖冲突（如 pydantic 1.x vs 2.x）
- **权限风险**: frozen 模式下插件目录位于程序安装路径，Windows Program Files / macOS .app 内部可能不可写
- **健康检查薄弱**: 仅靠 `.venv_valid` 标记文件判断环境可用性，无法检测损坏、杀软删除等异常
- **v2.1.0 审查遗留**: 自动化测试缺失（I-01）、CI/CD 缺失（I-02）、开发工具链缺失（I-03）

### 2.3 非目标

- 不构建"第三方插件市场"或插件商店
- 不实现插件签名/校验机制（留待 v2.3.0+）
- 不改变主程序与插件之间的 JSON subprocess 通信协议（已验证稳定）
- 不改变内置后端（PP-OCR、markitdown）的运行方式

---

## 3. 当前架构与目标架构

### 3.1 当前架构（v2.1.x）

```
主程序 (PyInstaller frozen)
    |
    +-- py/plugins/manager.py (PluginManager)
    |       共享 venv: data/plugins/.venv/
    |       硬编码: PACKAGE_NAMES = {"docling": "docling==2.92.0", ...}
    |       健康检查: .venv_valid 标记文件
    |
    +-- py/plugins/runner.py (subprocess JSON 协议)
    |
    +-- py/plugins/runners/
            docling_runner.py
            opendata_runner.py
```

**已知问题**:
- 所有插件共享一个 venv，依赖冲突风险
- 插件目录在程序安装路径下，正式发布时可能不可写
- 无 manifest / lockfile，不可复现
- 安装路径未统一走 `PACKAGE_NAMES` 映射，可能导致版本漂移
- `.venv_valid` 标记太弱，无法检测环境损坏
- uv 版本固定在 0.6.6，远低于当前稳定版

### 3.2 目标架构（v2.2.0）

```
主程序 (PyInstaller frozen)
    |
    +-- py/plugins/manager.py (PluginManager)
    |       每个插件独立 venv: {user_data}/plugins/{plugin_id}/.venv/
    |       Manifest 驱动: plugin_manifest.toml
    |       健康检查: venv_python.exists() + import 验证
    |
    +-- py/plugins/registry.py (PluginRegistry)
    |       注册表: 内置 + 外部 manifest 发现
    |       白名单控制: 只允许注册的插件
    |
    +-- py/plugins/runner.py (subprocess JSON 协议，不变)
    |
    +-- py/plugins/runners/
            docling_runner.py
            opendata_runner.py
```

---

## 4. 详细功能需求

### 4.1 P0: 插件目录迁移至用户数据目录

**优先级**: 必须完成
**复杂度**: 中

将插件 venv 从程序安装目录迁移到用户可写的数据目录。

**变更范围**:

| 文件 | 变更 |
|------|------|
| `py/plugins/paths.py` | `get_plugin_base_dir()` frozen 模式改为用户数据目录 |
| `py/plugins/manager.py` | 适配新的目录结构 |
| `py/config.py` | 无变更（`data_dir` 已有） |

**目录结构**:

```
# Frozen 模式
{data_dir}/plugins/
    docling/
        .venv/
    opendataloader/
        .venv/

# Dev 模式（不变）
{project_root}/.plugin_dev/
```

**迁移策略**:
- 首次启动检测旧目录 `data/plugins/.venv/`，如果存在则自动迁移到新位置
- 迁移完成后删除旧目录
- 迁移过程中如果出错，记录日志并提示用户重新安装插件

**跨平台用户数据目录**:
- 使用现有 `AppConfig.data_dir`（已正确处理 frozen/dev 模式）
- 不引入新的平台特定路径，保持与 data.db、models、audio 等一致

**验收标准**:
- [ ] Frozen 模式下插件 venv 位于 `{data_dir}/plugins/{plugin_id}/.venv/`
- [ ] Dev 模式路径不变
- [ ] 旧目录自动迁移，无需用户手动操作
- [ ] 迁移失败时不崩溃，记录日志并提示

---

### 4.2 P0: 每个插件独立 venv

**优先级**: 必须完成
**复杂度**: 中高

将共享 venv 拆分为每个插件独立的虚拟环境，消除依赖冲突风险。

**变更范围**:

| 文件 | 变更 |
|------|------|
| `py/plugins/paths.py` | 新增 `get_plugin_venv_dir(plugin_id)` 替代 `get_plugin_venv_dir()` |
| `py/plugins/manager.py` | `ensure_venv()` / `install_package()` / `uninstall_package()` 接受 `plugin_id` 参数 |
| `py/plugins/runner.py` | `run()` 根据 `plugin_id` 解析 venv python 路径 |
| `py/api/ocr_plugin.py` | 调用 manager 方法时传入 `plugin_id` |
| `frontend/src/composables/usePlugin.ts` | 适配新接口 |

**接口变更**:

```python
# Before (shared venv)
manager.ensure_venv()
manager.install_package("docling==2.92.0")

# After (per-plugin venv)
manager.ensure_venv("docling")
manager.install_package("docling", "docling==2.92.0")
```

**新增方法签名**:

```python
def get_plugin_venv_dir(self, plugin_id: str) -> Path
def get_plugin_venv_python(self, plugin_id: str) -> Path
def is_venv_ready(self, plugin_id: str) -> bool
def ensure_venv(self, plugin_id: str) -> str
def install_package(self, plugin_id: str, package_spec: str, ...) -> dict[str, Any]
def uninstall_package(self, plugin_id: str, package_name: str) -> dict[str, Any]
def destroy_venv(self, plugin_id: str) -> dict[str, Any]
def get_venv_size_mb(self, plugin_id: str) -> float
```

**验收标准**:
- [ ] docling 和 opendataloader 各自拥有独立 venv
- [ ] 安装/卸载一个插件不影响另一个插件
- [ ] `get_all_status()` 正确报告每个插件的安装状态
- [ ] 插件 runner 正确使用对应 venv 的 python

---

### 4.3 P0: 插件 Manifest 与注册表

**优先级**: 必须完成
**复杂度**: 中

引入 manifest 描述插件元信息，替代硬编码的 `PACKAGE_NAMES` 字典。

**Manifest 格式** (`plugin_manifest.toml`):

```toml
id = "docling"
name = "Docling 文档解析"
description = "高质量 PDF/文档布局分析，支持表格、OCR 和多格式输出"
version = "1.0.0"
python = "3.11"

[install]
package = "docling==2.92.0"

[runner]
module = "py.plugins.runners.docling_runner"
method = "extract"

[requirements]
env = ["plugin_venv"]  # 需要插件 venv
external = []          # 无外部依赖

[compatibility]
host_min_version = "2.0.0"
```

```toml
id = "opendataloader"
name = "OpenDataLoader PDF"
description = "基于 Java 的高保真 PDF 文本提取"
version = "1.0.0"
python = "3.11"

[install]
package = "opendataloader-pdf==2.4.0"

[runner]
module = "py.plugins.runners.opendata_runner"
method = "extract"

[requirements]
env = ["plugin_venv"]
external = ["java11"]

[compatibility]
host_min_version = "2.0.0"
```

**注册表** (`py/plugins/registry.py`):

```python
@dataclass(frozen=True)
class PluginManifest:
    id: str
    name: str
    description: str
    version: str
    python: str
    package: str          # pip install 规范
    module: str           # runner 模块
    method: str           # runner 入口方法
    requirements: tuple[str, ...]  # "plugin_venv", "java11"
    host_min_version: str

class PluginRegistry:
    """内置插件注册表，从 manifest 文件加载。"""

    def __init__(self) -> None:
        self._plugins: dict[str, PluginManifest] = {}
        self._load_builtin_manifests()

    def get(self, plugin_id: str) -> PluginManifest | None
    def get_all(self) -> dict[str, PluginManifest]
    def is_registered(self, plugin_id: str) -> bool
```

**Manifest 存放位置**: `py/plugins/manifests/{plugin_id}.toml`

**新增文件**:
- `py/plugins/registry.py` -- 注册表实现
- `py/plugins/manifests/docling.toml`
- `py/plugins/manifests/opendataloader.toml`

**变更文件**:
- `py/plugins/manager.py` -- 移除 `PACKAGE_NAMES` 硬编码，改用 registry
- `py/plugins/manager.py` -- 安装时通过 manifest 获取 package spec，统一版本映射
- `py/api/ocr_plugin.py` -- 使用 registry 获取插件信息

**验收标准**:
- [ ] `PACKAGE_NAMES` 硬编码已移除
- [ ] 插件元信息从 toml manifest 加载
- [ ] 安装时版本号从 manifest 获取，不依赖前端传值
- [ ] 新增插件只需添加 toml 文件 + runner，无需修改 manager

---

### 4.4 P1: 健康检查增强

**优先级**: 应当完成
**复杂度**: 低

替换 `.venv_valid` 标记文件为实际的 venv 完整性验证。

**健康检查策略**:

```python
def is_venv_healthy(self, plugin_id: str) -> bool:
    """Check if a plugin venv is actually usable."""
    venv_python = self.get_plugin_venv_python(plugin_id)
    if not venv_python.exists():
        return False

    # Verify python is executable
    try:
        result = subprocess.run(
            [str(venv_python), "-c", "import sys; print(sys.version)"],
            capture_output=True, timeout=10,
            creationflags=_SUBPROCESS_FLAGS,
        )
        if result.returncode != 0:
            return False
    except (subprocess.TimeoutExpired, OSError):
        return False

    return True
```

**变更范围**:
- `py/plugins/manager.py` -- `is_venv_ready()` 改用实际检测
- 移除 `.venv_valid` 标记文件的创建和检查逻辑

**降级处理**:
- 健康检查失败时自动重建 venv
- 重建失败时返回错误状态，前端提示用户

**验收标准**:
- [ ] `.venv_valid` 标记文件机制已移除
- [ ] 健康检查通过实际执行 venv python 验证
- [ ] python 被删除/损坏时正确报告不可用
- [ ] `ensure_venv()` 在检测到损坏时自动重建

---

### 4.5 P1: uv 版本升级与可配置化

**优先级**: 应当完成
**复杂度**: 低

将打包的 uv 版本从 0.6.6 升级到最新稳定版，并使其可配置。

**变更范围**:

| 文件 | 变更 |
|------|------|
| `build.py` | uv 版本从常量提取为构建参数，默认使用最新稳定版 |

**实现要点**:
- uv 下载 URL 模板化，版本号作为参数
- `build.py --uv-version x.y.z` 支持覆盖
- 默认版本在 `build.py` 顶部常量定义，方便后续更新

**验收标准**:
- [ ] uv 版本不再是硬编码 0.6.6
- [ ] 构建时可指定 uv 版本
- [ ] 默认版本 >= 0.6.14（安全修复版本）

---

### 4.6 P2: 开发基础设施

**优先级**: 建议完成
**复杂度**: 中

补齐 v2.1.0 审查中遗留的三项基础设施（I-01、I-02、I-03）。

#### 4.6.1 Python 开发工具链 (I-03)

在 `pyproject.toml` 中添加 dev 依赖组：

```toml
[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-cov>=5",
    "ruff>=0.5",
    "mypy>=1.10",
    "bandit>=1.8",
]
```

**验收标准**:
- [ ] `uv run pytest` 可执行测试
- [ ] `uv run ruff check .` 可运行 lint
- [ ] `uv run mypy py/` 可运行类型检查

#### 4.6.2 核心模块单元测试 (I-01)

优先覆盖核心模块，目标覆盖率 60%+（逐步提升到 80%）：

| 模块 | 优先级 | 测试文件 |
|------|--------|----------|
| `py/config.py` | P0 | `tests/test_config.py` |
| `py/storage.py` | P0 | `tests/test_storage.py` |
| `py/plugins/registry.py` | P0 | `tests/test_plugin_registry.py` |
| `py/plugins/manager.py` | P1 | `tests/test_plugin_manager.py` |
| `py/document_extractor.py` | P1 | `tests/test_document_extractor.py` |
| `py/plugins/paths.py` | P1 | `tests/test_plugin_paths.py` |

**测试策略**:
- 配置序列化/反序列化测试
- 存储层 CRUD 测试（使用 tmp_path fixture）
- 插件 manifest 解析测试
- 插件路径解析（frozen/dev 模式）测试
- 文档提取决策树路由测试（mock 各后端）

**验收标准**:
- [ ] 核心模块测试文件已创建
- [ ] `uv run pytest` 通过
- [ ] 覆盖率 >= 60%

#### 4.6.3 前端构建验证 CI (I-02)

最小可行 CI：仅做前端构建验证（不涉及 Python 环境复杂度）。

创建 `.github/workflows/frontend-build.yml`:

```yaml
name: Frontend Build Check
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: oven-sh/setup-bun@v2
      - run: cd frontend && bun install && bun run build
```

**验收标准**:
- [ ] GitHub Actions workflow 文件已创建
- [ ] push/PR 时自动触发前端构建验证
- [ ] 构建失败时 CI 标红

---

## 5. 技术约束

### 5.1 不变的约束

| 约束 | 原因 |
|------|------|
| JSON subprocess 通信协议 | 已验证稳定，无需修改 |
| 内置后端（PP-OCR、markitdown）运行方式 | 主进程内运行，不涉及插件 venv |
| Frozen dataclass 配置 | 架构一致性好 |
| PyWebVue bridge @expose 模式 | 前后端通信核心 |

### 5.2 新增约束

| 约束 | 原因 |
|------|------|
| 插件 ID 必须匹配 manifest 文件名 | 简化发现逻辑 |
| manifest 中 `package` 字段必须含版本锁定（`==`） | 防止版本漂移 |
| 插件 venv 不可写在程序安装目录 | 跨平台权限兼容 |
| 健康检查不可使用标记文件 | 需要实际验证 |

---

## 6. 实现计划

### Phase 1: 插件目录迁移与独立 venv (P0)

**预计工期**: 3-4 天

1. `py/plugins/paths.py` -- 重构为支持 per-plugin 目录
2. `py/plugins/manager.py` -- 所有方法接受 `plugin_id`，独立 venv 管理
3. `py/plugins/runner.py` -- 根据 `plugin_id` 解析 venv
4. `py/api/ocr_plugin.py` -- 适配新接口
5. `frontend/src/composables/usePlugin.ts` -- 适配前端
6. 旧目录自动迁移逻辑

### Phase 2: Manifest 与注册表 (P0)

**预计工期**: 2-3 天

1. 设计并实现 `PluginManifest` 数据类
2. 编写 docling/opendataloader 的 toml manifest
3. 实现 `PluginRegistry` 从 manifest 加载
4. 重构 `PluginManager` 使用 registry 替代 `PACKAGE_NAMES`
5. 修复安装路径的版本映射问题
6. 更新前端展示插件信息（名称、描述从 manifest 获取）

### Phase 3: 健康检查与 uv 升级 (P1)

**预计工期**: 1-2 天

1. 移除 `.venv_valid` 机制
2. 实现实际健康检查（python 存在性 + 可执行性）
3. 自动重建逻辑
4. uv 版本可配置化

### Phase 4: 开发基础设施 (P2)

**预计工期**: 2-3 天

1. `pyproject.toml` 添加 dev 依赖
2. 核心模块单元测试编写
3. GitHub Actions 前端构建验证

### 总预计工期: 8-12 天

---

## 7. 风险评估

| 风险 | 严重度 | 概率 | 缓解措施 |
|------|--------|------|----------|
| 插件 venv 迁移导致已安装用户环境丢失 | 高 | 低 | 自动迁移 + 迁移失败回退 |
| 独立 venv 增加磁盘占用（每个 venv ~30MB 基础） | 中 | 高 | 仅为已安装的插件创建 venv；提供 venv 大小展示 |
| toml 解析引入新依赖 | 低 | 低 | Python 3.11 标准库 `tomllib` 可用 |
| 健康检查增加启动时间 | 低 | 中 | 健康检查仅在访问插件功能时触发，不在应用启动时 |
| uv 版本升级导致不兼容 | 中 | 低 | uv 向后兼容 pip 接口；构建时可指定版本 |

---

## 8. 兼容性说明

### 8.1 向后兼容

- 已安装的插件自动迁移，无需用户重新安装
- 前端 API 调用签名保持一致（`call("install_plugin", "docling")`）
- 配置文件 `PluginConfig` 字段不变

### 8.2 升级路径

- v2.1.x -> v2.2.0: 自动迁移插件目录，无手动操作
- v2.2.0 新增 manifest 文件，随应用一起分发，无需用户干预

---

## 9. 验收标准总表

### P0 (必须)

- [ ] 插件 venv 位于 `{data_dir}/plugins/{plugin_id}/.venv/`（非程序安装目录）
- [ ] 每个插件独立 venv，互不影响
- [ ] 插件元信息从 toml manifest 加载，`PACKAGE_NAMES` 硬编码已移除
- [ ] 安装时版本号从 manifest 获取
- [ ] 旧目录自动迁移

### P1 (应当)

- [ ] `.venv_valid` 标记文件机制已移除
- [ ] 健康检查通过实际验证 venv python 可用性
- [ ] uv 版本可配置，默认 >= 0.6.14

### P2 (建议)

- [ ] `pyproject.toml` 包含 dev 依赖组
- [ ] 核心模块单元测试覆盖率 >= 60%
- [ ] GitHub Actions 前端构建验证 workflow 已配置

---

## 10. 未来展望 (v2.3.0+)

以下内容不在 v2.2.0 范围内，但应作为后续版本的设计参考：

| 功能 | 版本 | 说明 |
|------|------|------|
| 插件签名/校验 | v2.3.0 | 防止恶意插件注入 |
| 外部插件发现 | v2.3.0 | 从远程仓库发现和安装插件 |
| 插件权限模型 | v2.3.0 | 限制插件的网络/文件访问 |
| 完整 CI 流水线 | v2.3.0 | Python lint + type check + test |
| 插件依赖锁定 (uv.lock) | v2.3.0 | 可复现的插件环境构建 |
