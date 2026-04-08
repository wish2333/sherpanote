## ADDED Requirements

### Requirement: Drag overlay does not flicker when dragging files over child elements
The drag-and-drop visual feedback overlay SHALL remain stable (not flicker) when the mouse cursor moves between parent and child elements within the drop zone.

#### Scenario: Drag file over parent container with child elements
- **WHEN** user drags a file over the drop zone that contains child elements (buttons, cards, text)
- **THEN** the drag overlay remains visible and stable throughout the drag operation
- **AND** the overlay does not toggle between visible and hidden states

#### Scenario: Drag file into and out of the window
- **WHEN** user drags a file into the window and then drags it back out
- **THEN** the drag overlay appears when the file enters the window
- **AND** the drag overlay disappears when the file leaves the window

### Requirement: Dropping a file on the window does not open the system default browser
When a user drops a file onto the SherpaNote window, the system SHALL process the file within the application and SHALL NOT trigger the operating system's default file handler (e.g., opening the file in a browser).

#### Scenario: Drop audio file on window
- **WHEN** user drops a supported audio file onto any part of the SherpaNote window
- **THEN** the file is processed by SherpaNote for transcription
- **AND** no external application or browser is opened

#### Scenario: Drop non-audio file on window
- **WHEN** user drops a non-audio file onto the SherpaNote window
- **THEN** the system shows an error toast message "Unsupported audio format"
- **AND** no external application or browser is opened

### Requirement: Global drag prevention only blocks file-type drags
The global drag-and-drop prevention mechanism SHALL only intercept drag events that contain files. It SHALL NOT interfere with drag events for text selection, link dragging, or other non-file drag operations within the webview.

#### Scenario: Text selection drag is not blocked
- **WHEN** user drags to select text within the SherpaNote UI
- **THEN** the text selection works normally without interference
