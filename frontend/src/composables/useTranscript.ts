/**
 * useTranscript - Transcript data management composable.
 *
 * Handles listening for partial_result / final_result events,
 * managing segment lists, and file transcription progress.
 */
import { ref, onBeforeUnmount } from "vue";
import { call, onEvent } from "../bridge";
import { useAppStore } from "../stores/appStore";
import type { TranscriptRecord } from "../types";

interface TranscriptSegment {
  text: string;
  timestamp: number[];
}

export function useTranscript() {
  const store = useAppStore();

  const partialText = ref("");
  const finalSegments = ref<TranscriptSegment[]>([]);
  const transcribeProgress = ref(0);
  const segmentInfo = ref<{ current: number; total: number } | null>(null);
  const isTranscribingFile = ref(false);

  // Cleanup handles for event listeners.
  const cleanupFns: (() => void)[] = [];

  /** Start listening for ASR events. */
  function startListening() {
    const offPartial = onEvent<{ text: string }>("partial_result", ({ text }) => {
      partialText.value = text;
    });
    const offFinal = onEvent<{ text: string; timestamp: number[] }>(
      "final_result",
      ({ text, timestamp }) => {
        finalSegments.value = [
          ...finalSegments.value,
          { text, timestamp: timestamp ?? [] },
        ];
        partialText.value = "";
      },
    );
    cleanupFns.push(offPartial, offFinal);
  }

  /** Stop listening and reset state. */
  function stopListening() {
    cleanupFns.forEach((fn) => fn());
    cleanupFns.length = 0;
    partialText.value = "";
    finalSegments.value = [];
  }

  /** Reset state without stopping listeners. */
  function resetState() {
    partialText.value = "";
    finalSegments.value = [];
    transcribeProgress.value = 0;
    segmentInfo.value = null;
  }

  /** Transcribe an audio file via backend.

   * The backend runs transcription in a background thread.
   * This method returns a Promise that resolves when the
   * 'transcribe_complete' event arrives (or rejects on error).
   */
  async function transcribeFile(
    filePath: string,
  ): Promise<{ segments: TranscriptSegment[]; text: string; audio_path: string } | null> {
    isTranscribingFile.value = true;
    transcribeProgress.value = 0;
    segmentInfo.value = null;

    const offProgress = onEvent<{
      percent: number;
      segments?: { current: number; total: number };
    }>(
      "transcribe_progress",
      ({ percent, segments }) => {
        transcribeProgress.value = percent;
        if (segments) {
          segmentInfo.value = segments;
        }
      },
    );
    cleanupFns.push(offProgress);

    // Call the backend (returns immediately, work runs in thread).
    const res = await call("transcribe_file", filePath);

    if (!res.success) {
      isTranscribingFile.value = false;
      offProgress();
      store.showToast(res.error ?? "Failed to start transcription", "error");
      return null;
    }

    // Wait for the completion event from the background thread.
    return new Promise<{ segments: TranscriptSegment[]; text: string; audio_path: string } | null>((resolve) => {
      const offComplete = onEvent<{
        segments: TranscriptSegment[];
        text: string;
        audio_path: string;
      }>("transcribe_complete", (detail) => {
        offComplete();
        isTranscribingFile.value = false;
        offProgress();
        resolve({
          segments: detail.segments ?? [],
          text: detail.text ?? "",
          audio_path: detail.audio_path ?? filePath,
        });
      });

      const offError = onEvent<{ error: string }>("transcribe_error", (detail) => {
        offError();
        offComplete();
        isTranscribingFile.value = false;
        offProgress();
        store.showToast(detail.error ?? "File transcription failed", "error");
        resolve(null);
      });
    });
  }

  /** Save transcription result as a new record. */
  async function saveAsRecord(
    title: string,
    transcript: string,
    segments: TranscriptSegment[],
    audioPath: string | null = null,
    durationSeconds = 0,
  ): Promise<TranscriptRecord | null> {
    const res = await call<TranscriptRecord>("save_record", {
      title,
      transcript,
      segments,
      audio_path: audioPath,
      duration_seconds: durationSeconds,
    });
    if (res.success && res.data) {
      return res.data;
    }
    store.showToast(res.error ?? "Failed to save transcription", "error");
    return null;
  }

  onBeforeUnmount(() => {
    stopListening();
  });

  return {
    partialText,
    finalSegments,
    transcribeProgress,
    segmentInfo,
    isTranscribingFile,
    startListening,
    stopListening,
    resetState,
    transcribeFile,
    saveAsRecord,
  };
}
