# 多平台Python应用扩展

**导出日期**: 2026年5月8日


## User 1
一个python打包的多平台应用程序（win+macos+linux），如果想在打包后能够让用户自行选装其他python依赖库以实现其他功能，如何实现

## GPT 1
我会按“打包形态”和“插件/依赖安装机制”拆开讲，因为这里的关键不是 `pip install` 本身，而是打包后的程序是否还带有可用的 Python 解释器与可写的依赖目录。

## GPT 2
懒洋洋爱睡觉，核心结论是：

**可以实现，但不要把“用户随便 pip install 到打包程序内部”当成主方案。**  
更稳的架构是：**主程序打包成固定核心 + 外部可写的插件/依赖目录 + 由你的程序控制安装、加载和隔离。**

---

## 1. 先判断你的打包方式

如果你用的是 **PyInstaller / Nuitka / cx_Freeze** 这类“冻结应用”，打包后的 exe/appimage/app 本质上不是一个完整的普通 Python 开发环境。

以 PyInstaller 为例，冻结程序运行时 `sys.executable` 指向的是启动器/bootloader，不是普通 Python 解释器；PyInstaller 还会把运行资源放到 bundle 或临时目录里。官方文档也说明，frozen app 会设置 `sys.frozen` 和 `sys._MEIPASS`，one-file 模式下还会解压到临时目录。citeturn442159view1

所以：

```python
subprocess.run([sys.executable, "-m", "pip", "install", "xxx"])
```

在冻结应用里通常**不是可靠方案**。

---

## 2. 推荐架构：主程序 + 用户依赖目录

你可以设计成这样：

```text
MyApp
├── 核心程序：已打包，稳定运行
├── 插件管理器：负责安装/卸载/检测可选功能
├── 用户依赖目录：
│   ├── Windows: %APPDATA%/MyApp/python-packages/
│   ├── macOS: ~/Library/Application Support/MyApp/python-packages/
│   └── Linux: ~/.local/share/MyApp/python-packages/
└── 可选功能：
    ├── OCR 功能 -> pillow, pytesseract
    ├── AI 功能 -> openai, tiktoken
    ├── 数据分析 -> pandas, numpy
    └── 图像处理 -> opencv-python
```

安装时不要写入程序安装目录，而是写入用户目录。然后启动时把该目录加入 `sys.path`。

示例：

```python
import sys
from pathlib import Path

USER_PACKAGE_DIR = Path.home() / ".myapp" / "packages"
USER_PACKAGE_DIR.mkdir(parents=True, exist_ok=True)

if str(USER_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(USER_PACKAGE_DIR))
```

之后动态检测：

```python
import importlib.util

def has_package(name: str) -> bool:
    return importlib.util.find_spec(name) is not None

if has_package("pandas"):
    import pandas as pd
else:
    print("请先安装数据分析扩展")
```

---

## 3. 安装依赖：三种可选路线

### 方案 A：内置一个真正的 Python 运行时，最可控

这是商业应用里比较稳的方式。

你随应用一起带一个独立 Python，例如：

```text
MyApp/
├── myapp.exe
├── runtime/
│   ├── python.exe
│   └── Lib/site-packages/
└── user_packages/
```

安装扩展时调用你内置的 Python：

```python
import subprocess
from pathlib import Path

python_exe = Path("runtime/python.exe")  # Windows 示例
target_dir = Path.home() / ".myapp" / "packages"

subprocess.run([
    str(python_exe),
    "-m", "pip",
    "install",
    "--target",
    str(target_dir),
    "pandas==2.2.3"
], check=True)
```

`pip install --target` 的作用就是把包安装到指定目录，而不是默认环境。pip 官方文档也列出了 `pip install` 的 requirement、constraint、index 等机制，可以用于控制安装源和版本解析。citeturn442159view0

这个方案优点是：

- 不依赖用户电脑有没有 Python；
- Windows/macOS/Linux 行为更一致；
- 可以固定 Python 版本；
- 可以限制依赖安装目录；
- 可以做插件市场、扩展管理器。

