## ADDED Requirements

### Requirement: System can download a model archive with progress reporting
The system SHALL provide a function in `py/model_manager.py` to download a model archive from the configured download source. The download SHALL report progress via a callback invoked with `(bytes_downloaded: int, total_bytes: int)` tuples. The system SHALL use `urllib.request` for HTTP downloads with chunked reading (64KB chunks).

#### Scenario: Successful download with progress
- **WHEN** `download_model(model_id, on_progress=callback)` is called for a valid model
- **THEN** the model archive SHALL be downloaded to a temporary file
- **AND** the `on_progress` callback SHALL be invoked at least once per MB downloaded with current and total byte counts

#### Scenario: Download resumes on partial file
- **WHEN** a partial download exists for the model (temp file present)
- **THEN** the download SHALL resume from the last byte using HTTP Range header
- **AND** progress reporting SHALL reflect the combined already-downloaded + newly-downloaded bytes

#### Scenario: Download failure with clear error
- **WHEN** the download fails due to network error or HTTP error status
- **THEN** a clear error message SHALL be returned including the failure reason
- **AND** the partial download file SHALL be preserved (not deleted) to allow retry

### Requirement: System verifies model archive integrity after download
The system SHALL verify the SHA256 checksum of the downloaded archive against the expected hash from the model registry. Verification SHALL occur before extraction.

#### Scenario: Checksum matches
- **WHEN** the downloaded archive SHA256 matches the registry entry's expected SHA256
- **THEN** verification SHALL pass and extraction SHALL proceed

#### Scenario: Checksum mismatch
- **WHEN** the downloaded archive SHA256 does NOT match the expected SHA256
- **THEN** an integrity error SHALL be raised with a message indicating the mismatch
- **AND** the corrupted archive file SHALL be deleted

### Requirement: System extracts model archive to the models directory
The system SHALL extract the downloaded `.tar.bz2` archive into the configured models base directory (`~/sherpanote/models/`). The extraction SHALL create a subdirectory matching the `model_id`. For the VAD model, the `.onnx` file SHALL be placed directly in the models base directory.

#### Scenario: Standard model extraction
- **WHEN** `extract_model(model_id, archive_path, models_dir)` is called for a non-VAD model
- **THEN** the archive SHALL be extracted to `{models_dir}/{model_id}/`
- **AND** the temporary archive file SHALL be deleted after successful extraction

#### Scenario: VAD model extraction
- **WHEN** `extract_model("silero_vad", archive_path, models_dir)` is called
- **THEN** `silero_vad.onnx` SHALL be placed at `{models_dir}/silero_vad.onnx`

#### Scenario: Directory already exists
- **WHEN** the target directory already exists (model already installed)
- **THEN** the system SHALL prompt for confirmation before overwriting
- **AND** if confirmed, the existing directory SHALL be replaced

### Requirement: System validates installed model files
The system SHALL verify that all `required_files` listed in the model registry entry exist in the installed model directory. This validation runs after extraction and can also be run on previously installed models.

#### Scenario: All required files present
- **WHEN** `validate_model(model_id, models_dir)` is called and all required files exist
- **THEN** validation SHALL return `{"valid": True}`

#### Scenario: Missing required files
- **WHEN** `validate_model(model_id, models_dir)` is called but some required files are missing
- **THEN** validation SHALL return `{"valid": False, "missing": ["file1.onnx", ...]}`

### Requirement: System provides combined download-and-install operation
The system SHALL provide a high-level function that combines download, verification, extraction, and validation into a single operation with progress reporting.

#### Scenario: Full install succeeds
- **WHEN** `install_model(model_id, models_dir, on_progress=callback)` is called for a valid model
- **THEN** the model SHALL be downloaded, verified, extracted, and validated
- **AND** progress SHALL be reported across all phases (download: 0-85%, extract: 85-95%, validate: 95-100%)

#### Scenario: Install fails during download
- **WHEN** the download phase fails
- **THEN** no files SHALL be left in the models directory for this model
- **AND** a descriptive error SHALL be returned

### Requirement: System can delete an installed model
The system SHALL provide a function to delete an installed model directory.

#### Scenario: Delete installed model
- **WHEN** `delete_model(model_id, models_dir)` is called and the model directory exists
- **THEN** the model directory SHALL be recursively deleted
- **AND** success SHALL be returned

#### Scenario: Delete nonexistent model
- **WHEN** `delete_model(model_id, models_dir)` is called but the model directory does not exist
- **THEN** an appropriate error SHALL be returned

### Requirement: System lists installed models with status
The system SHALL scan the models base directory and return a list of installed models with their IDs and validation status.

#### Scenario: Multiple models installed
- **WHEN** `list_installed_models(models_dir)` is called and models exist
- **THEN** a list SHALL be returned with each entry containing `model_id`, `valid` (bool), and `size_mb` (directory size)

#### Scenario: No models installed
- **WHEN** `list_installed_models(models_dir)` is called and no model directories exist
- **THEN** an empty list SHALL be returned

### Requirement: VAD model is auto-downloaded with first ASR model
The system SHALL automatically download the VAD model (`silero_vad`) if it is not already installed when any ASR model is being installed.

#### Scenario: VAD not installed, ASR model install triggered
- **WHEN** `install_model("sherpa-onnx-paraformer-zh-2024-03-09", ...)` is called and `silero_vad.onnx` is not present in models_dir
- **THEN** the VAD model SHALL be downloaded automatically before or after the ASR model

#### Scenario: VAD already installed
- **WHEN** `install_model(...)` is called and `silero_vad.onnx` already exists
- **THEN** the VAD download SHALL be skipped
