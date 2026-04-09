### 问题

- 目前ASR模型镜像源下载功能未开放，选择镜像源仍会跳会Github源，默认源有Github仓库https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models，镜像源有魔搭社区https://www.modelscope.cn/models/zhaochaoqun/sherpa-onnx-asr-models/files（只有阿里系的一些模型），huggingfacehttps://huggingface.co/csukuangfj/models（和其他非ASR模型混在一起），huggingface还能用hf-mirror镜像。你看看怎么处理如何从不同镜像源获取模型的问题。可选择提供以下选项：
  - Hugging Face：使用 `huggingface_hub` 库
    - Hugging Face源
    - hf-mirror：设置 `endpoint` 为 `https://hf-mirror.com`
  - Github
    - Github源：https://k2-fsa.github.io/sherpa/onnx/lazarus/download-generated-subtitles.html
    - 如果不想挂代理只能需要用经常更新域名的源，需要从https://ghproxy.link/网站中获取当前可用的源。可以提供一个输入栏并提示用户获取可用域名填入
  - 魔搭社区：只提供阿里系模型下载
- 此外，我们设置界面提供的模型都太老了。而新模型太多了，能不能选择一些优质的模型可供选择，你需要评估一下，还有各种模型的各种功能如何与我们的代码整合（对于不同的模型的不同功能，如何更新和升级代码）我手动筛选一些合适的模型：
  - 优先魔搭也可下载的：
    - 非流式：Qwen3-ASR-0.6B.tar.bz2、Qwen3-ASR-1.7B.tar.bz2
    - 支持低延迟实时撰写：sherpa-onnx-funasr-nano-int8-2025-12-30.tar.bz2
    - 标明支持流式转写：sherpa-onnx-streaming-paraformer-bilingual-zh-en.tar.bz2、sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20.tar.bz2
  - 从Github源挑选的，应该在HuggingFace上也有
    - [sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25.tar.bz2](https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25.tar.bz2)——sha256:393f8a14e2f5fb96746aaab342997a40641001fbd5bf9592a080a8329178ee96
    - [sherpa-onnx-sense-voice-funasr-nano-2025-12-17.tar.bz2](https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-sense-voice-funasr-nano-2025-12-17.tar.bz2)——sha256:426db3bf7d2cc0d083089e57054033682726041a9de0cf51aaf98723b9908681
    - [sherpa-onnx-whisper-distil-large-v3.5.tar.bz2](https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-distil-large-v3.5.tar.bz2)——sha256:ec874c7346d24ef8063e05430ede616d66d80a410360283099d0bdf659187b1d
    - [sherpa-onnx-whisper-distil-large-v3.tar.bz2](https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-distil-large-v3.tar.bz2)——sha256:3c13a06664e66708180baf98d17a35a7bc59b3f0f926c0e300445ce0789b5a73
    - [sherpa-onnx-streaming-zipformer-small-ru-vosk-2025-08-16.tar.bz2](https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-zipformer-small-ru-vosk-2025-08-16.tar.bz2)——sha256:cc2e99ed0c67cae8801170e7b7539b4cac00b716076af86f974bf5b888d9370c
  - 专门支持生成字幕的https://k2-fsa.github.io/sherpa/onnx/lazarus/download-generated-subtitles-cn.html
    - sherpa-onnx-x.y.z-generate-subtitles-windows-x64-**sense_voice**-zh_en_ko_ja_yue
    - sherpa-onnx-x.y.z-generate-subtitles-windows-x64-**paraformer_2023_09_14-**-zh_en
  - silero_vad
    - [silero_vad.onnx](https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx)——sha256:9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6
- 在设置界面可以直接提供上面提到的一些链接，提示用户自行下载并配置。
- 添加系统代理设置：不使用代理/使用系统代理/自定义代理

