- 新增对sherpa-onnx-cohere-transcribe-14-lang-int8-2026-04-01的支持

  - 解决方案：已完成

- 语言选择没有正确配置

  - 比如我切换到了Chinese，但是传入的参数仍然是auto，示例：
  - 01:19:12 [INFO] py.asr: Using Cohere Transcribe offline model (dir: sherpa-onnx-cohere-transcribe-14-lang-int8-2026-04-01, lang: auto)
    01:19:18 [INFO] __main__: Offline recognizer created on main thread and assigned
    01:19:18 [DEBUG] pywebvue.bridge: execute_task: task 53c9dc35-0b13-48ae-a946-085e5a4385b3 completed, storing result
    01:19:18 [INFO] pywebvue.bridge: Task 53c9dc35-0b13-48ae-a946-085e5a4385b3 completed: success=True
    01:19:18 [INFO] pywebvue.bridge: Cleaned up pending result for task 53c9dc35-0b13-48ae-a946-085e5a4385b3
    01:19:18 [INFO] __main__: retranscribe_record: transcribing file Q:\Git\GiteaManager\sherpanote\data\audio\recording_20260409_162151.wav
    D:\a\sherpa-onnx\sherpa-onnx\sherpa-onnx/csrc/offline-recognizer-cohere-transcribe-impl.h:DecodeStream:99 Invalid language: 'auto'. Supported values: ar, de, el, en, es, fr, it, ja, ko, nl, pl, pt, vi, zh
    D:\a\sherpa-onnx\sherpa-onnx\sherpa-onnx/csrc/offline-recognizer-cohere-transcribe-impl.h:DecodeStream:99 Invalid language: 'auto'. Supported values: ar, de, el, en, es, fr, it, ja, ko, nl, pl, pt, vi, zh
    01:19:19 [INFO] __main__: retranscribe_record: transcription done, 0 segments, saving...
    01:19:19 [INFO] __main__: retranscribe_record: complete for record 1f230d3a-354c-4d42-a282-52584900b0bf
  - 其他模型传入的参数在控制台没有打印，我怀疑也没有正确配置。而且注意到cohere不支持auto，这个模型单独默认en吧
  - 解决方案：已完成
    - 现在当 start_streaming/transcribe_file 调用 _make_asr_config() 不传参时，会使用self._config.asr.language（即用户在设置中保存的语言），而不是硬编码的 "auto"。init_model 也同步更新了，传了 language就用传的，没传就用配置中的值。

- Whisper-large的几个模型目前都是翻译后的英文输出（设置语言为中文的情况下），不知道能否设置到中文输出？

  - 发现问题：Whisper API 支持 language 和 task 参数。当前代码两个都没传，所以 language 默认 "en"，Whisper会认为音频是英语然后翻译成英语，导致中文语音被翻译成英文输出。
  - 解决方案：language: str = 'en', task: str = 'transcribe'默认设置，通过传入这两个参数设置语言

- 检查一下其他模型有没有语言设置没有上传的问题？

  - 发现问题：FunASR Nano 和 SenseVoice 都支持 language 参数但没传
  - 解决输出：现在所有支持 language 参数的模型都会传入用户设置的语言，"auto" 时传空字符串让模型自动检测。Qwen3-ASR 、Paraformer 的 API 本身不支持 language 参数，由模型内部自动处理，无需修改。

- 检查一下vad下载代码，不同的源能否妥善切换？能否在模型列表中添加一下vad以方便手动下载

  - VAD 模型列表 (SettingsView.vue)

    - 移除了 m.model_type !== 'vad' 过滤条件，VAD 现在显示在可用模型列表中，支持手动下载/删除/重下

- 在Record界面提供模型设置（模型、语言）的快速修改（区分Streaming和Offline）

  - RecordView 快速设置栏 (RecordView.vue)

    - 在标题和控制按钮之间添加了紧凑的设置行，包含：
      - Streaming 模型选择（已安装的 streaming 模型）
      - Offline 模型选择（已安装的 offline 模型）
      - Language 语言选择

    - 录音/转写进行中时自动隐藏

    - 切换后立即保存到后端配置