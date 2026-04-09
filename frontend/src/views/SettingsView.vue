<script setup lang="ts">
/**
 * SettingsView - Application configuration page.
 *
 * Allows users to configure AI model settings, ASR settings,
 * manage AI provider presets, and download ASR models.
 * Uses store.showToast for feedback instead of inline message.
 */
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import { useAppStore } from "../stores/appStore";
import {
  call,
  onEvent,
  listAvailableModels,
  listInstalledModels,
  installModel,
  deleteModel,
  cancelModelInstall,
  pickDirectory,
} from "../bridge";
import type { AiConfig, AsrConfig, AiPreset, AiProcessingPreset, ModelEntry, InstalledModel, DownloadProgress } from "../types";

const store = useAppStore();
const router = useRouter();

const aiConfig = ref<AiConfig>(store.aiConfig);
const asrConfig = ref<AsrConfig>(store.asrConfig);
const autoAiModes = ref<string[]>(store.autoAiModes);
const maxTokensMode = ref<"auto" | "custom" | "default">("auto");
const maxVersions = ref(20);
const isSaving = ref(false);
const isTesting = ref(false);
const testResult = ref<{ success: boolean; message: string } | null>(null);
const activeTab = ref<"general" | "ai" | "processing" | "asr">("general");

const providers = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic (via OpenAI compat)" },
  { value: "ollama", label: "Ollama (Local)" },
  { value: "qwen", label: "Qwen" },
  { value: "openrouter", label: "OpenRouter" },
  { value: "custom", label: "Custom (OpenAI format)" },
];

const languages = [
  { value: "auto", label: "Auto Detect" },
  { value: "zh", label: "Chinese" },
  { value: "en", label: "English" },
  { value: "ja", label: "Japanese" },
  { value: "ko", label: "Korean" },
  { value: "yue", label: "Cantonese" },
  { value: "de", label: "German" },
  { value: "fr", label: "French" },
  { value: "es", label: "Spanish" },
  { value: "ru", label: "Russian" },
  { value: "it", label: "Italian" },
  { value: "pt", label: "Portuguese" },
];

const customLanguage = ref("");

// ---- AI Preset management ----
const aiPresets = ref<AiPreset[]>([]);
const showPresetForm = ref(false);
const editingPreset = ref<AiPreset | null>(null);
const presetForm = ref({
  name: "",
  provider: "openai",
  model: "",
  api_key: "" as string | null,
  base_url: "" as string | null,
  temperature: 0.7,
  max_tokens: 4096,
});
const deletePresetConfirmId = ref<string | null>(null);
const isTestingPreset = ref(false);
const presetTestResult = ref<{ success: boolean; message: string } | null>(null);

async function loadPresets() {
  const res = await call<AiPreset[]>("list_ai_presets");
  if (res.success && res.data) {
    aiPresets.value = res.data;
  }
}

function openNewPresetForm() {
  editingPreset.value = null;
  presetForm.value = {
    name: "",
    provider: "openai",
    model: "",
    api_key: "",
    base_url: "",
    temperature: 0.7,
    max_tokens: 4096,
  };
  showPresetForm.value = true;
}

function openEditPresetForm(preset: AiPreset) {
  editingPreset.value = preset;
  presetForm.value = {
    name: preset.name,
    provider: preset.provider,
    model: preset.model,
    api_key: preset.api_key ?? "",
    base_url: preset.base_url ?? "",
    temperature: preset.temperature,
    max_tokens: preset.max_tokens,
  };
  showPresetForm.value = true;
}

function cancelPresetForm() {
  showPresetForm.value = false;
  editingPreset.value = null;
  presetTestResult.value = null;
}

async function testPresetConnection() {
  isTestingPreset.value = true;
  presetTestResult.value = null;
  // Test using the current form values (unsaved).
  const config = {
    provider: presetForm.value.provider,
    model: presetForm.value.model,
    api_key: presetForm.value.api_key || null,
    base_url: presetForm.value.base_url || null,
  };
  const res = await call<{ response: string }>("test_ai_preset_connection", config);
  if (res.success && res.data) {
    presetTestResult.value = { success: true, message: "Connection successful" };
  } else {
    presetTestResult.value = { success: false, message: res.error ?? "Connection failed" };
  }
  isTestingPreset.value = false;
}

async function savePreset() {
  if (!presetForm.value.name.trim()) {
    store.showToast("Preset name is required", "warning");
    return;
  }
  const data = {
    name: presetForm.value.name.trim(),
    provider: presetForm.value.provider,
    model: presetForm.value.model,
    api_key: presetForm.value.api_key || null,
    base_url: presetForm.value.base_url || null,
    temperature: presetForm.value.temperature,
    max_tokens: presetForm.value.max_tokens,
  };

  if (editingPreset.value) {
    const res = await call("update_ai_preset", editingPreset.value.id, data);
    if (res.success) {
      store.showToast("Preset updated", "success");
    } else {
      store.showToast(res.error ?? "Failed to update preset", "error");
    }
  } else {
    (data as Record<string, unknown>).is_active = aiPresets.value.length === 0;
    const res = await call("create_ai_preset", data);
    if (res.success) {
      store.showToast("Preset created", "success");
    } else {
      store.showToast(res.error ?? "Failed to create preset", "error");
    }
  }
  showPresetForm.value = false;
  editingPreset.value = null;
  await loadPresets();
}

async function handleActivatePreset(presetId: string) {
  const res = await call("set_active_ai_preset", presetId);
  if (res.success) {
    store.showToast("Preset activated", "success");
    await loadPresets();
    await loadConfig();
  } else {
    store.showToast(res.error ?? "Failed to activate preset", "error");
  }
}

async function handleDeletePreset(presetId: string) {
  deletePresetConfirmId.value = null;
  const res = await call("delete_ai_preset", presetId);
  if (res.success) {
    store.showToast("Preset deleted", "success");
    await loadPresets();
    await loadConfig();
  } else {
    store.showToast(res.error ?? "Failed to delete preset", "error");
  }
}

