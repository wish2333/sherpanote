## ADDED Requirements

### Requirement: Independent sherpa-onnx diagnostic script
The system SHALL provide a standalone Python script that can be run independently from the main application to verify sherpa-onnx functionality. The script MUST be runnable via `uv run scripts/test_sherpa.py --script`.

#### Scenario: Run diagnostic script with no arguments
- **WHEN** user runs the diagnostic script without arguments
- **THEN** the script checks sherpa_onnx importability
- **AND** scans the default model directories for available models
- **AND** reports which models were found (streaming and offline)
- **AND** reports sherpa_onnx version and installation status

#### Scenario: Run diagnostic with a specific audio file
- **WHEN** user runs the script with `--file <path>` argument pointing to a valid audio file
- **THEN** the script loads the best available offline model
- **AND** transcribes the audio file
- **AND** outputs the transcription result with timestamps
- **AND** logs detailed information: model load time, audio duration, inference time, number of segments

#### Scenario: Run diagnostic with streaming test
- **WHEN** user runs the script with `--streaming` flag
- **THEN** the script loads the best available streaming model
- **AND** simulates feeding audio chunks to the recognizer
- **AND** outputs partial and final results in real-time
- **AND** logs timing information for each chunk

### Requirement: Diagnostic script provides detailed logging
All diagnostic operations SHALL produce detailed log output at INFO level, including timestamps, operation names, durations, and results. Log format MUST be human-readable in terminal output.

#### Scenario: Model loading log
- **WHEN** the script loads an ASR model
- **THEN** the log includes: model directory path, model type detected, load duration in milliseconds, and success/failure status

#### Scenario: Audio processing log
- **WHEN** the script processes an audio file
- **THEN** the log includes: file path, audio duration, sample rate, channel count, resampling info (if applied), and number of VAD segments detected

#### Scenario: Transcription result log
- **WHEN** the script produces a transcription result
- **THEN** the log includes: total inference time, number of segments, and the full transcription text

### Requirement: Diagnostic script validates audio file readability
Before attempting transcription, the script SHALL verify that the audio file can be read using the same decoding pipeline as the main application.

#### Scenario: Audio file cannot be decoded
- **WHEN** the specified audio file cannot be read by either `soundfile` or `audioread`
- **THEN** the script outputs a clear error message explaining the failure
- **AND** suggests installing ffmpeg as a dependency
- **AND** exits with a non-zero status code