缺点是包体会变大。

---

### 方案 B：要求用户系统已有 Python，不推荐给普通用户

你可以检测系统 Python：

```python
import shutil

python_cmd = shutil.which("python") or shutil.which("python3")
```

然后：

```python
subprocess.run([
    python_cmd,
    "-m", "pip",
    "install",
    "--target",
    str(target_dir),
    "some-package"
], check=True)
```

但这个方案问题很多：

- 用户 Python 版本不一致；
- pip 可能不存在；
- macOS/Linux 可能权限混乱；
- Windows 多 Python 环境容易装错；
- 原生扩展包 ABI 不匹配。

适合开发者工具，不适合普通桌面应用。

---

### 方案 C：预下载 wheel 包，做“离线扩展包”

如果你不希望用户在线安装，可以提前为不同平台准备 wheel：

```text
extensions/
├── win_amd64_cp311/
│   ├── numpy.whl
│   └── pandas.whl
├── macosx_arm64_cp311/
│   ├── numpy.whl
│   └── pandas.whl
└── manylinux_x86_64_cp311/
    ├── numpy.whl
    └── pandas.whl
```

安装时：

```bash
python -m pip install \
  --no-index \
  --find-links ./extensions/win_amd64_cp311 \
  --target ~/.myapp/packages \
  pandas
```

这对商业软件更安全，因为你可以提前测试、签名和固定版本。

---

## 4. 不建议“完全开放让用户随便装包”

技术上可以让用户输入包名：

```python
install_package("requests")
```

但安全风险很高。

更好的设计是做白名单：

```python
FEATURES = {
    "data_analysis": {
        "display_name": "数据分析扩展",
        "requirements": [
            "pandas==2.2.3",
            "numpy==2.1.3"
        ]
    },
    "image_tools": {
        "display_name": "图像处理扩展",
        "requirements": [
            "pillow==11.0.0"
        ]
    }
}
```

然后用户只看到：

```text
[ ] 数据分析扩展
[ ] 图像处理扩展
[ ] OCR 扩展
[ ] AI 扩展
```

而不是让用户直接输入任意 pip 包。

---

## 5. 可选依赖在开发阶段可以用 extras 声明

如果你的项目本身也是一个 Python package，可以在 `pyproject.toml` 里声明：

```toml
[project.optional-dependencies]
ocr = [
    "pillow>=10",
    "pytesseract>=0.3"
]

data = [
    "pandas>=2.2",
    "numpy>=2.0"
]

ai = [
    "openai>=1.0",
    "tiktoken>=0.7"
]
```

然后开发者可以：

```bash
pip install myapp[ocr]
pip install myapp[data]
pip install myapp[ai]
```

Python Packaging User Guide 里对 dependency specifier 的说明提到，依赖声明可以包含 extras，用来启用可选功能；也可以使用版本限制、URL、环境标记等。citeturn442159view2

不过注意：**extras 只是声明依赖关系，不等于打包后的 GUI 程序自动具备安装能力。**  
你仍然需要一个插件管理器来调用 pip/uv/conda/你的扩展安装逻辑。

---

## 6. 最稳的加载方式：插件单独进程运行

如果可选依赖很复杂，尤其涉及：

- numpy
- pandas
- torch
- opencv
- playwright
- tensorflow
- cryptography
- lxml

建议不要直接在主进程里动态 import，而是做成 worker：

```text
主程序 GUI
   |
   | JSON-RPC / HTTP / stdin-stdout
   v
插件 Worker Python 进程
   |
   v
用户安装的可选依赖
```

好处：

- 某个插件崩了，不会拖死主程序；
- 不同插件可以用不同依赖环境；
- 依赖冲突更容易处理；
- 更新插件不用重打包主程序；
- 可以按功能隔离权限。

例如：

```python
subprocess.Popen([
    str(plugin_python),
    "-m",
    "myapp_plugins.data_worker"
])
```

---

## 7. 多平台时必须注意 ABI 和 wheel