// ---- AI Processing Preset management ----
const processingPresets = ref<AiProcessingPreset[]>([]);
const showProcessingPresetForm = ref(false);
const editingProcessingPreset = ref<AiProcessingPreset | null>(null);
const deleteProcessingPresetConfirmId = ref<string | null>(null);
const processingPresetForm = ref({
  name: "",
  mode: "polish" as string,
  prompt: "",
});
const processingModeOptions: { value: string; label: string }[] = [
  { value: "polish", label: "Polish" },
  { value: "note", label: "Notes" },
  { value: "mindmap", label: "Mind Map" },
  { value: "brainstorm", label: "Brainstorm" },
  { value: "custom", label: "Custom" },
];

async function loadProcessingPresets() {
  const res = await call<AiProcessingPreset[]>("list_processing_presets");
  if (res.success && res.data) {
    processingPresets.value = res.data;
  }
}

function openNewProcessingPresetForm() {
  editingProcessingPreset.value = null;
  processingPresetForm.value = { name: "", mode: "polish", prompt: "" };
  showProcessingPresetForm.value = true;
}

function openEditProcessingPresetForm(preset: AiProcessingPreset) {
  editingProcessingPreset.value = preset;
  processingPresetForm.value = {
    name: preset.name,
    mode: preset.mode,
    prompt: preset.prompt,
  };
  showProcessingPresetForm.value = true;
}

function cancelProcessingPresetForm() {
  showProcessingPresetForm.value = false;
  editingProcessingPreset.value = null;
}

async function saveProcessingPreset() {
  if (!processingPresetForm.value.name.trim()) {
    store.showToast("Preset name is required", "warning");
    return;
  }
  if (!processingPresetForm.value.prompt.trim()) {
    store.showToast("Prompt is required", "warning");
    return;
  }
  const data = {
    name: processingPresetForm.value.name.trim(),
    mode: processingPresetForm.value.mode,
    prompt: processingPresetForm.value.prompt,
  };

  if (editingProcessingPreset.value) {
    const res = await call("update_processing_preset", editingProcessingPreset.value.id, data);
    if (res.success) {
      store.showToast("Preset updated", "success");
    } else {
      store.showToast(res.error ?? "Failed to update preset", "error");
    }
  } else {
    const res = await call("create_processing_preset", data);
    if (res.success) {
      store.showToast("Preset created", "success");
    } else {
      store.showToast(res.error ?? "Failed to create preset", "error");
    }
  }
  showProcessingPresetForm.value = false;
  editingProcessingPreset.value = null;
  await loadProcessingPresets();
}

async function handleDeleteProcessingPreset(presetId: string) {
  deleteProcessingPresetConfirmId.value = null;
  const res = await call("delete_processing_preset", presetId);
  if (res.success) {
    store.showToast("Preset deleted", "success");
    await loadProcessingPresets();
  } else {
    store.showToast(res.error ?? "Cannot delete built-in presets", "error");
  }
}

// ---- Model management state ----
const availableModels = ref<ModelEntry[]>([]);
const installedModels = ref<InstalledModel[]>([]);
const downloadingModelId = ref<string | null>(null);
const downloadProgress = ref<DownloadProgress | null>(null);
const deleteConfirmId = ref<string | null>(null);

const downloadSources = [
  { value: "github", label: "GitHub (Default)" },
  { value: "huggingface", label: "HuggingFace" },
  { value: "hf_mirror", label: "HF-Mirror" },
  { value: "ghproxy", label: "GitHub Proxy" },
  { value: "modelscope", label: "ModelScope" },
];

const proxyModes = [
  { value: "none", label: "No Proxy" },
  { value: "system", label: "System Proxy" },
  { value: "custom", label: "Custom Proxy" },
];

const installedStreamingModels = computed(() =>
  installedModels.value.filter((m) => m.model_type === "streaming"),
);

const installedOfflineModels = computed(() =>
  installedModels.value.filter((m) => m.model_type === "offline"),
);

function isModelInstalled(modelId: string): boolean {
  return installedModels.value.some((m) => m.model_id === modelId);
}

function isModelActive(modelId: string, type: "streaming" | "offline"): boolean {
  if (type === "streaming") return asrConfig.value.active_streaming_model === modelId;
  return asrConfig.value.active_offline_model === modelId;
}

function formatSize(mb: number): string {
  if (mb >= 1000) return `${(mb / 1000).toFixed(1)} GB`;
  return `${mb} MB`;
}

function isModelAvailableOnSource(model: ModelEntry): boolean {
  return model.sources.includes(asrConfig.value.download_source);
}

function sourceBadgeLabel(source: string): string {
  const map: Record<string, string> = {
    github: "GH",
    huggingface: "HF",
    hf_mirror: "HF-M",
    ghproxy: "GH-P",
    modelscope: "MS",
  };
  return map[source] || source;
}

function toggleAutoAiMode(mode: string) {
  if (autoAiModes.value.includes(mode)) {
    autoAiModes.value = autoAiModes.value.filter((m) => m !== mode);
  } else {
    autoAiModes.value = [...autoAiModes.value, mode];
  }
  saveConfig();
}

async function handlePickDirectory() {
  const res = await pickDirectory();
  if (res.success && res.data) {
    asrConfig.value = { ...asrConfig.value, model_dir: res.data.path };
  }
}

// ---- Config ----

