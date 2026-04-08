<script setup lang="ts">
/**
 * SettingsView - Application configuration page.
 *
 * Allows users to configure AI model settings and ASR settings.
 * Includes model management (download, delete, activate).
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
import type { AiConfig, AsrConfig, ModelEntry, InstalledModel, DownloadProgress } from "../types";

const store = useAppStore();
const router = useRouter();

const aiConfig = ref<AiConfig>(store.aiConfig);
const asrConfig = ref<AsrConfig>(store.asrConfig);
const isSaving = ref(false);
const isTesting = ref(false);
const testResult = ref<{ success: boolean; message: string } | null>(null);
const activeTab = ref<"ai" | "asr">("ai");

const providers = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic (via OpenAI compat)" },
  { value: "ollama", label: "Ollama (Local)" },
  { value: "qwen", label: "Qwen" },
];

const languages = [
  { value: "auto", label: "Auto Detect" },
  { value: "zh", label: "Chinese" },
  { value: "en", label: "English" },
];

// ---- Model management state ----
const availableModels = ref<ModelEntry[]>([]);
const installedModels = ref<InstalledModel[]>([]);
const downloadingModelId = ref<string | null>(null);
const downloadProgress = ref<DownloadProgress | null>(null);
const deleteConfirmId = ref<string | null>(null);

const useCustomMirror = computed(() => !!asrConfig.value.mirror_url);

const installedStreamingModels = computed(() =>
  installedModels.value.filter((m) => {
    const entry = availableModels.value.find((e) => e.model_id === m.model_id);
    return entry?.model_type === "streaming";
  }),
);

const installedOfflineModels = computed(() =>
  installedModels.value.filter((m) => {
    const entry = availableModels.value.find((e) => e.model_id === m.model_id);
    return entry?.model_type === "offline";
  }),
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

function setDownloadSource(source: string) {
  if (source === "mirror") {
    asrConfig.value = { ...asrConfig.value, mirror_url: asrConfig.value.mirror_url || "" };
  } else {
    asrConfig.value = { ...asrConfig.value, mirror_url: null };
  }
}

async function handlePickDirectory() {
  const res = await pickDirectory();
  if (res.success && res.data) {
    asrConfig.value = { ...asrConfig.value, model_dir: res.data.path };
  }
}

// ---- Config ----

async function loadConfig() {
  const res = await call<{ ai: AiConfig; asr: AsrConfig }>("get_config");
  if (res.success && res.data) {
    if (res.data.ai) {
      aiConfig.value = res.data.ai;
      store.aiConfig = res.data.ai;
    }
    if (res.data.asr) {
      asrConfig.value = res.data.asr;
      store.asrConfig = res.data.asr;
    }
  }
}

async function saveConfig() {
  isSaving.value = true;
  const res = await call("update_config", {
    ai: aiConfig.value,
    asr: asrConfig.value,
  });
  if (res.success) {
    store.aiConfig = aiConfig.value;
    store.asrConfig = asrConfig.value;
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
    // Clear active model if it was the deleted one.
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
        :class="{ 'tab-active': activeTab === 'ai' }"
        @click="activeTab = 'ai'"
      >AI Model</a>
      <a
        class="tab"
        :class="{ 'tab-active': activeTab === 'asr' }"
        @click="activeTab = 'asr'"
      >ASR Engine</a>
    </div>

    <!-- AI Configuration -->
    <div v-show="activeTab === 'ai'" class="card bg-base-100 border border-base-300 shadow-md">
      <div class="card-body">
        <h2 class="card-title text-base">AI Model Configuration</h2>
        <p class="text-sm text-base-content/60">
          Configure the LLM backend for text processing. Supports OpenAI-compatible APIs.
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
              <span class="label-text font-medium">
                Temperature: {{ aiConfig.temperature }}
              </span>
            </label>
            <input
              v-model.number="aiConfig.temperature"
              type="range"
              min="0"
              max="2"
              step="0.1"
              class="range range-primary"
            />
            <div class="flex justify-between text-xs text-base-content/40 px-1">
              <span>Precise</span>
              <span>Creative</span>
            </div>
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
              <select v-model="asrConfig.language" class="select select-bordered w-full">
                <option v-for="lang in languages" :key="lang.value" :value="lang.value">
                  {{ lang.label }}
                </option>
              </select>
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
                :value="useCustomMirror ? 'mirror' : 'github'"
                class="select select-bordered w-full"
                @change="setDownloadSource(($event.target as HTMLSelectElement).value)"
              >
                <option value="github">GitHub (Default)</option>
                <option value="mirror">Custom Mirror</option>
              </select>
            </div>

            <!-- Mirror URL (shown when custom mirror selected) -->
            <div v-if="useCustomMirror" class="form-control">
              <label class="label">
                <span class="label-text font-medium">Mirror URL</span>
              </label>
              <input
                v-model="asrConfig.mirror_url"
                type="text"
                class="input input-bordered w-full"
                placeholder="https://mirror.example.com/models/"
              />
              <label class="label">
                <span class="label-text-alt text-base-content/40">
                  Base URL for model downloads. Must end with /.
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
              v-for="model in availableModels.filter(m => m.model_type !== 'vad')"
              :key="model.model_id"
              class="flex items-center justify-between rounded-lg border border-base-300 p-3"
            >
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="font-medium text-sm truncate">{{ model.display_name }}</span>
                  <span
                    class="badge badge-sm"
                    :class="model.model_type === 'streaming' ? 'badge-primary' : 'badge-secondary'"
                  >{{ model.model_type }}</span>
                </div>
                <div class="mt-1 flex items-center gap-2 text-xs text-base-content/50">
                  <span>{{ model.languages.join(', ') }}</span>
                  <span>-</span>
                  <span>{{ formatSize(model.size_mb) }}</span>
                </div>
                <p class="mt-0.5 text-xs text-base-content/40 truncate">{{ model.description }}</p>
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
                      availableModels.find(e => e.model_id === model.model_id)?.model_type === 'streaming'
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
