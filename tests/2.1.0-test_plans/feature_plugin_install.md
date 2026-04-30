# Test Plan: Plugin Installation Flow

## Scope
`py/plugins/manager.py` (`PluginManager`), `py/plugins/paths.py`

## Prerequisites
- Python 3.11+ available (system or bundled)
- `uv` available on PATH
- Network connection for online tests
- Clean test venv (no prior plugin installation)

---

## Test Cases

### TC-001: Online install -- docling (P0)
- **Steps**:
  1. Create a fresh plugin venv via `PluginManager.ensure_venv()`
  2. Call `PluginManager.install_package("docling", on_output=callback)`
  3. Wait for installation to complete
- **Expected**: Installation succeeds. `callback` receives progress lines. Final `get_installed_version("docling")` returns a version string.
- **Priority**: P0

### TC-002: Install with progress callbacks (P0)
- **Steps**:
  1. Register an `on_output` callback during `install_package("docling")`
  2. Capture all callback invocations
- **Expected**: Callback is invoked multiple times with uv pip output lines. Lines are non-empty strings.
- **Priority**: P0

### TC-003: Offline install (no network) (P0)
- **Steps**:
  1. Disconnect from network (or simulate with an invalid PyPI index URL)
  2. Call `PluginManager.install_package("docling")`
- **Expected**: Returns `{"success": False, "error": "..."}`. Error message describes connectivity issue. No crash.
- **Priority**: P0

### TC-004: Insufficient disk space (P2)
- **Steps**:
  1. Simulate low disk space (fill a test drive to near capacity)
  2. Call `PluginManager.install_package("docling")`
- **Expected**: Installation fails gracefully. Error message indicates disk space issue. Partial files cleaned up.
- **Priority**: P2

### TC-005: Permission error (P1)
- **Steps**:
  1. Set the venv directory read-only (or choose a path the user cannot write to)
  2. Call `PluginManager.ensure_venv()` or `install_package("docling")`
- **Expected**: Returns error status. No crash. Error message indicates permission issue.
- **Priority**: P1

### TC-006: Already installed package re-install (P1)
- **Steps**:
  1. Ensure docling is already installed in the venv
  2. Call `PluginManager.install_package("docling")` again
- **Expected**: Succeeds (reinstall or no-op). Returns `{"success": True}`. Does not corrupt existing installation.
- **Priority**: P1

### TC-007: Uninstall package (P0)
- **Steps**:
  1. Ensure docling is installed in the venv
  2. Call `PluginManager.uninstall_package("docling")`
- **Expected**: Returns `{"success": True}`. `get_installed_version("docling")` returns `None`.
- **Priority**: P0

### TC-008: Uninstall non-existent package (P1)
- **Steps**:
  1. Ensure docling is NOT installed
  2. Call `PluginManager.uninstall_package("docling")`
- **Expected**: Returns `{"success": True}` (or gracefully reports "not installed"). No crash or error.
- **Priority**: P1

### TC-009: Destroy venv (P0)
- **Steps**:
  1. Create a venv and install one or more packages
  2. Call `PluginManager.destroy_venv()`
- **Expected**: Venv directory is removed. Subsequent `ensure_venv()` recreates it cleanly.
- **Priority**: P0

### TC-010: Ensure venv -- first creation (P0)
- **Steps**:
  1. Delete existing venv
  2. Call `PluginManager.ensure_venv()`
- **Expected**: Venv directory is created. Marker file (`.venv_ready` or similar) written. Subprocess can run Python from the venv.
- **Priority**: P0

### TC-011: Ensure venv -- already exists (P1)
- **Steps**:
  1. With a valid venv already present
  2. Call `PluginManager.ensure_venv()` again
- **Expected**: No duplicate creation. Returns quickly. Marker file unchanged.
- **Priority**: P1

### TC-012: get_all_status -- reflects reality (P0)
- **Steps**:
  1. With docling installed and opendataloader not installed
  2. Call `PluginManager.get_all_status()`
- **Expected**:
  - `statuses["docling"].installed == True`, `statuses["docling"].version` is a valid version string
  - `statuses["opendataloader"].installed == False`, `statuses["opendataloader"].version is None`
- **Priority**: P0

### TC-013: install_package with special path characters (P2)
- **Steps**:
  1. Create a venv at a path containing spaces and Unicode characters
  2. Call `PluginManager.install_package("docling")`
- **Expected**: Installation succeeds despite special characters in path.
- **Priority**: P2

---

## Regression Check
- [ ] Plugin venv uses the correct Python interpreter (bundled in frozen mode, system in dev mode)
- [ ] uv binary is found and used for all package operations
- [ ] No packages leak into the main application environment