Python 依赖不是所有包都能跨平台直接装。纯 Python 包问题不大，但带 C/C++/Rust 扩展的包必须匹配：

```text
操作系统：Windows / macOS / Linux
CPU 架构：x86_64 / arm64
Python 版本：cp310 / cp311 / cp312
libc：manylinux / musllinux
```

所以不要只写：

```text
numpy
opencv-python
```

而要考虑：

```text
numpy==2.1.3 ; platform_system == "Windows"
numpy==2.1.3 ; platform_system == "Darwin"
numpy==2.1.3 ; platform_system == "Linux"
```

Python dependency specifier 支持 environment markers，也就是根据平台、Python 版本等条件决定依赖是否生效。citeturn442159view2

---

## 8. 一个比较完整的实现模型

### 功能注册表

```python
FEATURES = {
    "ocr": {
        "name": "OCR 文字识别",
        "requirements": [
            "pillow==11.0.0",
            "pytesseract==0.3.13"
        ],
        "imports": ["PIL", "pytesseract"]
    },
    "data": {
        "name": "数据分析",
        "requirements": [
            "pandas==2.2.3",
            "numpy==2.1.3"
        ],
        "imports": ["pandas", "numpy"]
    }
}
```

### 检测功能是否可用

```python
import importlib.util

def feature_installed(feature: dict) -> bool:
    return all(
        importlib.util.find_spec(pkg) is not None
        for pkg in feature["imports"]
    )
```

### 安装功能依赖

```python
import subprocess
from pathlib import Path

APP_DIR = Path.home() / ".myapp"
PACKAGE_DIR = APP_DIR / "packages"
PACKAGE_DIR.mkdir(parents=True, exist_ok=True)

def install_feature(feature_id: str, python_exe: str):
    feature = FEATURES[feature_id]

    cmd = [
        python_exe,
        "-m",
        "pip",
        "install",
        "--target",
        str(PACKAGE_DIR),
        *feature["requirements"]
    ]

    subprocess.run(cmd, check=True)
```

### 启动时加载用户依赖目录

```python
import sys
from pathlib import Path

PACKAGE_DIR = Path.home() / ".myapp" / "packages"

if PACKAGE_DIR.exists():
    sys.path.insert(0, str(PACKAGE_DIR))
```

---

## 9. 我的建议方案

如果你是做面向普通用户的多平台桌面应用，我建议：

```text
主程序：PyInstaller / Nuitka 打包
Python runtime：随应用内置一个独立 Python
依赖安装：pip 或 uv 安装到用户目录
依赖来源：白名单 + 固定版本 + 可选离线 wheelhouse
插件执行：复杂功能放到子进程 worker
安全策略：不要允许用户任意输入 pip 包名
```

也就是：

```text
核心应用不要变
扩展能力外置
依赖安装进用户目录
插件通过白名单控制
复杂依赖用独立 worker 隔离
```

一句话总结：

**把打包程序当“壳”和“调度器”，把可选 Python 依赖放在用户可写目录或独立插件环境里安装，再通过 `sys.path` 或子进程加载；不要试图修改 frozen app 自身。**

## User 2
不用python runtime而用uv管理会不会更好

## GPT 3
我会把 `uv` 放在“依赖/环境管理器”的位置来判断，而不是把它当成 Python 解释器替代品；关键点是：它能管理 Python，但最终仍然需要一个 Python 运行时来执行代码。

## GPT 4
懒洋洋爱睡觉，**用 `uv` 管理会更好，但它不是“不用 Python runtime”的替代品**。更准确地说：

> **不要自己内置完整 Python runtime，可以改成：主程序内置 `uv` 二进制，由 `uv` 按需安装/管理 Python + venv + 依赖。**

这样通常比你手动带一个 `python.exe` / `python3` 目录更优雅。

---

## 结论

**推荐：PyInstaller/Nuitka 打包主程序 + 随包带 `uv` + 每个扩展一个 uv 管理的虚拟环境。**

结构大概是：

