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
const activeTab = ref<"general" | "ai" | "processing" | "model-settings" | "model-management">("general");

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
  installedModels.value.filter(
    (m) =>
      m.model_type === "streaming" ||
      // SenseVoice and Qwen3-ASR models support simulated streaming via VAD + offline recognizer.
      m.model_id.includes("sense-voice") || m.model_id.includes("sensevoice") ||
      m.model_id.includes("qwen3-asr"),
  ),
);

const installedOfflineModels = computed(() =>
  installedModels.value.filter((m) => m.model_type === "offline"),
);

const installedVadModels = computed(() =>
  installedModels.value.filter((m) => m.model_type === "vad"),
);

// ---- Non-linear VAD threshold mapping ----
// Raw slider 0-100 → threshold: 0-50 maps to 0.01-0.10 (fine), 50-100 maps to 0.10-0.90 (coarser)
function vadThresholdToRaw(threshold: number): number {
  if (threshold <= 0.1) return Math.round((threshold - 0.01) / 0.09 * 50);
  return Math.round(50 + (threshold - 0.1) / 0.8 * 50);
}
function rawToVadThreshold(raw: number): number {
  if (raw <= 50) return Math.round((raw / 50 * 0.09 + 0.01) * 1000) / 1000;
  return Math.round(((raw - 50) / 50 * 0.8 + 0.1) * 100) / 100;
}
const vadThresholdRaw = computed({
  get: () => vadThresholdToRaw(asrConfig.value.vad_threshold),
  set: (v: number) => { asrConfig.value.vad_threshold = rawToVadThreshold(v); },
});

// ---- Non-linear VAD max_speech_duration mapping ----
// Raw slider 0-100 → duration: 0-50 → 5-20s (fine), 50-80 → 20-60s, 80-100 → 60-120s
function speechToRaw(dur: number): number {
  if (dur <= 20) return Math.round((dur - 5) / 15 * 50);
  if (dur <= 60) return Math.round(50 + (dur - 20) / 40 * 30);
  return Math.round(80 + (dur - 60) / 60 * 20);
}
function rawToSpeech(raw: number): number {
  if (raw <= 50) return Math.round((raw / 50 * 15 + 5) * 10) / 10;
  if (raw <= 80) return Math.round(((raw - 50) / 30 * 40 + 20) * 10) / 10;
  return Math.round(((raw - 80) / 20 * 60 + 60) * 10) / 10;
}
const vadSpeechRaw = computed({
  get: () => speechToRaw(asrConfig.value.vad_max_speech_duration),
  set: (v: number) => { asrConfig.value.vad_max_speech_duration = rawToSpeech(v); },
});

