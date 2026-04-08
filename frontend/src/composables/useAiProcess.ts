/**
 * useAiProcess - AI processing composable.
 *
 * Handles streaming AI processing: sends text + mode to backend,
 * listens for ai_token / ai_complete events, manages result state,
 * and persists results to the current record.
 */
import { ref, onBeforeUnmount } from "vue";
import { call, onEvent } from "../bridge";
import { useAppStore } from "../stores/appStore";
import type { AiMode, AiResults, TranscriptRecord } from "../types";

const AI_MODES: { key: AiMode; label: string; desc: string }[] = [
  { key: "polish", label: "Polish", desc: "Revise into fluent prose" },
  { key: "note", label: "Notes", desc: "Structured study notes" },
  { key: "mindmap", label: "Mind Map", desc: "Markmap mind map" },
  { key: "brainstorm", label: "Brainstorm", desc: "Critical thinking" },
];

export function useAiProcess() {
  const store = useAppStore();

  const isProcessing = ref(false);
  const currentMode = ref<AiMode>("polish");
  const currentResult = ref("");
  const showPanel = ref(false);

  // Accumulated text for the current stream.
  let accumulatedText = "";

  const cleanupFns: (() => void)[] = [];

  /** Register event listeners for AI streaming. */
  function startListening() {
    const offToken = onEvent<{ text: string }>("ai_token", ({ text }) => {
      accumulatedText += text;
      currentResult.value = accumulatedText;
    });

    const offComplete = onEvent<{ result: string }>(
      "ai_complete",
      ({ result }) => {
        isProcessing.value = false;
        store.isAiProcessing = false;
        accumulatedText = "";
        currentResult.value = result;
      },
    );

    const offError = onEvent<{ error: string }>("ai_error", ({ error }) => {
      isProcessing.value = false;
      store.isAiProcessing = false;
      accumulatedText = "";
      store.showToast(error, "error");
    });

    cleanupFns.push(offToken, offComplete, offError);
  }

  /** Start AI processing with streaming. */
  async function processText(text: string, mode?: AiMode, customPrompt?: string | null): Promise<void> {
    if (!text.trim()) return;

    const targetMode = mode ?? currentMode.value;
    isProcessing.value = true;
    store.isAiProcessing = true;
    currentResult.value = "";
    accumulatedText = "";
    showPanel.value = true;

    // Ensure listeners are registered.
    if (cleanupFns.length === 0) {
      startListening();
    }

    await call("process_text_stream", text, targetMode, customPrompt ?? null);
  }

  /** Save the current AI result to a record. */
  async function saveResult(record: TranscriptRecord): Promise<TranscriptRecord | null> {
    if (!currentResult.value.trim() || !record) return null;

    const updatedAi: AiResults = {
      ...record.ai_results,
      [currentMode.value]: currentResult.value,
    };

    const res = await call<TranscriptRecord>("save_record", {
      ...record,
      ai_results: updatedAi,
    });

    if (res.success && res.data) {
      store.showToast("AI result saved", "success");
      return { ...res.data };
    }

    store.showToast("Failed to save AI result", "error");
    return null;
  }

  /** Copy the current result to clipboard. */
  function copyResult(): void {
    if (currentResult.value) {
      navigator.clipboard.writeText(currentResult.value);
      store.showToast("Copied to clipboard", "info");
    }
  }

  /** Clean up listeners. */
  function stopListening() {
    cleanupFns.forEach((fn) => fn());
    cleanupFns.length = 0;
  }

  /** Cancel the current AI streaming request. */
  async function cancelProcessing(): Promise<void> {
    accumulatedText = "";
    await call("cancel_ai");
    isProcessing.value = false;
    store.isAiProcessing = false;
    store.showToast("AI processing cancelled", "info");
  }

  onBeforeUnmount(() => {
    stopListening();
  });

  return {
    isProcessing,
    currentMode,
    currentResult,
    showPanel,
    aiModes: AI_MODES,
    startListening,
    processText,
    saveResult,
    copyResult,
    cancelProcessing,
    stopListening,
  };
}
