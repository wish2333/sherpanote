## ADDED Requirements

### Requirement: Settings ASR tab shows model management section
The Settings page ASR tab SHALL include a "Model Management" section below the existing configuration fields. This section SHALL display two sub-sections: "Available Models" (catalog) and "Installed Models".

#### Scenario: ASR tab shows model management
- **WHEN** the user navigates to Settings and clicks the "ASR Engine" tab
- **THEN** below the existing ASR config fields, a "Model Management" section SHALL be visible with "Available Models" and "Installed Models" headings

### Requirement: Available models catalog shows model details and download button
The "Available Models" section SHALL display a list of models from the registry. Each model entry SHALL show: display name, model type badge (streaming/offline), supported languages, approximate size, and a "Download" button. Models already installed SHALL show a "Installed" badge instead of the download button.

#### Scenario: Catalog displays streaming model
- **WHEN** the available models list is rendered
- **THEN** each model entry SHALL show display name, type badge, languages, size, and a download/action button

#### Scenario: Installed model shows Installed badge
- **WHEN** a model from the catalog is already installed
- **THEN** the download button SHALL be replaced with an "Installed" badge

### Requirement: Download button triggers model installation with progress
Clicking "Download" on a model SHALL call the backend `install_model` API. A progress bar SHALL appear showing download progress (percentage). The button SHALL be disabled during download. On success, a toast notification SHALL appear and the model SHALL move to the "Installed" section. On failure, an error toast SHALL appear with the error message.

#### Scenario: Successful download
- **WHEN** user clicks "Download" on an available model
- **THEN** a progress bar SHALL appear showing download percentage
- **AND** when complete, a success toast SHALL appear
- **AND** the model SHALL appear in the "Installed Models" list

#### Scenario: Failed download
- **WHEN** the download fails
- **THEN** an error toast SHALL appear with the failure reason
- **AND** the progress bar SHALL be dismissed

#### Scenario: Cancel during download
- **WHEN** a download is in progress, the download button SHALL be replaced with a "Cancel" button
- **AND** clicking "Cancel" SHALL abort the download

### Requirement: Installed models section shows model status and actions
The "Installed Models" section SHALL list all installed models with: display name, model type, validation status (valid/invalid), disk size, and a "Delete" button. If a model is set as the active streaming or offline model, it SHALL show an "Active" badge. An "Activate" button SHALL be available to set a model as the active streaming or offline model.

#### Scenario: Installed model displayed
- **WHEN** the installed models list is rendered
- **THEN** each entry SHALL show display name, type, validation status, size, and action buttons

#### Scenario: Active model has Active badge
- **WHEN** an installed model matches the current active streaming or offline model
- **THEN** an "Active" badge SHALL be displayed next to its type label

#### Scenario: Delete model with confirmation
- **WHEN** user clicks "Delete" on an installed model
- **THEN** a confirmation dialog SHALL appear
- **AND** upon confirmation, the model SHALL be deleted and removed from the list

### Requirement: Active model selection via dropdown
The existing ASR configuration section SHALL add two dropdown selects: "Streaming Model" and "Offline Model". These SHALL be populated with installed models of the corresponding type. Changing the selection SHALL update the `active_streaming_model` and `active_offline_model` config fields and save the configuration.

#### Scenario: Streaming model dropdown populated
- **WHEN** the ASR config section is rendered and streaming models are installed
- **THEN** the "Streaming Model" dropdown SHALL list all installed streaming models
- **AND** the currently active model SHALL be pre-selected

#### Scenario: No models installed
- **WHEN** no streaming models are installed
- **THEN** the "Streaming Model" dropdown SHALL show "None installed" and be disabled

#### Scenario: Model selection persists
- **WHEN** user selects a different model from the dropdown
- **THEN** the configuration SHALL be saved automatically
- **AND** the ASR engine SHALL use the newly selected model on next recognition

### Requirement: Download source selection
The ASR configuration section SHALL include a "Download Source" field with options for "GitHub (Default)" and "Custom Mirror". When "Custom Mirror" is selected, a text input SHALL appear for the mirror URL. This URL SHALL be saved to `AsrConfig.mirror_url`.

#### Scenario: Default source selected
- **WHEN** the download source is set to "GitHub (Default)"
- **THEN** the mirror URL input SHALL be hidden
- **AND** downloads SHALL use GitHub releases

#### Scenario: Custom mirror configured
- **WHEN** user selects "Custom Mirror" and enters a URL
- **THEN** the URL SHALL be saved to `AsrConfig.mirror_url`
- **AND** model downloads SHALL use the mirror URL as the base
