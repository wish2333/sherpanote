/**
 * useRecording - Microphone recording composable.
 *
 * Manages Web Audio API lifecycle: getUserMedia permission,
 * AudioContext, ScriptProcessorNode, Base64 PCM encoding,
 * and timer display. Feature-detects ScriptProcessorNode support.
 *
 * Includes:
 * - Sample rate resampling for macOS (WebKit/pywebview often ignores
 *   the requested sampleRate and uses hardware rate instead).
 * - Silence detection: warns user if no audio input for 3+ seconds.
 * - AudioContext retry logic for reliability on macOS.
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

// Silence detection thresholds.
const SILENCE_THRESHOLD = 0.01; // RMS threshold (~ -40dB)
const SILENCE_DURATION_MS = 3000; // 3 seconds of silence before warning

/** Synchronous linear interpolation resampler. */
function resampleLinear(input: Float32Array, fromRate: number, toRate: number): Float32Array {
  if (fromRate === toRate) return input;
  const duration = input.length / fromRate;
  const outputLength = Math.round(duration * toRate);
  const output = new Float32Array(outputLength);
  const step = fromRate / toRate;
  for (let i = 0; i < outputLength; i++) {
    const srcPos = i * step;
    const idx = Math.floor(srcPos);
    const frac = srcPos - idx;
    if (idx + 1 < input.length) {
      output[i] = input[idx] * (1 - frac) + input[idx + 1] * frac;
    } else {
      output[i] = input[Math.min(idx, input.length - 1)];
    }
  }
  return output;
}

/** Compute RMS (root-mean-square) of a Float32Array. */
function computeRMS(samples: Float32Array): number {
  let sum = 0;
  for (let i = 0; i < samples.length; i++) {
    sum += samples[i] * samples[i];
  }
  return Math.sqrt(sum / samples.length);
}

export function useRecording() {
  const store = useAppStore();

  const isRecording = ref(false);
  const isLoadingModel = ref(false);
  const elapsedTime = ref(0);
  const isSupported = ref(true);
  const silenceWarning = ref(false);

  // Internal refs for cleanup.
  let audioCtx: AudioContext | null = null;
  let mediaStream: MediaStream | null = null;
  let processor: ScriptProcessorNode | null = null;
  let timerInterval: ReturnType<typeof setInterval> | null = null;
  let _silenceStart: number | null = null;
  let _silenceWarned = false;

  // Cleanup handle for pending streaming_ready / streaming_error listeners.
  let _cancelStreamingWait: (() => void) | null = null;

  /** Detect ScriptProcessorNode support. */
  function checkSupport(): boolean {
    const supported =
      typeof AudioContext !== "undefined" &&
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
    _silenceStart = null;
    _silenceWarned = false;
    silenceWarning.value = false;
  }

  /** Start microphone recording and streaming to backend. */
  async function startRecording(): Promise<boolean> {
    if (!checkSupport()) {
      store.showToast("Web Audio API not supported in this environment", "error");
      return false;
    }

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        const isMac = navigator.userAgent.includes("Mac") || navigator.platform.includes("Mac");
        if (isMac) {
          store.showToast(
            "macOS requires NSMicrophoneUsageDescription in Info.plist for microphone access. " +
              "Please rebuild the app with the updated app.spec.",
            "error",
          );
        } else {
          store.showToast(
            "Microphone access requires a secure context (HTTPS or localhost).",
            "error",
          );
        }
        return false;
      }

      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
        },
      });

      // Create AudioContext with retry logic.
      // On macOS (WebKit/pywebview), AudioContext often starts suspended.
      let actualSampleRate = 16000;
      for (let attempt = 0; attempt < 3; attempt++) {
        if (audioCtx) {
          audioCtx.close();
        }
        audioCtx = new AudioContext({ sampleRate: 16000 });
        if (audioCtx.state === "suspended") {
          await audioCtx.resume();
        }
        if (audioCtx.state === "running") {
          break;
        }
        if (attempt < 2) {
          await new Promise((r) => setTimeout(r, 200));
        }
      }
      if (!audioCtx || audioCtx.state !== "running") {
        throw new Error(`AudioContext not running. Check microphone permissions.`);
      }

      actualSampleRate = audioCtx.sampleRate;
      const source = audioCtx.createMediaStreamSource(mediaStream);
      processor = audioCtx.createScriptProcessor(4096, 1, 1);

      let streamingReady = false;
      let cancelled = false;

      // Audio chunks are captured immediately but only sent once the
      // backend model is loaded (streaming_ready). Early chunks are
      // discarded -- this avoids blocking the pywebview main thread.
      processor.onaudioprocess = (e) => {
        if (!streamingReady) return;
        const rawAudio = e.inputBuffer.getChannelData(0);

        // Silence detection: monitor RMS of raw input audio.
        const rms = computeRMS(rawAudio);
        if (rms < SILENCE_THRESHOLD) {
          if (_silenceStart === null) {
            _silenceStart = Date.now();
          } else if (!_silenceWarned && Date.now() - _silenceStart > SILENCE_DURATION_MS) {
            silenceWarning.value = true;
            _silenceWarned = true;
          }
        } else {
          _silenceStart = null;
          _silenceWarned = false;
          silenceWarning.value = false;
        }

        // Resample if the actual sample rate differs from 16000Hz.
        const audioData =
          actualSampleRate !== 16000
            ? resampleLinear(rawAudio, actualSampleRate, 16000)
            : rawAudio;

        const base64 = float32ToBase64(audioData);
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
    silenceWarning,
    startRecording,
    stopRecording,
    formatTime,
  };
}