function supportsSimulatedStreaming(modelId: string): boolean {
  return modelId.includes("sense-voice") || modelId.includes("sensevoice") ||
    modelId.includes("qwen3-asr");
}

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
        返回
      </button>
      <h1 class="text-xl font-bold tracking-tight text-base-content">设置</h1>
    </div>

    <!-- Tab navigation -->
    <div class="tabs tabs-boxed mb-6 bg-base-200">
      <a
        class="tab"
        :class="{ 'tab-active': activeTab === 'general' }"
        @click="activeTab = 'general'"
      >通用</a>
      <a
        class="tab"
        :class="{ 'tab-active': activeTab === 'ai' }"
        @click="activeTab = 'ai'"
      >AI 模型</a>
      <a
        class="tab"
        :class="{ 'tab-active': activeTab === 'processing' }"
        @click="activeTab = 'processing'"
      >处理</a>
      <a
        class="tab"
        :class="{ 'tab-active': activeTab === 'model-settings' }"
        @click="activeTab = 'model-settings'"
      >模型设置</a>
      <a
        class="tab"
        :class="{ 'tab-active': activeTab === 'model-management' }"
        @click="activeTab = 'model-management'"
      >模型管理</a>
    </div>

    <!-- General Settings -->
    <div v-show="activeTab === 'general'" class="space-y-4">
      <div class="card bg-base-100 border border-base-300 shadow-md">
        <div class="card-body">
          <h2 class="card-title text-base">版本历史</h2>
          <p class="text-sm text-base-content/60">
            配置每条记录保留的版本数量。保存版本会手动或退出时自动创建快照。
          </p>

          <div class="mt-4 space-y-4">
            <!-- Max Version History -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">最大版本历史</span>
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
                  每条记录的最大版本数。0 = 不限。超出时自动删除最旧版本。
                </span>
              </label>
            </div>

            <!-- Auto Punctuation Toggle -->
            <div class="form-control">
              <label class="label cursor-pointer justify-start gap-4">
                <span class="label-text font-medium">自动标点</span>
                <input
                  v-model="asrConfig.auto_punctuate"
                  type="checkbox"
                  class="toggle toggle-primary"
                />
              </label>
              <label class="label">
                <span class="label-text-alt text-base-content/40">
                  使用 AI 为转写结果添加标点符号。需要配置 AI。
                </span>
              </label>
            </div>

            <!-- Auto AI Processing after Transcription -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">自动 AI 处理</span>
              </label>
              <label class="label">
                <span class="label-text-alt text-base-content/40">
                  选择转写完成后自动运行的 AI 处理模式。
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
                  Active: {{ autoAiModes.join(', ') }}。需要配置 AI。
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
              保存
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
            <h2 class="card-title text-base">API 预设</h2>
            <button
              class="btn btn-outline btn-sm"
              @click="openNewPresetForm"
            >
              添加预设
            </button>
          </div>
          <p class="text-sm text-base-content/60">
            保存多个 API 配置，方便在不同服务商之间快速切换。
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
                :title="preset.is_active ? '当前正在使用' : '点击切换'"
              >
                <div class="flex items-center gap-2">
                  <span class="font-medium text-sm">{{ preset.name }}</span>
                  <span v-if="preset.is_active" class="badge badge-primary badge-xs">使用中</span>
                </div>
                <div class="mt-0.5 text-xs text-base-content/50">
                  {{ preset.provider }} / {{ preset.model }}
                </div>
              </button>
              <div class="ml-3 flex items-center gap-1 flex-shrink-0">
                <button
                  class="btn btn-ghost btn-xs"
                  title="编辑"
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
                >确认</button>
                <button
                  v-else
                  class="btn btn-ghost btn-xs text-error"
                  title="删除"
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
            暂无预设，点击"添加预设"创建。
          </p>

          <!-- Preset form (inline) -->
          <div v-if="showPresetForm" class="mt-4 rounded-lg border border-base-300 p-4 space-y-3">
            <h3 class="text-sm font-semibold">
              {{ editingPreset ? '编辑预设' : '新建预设' }}
            </h3>
            <div class="form-control">
              <label class="label"><span class="label-text text-sm">预设名称</span></label>
              <input
                v-model="presetForm.name"
                type="text"
                class="input input-bordered input-sm w-full"
                placeholder="e.g. GPT-4o, Local Ollama"
              />
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div class="form-control">
                <label class="label"><span class="label-text text-sm">服务商</span></label>
                <select v-model="presetForm.provider" class="select select-bordered select-sm w-full">
                  <option v-for="p in providers" :key="p.value" :value="p.value">{{ p.label }}</option>
                </select>
              </div>
              <div class="form-control">
                <label class="label"><span class="label-text text-sm">模型</span></label>
                <input
                  v-model="presetForm.model"
                  type="text"
                  class="input input-bordered input-sm w-full"
                  placeholder="gpt-4o-mini"
                />
              </div>
            </div>
            <div class="form-control">
              <label class="label"><span class="label-text text-sm">API 密钥</span></label>
              <input
                v-model="presetForm.api_key"
                type="password"
                class="input input-bordered input-sm w-full"
                placeholder="sk-..."
              />
            </div>
            <div class="form-control">
              <label class="label"><span class="label-text text-sm">接口地址</span></label>
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
                测试
              </button>
              <div class="flex gap-2">
                <button class="btn btn-ghost btn-sm" @click="cancelPresetForm">取消</button>
                <button class="btn btn-primary btn-sm" @click="savePreset">
                  {{ editingPreset ? '更新' : '创建' }}
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
          <h2 class="card-title text-base">AI 模型配置</h2>
          <p class="text-sm text-base-content/60">
            微调当前 AI 服务商配置。修改后需保存。
          </p>

          <div class="mt-4 space-y-4">
            <!-- Provider -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">服务商</span>
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
                <span class="label-text font-medium">模型</span>
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
                <span class="label-text font-medium">API 密钥</span>
              </label>
              <input
                v-model="aiConfig.api_key"
                type="password"
                class="input input-bordered w-full"
                placeholder="sk-... (leave empty for local models)"
              />
              <label class="label">
                <span class="label-text-alt text-base-content/40">
                  Ollama（本地模型）无需填写。
                </span>
              </label>
            </div>

            <!-- Base URL -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">自定义接口地址</span>
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
                <span class="label-text font-medium">温度</span>
                <span class="label-text-alt text-base-content/50">{{ aiConfig.temperature }}</span>
              </label>
              <label class="flex items-center gap-3">
                <span class="text-xs text-base-content/40 w-12 shrink-0">精确</span>
                <input
                  v-model.number="aiConfig.temperature"
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  class="range range-primary range-xs flex-1"
                />
                <span class="text-xs text-base-content/40 w-12 text-right shrink-0">创意</span>
              </label>
            </div>

            <!-- Max Tokens Mode -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">最大 Token 数</span>
              </label>
              <div class="flex flex-col gap-2">
                <label
                  v-for="opt in [
                    { value: 'auto' as const, label: '自动', desc: '根据输入长度估算' },
                    { value: 'custom' as const, label: '固定值', desc: '使用下方设定值' },
                    { value: 'default' as const, label: '模型默认', desc: '不限制，由模型决定' },
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
                <span class="label-text font-medium">Token 数值</span>
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
              测试连接
            </button>
            <button
              class="btn btn-primary btn-sm"
              :disabled="isSaving"
              @click="saveConfig"
            >
              <span v-if="isSaving" class="loading loading-spinner loading-xs"></span>
              保存 Configuration
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
            <h2 class="card-title text-base">AI 处理预设</h2>
            <button
              class="btn btn-outline btn-sm"
              @click="openNewProcessingPresetForm"
            >
              添加预设
            </button>
          </div>
          <p class="text-sm text-base-content/60">
            管理 AI 文本处理的提示词模板。内置预设不可删除。
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
                  <span v-if="preset.id.startsWith('builtin_')" class="badge badge-ghost badge-xs">内置</span>
                </div>
                <div class="mt-0.5 text-xs text-base-content/40 truncate max-w-[400px]">
                  {{ preset.prompt.slice(0, 100) }}{{ preset.prompt.length > 100 ? '...' : '' }}
                </div>
              </div>
              <div class="ml-3 flex items-center gap-1 flex-shrink-0">
                <button
                  class="btn btn-ghost btn-xs"
                  title="编辑"
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
                >确认</button>
                <button
                  v-else-if="!preset.id.startsWith('builtin_')"
                  class="btn btn-ghost btn-xs text-error"
                  title="删除"
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
              {{ editingProcessingPreset ? '编辑处理预设' : '新建处理预设' }}
            </h3>
            <div class="grid grid-cols-2 gap-3">
              <div class="form-control">
                <label class="label"><span class="label-text text-sm">预设名称</span></label>
                <input
                  v-model="processingPresetForm.name"
                  type="text"
                  class="input input-bordered input-sm w-full"
                  placeholder="e.g. Quick Summary"
                />
              </div>
              <div class="form-control">
                <label class="label"><span class="label-text text-sm">模式</span></label>
                <select v-model="processingPresetForm.mode" class="select select-bordered select-sm w-full">
                  <option v-for="m in processingModeOptions" :key="m.value" :value="m.value">{{ m.label }}</option>
                </select>
              </div>
            </div>
            <div class="form-control">
              <label class="label"><span class="label-text text-sm">提示词模板</span></label>
              <label class="label"><span class="label-text-alt text-base-content/40">使用 {text} 作为输入文本的占位符。</span></label>
              <textarea
                v-model="processingPresetForm.prompt"
                class="textarea textarea-bordered w-full text-sm"
                rows="6"
                placeholder="在此输入提示词模板。使用 {text} 标记需要插入用户文本的位置。"
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

    <!-- 模型设置 -->
    <div v-show="activeTab === 'model-settings'" class="space-y-4">
      <!-- ASR Engine Configuration Card -->
      <div class="card bg-base-100 border border-base-300 shadow-md">
        <div class="card-body">
          <h2 class="card-title text-base">ASR 引擎配置</h2>
          <p class="text-sm text-base-content/60">
            配置 sherpa-onnx 语音识别引擎的运行参数。
          </p>

          <div class="mt-4 space-y-4">
            <!-- Active Streaming Model -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">流式识别模型</span>
              </label>
              <select
                v-model="asrConfig.active_streaming_model"
                class="select select-bordered w-full"
                @change="saveConfig"
              >
                <option value="">(自动检测)</option>
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
                <span class="label-text font-medium">离线识别模型</span>
              </label>
              <select
                v-model="asrConfig.active_offline_model"
                class="select select-bordered w-full"
                @change="saveConfig"
              >
                <option value="">(自动检测)</option>
                <option
                  v-for="m in installedOfflineModels"
                  :key="m.model_id"
                  :value="m.model_id"
                >
                  {{ availableModels.find(e => e.model_id === m.model_id)?.display_name ?? m.model_id }}
                </option>
              </select>
            </div>

            <!-- VAD Settings -->
            <div class="divider text-xs">VAD 语音检测</div>
            <p class="text-xs text-base-content/50">
              VAD（Voice Activity Detection）用于检测语音段落的起止。以下参数影响实时流式识别和文件转写的分段行为。
            </p>

            <!-- active_vad_model -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">VAD 模型</span>
              </label>
              <select
                v-model="asrConfig.active_vad_model"
                class="select select-bordered w-full"
                @change="saveConfig"
              >
                <option value="auto">自动（优先 v5）</option>
                <option
                  v-for="m in installedVadModels"
                  :key="m.model_id"
                  :value="m.model_id"
                >
                  {{ availableModels.find(e => e.model_id === m.model_id)?.display_name ?? m.model_id }}
                </option>
              </select>
              <p class="text-xs text-base-content/40 mt-1">
                自动模式下优先使用 v5，无 v5 时回退 v4。在模型管理页下载。
              </p>
            </div>

            <!-- offline_use_vad -->
            <div class="form-control">
              <label class="label cursor-pointer justify-start gap-3">
                <input
                  v-model="asrConfig.offline_use_vad"
                  type="checkbox"
                  class="toggle toggle-primary toggle-sm"
                  @change="saveConfig"
                />
                <span class="label-text font-medium">文件转写使用 VAD 分段</span>
              </label>
              <p class="text-xs text-base-content/40 ml-11">
                关闭后，文件转写将整段音频一次性识别，不分段。适合短音频或不需要分段的场景。
              </p>
            </div>

            <!-- vad_padding -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">分段前后静音填充 (秒)</span>
                <span class="label-text-alt text-base-content/50">{{ (asrConfig.vad_padding * 1000).toFixed(0) }}ms</span>
              </label>
              <label class="flex items-center gap-3">
                <span class="text-xs text-base-content/40 w-12 shrink-0">无</span>
                <input
                  v-model.number="asrConfig.vad_padding"
                  type="range"
                  min="0"
                  max="3.0"
                  step="0.1"
                  class="range range-primary range-xs flex-1"
                  @change="saveConfig"
                />
                <span class="text-xs text-base-content/40 w-12 text-right shrink-0">3s</span>
              </label>
              <p class="label text-base-content/40 text-xs mt-1">
                在每个 VAD 分段前后添加静音，避免语音截断导致的识别错误。设为 0 关闭。默认 800ms。
              </p>
            </div>

            <!-- vad_threshold -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">语音检测阈值</span>
                <span class="label-text-alt text-base-content/50">{{ asrConfig.vad_threshold.toFixed(3) }}</span>
              </label>
              <label class="flex items-center gap-3">
                <span class="text-xs text-base-content/40 w-12 shrink-0">灵敏</span>
                <input
                  v-model.number="vadThresholdRaw"
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  class="range range-primary range-xs flex-1"
                  @change="saveConfig"
                />
                <span class="text-xs text-base-content/40 w-12 text-right shrink-0">严格</span>
              </label>
              <p class="label text-base-content/40 text-xs mt-1">
                语音/静音判定阈值。值越低越灵敏（更容易检测到语音），值越高越严格。0.01-0.10 区间有更精细的控制。默认 0.05。
              </p>
            </div>

            <!-- vad_min_silence_duration -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">最小静音时长 (秒)</span>
                <span class="label-text-alt text-base-content/50">{{ asrConfig.vad_min_silence_duration.toFixed(1) }}s</span>
              </label>
              <label class="flex items-center gap-3">
                <span class="text-xs text-base-content/40 w-12 shrink-0">短</span>
                <input
                  v-model.number="asrConfig.vad_min_silence_duration"
                  type="range"
                  min="0.1"
                  max="5.0"
                  step="0.1"
                  class="range range-primary range-xs flex-1"
                  @change="saveConfig"
                />
                <span class="text-xs text-base-content/40 w-12 text-right shrink-0">长</span>
              </label>
              <p class="label text-base-content/40 text-xs mt-1">
                静音超过此时长后，当前语音段将被截断。值越大，越允许说话中的停顿不被切断。实时流式会自动乘以 1.6 倍。
              </p>
            </div>

            <!-- vad_min_speech_duration -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">最小语音时长 (秒)</span>
                <span class="label-text-alt text-base-content/50">{{ asrConfig.vad_min_speech_duration.toFixed(2) }}s</span>
              </label>
              <label class="flex items-center gap-3">
                <span class="text-xs text-base-content/40 w-12 shrink-0">短</span>
                <input
                  v-model.number="asrConfig.vad_min_speech_duration"
                  type="range"
                  min="0.05"
                  max="2.0"
                  step="0.05"
                  class="range range-primary range-xs flex-1"
                  @change="saveConfig"
                />
                <span class="text-xs text-base-content/40 w-12 text-right shrink-0">长</span>
              </label>
              <p class="label text-base-content/40 text-xs mt-1">
                短于此时间的语音段将被忽略，用于过滤噪声、咳嗽等短暂声音。
              </p>
            </div>

            <!-- vad_max_speech_duration -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">最大语音时长 (秒)</span>
                <span class="label-text-alt text-base-content/50">{{ asrConfig.vad_max_speech_duration.toFixed(1) }}s</span>
              </label>
              <label class="flex items-center gap-3">
                <span class="text-xs text-base-content/40 w-12 shrink-0">短</span>
                <input
                  v-model.number="vadSpeechRaw"
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  class="range range-primary range-xs flex-1"
                  @change="saveConfig"
                />
                <span class="text-xs text-base-content/40 w-12 text-right shrink-0">长</span>
              </label>
              <p class="label text-base-content/40 text-xs mt-1">
                单个语音段的最大时长。超过此时长将被强制分段。5-20s 区间精细可调。默认 8s。
              </p>
            </div>

            <!-- Language -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">识别语言</span>
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
                  ASR 识别语言代码。从列表选择或自定义。
                </span>
              </label>
            </div>

            <!-- GPU Toggle -->
            <div class="form-control">
              <label class="label cursor-pointer justify-start gap-4">
                <span class="label-text font-medium">启用 GPU</span>
                <input
                  v-model="asrConfig.use_gpu"
                  type="checkbox"
                  class="toggle toggle-primary"
                />
              </label>
              <label class="label">
                <span class="label-text-alt text-base-content/40">
                  启用 GPU 加速（需要 CUDA/OpenCL 支持）。
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
              保存 Configuration
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 模型管理 -->
    <div v-show="activeTab === 'model-management'" class="space-y-4">
      <!-- Download & Network Settings Card -->
      <div class="card bg-base-100 border border-base-300 shadow-md">
        <div class="card-body">
          <h2 class="card-title text-base">下载与网络</h2>

          <div class="mt-4 space-y-4">
            <!-- Model Directory -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">模型目录</span>
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
                  模型文件存放目录（tokens.txt, *.onnx）。
                </span>
              </label>
            </div>

            <!-- Download Source -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">下载源</span>
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
                <span class="label-text font-medium">GitHub 代理域名</span>
              </label>
              <input
                v-model="asrConfig.custom_ghproxy_domain"
                type="text"
                class="input input-bordered w-full"
                placeholder="https://xxx.example.com"
              />
              <label class="label">
                <span class="label-text-alt text-base-content/40">
                  访问 <a href="https://ghproxy.link/" target="_blank" rel="noopener noreferrer" class="link">ghproxy.link</a> 查找可用的代理域名。
                </span>
              </label>
            </div>

            <!-- ModelScope info -->
            <div v-if="asrConfig.download_source === 'modelscope'" class="form-control">
              <label class="label">
                <span class="label-text-alt text-base-content/50">
                  ModelScope 仅提供阿里生态模型（Paraformer、SenseVoice、FunASR）。
                </span>
              </label>
            </div>

            <!-- Network Proxy -->
            <div class="form-control">
              <label class="label">
                <span class="label-text font-medium">网络代理</span>
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
                <span class="label-text font-medium">代理地址</span>
              </label>
              <input
                v-model="asrConfig.proxy_url"
                type="text"
                class="input input-bordered w-full"
                placeholder="http://127.0.0.1:7890"
              />
              <label class="label">
                <span class="label-text-alt text-base-content/40">
                  HTTP/HTTPS 代理地址，例如 http://host:port
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
              保存 Configuration
            </button>
          </div>
        </div>
      </div>

      <!-- Available Models -->
      <div class="card bg-base-100 border border-base-300 shadow-md">
        <div class="card-body">
          <h2 class="card-title text-base">可用模型</h2>
          <p class="text-sm text-base-content/60">
            下载 ASR 模型用于本地语音识别。VAD 模型会在首次下载 ASR 模型时自动下载，也可以在此手动下载。
          </p>

          <div class="mt-4 space-y-2">
            <div
              v-for="model in availableModels.filter(m => m.model_type !== 'tool')"
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
                  >取消</button>
                </div>
                <!-- Already installed -->
                <span v-else-if="isModelInstalled(model.model_id)" class="badge badge-success badge-sm">已安装</span>
                <!-- Not available on current source -->
                <span v-else-if="!isModelAvailableOnSource(model)" class="text-xs text-base-content/40">N/A</span>
                <!-- Download button -->
                <button
                  v-else
                  class="btn btn-primary btn-sm"
                  :disabled="!!downloadingModelId"
                  @click="handleInstallModel(model.model_id)"
                >下载</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Installed Models -->
      <div v-if="installedModels.length > 0" class="card bg-base-100 border border-base-300 shadow-md">
        <div class="card-body">
          <h2 class="card-title text-base">已安装模型</h2>
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
                <template v-if="model.model_type !== 'vad'">
                  <button
                    v-if="isModelActive(model.model_id, 'streaming') || isModelActive(model.model_id, 'offline')"
                    class="btn btn-ghost btn-xs"
                    @click="
                      isModelActive(model.model_id, 'streaming')
                        ? handleSetActiveModel(model.model_id, 'streaming')
                        : handleSetActiveModel(model.model_id, 'offline')
                    "
                  >停用</button>
                  <button
                    v-else
                    class="btn btn-outline btn-xs"
                    @click="
                      model.model_type === 'streaming' || supportsSimulatedStreaming(model.model_id)
                        ? handleSetActiveModel(model.model_id, 'streaming')
                        : handleSetActiveModel(model.model_id, 'offline')
                    "
                  >启用</button>
                </template>
                <!-- Delete button -->
                <button
                  v-if="deleteConfirmId === model.model_id"
                  class="btn btn-error btn-xs"
                  @click="handleDeleteModel(model.model_id)"
                >确认</button>
                <button
                  v-else
                  class="btn btn-ghost btn-xs text-error"
                  @click="deleteConfirmId = model.model_id"
                >删除</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Related Links -->
      <div class="card bg-base-100 border border-base-300 shadow-md">
        <div class="card-body">
          <h2 class="card-title text-base">相关链接</h2>
          <p class="text-sm text-base-content/60">
            sherpa-onnx 模型和工具的外部资源。可以手动下载模型并放入模型目录。
          </p>
          <div class="mt-4 space-y-3">

            <div class="divider text-xs">模型源</div>

            <!-- Model source links -->
            <div class="grid grid-cols-1 gap-2">
              <div class="flex items-center justify-between">
                <span class="text-sm">GitHub Releases (All Models)</span>
                <a
                  href="https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="btn btn-outline btn-xs"
                >打开</a>
              </div>
              <div class="flex items-center justify-between">
                <span class="text-sm">HuggingFace (csukuangfj/models)</span>
                <a
                  href="https://huggingface.co/csukuangfj/models"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="btn btn-outline btn-xs"
                >打开</a>
              </div>
              <div class="flex items-center justify-between">
                <span class="text-sm">ModelScope (Alibaba Ecosystem)</span>
                <a
                  href="https://www.modelscope.cn/models/zhaochaoqun/sherpa-onnx-asr-models/files"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="btn btn-outline btn-xs"
                >打开</a>
              </div>
              <div class="flex items-center justify-between">
                <span class="text-sm">GitHub Proxy List</span>
                <a
                  href="https://ghproxy.link/"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="btn btn-outline btn-xs"
                >打开</a>
              </div>
            </div>

            <div class="divider text-xs">其他工具</div>

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