async function loadConfig() {
  const res = await call<{ ai: AiConfig; asr: AsrConfig; auto_ai_modes?: string[]; max_tokens_mode?: string; max_versions?: number }>("get_config");
  if (res.success && res.data) {
    if (res.data.ai) {
      aiConfig.value = res.data.ai;
      store.aiConfig = res.data.ai;
    }
    if (res.data.asr) {
      asrConfig.value = res.data.asr;
      store.asrConfig = res.data.asr;
      // If language is not a preset value, treat as custom.
      const langVal = res.data.asr.language;
      if (langVal && !languages.some((l) => l.value === langVal)) {
        customLanguage.value = langVal;
        asrConfig.value = { ...asrConfig.value, language: "__custom__" };
      }
    }
    autoAiModes.value = res.data.auto_ai_modes ?? [];
    store.autoAiModes = autoAiModes.value;
    maxTokensMode.value = (["auto", "custom", "default"].includes(res.data.max_tokens_mode ?? "")
      ? (res.data.max_tokens_mode as "auto" | "custom" | "default")
      : "auto");
    maxVersions.value = res.data.max_versions ?? 20;
  }
}

async function saveConfig() {
  isSaving.value = true;
  // Resolve custom language before saving.
  const asrToSave = { ...asrConfig.value };
  if (asrToSave.language === "__custom__") {
    asrToSave.language = customLanguage.value || "auto";
  }
  const res = await call("update_config", {
    ai: aiConfig.value,
    asr: asrToSave,
    auto_ai_modes: autoAiModes.value,
    max_tokens_mode: maxTokensMode.value,
    max_versions: maxVersions.value,
  });
  if (res.success) {
    store.aiConfig = aiConfig.value;
    store.asrConfig = asrToSave;
    store.autoAiModes = autoAiModes.value;
    store.showToast("Configuration saved", "success");
  } else {
    store.showToast(res.error ?? "Failed to save configuration", "error");
  }
  isSaving.value = false;
}

async function testConnection() {
  isTesting.value = true;
  testResult.value = null;
  const res = await call<{ response: string }>("test_ai_connection");
  if (res.success && res.data) {
    testResult.value = { success: true, message: "Connection successful" };
    store.showToast("AI connection OK", "success");
  } else {
    testResult.value = { success: false, message: res.error ?? "Connection failed" };
  }
  isTesting.value = false;
}

// ---- Model management ----

async function loadModels() {
  const [availRes, instRes] = await Promise.all([
    listAvailableModels(),
    listInstalledModels(),
  ]);
  if (availRes.success && availRes.data) {
    availableModels.value = availRes.data;
  }
  if (instRes.success && instRes.data) {
    installedModels.value = instRes.data;
  }
}

async function handleInstallModel(modelId: string) {
  if (downloadingModelId.value) return;

  downloadingModelId.value = modelId;
  downloadProgress.value = null;

  const res = await installModel(modelId);
  if (!res.success) {
    store.showToast(res.error ?? "Failed to start download", "error");
    downloadingModelId.value = null;
  }
}

async function handleCancelInstall() {
  if (!downloadingModelId.value) return;
  await cancelModelInstall();
}

async function handleDeleteModel(modelId: string) {
  deleteConfirmId.value = null;
  const res = await deleteModel(modelId);
  if (res.success) {
    installedModels.value = installedModels.value.filter((m) => m.model_id !== modelId);
    store.showToast("Model deleted", "success");
    const cfg = { ...asrConfig.value };
    if (cfg.active_streaming_model === modelId) cfg.active_streaming_model = "";
    if (cfg.active_offline_model === modelId) cfg.active_offline_model = "";
    asrConfig.value = cfg;
    await saveConfig();
  } else {
    store.showToast(res.error ?? "Failed to delete model", "error");
  }
}

async function handleSetActiveModel(modelId: string, type: "streaming" | "offline") {
  const cfg = { ...asrConfig.value };
  if (type === "streaming") {
    cfg.active_streaming_model = cfg.active_streaming_model === modelId ? "" : modelId;
  } else {
    cfg.active_offline_model = cfg.active_offline_model === modelId ? "" : modelId;
  }
  asrConfig.value = cfg;
  await saveConfig();
}

// ---- Event listeners ----

const offDownloadProgress = onEvent<DownloadProgress>("model_download_progress", (detail) => {
  downloadProgress.value = detail;
});

const offInstallComplete = onEvent<{ model_id: string }>("model_install_complete", (detail) => {
  downloadingModelId.value = null;
  downloadProgress.value = null;
  store.showToast(`Model installed: ${detail.model_id}`, "success");
  loadModels();
});

const offInstallError = onEvent<{ error: string }>("model_install_error", (detail) => {
  downloadingModelId.value = null;
  downloadProgress.value = null;
  store.showToast(detail.error ?? "Model installation failed", "error");
});

onMounted(async () => {
  await loadConfig();
  await loadModels();
  await loadPresets();
  await loadProcessingPresets();
});

onUnmounted(() => {
  offDownloadProgress();
  offInstallComplete();
  offInstallError();
});
</script>