```text
MyApp/
├── myapp.exe / MyApp.app / myapp
├── bin/
│   └── uv / uv.exe
└── app core

用户目录：
~/.myapp/
├── runtimes/          # uv 管理的 Python
├── envs/
│   ├── ocr/
│   ├── data/
│   └── ai/
├── wheel-cache/
└── plugins/
```

主程序本身仍然是冻结后的应用。  
可选功能通过 `uv` 创建独立 Python 环境来跑。

---

## 为什么 `uv` 更适合这个场景

`uv` 官方定位就是一个跨平台 Python 包和项目管理工具，支持 Windows、macOS、Linux；它可以替代常见的 `pip`、`pip-tools`、`virtualenv`、`pyenv` 等工作流，并且支持安装和管理 Python 版本。citeturn644638view0

它还有一个很关键的点：**uv 自己不依赖 Python**。官方文档说明，uv 可以安装到任意 Python 环境，也可以修改指定虚拟环境；但它最终仍然需要找到一个 Python 环境来安装依赖和构建源码包。citeturn644638view2

所以它的实际意义是：

```text
不用你手动内置 Python runtime
但 uv 会帮你下载/管理 Python runtime
```

---

## 最推荐的落地方式

### 1. 主程序只负责 UI 和调度

主程序不要直接 `import pandas`、`import torch`、`import opencv`。

主程序只做：

```text
检测扩展是否安装
调用 uv 创建环境
调用 worker 子进程
和 worker 通过 JSON / HTTP / stdin-stdout 通信
```

---

### 2. 每个功能一个环境

例如：

```text
~/.myapp/envs/ocr
~/.myapp/envs/data
~/.myapp/envs/ai
```

安装 OCR 扩展：

```bash
uv venv ~/.myapp/envs/ocr --python 3.12
uv pip install --python ~/.myapp/envs/ocr pillow pytesseract
```

安装数据分析扩展：

```bash
uv venv ~/.myapp/envs/data --python 3.12
uv pip install --python ~/.myapp/envs/data pandas numpy
```

`uv venv` 可以创建虚拟环境；如果不激活环境，uv 也能自动发现 `.venv`，或者你可以显式用 `--python /path/to/venv` 指定目标环境。citeturn281237view1turn644638view2

---

### 3. 运行插件 worker

Windows：

```python
worker_python = r"C:\Users\User\.myapp\envs\data\Scripts\python.exe"
```

macOS / Linux：

```python
worker_python = "/home/user/.myapp/envs/data/bin/python"
```

然后：

```python
import subprocess

subprocess.Popen([
    worker_python,
    "-m",
    "myapp_plugins.data_worker"
])
```

这比把用户安装的依赖硬塞进主程序 `sys.path` 稳很多。

---

## `uv` 的最大优势

### 速度快

官方文档宣称 uv 比 pip 快 10–100 倍，并且有全局缓存，能减少重复下载和磁盘占用。citeturn644638view0

对于“用户点一下安装扩展”的场景，这个体验差异很明显。

---

### 可以自动管理 Python

用户电脑没有 Python 也没关系。uv 文档说明，如果系统已有 Python，它会自动检测并使用；如果缺少所需 Python，uv 可以自动下载并管理 Python 版本。citeturn644638view1

也就是说用户不需要自己装 Python。

---

### 更适合多平台

你可以在三个平台分别带一个对应的 `uv` 二进制：

```text
Windows: uv.exe
macOS arm64/x86_64: uv
Linux x86_64/aarch64: uv
```

uv 官方安装页也说明它可以通过独立安装器安装，并支持 macOS、Linux、Windows。citeturn644638view0

---

### 可以更好控制缓存和安装目录

uv 默认会把缓存放在用户目录下，例如 macOS/Linux 的 `$HOME/.cache/uv`，Windows 的 `%LOCALAPPDATA%\uv\cache`；也可以通过 `UV_CACHE_DIR` 改位置。citeturn281237view0

这对桌面应用很重要，因为你应该避免写入安装目录。

---

## 但要注意：uv 不是万能替代品

### 1. 它仍然需要 Python

