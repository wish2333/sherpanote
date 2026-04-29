"""Multi-strategy Java 11+ runtime detection.

Required by opendataloader-pdf which needs Java 11+ to run.

Detection strategies (in order):
1. User manual override from config
2. JAVA_HOME environment variable
3. System PATH
4. Platform-specific known installation paths
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JavaDetectionResult:
    """Result of Java runtime detection."""

    found: bool
    path: str | None = None
    version: str | None = None
    error: str | None = None


def _run_java_version(java_path: str) -> tuple[str, str, int]:
    """Run java -version and return (stdout, stderr, returncode)."""
    try:
        result = subprocess.run(
            [java_path, "-version"],
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
            errors="replace",
        )
        # java -version outputs to stderr, not stdout
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Timed out", -1
    except FileNotFoundError:
        return "", "File not found", -1
    except OSError as exc:
        return "", str(exc), -1


def _parse_java_version(output: str) -> str | None:
    """Parse Java version from 'java -version' output.

    Handles multiple output formats:
    - '1.8.0_292' -> 8
    - '11.0.20' -> 11
    - '17.0.8+7' -> 17
    - '21.0.2' -> 21
    - openjdk version "21.0.2" ...
    """
    # Pattern for Java 9+ version format
    match = re.search(r'version "(\d+)', output)
    if match:
        return match.group(1)

    # Pattern for old 1.x format
    match = re.search(r'version "1\.(\d+)', output)
    if match:
        return match.group(1)

    # Fallback: first number in output
    match = re.search(r'(\d+)\.\d+', output)
    if match:
        return match.group(1)

    return None


def validate_java_version(java_path: str) -> tuple[bool, str | None, str | None]:
    """Check if a Java executable meets the minimum version requirement.

    Args:
        java_path: Path to the java executable.

    Returns:
        (is_valid, version_string_or_none, error_or_none).
    """
    stdout, stderr, code = _run_java_version(java_path)
    output = stdout + stderr

    if code != 0:
        return False, None, f"java -version failed (exit code {code}): {output.strip()}"

    version_str = _parse_java_version(output)
    if version_str is None:
        return False, None, f"Could not parse Java version from: {output.strip()}"

    try:
        major = int(version_str)
    except ValueError:
        return False, None, f"Invalid Java version number: {version_str}"

    if major < 11:
        return False, version_str, f"Java {major} found, but Java 11+ is required"

    return True, version_str, None


def detect_java(
    manual_path: str | None = None,
    on_search: Callable[[str], None] | None = None,
) -> JavaDetectionResult:
    """Detect Java 11+ using multiple strategies.

    Args:
        manual_path: Optional user-specified Java path (highest priority).
        on_search: Optional callback receiving search step descriptions.

    Returns:
        JavaDetectionResult with found/path/version/error.
    """

    def _log(msg: str) -> None:
        logger.debug("Java detection: %s", msg)
        if on_search:
            on_search(msg)

    # Strategy 1: Manual override
    if manual_path:
        _log(f"Checking manual path: {manual_path}")
        p = Path(manual_path)
        if p.exists():
            valid, version, error = validate_java_version(str(p))
            if valid:
                return JavaDetectionResult(
                    found=True, path=str(p), version=version,
                )
            return JavaDetectionResult(
                found=False, error=f"Manual path invalid: {error}",
            )
        return JavaDetectionResult(
            found=False, error=f"Manual Java path not found: {manual_path}",
        )

    # Strategy 2: JAVA_HOME
    import os
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        candidates = [
            Path(java_home) / "bin" / ("java.exe" if _is_windows() else "java"),
        ]
        for java in candidates:
            if java.exists():
                _log(f"Found via JAVA_HOME: {java}")
                valid, version, error = validate_java_version(str(java))
                if valid:
                    return JavaDetectionResult(
                        found=True, path=str(java), version=version,
                    )
                _log(f"JAVA_HOME Java too old: {error}")

    # Strategy 3: System PATH
    system_java = shutil.which("java")
    if system_java:
        _log(f"Found via PATH: {system_java}")
        valid, version, error = validate_java_version(system_java)
        if valid:
            return JavaDetectionResult(
                found=True, path=system_java, version=version,
            )
        _log(f"PATH Java too old: {error}")

    # Strategy 4: Platform-specific known paths
    _log("Searching platform installation paths...")
    for java in _get_known_java_paths():
        if java.exists():
            _log(f"Found at known path: {java}")
            valid, version, error = validate_java_version(str(java))
            if valid:
                return JavaDetectionResult(
                    found=True, path=str(java), version=version,
                )
            _log(f"Known path Java too old: {error}")

    return JavaDetectionResult(
        found=False,
        error="Java 11+ not found. Install from https://adoptium.net/ or specify path in settings.",
    )


def _is_windows() -> bool:
    import sys
    return sys.platform == "win32"


def _get_known_java_paths() -> list[Path]:
    """Return list of candidate Java paths for the current platform."""
    import sys
    candidates: list[Path] = []

    if sys.platform == "win32":
        program_files = [
            Path(os.environ.get("ProgramFiles", "C:\\Program Files")),
            Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")),
        ]
        for pf in program_files:
            # Oracle JDK
            candidates.extend(sorted(pf.glob("Java\\*\\bin\\java.exe")))
            # Eclipse Adoptium / Temurin
            candidates.extend(sorted(pf.glob("Eclipse Adoptium\\*\\bin\\java.exe")))
            # Microsoft OpenJDK
            candidates.extend(sorted(pf.glob("Microsoft\\*\\bin\\java.exe")))
    elif sys.platform == "darwin":
        jvm_base = Path("/Library/Java/JavaVirtualMachines")
        candidates.extend(sorted(jvm_base.glob("*/Contents/Home/bin/java")))
        # Homebrew
        candidates.append(Path("/opt/homebrew/opt/openjdk/bin/java"))
        candidates.append(Path("/usr/local/opt/openjdk/bin/java"))
    else:
        # Linux
        candidates.extend(sorted(Path("/usr/lib/jvm").glob("*/bin/java")))
        candidates.extend(sorted(Path("/usr/lib/jvm").glob("java-*\\*\\bin\\java")))

    return candidates


# Need os import at module level for _get_known_java_paths
import os
