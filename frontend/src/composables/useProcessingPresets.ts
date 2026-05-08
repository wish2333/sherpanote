/** Composable for processing preset CRUD operations. */

import { ref } from "vue";
import { call } from "../bridge";
import { useAppStore } from "../stores/appStore";
import type { AiProcessingPreset } from "../types";

export function useProcessingPresets() {
  const store = useAppStore();

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

  async function resetBuiltinPresets() {
    const res = await call("reset_builtin_presets");
    if (res.success) {
      store.showToast("Built-in presets restored to defaults", "success");
      await loadProcessingPresets();
    } else {
      store.showToast(res.error ?? "Failed to reset presets", "error");
    }
  }

  return {
    processingPresets,
    showProcessingPresetForm,
    editingProcessingPreset,
    deleteProcessingPresetConfirmId,
    processingPresetForm,
    processingModeOptions,
    loadProcessingPresets,
    openNewProcessingPresetForm,
    openEditProcessingPresetForm,
    cancelProcessingPresetForm,
    saveProcessingPreset,
    handleDeleteProcessingPreset,
    resetBuiltinPresets,
  };
}