uv 自己不依赖 Python，但安装依赖、运行插件、构建源码包时仍然需要 Python 环境。官方文档也明确说，uv 需要定位一个 Python 环境来安装依赖和构建源码包。citeturn644638view2

所以你不能理解成：

```text
uv = Python runtime 替代品
```

应该理解成：

```text
uv = Python runtime 管理器 + 依赖管理器 + 虚拟环境管理器
```

---

### 2. 首次使用可能需要联网下载 Python

如果你不内置 Python，第一次安装扩展时，uv 可能需要下载 Python。uv 文档说明，默认情况下 uv 会在需要时自动下载 Python，例如创建 venv 时如果系统没有 Python，就会先安装 Python。citeturn644638view1

所以你需要考虑：

```text
用户是否能联网
公司代理/证书环境
下载失败怎么提示
是否需要离线安装包
```

---

### 3. uv 和 pip 不是 100% 一模一样

uv 提供 pip-compatible interface，但官方也说明它不是 pip 的精确克隆，偏离常见 pip 工作流越远，越可能遇到行为差异。citeturn644638view3turn644638view4

所以不要让用户自由输入任意 pip 命令。  
最好由你的程序控制安装逻辑。

---

## 我建议你的最终架构

```text
主程序：
  PyInstaller / Nuitka 打包
  不带完整 Python 开发环境
  只带 uv 二进制

扩展管理：
  每个扩展一个 pyproject.toml 或 requirements.lock
  用 uv 创建独立 venv
  固定 Python 版本，例如 3.12
  固定依赖版本
  白名单安装，不允许用户任意 pip install

运行方式：
  主程序调用插件 worker 子进程
  worker 使用 uv 管理的 venv Python
  主程序和 worker 用 JSON-RPC / HTTP / stdin-stdout 通信
```

---

## 示例：安装一个扩展

```python
import subprocess
from pathlib import Path
import platform

APP_HOME = Path.home() / ".myapp"
UV = Path(__file__).parent / "bin" / ("uv.exe" if platform.system() == "Windows" else "uv")

def install_extension(name: str, requirements: list[str]):
    env_dir = APP_HOME / "envs" / name
    env_dir.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run([
        str(UV),
        "venv",
        str(env_dir),
        "--python",
        "3.12",
    ], check=True)

    subprocess.run([
        str(UV),
        "pip",
        "install",
        "--python",
        str(env_dir),
        *requirements,
    ], check=True)
```

调用：

```python
install_extension("data", [
    "pandas==2.2.3",
    "numpy==2.1.3",
])
```

---

## 离线版怎么做

如果你不想让用户现场联网，可以提前做 wheelhouse：

```text
resources/wheels/
├── win_amd64_cp312/
├── macos_arm64_cp312/
├── macos_x86_64_cp312/
└── linux_x86_64_cp312/
```

然后安装：

```bash
uv pip install \
  --python ~/.myapp/envs/data \
  --no-index \
  --find-links ./resources/wheels/win_amd64_cp312 \
  pandas numpy
```

`uv venv` 和 `uv pip install` 都支持配置索引、缓存、find-links 等参数；`--find-links` 可以指向本地 wheel/sdist 目录。citeturn281237view1

---

## 最佳实践选择

| 方案 | 推荐度 | 适合场景 |
|---|---:|---|
| 主程序内置完整 Python runtime | 中 | 完全离线、强控制、企业内部分发 |
| 主程序内置 uv，让 uv 管理 Python 和依赖 | **高** | 普通多平台桌面应用、扩展功能、按需安装 |
| 依赖用户系统 Python | 低 | 面向开发者的 CLI 工具 |
| 用户自由输入 pip 包名 | 低 | 风险高，容易崩环境 |
| 每个扩展独立 uv venv + worker | **最高** | 可维护、可隔离、跨平台更稳 |

---

所以我的建议是：

**用 uv 更好，但不要把它当 runtime 替代品。**  
你可以不内置 Python runtime，改为**内置 uv，让 uv 在用户目录里按需管理 Python 和扩展环境**。主程序只负责调度，插件功能放到独立 venv 的 worker 进程里跑。这样是目前最干净、最可维护的方案。