###   Changes Summary

  Backend (Python)

  py/config.py
  - Replaced mirror_url: str | None with download_source, custom_ghproxy_domain, proxy_mode, proxy_url
  - Added migration logic in from_dict() for old configs

  py/model_registry.py (major rewrite)
  - New ModelEntry fields: sha256, sources, hf_filename, modelscope_file_path, manual_download_links
  - Updated model catalog with 8 ASR models + 2 tool entries
  - New get_download_url(model, source, ghproxy_domain) dispatcher supporting 5 sources
  - New model_to_dict() serializer for frontend

  py/model_manager.py (major rewrite)
  - Added proxy support (_build_opener, proxy_mode/proxy_url params)
  - Added download_from_huggingface() using huggingface_hub library
  - Added download_model() unified dispatcher
  - Updated ModelInstaller with new source/proxy params
  - Updated list_installed_models() to scan all subdirectories (not just known models)

  py/asr.py
  - Added Qwen3-ASR detection in _create_offline_recognizer() (experimental, falls back gracefully)
  - Updated fallback lists in _find_streaming_model() and _find_offline_model() with new models

  main.py
  - Updated bridge to pass new config fields to ModelInstaller
  - Updated list_available_models() to use model_to_dict()
  - Added get_download_links() exposed method

  pyproject.toml
  - Added huggingface_hub>=0.20.0 dependency

  Frontend (TypeScript/Vue)

  frontend/src/types.ts
  - Updated AsrConfig: replaced mirror_url with new fields
  - Updated ModelEntry: added sources, manual_download_links

  frontend/src/stores/appStore.ts
  - Updated default asrConfig to match new interface

  frontend/src/types/index.ts
  - Updated stale duplicate AsrConfig interface

  frontend/src/bridge.ts
  - Added getDownloadLinks() helper

  frontend/src/views/SettingsView.vue
  - Replaced GitHub/Mirror dropdown with 5-source selector (GH, HF, HF-Mirror, GH-Proxy, ModelScope)
  - Added GitHub Proxy domain input
  - Added proxy settings (None/System/Custom)
  - Added source availability badges on models
  - Grays out unavailable models on current source
  - Added "Tools" section for subtitle generation links

  Manual Testing Checklist

  - Config migration: old mirror_url loads without error
  - Download from GitHub works (test with silero_vad or paraformer-zh-small)
  - Download from HuggingFace / HF-Mirror works
  - Proxy settings (none/system/custom) affect download behavior
  - Qwen3-ASR model downloads and transcribes (experimental)
  - Old installed models still appear in "Installed Models"
  - Source badges show correctly; unavailable models grayed out
  - Tools section shows subtitle generation links
  - Download cancel + resume still works

### 修改后问题

- 原本的模型检测功能错误了，没有正确识别到模型。我猜测是现在的代码只能识别预设的模型，这是不对的，应该要支持所有模型，不然用户也没法自行手动下载模型配置进来啊。但是如何sherpa-onnx是如何去问流式与非流式模型的呢？
- FunASR-nano和Qwen3-ASR不能直接使用，暂时删除对应的列表吧。
- Tools那一栏改成Related Links放到Installed Models后面，把几个模型源的链接加入到里面
- sherpa-onnx-whisper-distil-large-v3.5的各个文件有distil-large-v3.5-的前缀，如distil-large-v3.5-tokens.txt，需要添加带前缀的模型的支持（不止局限于这个前缀）
- Auto Punctuation和Auto Al Processing这两栏挪到General页面里吧

###   Changes

  Fixes Applied

  1. Model detection - supports arbitrary models (py/asr.py)
  - Added _find_file() helper that matches files by suffix pattern (e.g. distil-large-v3.5-tokens.txt matches
    tokens.txt)
  - Added _has_model_files() to check if any directory looks like a valid model
  - _find_streaming_model(): removed hardcoded candidate list, now scans all subdirectories for model files
  - _find_offline_model(): same - scans all subdirectories, only skips known streaming models
  - _create_online_recognizer(): uses _find_file() for encoder/decoder/joiner/tokens
  - _create_offline_recognizer(): uses _find_file() for tokens/model/encoder/decoder
  - Removed Qwen3-ASR detection code

  2. Removed non-working models (py/model_registry.py)
  - Removed sherpa-onnx-funasr-nano-int8-2025-12-30 (streaming)
  - Removed sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25 (offline)

  3. Related Links (frontend/src/views/SettingsView.vue)
  - Moved from before Installed Models to after it
  - Renamed "Tools" to "Related Links"
  - Added model source links: GitHub Releases, HuggingFace, ModelScope, GitHub Proxy List
  - Subtitle generation tools are shown at the top of this section

  4. Prefixed file support (py/model_manager.py)
  - validate_model() now uses _find_file() with suffix matching
  - Unknown models are validated by checking for tokens.txt + any .onnx file (both with prefix support)

  Manual Testing Checklist

  - Existing installed models (from old versions) are still detected
  - Manually downloaded models placed in the models directory are detected
  - whisper-distil-large-v3.5 with prefixed files (distil-large-v3.5-tokens.txt, etc.) loads correctly
  - Related Links section appears after Installed Models
  - All Related Links URLs open correctly in browser
  - Download from each source still works

  py/model_registry.py - Added two models:
  - sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25 (offline, zh/en/ja/ko, 390MB, SenseVoice API)
  - sherpa-onnx-streaming-zipformer-small-ru-vosk-2025-08-16 (streaming, ru, 45MB, Zipformer transducer)

  py/asr.py - Qwen3-ASR detection:
  - Extended SenseVoice detection to match "qwen3" in directory name, so Qwen3-ASR models use from_sense_voice() API

  frontend/src/views/SettingsView.vue:
  - Auto Punctuation + Auto AI Processing moved from ASR tab to General tab
  - Language changed from <select> to <input> with <datalist>, allowing custom language codes while keeping suggestions
    (Auto Detect, Chinese, English)
  - GitHub Proxy hint clarified: links to ghproxy.link for finding available proxy domains, with better placeholder text

