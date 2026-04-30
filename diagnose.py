"""Diagnostic script to check for common crash causes."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

print("=" * 70)
print("SherpaNote Diagnostics")
print("=" * 70)

# 1. Check Python environment
print("\n[1] Python Environment")
print(f"  Python: {sys.version}")
print(f"  Executable: {sys.executable}")
print(f"  Platform: {sys.platform}")

# 2. Check critical packages
print("\n[2] Critical Packages")
try:
    import webview
    print(f"  pywebview: {webview.__version__ if hasattr(webview, '__version__') else 'unknown'}")
except ImportError as e:
    print(f"  pywebview: MISSING - {e}")

try:
    import sherpa_onnx
    print(f"  sherpa_onnx: {getattr(sherpa_onnx, '__version__', 'unknown')}")
except ImportError as e:
    print(f"  sherpa_onnx: MISSING - {e}")

try:
    import numpy as np
    print(f"  numpy: {np.__version__}")
except ImportError as e:
    print(f"  numpy: MISSING - {e}")

# 3. Check model directories
print("\n[3] Model Directories")
from py.config import _DEFAULT_MODELS_DIR
models_dir = Path(_DEFAULT_MODELS_DIR)
print(f"  Default models dir: {models_dir}")
print(f"  Exists: {models_dir.exists()}")

if models_dir.exists():
    streaming_models = [
        "sherpa-onnx-streaming-paraformer-bilingual-zh-en",
        "sherpa-onnx-streaming-zipformer-en",
        "sherpa-onnx-streaming-zipformer-zh",
    ]
    offline_models = [
        "sherpa-onnx-paraformer-zh",
        "sherpa-onnx-whisper-small",
        "sherpa-onnx-whisper-base",
    ]

    print("  Streaming models found:")
    for name in streaming_models:
        if (models_dir / name).exists():
            print(f"    [OK] {name}")
        else:
            print(f"    [--] {name} (not found)")

    print("  Offline models found:")
    for name in offline_models:
        if (models_dir / name).exists():
            print(f"    [OK] {name}")
        else:
            print(f"    [--] {name} (not found)")

    # Check for tokens.txt
    if (models_dir / "tokens.txt").exists():
        print("    [OK] tokens.txt in models root")
    else:
        print("    [WARN] tokens.txt not in models root")

# 4. Threading check
print("\n[4] Threading")
print(f"  Current thread: {threading.current_thread().name}")
print(f"  Active threads: {threading.active_count()}")

# 5. Check for log directory
print("\n[5] Logging")
log_dir = Path.home() / ".sherpanote" / "logs"
print(f"  Log directory: {log_dir}")
print(f"  Exists: {log_dir.exists()}")
if log_dir.exists():
    log_files = list(log_dir.glob("*.log"))
    print(f"  Log files: {len(log_files)}")
    for log in log_files[-3:]:  # Show last 3
        size = log.stat().st_size / 1024
        print(f"    {log.name} ({size:.1f} KB)")

    crash_file = log_dir / "last_crash.txt"
    if crash_file.exists():
        print(f"  [CRASH REPORT FOUND] {crash_file}")
        print("  Last few lines:")
        try:
            with open(crash_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()[-10:]
                for line in lines:
                    print(f"    {line.rstrip()}")
        except Exception as e:
            print(f"    (could not read: {e})")

# 6. pywebview specific checks
print("\n[6] pywebview Configuration")
try:
    import webview
    # Check if we're on Windows
    if sys.platform == "win32":
        print("  Platform: Windows (WebView2/COM)")
        print("  Important: evaluate_js must be called on main thread only")
        print("  Fix: _flush_events queue + setInterval (implemented)")
except Exception as e:
    print(f"  Error checking pywebview: {e}")

# 7. Bridge class check
print("\n[7] Bridge Implementation")
try:
    from pywebvue.bridge import Bridge
    bridge = Bridge()
    print(f"  Bridge._event_queue type: {type(bridge._event_queue).__name__}")
    print(f"  Bridge._window initially: {bridge._window}")
    print(f"  Has _flush_events: {hasattr(Bridge, '_flush_events')}")
    print(f"  Has get_dropped_files: {hasattr(Bridge, 'get_dropped_files')}")
except Exception as e:
    print(f"  Error: {e}")

# 8. SherpaASR check
print("\n[8] SherpaASR Implementation")
try:
    from py.asr import SherpaASR
    print(f"  SherpaASR has _lock: {hasattr(SherpaASR, '_lock')}")
    # Create instance to check
    from py.config import AsrConfig
    asr = SherpaASR(AsrConfig())
    print(f"  Instance lock type: {type(asr._lock).__name__}")
    print(f"  Instance has _online_recognizer (None initially): {asr._online_recognizer is None}")
    print(f"  Instance has _offline_recognizer (None initially): {asr._offline_recognizer is None}")
except Exception as e:
    print(f"  Error: {e}")

print("\n" + "=" * 70)
print("Diagnostics complete")
print("=" * 70)
print("\nIf crashes persist:")
print("1. Check the log file: ~/.sherpanote/data/logs/sherpanote.log")
print("2. Look for 'CRITICAL' entries or crash traces")
print("3. Run with debugger: uv run python -m debugpy --listen 5678 main.py")
print("=" * 70)