## User 3
https://github.com/wish2333/sherpanote评估一下该项目的插件管理器方案

## GPT 5
我会先看仓库结构、插件相关代码与文档，再按“依赖安装、隔离、安全、跨平台、可维护性”几个维度评估它是否适合你前面说的多平台打包场景。

## GPT 6
我已经看到了它不是“通用插件市场”式方案，而是“可选文档引擎后端管理器”：当前主要服务于 docling 和 opendataloader-pdf 两个重型可选依赖。这个定位会直接影响评价。

## GPT 7
懒洋洋爱睡觉，结论先说：

**SherpaNote 这个方案方向是对的，但它更像“可选文档处理后端管理器”，还不是完整意义上的“通用插件管理器”。**

如果你的目标是：  
**打包后的多平台桌面应用，让用户按需安装一些重型 Python 功能包**，它的思路值得参考。  
如果你的目标是：  
**让第三方开发者自由发布插件、用户自由扩展功能生态**，它还差一层插件协议、隔离模型和依赖治理。

---

## 我对它的评分

按“可选依赖管理”来评：

**8 / 10**

按“通用插件系统”来评：

**5.5 / 10**

它的核心设计是：

```text
主程序 PyInstaller 打包
    ↓
打包时可选择 --with-plugins
    ↓
随应用携带 python-build-standalone + uv
    ↓
运行后创建 plugin venv
    ↓
用 uv pip install 安装 docling / opendataloader-pdf
    ↓
插件功能通过 subprocess 执行
    ↓
主程序与插件通过 JSON stdin/stdout 通信
```

README 也明确写了它的插件系统是“bundled Python subprocess with uv”的运行时隔离，并且目前插件主要是 docling 与 opendataloader-pdf 这类文档提取后端。citeturn722767view0turn913338view0

---

## 方案优点

### 1. 没有把依赖塞进 frozen app，本质方向正确

它没有尝试在 PyInstaller 主程序内部直接 `pip install`，而是把可选依赖放到一个插件虚拟环境里。`manager.py` 里会用 bundled uv 创建 venv，再用 `uv pip install --python ` 安装包。这个方向非常适合你前面问的“打包后让用户选装 Python 依赖”的场景。citeturn221602view0

这比：

```python
sys.executable -m pip install xxx
```

稳定很多。

因为主程序是 frozen app，而插件依赖在单独 venv 里，不污染宿主环境。

---

### 2. 插件通过子进程跑，隔离做得比 `sys.path` 动态加载好

`runner.py` 里插件不是直接 import 到主进程，而是用 venv 里的 Python 执行：

```text
python -m py.plugins.runners.xxx --json-input ...
```

然后 stdout 返回 JSON，stderr 输出进度事件。这个模式很实用：插件崩溃、依赖冲突、原生库加载失败时，不容易直接拖死主 GUI 进程。citeturn221602view2

这个思路比：

```python
sys.path.insert(...)
import plugin
```

更适合桌面应用。

---

### 3. 对重型依赖很友好

它把 docling、opendataloader-pdf 这种“不是所有用户都需要、安装又重”的依赖放到可选后端中。README 里也写了 OCR/文档识别默认有 PP-OCR、markitdown，插件后端则是可选高级引擎。citeturn722767view0turn913338view0

这类功能非常适合插件化：

```text
基础用户：只用内置 OCR / markitdown
高级用户：再安装 docling / opendataloader-pdf
```

这能明显减小主包体积，也能避免一开始就把复杂依赖全塞给用户。

---

### 4. 失败回退逻辑不错

`DocumentExtractor` 里有明确决策树：图片走 PP-OCR，Office 文档走 markitdown，PDF 先判断文本层；如果配置的 docling 或 opendataloader 不可用，会回退到 markitdown 或 PP-OCR。citeturn913338view0

这个设计很重要。插件系统最怕“装不上就功能全废”，它这里做到了：

