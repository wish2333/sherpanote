# Test Plan: Java Runtime Detection

## Scope
`py/plugins/java_detect.py`

## Prerequisites
- Windows environment (primary test platform)
- Optional: JDK 11, 17, or 21 installed
- Optional: JDK 8 installed (for version-too-old test)
- Ability to set/unset `JAVA_HOME` environment variable

---

## Test Cases

### TC-001: Detect via JAVA_HOME (P0)
- **Steps**:
  1. Set `JAVA_HOME` to a JDK 17 installation path
  2. Ensure `java` is NOT in current PATH (temporarily remove)
  3. Call `detect_java(manual_path=None)`
- **Expected**: Returns `found=True`, `path` points to `{JAVA_HOME}/bin/java`, `version` starts with "17".
- **Priority**: P0

### TC-002: Detect via system PATH (P0)
- **Steps**:
  1. Unset `JAVA_HOME`
  2. Ensure `java` is in system PATH
  3. Call `detect_java(manual_path=None)`
- **Expected**: Returns `found=True` if PATH contains Java 11+. `path` is the java binary location. `version` is the major version >= 11.
- **Priority**: P0

### TC-003: Manual path -- valid (P0)
- **Steps**:
  1. Unset `JAVA_HOME`, remove java from PATH
  2. Call `detect_java(manual_path="C:/path/to/jdk-17/bin/java.exe")`
- **Expected**: Returns `found=True`, `path` matches the manual path, `version` starts with "17".
- **Priority**: P0

### TC-004: Manual path -- invalid (P0)
- **Steps**:
  1. Call `detect_java(manual_path="C:/nonexistent/java.exe")`
- **Expected**: Returns `found=False`, `error` describes "not found" or similar. No crash.
- **Priority**: P0

### TC-005: Old Java version (Java 8) (P0)
- **Steps**:
  1. Point JAVA_HOME or manual_path to a Java 8 installation
  2. Call `detect_java()`
- **Expected**: Returns `found=False` (version < 11). `error` message indicates version too old. `version` field contains "8" (or "1.8").
- **Priority**: P0

### TC-006: No Java installed at all (P0)
- **Steps**:
  1. Unset JAVA_HOME, remove java from PATH, no known Java directories
  2. Call `detect_java(manual_path=None)`
- **Expected**: Returns `found=False`. `error` message is user-friendly, suggests installing from Adoptium (https://adoptium.net/). No crash.
- **Priority**: P0

### TC-007: Windows known paths (P1)
- **Steps**:
  1. Install a JDK to `C:\Program Files\Java\jdk-17`
  2. Unset JAVA_HOME, remove java from PATH
  3. Call `detect_java(manual_path=None)`
- **Expected**: Detection finds java under `C:\Program Files\Java\*`. `found=True`.
- **Priority**: P1

### TC-008: Version parsing -- "1.8.0_292" (P0)
- **Steps**:
  1. Simulate `java -version` output containing `"1.8.0_292"`
  2. Parse the version string
- **Expected**: Major version extracted as `8`. `found=False` (8 < 11).
- **Priority**: P0

### TC-009: Version parsing -- "11.0.20+7" (P0)
- **Steps**:
  1. Simulate `java -version` output containing `"11.0.20"`
  2. Parse the version string
- **Expected**: Major version extracted as `11`. `found=True`.
- **Priority**: P0

### TC-010: Version parsing -- "21.0.2" (P0)
- **Steps**:
  1. Simulate `java -version` output containing `"21.0.2"`
  2. Parse the version string
- **Expected**: Major version extracted as `21`. `found=True`.
- **Priority**: P0

### TC-011: Version parsing -- "openjdk version "17.0.1"" (P0)
- **Steps**:
  1. Simulate `java -version` output with OpenJDK-style prefix: `openjdk version "17.0.1" 2021-10-19 LTS`
  2. Parse the version string
- **Expected**: Major version extracted as `17`. `found=True`.
- **Priority**: P0

### TC-012: Eclipse Adoptium path (Windows) (P2)
- **Steps**:
  1. Install Eclipse Adoptium JDK at `C:\Program Files\Eclipse Adoptium\jdk-17.0.9.9-hotspot\`
  2. Unset JAVA_HOME, remove java from PATH
  3. Call `detect_java(manual_path=None)`
- **Expected**: Detection finds java under Eclipse Adoptium path. `found=True`.
- **Priority**: P2

---

## Regression Check
- [ ] Detection does not modify system environment variables
- [ ] Detection result is cached or re-runnable without side effects
- [ ] Error messages do not leak sensitive path information unnecessarily
