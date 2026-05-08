/** Composable for audio playback controls. */

import { ref, type Ref } from "vue";
import { useAppStore } from "../stores/appStore";
import type { Segment } from "../types";

export function useAudioPlayback(
  audioRef: Ref<HTMLAudioElement | null>,
  getSegments: () => Segment[],
) {
  const store = useAppStore();

  const isPlaying = ref(false);
  const audioCurrentTime = ref(0);
  const audioDuration = ref(0);
  const audioVolume = ref(1);
  const isMuted = ref(false);

  function onTimeUpdate() {
    if (!audioRef.value) return;
    audioCurrentTime.value = audioRef.value.currentTime;
    const current = audioRef.value.currentTime;
    const segments = getSegments();
    const active = segments.find(
      (s) => s.start_time <= current && s.end_time > current,
    );
    store.activeSegmentIndex = active?.index ?? -1;
  }

  function onLoadedMetadata() {
    if (audioRef.value) {
      audioDuration.value = audioRef.value.duration;
    }
  }

  function togglePlayback() {
    if (!audioRef.value) return;
    if (isPlaying.value) {
      audioRef.value.pause();
    } else {
      audioRef.value.play();
    }
    isPlaying.value = !isPlaying.value;
  }

  function toggleMute() {
    if (!audioRef.value) return;
    isMuted.value = !isMuted.value;
    audioRef.value.muted = isMuted.value;
  }

  function onVolumeChange(value: number) {
    audioVolume.value = value;
    if (!audioRef.value) return;
    audioRef.value.volume = value;
    if (value > 0 && isMuted.value) {
      isMuted.value = false;
      audioRef.value.muted = false;
    }
  }

  function seekToSegment(segment: Segment) {
    if (!audioRef.value) return;
    audioRef.value.currentTime = segment.start_time;
    audioRef.value.play();
    isPlaying.value = true;
  }

  function formatAudioTime(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  }

  return {
    isPlaying,
    audioCurrentTime,
    audioDuration,
    audioVolume,
    isMuted,
    onTimeUpdate,
    onLoadedMetadata,
    togglePlayback,
    toggleMute,
    onVolumeChange,
    seekToSegment,
    formatAudioTime,
  };
}