```text
插件可用 → 用高级引擎
插件不可用 → 回退内置引擎
```

用户体验会稳定很多。

---

## 主要问题

### 1. 现在是“共享 venv”，不适合长期扩展很多插件

它目前只有一个：

```text
data/plugins/.venv
```

所有插件都装进同一个环境。`paths.py` 里 frozen 模式下插件目录是基于可执行文件目录的 `data/plugins/.venv`。citeturn221602view1

两个插件时问题不大，但插件多了会遇到：

```text
插件 A 需要 numpy 1.x
插件 B 需要 numpy 2.x

插件 A 需要 pydantic 1.x
插件 B 需要 pydantic 2.x
```

共享 venv 很容易依赖冲突。

更稳的是：

```text
plugins/
├── docling/
│   └── .venv/
├── opendataloader/
│   └── .venv/
└── future_plugin_x/
    └── .venv/
```

也就是：**一个插件一个 venv**。

---

### 2. 插件目录放在程序目录下，打包发布时可能踩权限坑

`get_plugin_base_dir()` 在 frozen 模式下返回的是：

```text
{base_dir}/data/plugins/
```

而 `base_dir` 是可执行文件所在目录。citeturn221602view1

这在开发时没问题，但正式发布会有风险：

```text
Windows 安装到 Program Files → 普通用户可能无写权限
macOS .app 内部写入 → 可能破坏签名 / 权限不稳定
Linux AppImage / /opt 安装 → 也可能不可写
```

更推荐放到用户数据目录：

```text
Windows: %LOCALAPPDATA%/SherpaNote/plugins/
macOS: ~/Library/Application Support/SherpaNote/plugins/
Linux: ~/.local/share/SherpaNote/plugins/
```

这点我会认为是它当前方案里比较需要优先改的地方。

---

### 3. 它还不是“真正的插件协议”

现在的插件列表是硬编码的：

```python
DOCLING_PACKAGE = "docling==2.92.0"
OPENDATA_PACKAGE = "opendataloader-pdf==2.4.0"
PACKAGE_NAMES = {
    "docling": DOCLING_PACKAGE,
    "opendataloader": OPENDATA_PACKAGE,
}
```

也就是说，它目前不是那种可以让第三方丢一个插件包进来自动发现的机制，而是主程序预先知道有哪些后端、有哪些 runner、有哪些 UI 开关。citeturn221602view0turn913338view1turn913338view2

如果要升级成真正插件系统，至少要有：

```text
plugin.toml / manifest.json
插件 ID
插件版本
入口命令
依赖声明
权限声明
兼容的宿主版本
安装源
签名 / 校验
卸载策略
```

现在还没有这些。

---

### 4. 版本固定思路有，但安装路径里有一个疑点

`manager.py` 里定义了 pinned package：

```text
docling==2.92.0
opendataloader-pdf==2.4.0
```

但 `main.py` 的 `install_plugin(package_name)` 看起来是把前端传来的 `package_name` 直接传给 `pm.install_package(package_name)`；卸载时才做 `PACKAGE_NAMES.get(package_name, package_name)` 映射。citeturn852281view0turn221602view0

也就是说，如果前端传的是：

```text
docling
```

那实际安装可能是：

```bash
uv pip install docling
```

而不是：

```bash
uv pip install docling==2.92.0
```

这会导致版本漂移。  
这个点需要进一步核实 UI 传入的到底是 `docling` 还是 `docling==2.92.0`，但从后端代码看，**安装路径最好也统一走 PACKAGE_NAMES 映射**。

建议改成：

```python
from py.plugins.manager import PACKAGE_NAMES

pip_name = PACKAGE_NAMES.get(package_name, package_name)
result = pm.install_package(pip_name, on_output=on_output, index_url=index_url)
```

---

### 5. `.venv_valid` 标记太弱

它创建 venv 后写一个：

```text
.venv_valid
```

之后只要 marker 存在就认为 venv 可用。citeturn221602view0

但实际可能出现：

