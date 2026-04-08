## ADDED Requirements

### Requirement: Recorded audio is saved to data/audio/ directory
After a recording session completes, the system SHALL save the recorded audio as a WAV file to the `data/audio/` directory instead of `data/temp/`.

#### Scenario: Complete a recording session
- **WHEN** user stops a recording session with recorded audio data
- **THEN** the system saves the audio as a WAV file in `<data_dir>/audio/` directory
- **AND** the WAV file is named with a timestamp pattern (e.g., `recording_20260407_123456.wav`)
- **AND** the `data/audio/` directory is created automatically if it does not exist

### Requirement: Recorded audio path is stored in the database
When a recording is saved as a record, the system SHALL store the audio file path in the `audio_path` field of the `records` table.

#### Scenario: Save recording as record
- **WHEN** user completes a recording and the record is saved to the database
- **THEN** the `audio_path` field in the `records` table contains the full path to the saved WAV file
- **AND** the record can be retrieved with the correct `audio_path` value

### Requirement: Records panel includes a manual recognition button
Each record card in the records list SHALL display a button that allows the user to manually trigger audio recognition (re-transcription) for that record.

#### Scenario: Record has an audio file and user clicks recognition button
- **WHEN** a record has a non-null `audio_path` and the user clicks the "Recognize" button
- **THEN** the system reads the audio file from `audio_path`
- **AND** transcribes the audio using the offline recognizer
- **AND** updates the record's `transcript` and `segments` fields with the new results
- **AND** shows a progress indicator during transcription

#### Scenario: Record has no audio file
- **WHEN** a record has a null or empty `audio_path`
- **THEN** the "Recognize" button is not displayed or is disabled

#### Scenario: Transcription is already in progress
- **WHEN** the user clicks "Recognize" while another transcription is running
- **THEN** the system shows a message that a transcription is already in progress
- **AND** does not start a second transcription

### Requirement: Backend provides retranscribe API endpoint
The system SHALL expose a `retranscribe_record` API that accepts a record ID and re-transcribes its associated audio file.

#### Scenario: Retranscribe a record with valid audio
- **WHEN** `retranscribe_record(record_id)` is called and the record has a valid `audio_path`
- **THEN** the system reads the audio file, transcribes it, and updates the record
- **AND** emits `transcribe_progress` events during processing
- **AND** returns the updated record data

#### Scenario: Retranscribe a record with missing audio file
- **WHEN** `retranscribe_record(record_id)` is called but the audio file at `audio_path` does not exist
- **THEN** the system returns an error message indicating the audio file was not found
- **AND** does not modify the record