### 修改后问题

- 选了Github Proxy之后，模型列表全灰了没法点下载，应该是和Github一样的。而且好像再切换成其他下载源也仍然还是Github Proxy源，和我选择的源不同。
- ！原本的模型检测功能仍然有问题，没有正确识别到模型。我猜测是现在的代码只能识别预设的模型，这是不对的，应该要支持所有模型，不然用户也没法自行手动下载模型配置进来啊。但是如何sherpa-onnx是如何去问流式与非流式模型的呢？这个你一定要弄清楚，帮我解决这个问题。
- Whisper运行有点小问题，报错如下：
  - Task'create_offline_recognizer' failed: No
    recognized offline model files in
    Q:IGitIGiteaManagersherpanotelmodelsIsherpa-
    onnx-whisper-distil-large-v3.5. Expected
    model.onnx (SenseVoice/Paraformer) or
    encoder.onnx + decoder.onnx (Whisper).

  Problem 1: File matching broken for prefixed+quantized filenames

  The whisper model files are distil-large-v3.5-encoder.int8.onnx, distil-large-v3.5-decoder.int8.onnx,
  distil-large-v3.5-tokens.txt. The old endswith("encoder.onnx") failed because the file ends with int8.onnx, not
  encoder.onnx.

  Fix: Replaced simple endswith with _match_model_file() that parses filenames into (core_name, quantization, extension)
   components and matches accordingly. Handles all combinations: exact, prefixed, quantized, and prefixed+quantized.
  Applied to both py/asr.py and py/model_manager.py.

  Problem 2: Streaming vs offline model detection

  The old code used _has_model_files() which just checked for any .onnx+tokens.txt -- this meant both
  _find_streaming_model() and _find_offline_model() could return the same directory (e.g., whisper would be picked as
  streaming too).

  Fix: Added _classify_model_dir() with file-based heuristics:
  - joiner.onnx present -> streaming (Transducer/Zipformer)
  - model.onnx without encoder -> offline (Paraformer/SenseVoice)
  - encoder + decoder only -> ambiguous, use directory name ("whisper"=offline, "streaming"/"zipformer"=streaming,
    default=offline)

  Manual testing checklist:
  - Whisper distil-large-v3.5 offline transcription (was broken, should now work)
  - Streaming paraformer still works for real-time recognition
  - Offline paraformer still works for file transcription
  - A user-downloaded model placed in the model directory is detected and classified correctly

### 检测与模型适配问题

把以下模型添加到列表里

仅魔搭社区：

- 非流式：Qwen3-ASR-0.6B.tar.bz2、Qwen3-ASR-1.7B.tar.bz2

全部源：

- sherpa-onnx-funasr-nano-int8-2025-12-30.tar.bz2

然后我从Sherpa-onnx官网找到了一些适配的示例，你根据示例、我当前代码和models文件夹里下载下来的模型情况，修复一下代码的适配问题。

#### Whisper适配示例

```
python3 ./test.py \
    --encoder ./large-v3-encoder.onnx \
    --decoder ./large-v3-decoder.onnx \
    --tokens ./large-v3-tokens.txt \
    ./0.wav
```

#### sherpa-onnx-funasr-nano-int8-2025-12-30适配示例

To decode the test file `./sherpa-onnx-funasr-nano-int8-2025-12-30/test_wavs/dia_hunan.wav`:

