## ADDED Requirements

### Requirement: Audio file upload supports MP3 and other formats via fallback decoder
The system SHALL successfully read and transcribe audio files in all supported formats (MP3, WAV, M4A, FLAC, OGG, WMA) on Windows. When `soundfile` fails to open a file, the system SHALL automatically fall back to `audioread` for decoding.

#### Scenario: Upload MP3 file for transcription
- **WHEN** user drags or selects an MP3 file for transcription
- **THEN** the system reads the file using `audioread` as fallback decoder
- **AND** returns the audio as 16kHz mono float32 PCM
- **AND** no "Error opening: System error" is displayed

#### Scenario: Upload WAV file (soundfile-supported format)
- **WHEN** user uploads a WAV file
- **THEN** the system reads the file using `soundfile` (primary decoder)
- **AND** transcribes successfully without fallback

#### Scenario: Upload unsupported or corrupted file
- **WHEN** user uploads a file that neither `soundfile` nor `audioread` can decode
- **THEN** the system displays a user-friendly error message indicating the file could not be read
- **AND** does not crash or hang
