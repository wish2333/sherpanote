/**
 * useRecording - Microphone recording composable.
 *
 * Manages Web Audio API lifecycle: getUserMedia permission,
 * AudioContext, ScriptProcessorNode, Base64 PCM encoding,
 * and timer display. Feature-detects ScriptProcessorNode support.
 *
 * Model loading runs in a background thread on the Python side.
 * The composable waits for a 'streaming_ready' event before
 * sending audio chunks, to avoid blocking the pywebview main thread.
 */
import { ref, onBeforeUnmount } from "vue";
import { call, onEvent } from "../bridge";
import { useAppStore } from "../stores/appStore";

interface RecordingSegment {
  text: string;
  timestamp: number[];
}

export function useRecording() {
  const store = useAppStore();

  const isRecording = ref(false);
  const isLoadingModel = ref(false);
  const elapsedTime = ref(0);
  const isSupported = ref(true);

  // Internal refs for cleanup.
  let audioCtx: AudioContext | null = null;
  let mediaStream: MediaStream | null = null;
  let processor: ScriptProcessorNode | null = null;
  let timerInterval: ReturnType<typeof setInterval> | null = null;

  // Cleanup handle for pending streaming_ready / streaming_error listeners.
  let _cancelStreamingWait: (() => void) | null = null;

  /** Detect ScriptProcessorNode support. */
  function checkSupport(): boolean {
    const supported = typeof AudioContext !== "undefined" &&
      typeof AudioContext.prototype.createScriptProcessor === "function";
    isSupported.value = supported;
    return supported;
  }

  /** Convert Float32Array PCM to Base64 string. */
  function float32ToBase64(float32Array: Float32Array): string {
    const bytes = new Uint8Array(float32Array.buffer);
    let binary = "";
    for (let i = 0; i < bytes.length; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }

  /** Tear down audio resources. */
  function cleanupAudio() {
    if (processor) {
      processor.disconnect();
      processor = null;
    }
    if (audioCtx) {
      audioCtx.close();
      audioCtx = null;
    }
    if (mediaStream) {
      mediaStream.getTracks().forEach((t) => t.stop());
      mediaStream = null;
    }
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
  }

  /** Start microphone recording and streaming to backend. */
  async function startRecording(): Promise<boolean> {
    if (!checkSupport()) {
      store.showToast("Web Audio API not supported in this environment", "error");
      return false;
    }

    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
        },
      });

      audioCtx = new AudioContext({ sampleRate: 16000 });
      const source = audioCtx.createMediaStreamSource(mediaStream);
      processor = audioCtx.createScriptProcessor(4096, 1, 1);

      let streamingReady = false;
      let cancelled = false;

      // Audio chunks are captured immediately but only sent once the
      // backend model is loaded (streaming_ready). Early chunks are
      // discarded -- this avoids blocking the pywebview main thread.
      processor.onaudioprocess = (e) => {
        if (!streamingReady) return;
        const float32Data = e.inputBuffer.getChannelData(0);
        const base64 = float32ToBase64(float32Data);
        call("feed_audio", base64).catch(() => {});
      };

      source.connect(processor);
      processor.connect(audioCtx.destination);

      // Ask the backend to start streaming (model loads in a thread).
      isLoadingModel.value = true;
      const startRes = await call("start_streaming");
      if (!startRes.success) {
        cleanupAudio();
        throw new Error(startRes.error ?? "Failed to start streaming");
      }

      // Wait for the model to finish loading in the background thread.
      await new Promise<void>((resolve, reject) => {
        const offReady = onEvent("streaming_ready", () => {
          offReady();
          offErr();
          if (cancelled) return;
          streamingReady = true;
          resolve();
        });
        const offErr = onEvent<{ error: string }>("streaming_error", ({ error }) => {
          offReady();
          offErr();
          if (cancelled) return;
          reject(new Error(error));
        });
        // Store cleanup so stopRecording / unmount can cancel the wait.
        _cancelStreamingWait = () => {
          cancelled = true;
          offReady();
          offErr();
        };
      });

      _cancelStreamingWait = null;
      isLoadingModel.value = false;
      isRecording.value = true;
      store.isRecording = true;
      elapsedTime.value = 0;

      timerInterval = setInterval(() => {
        elapsedTime.value++;
      }, 1000);

      return true;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to start recording";
      store.showToast(msg, "error");
      isLoadingModel.value = false;
      cleanupAudio();
      return false;
    }
  }

  /** Stop recording and cleanup audio resources. Returns final text + segments + audio_path. */
  async function stopRecording(): Promise<{ text: string; segments: RecordingSegment[]; audio_path: string | null } | null> {
    isRecording.value = false;
    store.isRecording = false;

    // Cancel pending streaming_ready wait if we stopped before model loaded.
    if (_cancelStreamingWait) {
      _cancelStreamingWait();
      _cancelStreamingWait = null;
    }

    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }

    // Stop audio processing.
    cleanupAudio();

    const res = await call<{ text: string; segments: RecordingSegment[]; audio_path: string | null }>("stop_streaming");
    if (res.success && res.data) {
      return {
        text: res.data.text ?? "",
        segments: res.data.segments ?? [],
        audio_path: res.data.audio_path ?? null,
      };
    }

    store.showToast(res.error ?? "Failed to finalize recording", "error");
    return null;
  }

  /** Format seconds as MM:SS. */
  function formatTime(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  }

  /** Auto-stop on component unmount. */
  onBeforeUnmount(async () => {
    if (isRecording.value) {
      await stopRecording();
    }
  });

  return {
    isRecording,
    isLoadingModel,
    elapsedTime,
    isSupported,
    startRecording,
    stopRecording,
    formatTime,
  };
}