<template>
  <div class="mx-auto max-w-2xl px-4 py-6">
    <!-- Header -->
    <div class="mb-6 flex items-center gap-3">
      <button class="btn btn-ghost btn-sm" @click="router.push('/')">
        <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 18l-6-6 6-6" />
        </svg>
        Back
      </button>
      <h1 class="text-xl font-bold tracking-tight text-base-content">Settings</h1>
    </div>

    <!-- Tab navigation -->
    <div class="tabs tabs-boxed mb-6 bg-base-200">
      <a
        class="tab"
        :class="{ 'tab-active': activeTab === 'general' }"
        @click="activeTab = 'general'"
      >General</a>
      <a
        class="tab"
        :class="{ 'tab-active': activeTab === 'ai' }"
        @click="activeTab = 'ai'"
      >AI Model</a>
      <a
        class="tab"
        :class="{ 'tab-active': activeTab === 'processing' }"
        @click="activeTab = 'processing'"
      >Processing</a>
      <a
        class="tab"
        :class="{ 'tab-active': activeTab === 'asr' }"
        @click="activeTab = 'asr'"
      >ASR Engine</a>
    </div>

    <!-- General Settings -->
    <div v-show="activeTab === 'general'" class="space-y-4">
      <div class="card bg-base-100 border border-base-300 shadow-md">
        <div class="card-body">
          <h2 class="card-title text-base">Version History</h2>
          <p class="text-sm text-base-content/60">
            Configure how many versions are kept per record.
            Save Version creates a snapshot manually or automatically on exit.
          </p>

          <div class="mt-4 space-y-4">
            <!-- Max Version History -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">Max Version History</span>
              </label>
              <input
                v-model.number="maxVersions"
                type="number"
                min="0"
                max="1000"
                step="1"
                class="input input-bordered input-sm w-full max-w-[200px]"
              />
              <label class="label">
                <span class="label-text-alt text-base-content/40">
                  Maximum versions per record. 0 = unlimited. Oldest versions are auto-deleted.
                </span>
              </label>
            </div>

            <!-- Auto Punctuation Toggle -->
            <div class="form-control">
              <label class="label cursor-pointer justify-start gap-4">
                <span class="label-text font-medium">Auto Punctuation</span>
                <input
                  v-model="asrConfig.auto_punctuate"
                  type="checkbox"
                  class="toggle toggle-primary"
                />
              </label>
              <label class="label">
                <span class="label-text-alt text-base-content/40">
                  Use AI to add punctuation marks to transcription output. Requires AI configuration.
                </span>
              </label>
            </div>

            <!-- Auto AI Processing after Transcription -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">Auto AI Processing</span>
              </label>
              <label class="label">
                <span class="label-text-alt text-base-content/40">
                  Select AI processing modes to run automatically after transcription completes.
                </span>
              </label>
              <div class="flex flex-wrap gap-2 mt-1">
                <label
                  v-for="mode in [
                    { key: 'polish', label: 'Polish' },
                    { key: 'note', label: 'Notes' },
                    { key: 'mindmap', label: 'Mind Map' },
                    { key: 'brainstorm', label: 'Brainstorm' },
                  ]"
                  :key="mode.key"
                  class="label cursor-pointer gap-1 border rounded-lg px-3 py-1"
                  :class="autoAiModes.includes(mode.key) ? 'border-primary bg-primary/10' : 'border-base-300'"
                >
                  <input
                    type="checkbox"
                    :checked="autoAiModes.includes(mode.key)"
                    class="checkbox checkbox-xs checkbox-primary"
                    @change="toggleAutoAiMode(mode.key)"
                  />
                  <span class="label-text text-sm">{{ mode.label }}</span>
                </label>
              </div>
              <label v-if="autoAiModes.length > 0" class="label">
                <span class="label-text-alt text-base-content/40">
                  Active: {{ autoAiModes.join(', ') }}. Requires AI configuration.
                </span>
              </label>
            </div>
          </div>

          <div class="card-actions mt-4 justify-end">
            <button
              class="btn btn-primary btn-sm"
              :disabled="isSaving"
              @click="saveConfig"
            >
              <span v-if="isSaving" class="loading loading-spinner loading-xs"></span>
              Save
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- AI Configuration -->
    <div v-show="activeTab === 'ai'" class="space-y-4">
      <!-- API Presets Card -->
      <div class="card bg-base-100 border border-base-300 shadow-md">
        <div class="card-body">
          <div class="flex items-center justify-between">
            <h2 class="card-title text-base">API Presets</h2>
            <button
              class="btn btn-outline btn-sm"
              @click="openNewPresetForm"
            >
              Add Preset
            </button>
          </div>
          <p class="text-sm text-base-content/60">
            Save multiple API configurations for quick switching between providers.
          </p>

          <!-- Preset list -->
          <div v-if="aiPresets.length > 0" class="mt-4 space-y-2">
            <div
              v-for="preset in aiPresets"
              :key="preset.id"
              class="flex items-center justify-between rounded-lg border p-3"
              :class="preset.is_active ? 'border-primary bg-primary/5' : 'border-base-300'"
            >
              <button
                class="flex-1 min-w-0 text-left"
                @click="handleActivatePreset(preset.id)"
                :title="preset.is_active ? 'Already active' : 'Click to activate'"
              >
                <div class="flex items-center gap-2">
                  <span class="font-medium text-sm">{{ preset.name }}</span>
                  <span v-if="preset.is_active" class="badge badge-primary badge-xs">Active</span>
                </div>
                <div class="mt-0.5 text-xs text-base-content/50">
                  {{ preset.provider }} / {{ preset.model }}
                </div>
              </button>
              <div class="ml-3 flex items-center gap-1 flex-shrink-0">
                <button
                  class="btn btn-ghost btn-xs"
                  title="Edit"
                  @click="openEditPresetForm(preset)"
                >
                  <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
                    <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
                  </svg>
                </button>
                <button
                  v-if="deletePresetConfirmId === preset.id"
                  class="btn btn-error btn-xs"
                  @click="handleDeletePreset(preset.id)"
                >Confirm</button>
                <button
                  v-else
                  class="btn btn-ghost btn-xs text-error"
                  title="Delete"
                  @click="deletePresetConfirmId = preset.id"
                >
                  <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6" />
                    <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
                    <path d="M10 11v6" />
                    <path d="M14 11v6" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
          <p v-else class="mt-4 text-sm text-base-content/40">
            No presets yet. Click "Add Preset" to create one.
          </p>

          <!-- Preset form (inline) -->
          <div v-if="showPresetForm" class="mt-4 rounded-lg border border-base-300 p-4 space-y-3">
            <h3 class="text-sm font-semibold">
              {{ editingPreset ? 'Edit Preset' : 'New Preset' }}
            </h3>
            <div class="form-control">
              <label class="label"><span class="label-text text-sm">Preset Name</span></label>
              <input
                v-model="presetForm.name"
                type="text"
                class="input input-bordered input-sm w-full"
                placeholder="e.g. GPT-4o, Local Ollama"
              />
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div class="form-control">
                <label class="label"><span class="label-text text-sm">Provider</span></label>
                <select v-model="presetForm.provider" class="select select-bordered select-sm w-full">
                  <option v-for="p in providers" :key="p.value" :value="p.value">{{ p.label }}</option>
                </select>
              </div>
              <div class="form-control">
                <label class="label"><span class="label-text text-sm">Model</span></label>
                <input
                  v-model="presetForm.model"
                  type="text"
                  class="input input-bordered input-sm w-full"
                  placeholder="gpt-4o-mini"
                />
              </div>
            </div>
            <div class="form-control">
              <label class="label"><span class="label-text text-sm">API Key</span></label>
              <input
                v-model="presetForm.api_key"
                type="password"
                class="input input-bordered input-sm w-full"
                placeholder="sk-..."
              />
            </div>
            <div class="form-control">
              <label class="label"><span class="label-text text-sm">Base URL</span></label>
              <input
                v-model="presetForm.base_url"
                type="text"
                class="input input-bordered input-sm w-full"
                placeholder="https://api.openai.com/v1"
              />
            </div>
            <div class="flex gap-2 justify-between items-center">
              <button
                class="btn btn-outline btn-sm"
                :disabled="isTestingPreset"
                @click="testPresetConnection"
              >
                <span v-if="isTestingPreset" class="loading loading-spinner loading-xs"></span>
                Test
              </button>
              <div class="flex gap-2">
                <button class="btn btn-ghost btn-sm" @click="cancelPresetForm">Cancel</button>
                <button class="btn btn-primary btn-sm" @click="savePreset">
                  {{ editingPreset ? 'Update' : 'Create' }}
                </button>
              </div>
            </div>
            <!-- Preset test result -->
            <div
              v-if="presetTestResult"
              class="rounded-lg p-2 text-sm"
              :class="presetTestResult.success ? 'bg-success/10 text-success' : 'bg-error/10 text-error'"
            >
              {{ presetTestResult.message }}
            </div>
          </div>
        </div>
      </div>

      <!-- Current AI Configuration Card -->
      <div class="card bg-base-100 border border-base-300 shadow-md">
        <div class="card-body">
          <h2 class="card-title text-base">AI Model Configuration</h2>
          <p class="text-sm text-base-content/60">
            Fine-tune the active AI provider. Changes here are saved as the current config.
          </p>

          <div class="mt-4 space-y-4">
            <!-- Provider -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">Provider</span>
              </label>
              <select v-model="aiConfig.provider" class="select select-bordered w-full">
                <option v-for="p in providers" :key="p.value" :value="p.value">
                  {{ p.label }}
                </option>
              </select>
            </div>

            <!-- Model -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">Model</span>
              </label>
              <input
                v-model="aiConfig.model"
                type="text"
                class="input input-bordered w-full"
                placeholder="e.g. gpt-4o-mini, qwen2.5:7b"
              />
            </div>

            <!-- API Key -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">API Key</span>
              </label>
              <input
                v-model="aiConfig.api_key"
                type="password"
                class="input input-bordered w-full"
                placeholder="sk-... (leave empty for local models)"
              />
              <label class="label">
                <span class="label-text-alt text-base-content/40">
                  Not required for Ollama (local models).
                </span>
              </label>
            </div>

            <!-- Base URL -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">Custom API URL</span>
              </label>
              <input
                v-model="aiConfig.base_url"
                type="text"
                class="input input-bordered w-full"
                placeholder="https://api.openai.com/v1 (optional)"
              />
            </div>

            <!-- Temperature -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">Temperature</span>
                <span class="label-text-alt text-base-content/50">{{ aiConfig.temperature }}</span>
              </label>
              <label class="flex items-center gap-3">
                <span class="text-xs text-base-content/40 w-12 shrink-0">Precise</span>
                <input
                  v-model.number="aiConfig.temperature"
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  class="range range-primary range-xs flex-1"
                />
                <span class="text-xs text-base-content/40 w-12 text-right shrink-0">Creative</span>
              </label>
            </div>

            <!-- Max Tokens Mode -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">Max Tokens</span>
              </label>
              <div class="flex flex-col gap-2">
                <label
                  v-for="opt in [
                    { value: 'auto' as const, label: 'Auto', desc: 'Estimate based on input length' },
                    { value: 'custom' as const, label: 'Fixed', desc: 'Use the value below' },
                    { value: 'default' as const, label: 'Model Default', desc: 'No limit, let model decide' },
                  ]"
                  :key="opt.value"
                  class="flex items-center gap-3 cursor-pointer"
                >
                  <input
                    type="radio"
                    name="maxTokensMode"
                    :value="opt.value"
                    class="radio radio-primary radio-sm"
                    :checked="maxTokensMode === opt.value"
                    @change="maxTokensMode = opt.value"
                  />
                  <div>
                    <span class="text-sm font-medium">{{ opt.label }}</span>
                    <span class="text-xs text-base-content/50 block">{{ opt.desc }}</span>
                  </div>
                </label>
              </div>
            </div>

            <!-- Max Tokens Value (visible when custom) -->
            <div v-if="maxTokensMode === 'custom'" class="form-control">
              <label class="label">
                <span class="label-text font-medium">Tokens Value</span>
              </label>
              <input
                v-model.number="aiConfig.max_tokens"
                type="number"
                min="256"
                max="128000"
                step="256"
                class="input input-bordered input-sm w-full"
              />
            </div>
          </div>

          <!-- Save button -->
          <div class="card-actions mt-4 justify-between">
            <button
              class="btn btn-outline btn-sm"
              :disabled="isTesting || isSaving"
              @click="testConnection"
            >
              <span v-if="isTesting" class="loading loading-spinner loading-xs"></span>
              Test Connection
            </button>
            <button
              class="btn btn-primary btn-sm"
              :disabled="isSaving"
              @click="saveConfig"
            >
              <span v-if="isSaving" class="loading loading-spinner loading-xs"></span>
              Save Configuration
            </button>
          </div>

          <!-- Test result -->
          <div
            v-if="testResult"
            class="mt-2 rounded-lg p-3 text-sm"
            :class="testResult.success ? 'bg-success/10 text-success' : 'bg-error/10 text-error'"
          >
            {{ testResult.message }}
          </div>
        </div>
      </div>
    </div>

    <!-- AI Processing Presets -->
    <div v-show="activeTab === 'processing'" class="space-y-4">
      <div class="card bg-base-100 border border-base-300 shadow-md">
        <div class="card-body">
          <div class="flex items-center justify-between">
            <h2 class="card-title text-base">AI Processing Presets</h2>
            <button
              class="btn btn-outline btn-sm"
              @click="openNewProcessingPresetForm"
            >
              Add Preset
            </button>
          </div>
          <p class="text-sm text-base-content/60">
            Manage prompt templates for AI text processing. Built-in presets cannot be deleted.
          </p>

          <!-- Preset list -->
          <div v-if="processingPresets.length > 0" class="mt-4 space-y-2">
            <div
              v-for="preset in processingPresets"
              :key="preset.id"
              class="flex items-center justify-between rounded-lg border border-base-300 p-3"
            >
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="font-medium text-sm">{{ preset.name }}</span>
                  <span class="badge badge-sm">{{ preset.mode }}</span>
                  <span v-if="preset.id.startsWith('builtin_')" class="badge badge-ghost badge-xs">built-in</span>
                </div>
                <div class="mt-0.5 text-xs text-base-content/40 truncate max-w-[400px]">
                  {{ preset.prompt.slice(0, 100) }}{{ preset.prompt.length > 100 ? '...' : '' }}
                </div>
              </div>
              <div class="ml-3 flex items-center gap-1 flex-shrink-0">
                <button
                  class="btn btn-ghost btn-xs"
                  title="Edit"
                  @click="openEditProcessingPresetForm(preset)"
                >
                  <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
                    <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
                  </svg>
                </button>
                <button
                  v-if="deleteProcessingPresetConfirmId === preset.id"
                  class="btn btn-error btn-xs"
                  @click="handleDeleteProcessingPreset(preset.id)"
                >Confirm</button>
                <button
                  v-else-if="!preset.id.startsWith('builtin_')"
                  class="btn btn-ghost btn-xs text-error"
                  title="Delete"
                  @click="deleteProcessingPresetConfirmId = preset.id"
                >
                  <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6" />
                    <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
                    <path d="M10 11v6" />
                    <path d="M14 11v6" />
                  </svg>
                </button>
              </div>
            </div>
          </div>

          <!-- Processing preset form (inline) -->
          <div v-if="showProcessingPresetForm" class="mt-4 rounded-lg border border-base-300 p-4 space-y-3">
            <h3 class="text-sm font-semibold">
              {{ editingProcessingPreset ? 'Edit Processing Preset' : 'New Processing Preset' }}
            </h3>
            <div class="grid grid-cols-2 gap-3">
              <div class="form-control">
                <label class="label"><span class="label-text text-sm">Preset Name</span></label>
                <input
                  v-model="processingPresetForm.name"
                  type="text"
                  class="input input-bordered input-sm w-full"
                  placeholder="e.g. Quick Summary"
                />
              </div>
              <div class="form-control">
                <label class="label"><span class="label-text text-sm">Mode</span></label>
                <select v-model="processingPresetForm.mode" class="select select-bordered select-sm w-full">
                  <option v-for="m in processingModeOptions" :key="m.value" :value="m.value">{{ m.label }}</option>
                </select>
              </div>
            </div>
            <div class="form-control">
              <label class="label"><span class="label-text text-sm">Prompt Template</span></label>
              <label class="label"><span class="label-text-alt text-base-content/40">Use {text} as placeholder for the input text.</span></label>
              <textarea
                v-model="processingPresetForm.prompt"
                class="textarea textarea-bordered w-full text-sm"
                rows="6"
                placeholder="Enter your prompt template here. Use {text} where the user's text should be inserted."
              ></textarea>
            </div>
            <div class="flex gap-2 justify-end">
              <button class="btn btn-ghost btn-sm" @click="cancelProcessingPresetForm">Cancel</button>
              <button class="btn btn-primary btn-sm" @click="saveProcessingPreset">
                {{ editingProcessingPreset ? 'Update' : 'Create' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ASR Configuration -->
    <div v-show="activeTab === 'asr'" class="space-y-4">
      <!-- Basic ASR Settings Card -->
      <div class="card bg-base-100 border border-base-300 shadow-md">
        <div class="card-body">
          <h2 class="card-title text-base">ASR Engine Configuration</h2>
          <p class="text-sm text-base-content/60">
            Configure the sherpa-onnx speech recognition engine.
          </p>

          <div class="mt-4 space-y-4">
            <!-- Active Streaming Model -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">Streaming Model</span>
              </label>
              <select
                v-model="asrConfig.active_streaming_model"
                class="select select-bordered w-full"
                @change="saveConfig"
              >
                <option value="">(Auto-detect)</option>
                <option
                  v-for="m in installedStreamingModels"
                  :key="m.model_id"
                  :value="m.model_id"
                >
                  {{ availableModels.find(e => e.model_id === m.model_id)?.display_name ?? m.model_id }}
                </option>
              </select>
            </div>

            <!-- Active Offline Model -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">Offline Model</span>
              </label>
              <select
                v-model="asrConfig.active_offline_model"
                class="select select-bordered w-full"
                @change="saveConfig"
              >
                <option value="">(Auto-detect)</option>
                <option
                  v-for="m in installedOfflineModels"
                  :key="m.model_id"
                  :value="m.model_id"
                >
                  {{ availableModels.find(e => e.model_id === m.model_id)?.display_name ?? m.model_id }}
                </option>
              </select>
            </div>

            <!-- Model Directory -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">Model Directory</span>
              </label>
              <div class="flex gap-2">
                <input
                  v-model="asrConfig.model_dir"
                  type="text"
                  class="input input-bordered flex-1"
                  placeholder="Path to sherpa-onnx model files"
                />
                <button class="btn btn-outline btn-sm" @click="handlePickDirectory">Browse</button>
              </div>
              <label class="label">
                <span class="label-text-alt text-base-content/40">
                  Directory containing the sherpa-onnx model files (tokens.txt, *.onnx).
                </span>
              </label>
            </div>

            <!-- Language -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">Language</span>
              </label>
              <select
                v-model="asrConfig.language"
                class="select select-bordered w-full"
              >
                <option v-for="lang in languages" :key="lang.value" :value="lang.value">
                  {{ lang.label }}
                </option>
                <option value="__custom__">Custom...</option>
              </select>
              <input
                v-if="asrConfig.language === '__custom__'"
                v-model="customLanguage"
                type="text"
                class="input input-bordered w-full mt-1"
                placeholder="Enter language code (e.g. zh, en, ja)"
                @input="asrConfig.language = customLanguage || '__custom__'"
              />
              <label class="label">
                <span class="label-text-alt text-base-content/40">
                  Language code for ASR. Select from list or choose Custom.
                </span>
              </label>
            </div>

            <!-- GPU Toggle -->
            <div class="form-control">
              <label class="label cursor-pointer justify-start gap-4">
                <span class="label-text font-medium">Use GPU</span>
                <input
                  v-model="asrConfig.use_gpu"
                  type="checkbox"
                  class="toggle toggle-primary"
                />
              </label>
              <label class="label">
                <span class="label-text-alt text-base-content/40">
                  Enable GPU acceleration if available (requires CUDA/OpenCL).
                </span>
              </label>
            </div>

            <!-- Download Source -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">Download Source</span>
              </label>
              <select
                v-model="asrConfig.download_source"
                class="select select-bordered w-full"
              >
                <option v-for="src in downloadSources" :key="src.value" :value="src.value">
                  {{ src.label }}
                </option>
              </select>
            </div>

            <!-- GitHub Proxy Domain (shown when ghproxy selected) -->
            <div v-if="asrConfig.download_source === 'ghproxy'" class="form-control">
              <label class="label">
                <span class="label-text font-medium">GitHub Proxy Domain</span>
              </label>
              <input
                v-model="asrConfig.custom_ghproxy_domain"
                type="text"
                class="input input-bordered w-full"
                placeholder="https://xxx.example.com"
              />
              <label class="label">
                <span class="label-text-alt text-base-content/40">
                  Visit <a href="https://ghproxy.link/" target="_blank" rel="noopener noreferrer" class="link">ghproxy.link</a> to find currently available proxy domains, then paste one here.
                </span>
              </label>
            </div>

            <!-- ModelScope info -->
            <div v-if="asrConfig.download_source === 'modelscope'" class="form-control">
              <label class="label">
                <span class="label-text-alt text-base-content/50">
                  ModelScope only provides Alibaba ecosystem models (Paraformer, SenseVoice, FunASR).
                </span>
              </label>
            </div>

            <!-- Network Proxy -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">Network Proxy</span>
              </label>
              <select
                v-model="asrConfig.proxy_mode"
                class="select select-bordered w-full"
              >
                <option v-for="pm in proxyModes" :key="pm.value" :value="pm.value">
                  {{ pm.label }}
                </option>
              </select>
            </div>

            <!-- Custom Proxy URL (shown when custom proxy selected) -->
            <div v-if="asrConfig.proxy_mode === 'custom'" class="form-control">
              <label class="label">
                <span class="label-text font-medium">Proxy URL</span>
              </label>
              <input
                v-model="asrConfig.proxy_url"
                type="text"
                class="input input-bordered w-full"
                placeholder="http://127.0.0.1:7890"
              />
              <label class="label">
                <span class="label-text-alt text-base-content/40">
                  HTTP/HTTPS proxy URL, e.g. http://host:port
                </span>
              </label>
            </div>
          </div>

          <!-- Save button -->
          <div class="card-actions mt-4 justify-end">
            <button
              class="btn btn-primary btn-sm"
              :disabled="isSaving"
              @click="saveConfig"
            >
              <span v-if="isSaving" class="loading loading-spinner loading-xs"></span>
              Save Configuration
            </button>
          </div>
        </div>
      </div>

      <!-- Model Management: Available Models -->
      <div class="card bg-base-100 border border-base-300 shadow-md">
        <div class="card-body">
          <h2 class="card-title text-base">Available Models</h2>
          <p class="text-sm text-base-content/60">
            Download ASR models for local speech recognition. VAD model is auto-downloaded with the first ASR model.
          </p>

          <div class="mt-4 space-y-2">
            <div
              v-for="model in availableModels.filter(m => m.model_type !== 'vad' && m.model_type !== 'tool')"
              :key="model.model_id"
              class="flex items-center justify-between rounded-lg border p-3"
              :class="isModelAvailableOnSource(model) ? 'border-base-300' : 'border-base-300 bg-base-200 opacity-60'"
            >
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="font-medium text-sm truncate">{{ model.display_name }}</span>
                  <span
                    class="badge badge-sm"
                    :class="model.model_type === 'streaming' ? 'badge-primary' : 'badge-secondary'"
                  >{{ model.model_type }}</span>
                  <span
                    v-for="src in model.sources"
                    :key="src"
                    class="badge badge-ghost badge-xs"
                    :class="src === asrConfig.download_source ? 'badge-outline' : ''"
                  >{{ sourceBadgeLabel(src) }}</span>
                </div>
                <div class="mt-1 flex items-center gap-2 text-xs text-base-content/50">
                  <span>{{ model.languages.join(', ') }}</span>
                  <span>-</span>
                  <span>{{ formatSize(model.size_mb) }}</span>
                </div>
                <p class="mt-0.5 text-xs text-base-content/40 truncate">{{ model.description }}</p>
                <!-- Manual download links -->
                <div v-if="model.manual_download_links && model.manual_download_links.length > 0" class="mt-1 flex flex-wrap gap-1">
                  <a
                    v-for="link in model.manual_download_links"
                    :key="link.label"
                    :href="link.url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="text-xs text-primary underline"
                  >{{ link.label }}</a>
                </div>
              </div>
              <div class="ml-3 flex-shrink-0">
                <!-- Download progress -->
                <div v-if="downloadingModelId === model.model_id && downloadProgress" class="text-center">
                  <progress
                    class="progress progress-primary w-24"
                    :value="downloadProgress.percent"
                    max="100"
                  ></progress>
                  <div class="text-xs text-base-content/50 mt-1">{{ downloadProgress.percent }}%</div>
                  <button
                    class="btn btn-ghost btn-xs mt-1 text-error"
                    @click="handleCancelInstall"
                  >Cancel</button>
                </div>
                <!-- Already installed -->
                <span v-else-if="isModelInstalled(model.model_id)" class="badge badge-success badge-sm">Installed</span>
                <!-- Not available on current source -->
                <span v-else-if="!isModelAvailableOnSource(model)" class="text-xs text-base-content/40">N/A</span>
                <!-- Download button -->
                <button
                  v-else
                  class="btn btn-primary btn-sm"
                  :disabled="!!downloadingModelId"
                  @click="handleInstallModel(model.model_id)"
                >Download</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Model Management: Installed Models -->
      <div v-if="installedModels.length > 0" class="card bg-base-100 border border-base-300 shadow-md">
        <div class="card-body">
          <h2 class="card-title text-base">Installed Models</h2>
          <div class="mt-4 space-y-2">
            <div
              v-for="model in installedModels"
              :key="model.model_id"
              class="flex items-center justify-between rounded-lg border border-base-300 p-3"
            >
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="font-medium text-sm truncate">{{ model.model_id }}</span>
                  <span
                    v-if="isModelActive(model.model_id, 'streaming')"
                    class="badge badge-info badge-sm"
                  >Active (Streaming)</span>
                  <span
                    v-if="isModelActive(model.model_id, 'offline')"
                    class="badge badge-info badge-sm"
                  >Active (Offline)</span>
                  <span
                    v-if="!model.valid"
                    class="badge badge-warning badge-sm"
                  >Invalid</span>
                </div>
                <div class="mt-1 text-xs text-base-content/50">
                  {{ formatSize(model.size_mb) }}
                </div>
              </div>
              <div class="ml-3 flex items-center gap-2 flex-shrink-0">
                <!-- Activate button (for ASR models, not VAD) -->
                <template v-if="model.model_id !== 'silero_vad'">
                  <button
                    v-if="isModelActive(model.model_id, 'streaming') || isModelActive(model.model_id, 'offline')"
                    class="btn btn-ghost btn-xs"
                    @click="
                      isModelActive(model.model_id, 'streaming')
                        ? handleSetActiveModel(model.model_id, 'streaming')
                        : handleSetActiveModel(model.model_id, 'offline')
                    "
                  >Deactivate</button>
                  <button
                    v-else
                    class="btn btn-outline btn-xs"
                    @click="
                      model.model_type === 'streaming'
                        ? handleSetActiveModel(model.model_id, 'streaming')
                        : handleSetActiveModel(model.model_id, 'offline')
                    "
                  >Activate</button>
                </template>
                <!-- Delete button -->
                <button
                  v-if="deleteConfirmId === model.model_id"
                  class="btn btn-error btn-xs"
                  @click="handleDeleteModel(model.model_id)"
                >Confirm</button>
                <button
                  v-else
                  class="btn btn-ghost btn-xs text-error"
                  @click="deleteConfirmId = model.model_id"
                >Delete</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Related Links -->
      <div class="card bg-base-100 border border-base-300 shadow-md">
        <div class="card-body">
          <h2 class="card-title text-base">Related Links</h2>
          <p class="text-sm text-base-content/60">
            External resources for sherpa-onnx models and tools. You can manually download models and place them in the model directory.
          </p>
          <div class="mt-4 space-y-3">

            <div class="divider text-xs">Model Sources</div>

            <!-- Model source links -->
            <div class="grid grid-cols-1 gap-2">
              <div class="flex items-center justify-between">
                <span class="text-sm">GitHub Releases (All Models)</span>
                <a
                  href="https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="btn btn-outline btn-xs"
                >Open</a>
              </div>
              <div class="flex items-center justify-between">
                <span class="text-sm">HuggingFace (csukuangfj/models)</span>
                <a
                  href="https://huggingface.co/csukuangfj/models"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="btn btn-outline btn-xs"
                >Open</a>
              </div>
              <div class="flex items-center justify-between">
                <span class="text-sm">ModelScope (Alibaba Ecosystem)</span>
                <a
                  href="https://www.modelscope.cn/models/zhaochaoqun/sherpa-onnx-asr-models/files"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="btn btn-outline btn-xs"
                >Open</a>
              </div>
              <div class="flex items-center justify-between">
                <span class="text-sm">GitHub Proxy List</span>
                <a
                  href="https://ghproxy.link/"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="btn btn-outline btn-xs"
                >Open</a>
              </div>
            </div>

            <div class="divider text-xs">Other Links</div>
            
            <!-- Subtitle generation tools -->
            <div v-for="tool in availableModels.filter(m => m.model_type === 'tool')" :key="tool.model_id">
              <div class="text-sm font-medium">{{ tool.display_name }}</div>
              <div class="text-xs text-base-content/50">{{ tool.description }}</div>
              <div class="mt-1 flex gap-2">
                <a
                  v-for="link in tool.manual_download_links"
                  :key="link.label"
                  :href="link.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="btn btn-outline btn-xs"
                >{{ link.label }}</a>
              </div>
            </div>

          </div>
        </div>
      </div>

      <!-- App Info -->
      <div class="card bg-base-200 border border-base-300">
        <div class="card-body">
          <h2 class="card-title text-base">About</h2>
          <div class="text-sm text-base-content/70 space-y-1">
            <p><strong>SherpaNote</strong> - AI-powered voice learning assistant</p>
            <p>Speech recognition by sherpa-onnx (local, privacy-first)</p>
            <p>AI processing via configurable LLM backend</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
