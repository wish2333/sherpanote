/** Composable for AI preset CRUD operations. */

import { ref } from "vue";
import { call } from "../bridge";
import { useAppStore } from "../stores/appStore";
import type { AiPreset } from "../types";

export function useAiPresets(onChanged?: () => void) {
  const store = useAppStore();

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
    const data: Record<string, unknown> = {
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
      data.is_active = aiPresets.value.length === 0;
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
    onChanged?.();
  }

  async function handleActivatePreset(presetId: string) {
    const res = await call("set_active_ai_preset", presetId);
    if (res.success) {
      store.showToast("Preset activated", "success");
      await loadPresets();
      onChanged?.();
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
      onChanged?.();
    } else {
      store.showToast(res.error ?? "Failed to delete preset", "error");
    }
  }

  return {
    aiPresets,
    showPresetForm,
    editingPreset,
    presetForm,
    deletePresetConfirmId,
    isTestingPreset,
    presetTestResult,
    loadPresets,
    openNewPresetForm,
    openEditPresetForm,
    cancelPresetForm,
    testPresetConnection,
    savePreset,
    handleActivatePreset,
    handleDeletePreset,
  };
}