```text
python.exe 被杀软删了
site-packages 损坏
uv 版本变化后环境不兼容
用户手动删了一半目录
安装中断但 marker 仍存在
```

更稳的检测应该是：

```python
venv_python.exists()
and subprocess.run([venv_python, "-c", "import sys; print(sys.version)"])
```

甚至按插件检测：

```python
python -c "import docling"
python -c "import opendataloader_pdf"
```

---

### 6. uv 版本明显偏旧

`build.py` 里插件 runtime 固定：

```text
Python 3.11.11
uv 0.6.6
```

citeturn397026view0

但 uv 官方文档当前安装示例已经指向 0.11.11，且 uv 的 GitHub release 0.11.6 在 2026-04-09 修过一个低危卸载相关安全问题。citeturn825922view0turn315822view0

所以如果你参考这个方案，**不要照抄 uv 0.6.6**。  
应该把 uv 版本作为构建参数或配置项，并定期升级。

---

## 对你的场景怎么取舍

如果你的目标是：

```text
打包后的 win + macOS + Linux 应用
用户可选装 OCR、AI、数据分析、文档处理等能力
```

那 SherpaNote 这套方案可以借鉴：

```text
✅ bundled uv
✅ bundled Python / uv-managed Python
✅ 插件 venv
✅ 子进程执行插件
✅ JSON 协议通信
✅ UI 显示安装状态、进度、卸载
✅ 内置功能兜底
```

但不建议原样照搬：

```text
❌ 不建议所有插件共享一个 venv
❌ 不建议写入程序安装目录
❌ 不建议没有 lockfile
❌ 不建议后端直接安装前端传来的 package 字符串
❌ 不建议只靠 .venv_valid 判断环境可用
❌ 不建议把它称为完整插件生态
```

---

## 我建议你改成这个结构

```text
App Core
├── PyInstaller / Nuitka 主程序
├── bundled uv
├── bundled minimal Python 或 uv-managed Python
└── PluginManager

用户目录
└── MyApp/
    ├── plugins/
    │   ├── docling/
    │   │   ├── plugin.toml
    │   │   ├── uv.lock
    │   │   └── .venv/
    │   ├── opendataloader/
    │   │   ├── plugin.toml
    │   │   ├── uv.lock
    │   │   └── .venv/
    │   └── data_analysis/
    │       ├── plugin.toml
    │       ├── uv.lock
    │       └── .venv/
    ├── cache/
    ├── logs/
    └── models/
```

插件 manifest 可以这样：

```toml
id = "docling"
name = "Docling 文档解析"
version = "1.0.0"
python = "3.11"
entry = "py.plugins.runners.docling_runner"

dependencies = [
  "docling==2.92.0"
]

[permissions]
filesystem = ["read_user_selected_files"]
network = ["huggingface"]
```

安装时：

```bash
uv venv ~/.myapp/plugins/docling/.venv --python 3.11
uv pip sync ~/.myapp/plugins/docling/requirements.lock --python ~/.myapp/plugins/docling/.venv
```

运行时：

```bash
~/.myapp/plugins/docling/.venv/bin/python \
  -m py.plugins.runners.docling_runner \
  --json-input ...
```

这样就比 SherpaNote 当前方案更适合长期扩展。

---

## 最终评价

**SherpaNote 的方案非常适合做“可选重型依赖后端”**，尤其是 OCR、PDF、AI、视频下载、数据分析这类功能。它已经抓住了正确核心：**主程序 frozen，插件依赖外置，uv 管理环境，子进程隔离执行**。

但它还不是成熟插件平台。  
你可以把它当成一个很好的 MVP 参考，然后重点补这几块：

```text
1. 插件目录迁移到用户可写目录
2. 每个插件独立 venv
3. 安装时强制白名单 / manifest / lockfile
4. 修正安装路径的版本映射
5. venv 健康检查不要只靠 marker
6. uv 版本升级并做校验
7. 增加插件权限模型和签名校验
```

一句话：

**参考它的 runtime isolation + uv subprocess 方案，但不要照搬它的共享 venv 和硬编码后端管理方式。**