```
./build/bin/sherpa-onnx-offline \
  --funasr-nano-encoder-adaptor=./sherpa-onnx-funasr-nano-int8-2025-12-30/encoder_adaptor.int8.onnx \
  --funasr-nano-llm=./sherpa-onnx-funasr-nano-int8-2025-12-30/llm.int8.onnx \
  --funasr-nano-tokenizer=./sherpa-onnx-funasr-nano-int8-2025-12-30/Qwen3-0.6B \
  --funasr-nano-embedding=./sherpa-onnx-funasr-nano-int8-2025-12-30/embedding.int8.onnx \
  ./sherpa-onnx-funasr-nano-int8-2025-12-30/test_wavs/dia_hunan.wav
```

You should see the following output:

```
/Users/fangjun/open-source/sherpa-onnx/sherpa-onnx/csrc/parse-options.cc:Read:373 ./build/bin/sherpa-onnx-offline --funasr-nano-encoder-adaptor=./sherpa-onnx-funasr-nano-int8-2025-12-30/encoder_adaptor.int8.onnx --funasr-nano-llm=./sherpa-onnx-funasr-nano-int8-2025-12-30/llm.int8.onnx --funasr-nano-tokenizer=./sherpa-onnx-funasr-nano-int8-2025-12-30/Qwen3-0.6B --funasr-nano-embedding=./sherpa-onnx-funasr-nano-int8-2025-12-30/embedding.int8.onnx ./sherpa-onnx-funasr-nano-int8-2025-12-30/test_wavs/dia_hunan.wav 

OfflineRecognizerConfig(feat_config=FeatureExtractorConfig(sampling_rate=16000, feature_dim=80, low_freq=20, high_freq=-400, dither=0, normalize_samples=True, snip_edges=False), model_config=OfflineModelConfig(transducer=OfflineTransducerModelConfig(encoder_filename="", decoder_filename="", joiner_filename=""), paraformer=OfflineParaformerModelConfig(model=""), nemo_ctc=OfflineNemoEncDecCtcModelConfig(model=""), whisper=OfflineWhisperModelConfig(encoder="", decoder="", language="", task="transcribe", tail_paddings=-1), fire_red_asr=OfflineFireRedAsrModelConfig(encoder="", decoder=""), tdnn=OfflineTdnnModelConfig(model=""), zipformer_ctc=OfflineZipformerCtcModelConfig(model=""), wenet_ctc=OfflineWenetCtcModelConfig(model=""), sense_voice=OfflineSenseVoiceModelConfig(model="", language="auto", use_itn=False), moonshine=OfflineMoonshineModelConfig(preprocessor="", encoder="", uncached_decoder="", cached_decoder=""), dolphin=OfflineDolphinModelConfig(model=""), canary=OfflineCanaryModelConfig(encoder="", decoder="", src_lang="", tgt_lang="", use_pnc=True), omnilingual=OfflineOmnilingualAsrCtcModelConfig(model=""), funasr_nano=OfflineFunASRNanoModelConfig(encoder_adaptor="./sherpa-onnx-funasr-nano-int8-2025-12-30/encoder_adaptor.int8.onnx", llm="./sherpa-onnx-funasr-nano-int8-2025-12-30/llm.int8.onnx", embedding="./sherpa-onnx-funasr-nano-int8-2025-12-30/embedding.int8.onnx", tokenizer="./sherpa-onnx-funasr-nano-int8-2025-12-30/Qwen3-0.6B", system_prompt="You are a helpful assistant.", user_prompt="语音转写：", max_new_tokens=512, temperature=1e-06, top_p=0.8, seed=42), medasr=OfflineMedAsrCtcModelConfig(model=""), telespeech_ctc="", tokens="", num_threads=2, debug=False, provider="cpu", model_type="", modeling_unit="cjkchar", bpe_vocab=""), lm_config=OfflineLMConfig(model="", scale=0.5, lodr_scale=0.01, lodr_fst="", lodr_backoff_id=-1), ctc_fst_decoder_config=OfflineCtcFstDecoderConfig(graph="", max_active=3000), decoding_method="greedy_search", max_active_paths=4, hotwords_file="", hotwords_score=1.5, blank_penalty=0, rule_fsts="", rule_fars="", hr=HomophoneReplacerConfig(lexicon="", rule_fsts=""))
Creating recognizer ...
recognizer created in 1.641 s
Started
Done!

./sherpa-onnx-funasr-nano-int8-2025-12-30/test_wavs/dia_hunan.wav
{"lang": "", "emotion": "", "event": "", "text": "他总的来讲，孙膑对本怀的理解、文样比庞涓略胜一筹。", "timestamps": [0.00, 0.33, 0.66, 1.00, 1.33, 1.66, 1.99, 2.32, 2.66, 2.99, 3.32, 3.65, 3.98, 4.31, 4.65, 4.98, 5.31, 5.64, 5.97, 6.31, 6.64], "durations": [], "tokens":["他", "总的", "来讲", "，", "孙", "膑", "对", "本", "怀", "的理解", "、", "文", "样", "比", "庞", "涓", "略", "胜", "一", "筹", "。"], "ys_log_probs": [], "words": []}
----
num threads: 2
decoding method: greedy_search
Elapsed seconds: 1.154 s
Real time factor (RTF): 1.154 / 7.012 = 0.165
```

#### sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25适配示例

##### Real-time/Streaming Speech recognition from a microphone with VAD[](https://k2-fsa.github.io/sherpa/onnx/qwen3-asr/pretrained.html#real-time-streaming-speech-recognition-from-a-microphone-with-vad)

```
wget https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx

./build/bin/sherpa-onnx-vad-microphone-simulated-streaming-asr \
  --silero-vad-model=./silero_vad.onnx \
  --qwen3-asr-conv-frontend=./sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25/conv_frontend.onnx \
  --qwen3-asr-encoder=./sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25/encoder.int8.onnx \
  --qwen3-asr-decoder=./sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25/decoder.int8.onnx \
  --qwen3-asr-tokenizer=./sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25/tokenizer \
  --qwen3-asr-max-new-tokens=512 \
  --num-threads=3
```

##### Speech recognition from a microphone[](https://k2-fsa.github.io/sherpa/onnx/qwen3-asr/pretrained.html#speech-recognition-from-a-microphone)

```
./build/bin/sherpa-onnx-microphone-offline \
  --tokens=./sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/tokens.txt \
  --qwen3-asr-conv-frontend=./sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25/conv_frontend.onnx \
  --qwen3-asr-encoder=./sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25/encoder.int8.onnx \
  --qwen3-asr-decoder=./sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25/decoder.int8.onnx \
  --qwen3-asr-tokenizer=./sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25/tokenizer \
  --qwen3-asr-max-new-tokens=512 \
  --num-threads=3
```

##### Speech recognition from a microphone with VAD[](https://k2-fsa.github.io/sherpa/onnx/qwen3-asr/pretrained.html#speech-recognition-from-a-microphone-with-vad)

```
wget https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx

./build/bin/sherpa-onnx-vad-microphone-offline-asr \
  --silero-vad-model=./silero_vad.onnx \
  --qwen3-asr-conv-frontend=./sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25/conv_frontend.onnx \
  --qwen3-asr-encoder=./sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25/encoder.int8.onnx \
  --qwen3-asr-decoder=./sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25/decoder.int8.onnx \
  --qwen3-asr-tokenizer=./sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25/tokenizer \
  --qwen3-asr-max-new-tokens=512 \
  --num-threads=3
```

##### Decode a long audio file with VAD (Example 1/2, English)[](https://k2-fsa.github.io/sherpa/onnx/qwen3-asr/pretrained.html#decode-a-long-audio-file-with-vad-example-1-2-english)

The following examples show how to decode a very long audio file with the help of VAD.

```
wget https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx
wget https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/Obama.wav

./build/bin/sherpa-onnx-vad-with-offline-asr \
  --silero-vad-model=./silero_vad.onnx \
  --silero-vad-threshold=0.2 \
  --silero-vad-min-speech-duration=0.2 \
  --qwen3-asr-conv-frontend=./sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25/conv_frontend.onnx \
  --qwen3-asr-encoder=./sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25/encoder.int8.onnx \
  --qwen3-asr-decoder=./sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25/decoder.int8.onnx \
  --qwen3-asr-tokenizer=./sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25/tokenizer \
  --qwen3-asr-max-new-tokens=512 \
  --num-threads=2 \
  ./Obama.wav
```

### 其他问题

- 前端问题：虽然Language可以手动输入了，但是下拉选项呢？不见了，只剩auto了
- hf配置怀疑有误，感觉每个模型都下载不了
- 流式模型会闪退可能是适配问题，先根据上方指导进行修改
- 目前models里两个streaming模型只有zipformer会被检测到，不知道什么情况

###   Changes Summary

  py/model_registry.py

  - 新增 hf_repo_id 字段，支持按模型独立配置 HF repo
  - HF repo 从旧的 monolithic csukuangfj/models 改为 per-model csukuangfj/{model_id}
  - 修复 Qwen3-ASR required_files（从错误的 tokens.txt, model.int8.onnx 改为 conv_frontend.onnx, encoder.int8.onnx,
    decoder.int8.onnx）
  - 新增 3 个模型: Qwen3-ASR 0.6B (ModelScope), Qwen3-ASR 1.7B (ModelScope), FunASR Nano Int8
  - silero_vad 使用专用 hf_repo_id="csukuangfj/vad"

  py/model_manager.py

  - download_from_huggingface() 使用 model.hf_repo_id or f"csukuangfj/{model.model_id}" 替代硬编码

  py/asr.py

  - _classify_model_dir: 新增 conv_frontend.onnx(Qwen3-ASR)、encoder_adaptor.onnx/llm.onnx(FunASR Nano) 检测；修复同时有
      model.onnx 和 encoder.onnx 的模型返回 None 的问题
  - _create_offline_recognizer: 新增 Qwen3-ASR (from_qwen3_asr) 和 FunASR Nano (from_funasr_nano) 路径，优先级最高；移除
      "qwen3" 的 SenseVoice 误判
  - _create_online_recognizer: 修复优先检测 joiner.onnx 判断 Zipformer，避免 Zipformer 被误判为 Paraformer
  - 新增 _find_tokenizer_dir 辅助方法
  - Qwen3-ASR 添加 monkey-patch 修复 sherpa-onnx 的 hotwords 参数 bug

  frontend/src/views/SettingsView.vue

  - Language 下拉选项从 3 个扩充到 12 个 (ja, ko, yue, de, fr, es, ru, it, pt)

  Manual Testing Checklist

  - HuggingFace / HF-Mirror 下载 silero_vad 或其他模型成功
  - FunASR Nano 模型检测和文件转录正常
  - Qwen3-ASR 模型检测和文件转录正常
  - Whisper distil-large-v3.5 文件转录正常（前缀文件名匹配）
  - 两个流式模型均能正常识别
  - Language 下拉显示 12 种语言选项
  - 新模型（Qwen3-ASR 0.6B/1.7B ModelScope, FunASR Nano）出现在可用模型列表中

### 修改后问题

- 模型识别还有问题，sherpa-onnx-streaming-paraformer-trilingual-zh-cantonese-en这个流式模型，和sherpa-onnx-paraformer-trilingual-zh-cantonese-en这个离线模型都没有识别到。而且sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25应该也是可以进行流式的（两用）
- 有时候在Audio Files删文件时显示expected str, bytes or os.PathLike object, not NoneType，不过刷新一下记录消失了，文件也删了
- Language还是点不开下拉选项栏

###   Changes Summary

  py/model_manager.py

  - list_installed_models: 对未知模型使用 SherpaASR._classify_model_dir() 推断 model_type（不再返回 "unknown"）
  - VAD 条目补上 model_type: "vad"

  frontend/src/views/SettingsView.vue

  - installedStreamingModels/installedOfflineModels: 直接用 m.model_type 过滤，不再查 registry
  - Activate 按钮同理用 model.model_type 判断
  - Language 从 <input> + <datalist> 改为 <select> + Custom 输入框，下拉选项可正常展开
  - loadConfig 时检测自定义 language 值
  - saveConfig 时将 "__custom__" 解析为实际值

  main.py

  - delete_audio_file: 修复 audio_path 为 None 时 Path(None) 报错

  关于 Qwen3-ASR 流式

  当前安装的 sherpa-onnx 没有 OnlineQwen3ASRModelConfig 和 OnlineRecognizer.from_qwen3_asr。CLI 工具的 "streaming"
  示例实际上是 VAD 分段 + offline 模型的方式，不是真正的流式。目前 Qwen3-ASR 只支持离线转写。

  Manual Testing Checklist

  - streaming-paraformer-trilingual-zh-cantonese-en 出现在 Installed Models 中（Streaming 分类）
  - paraformer-trilingual-zh-cantonese-en 出现在 Installed Models 中（Offline 分类）
  - Language 下拉点击可展开所有 12 个选项
  - Language 选 Custom 后可输入自定义值并保存
  - 删除 Audio Files 中的文件不再报 NoneType 错误