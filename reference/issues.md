## dev-2.0.1-pre1

### Issues

- 研究目前带时间戳的转录结果的显示逻辑，应该是没有音频就不显示，但是是否每一个转录记录保存到了数据库中？srt导出时是否能带上导出？
- 目前OCR界面中的添加按钮点击后无效（请参考录音/转录界面修改）
- ASR设置模型管理界面中，点击浏览模型目录按钮切换模型目录之后需要重进设置页面才生效，，需要修改为用浏览按钮修改模型目录之后立刻刷新界面（考虑到还有输入修改的逻辑，需要区分，输入修改的，需要点击确认修改按钮才生效并刷新界面）

### 解决方案

```
修复完成。问题是 pywebview 版本不支持 allows_multiple_selection 关键字参数。现在用 try/except TypeError
  做了兼容处理，不支持时回退到不带该参数的调用（即单选模式）。                            

  三个任务的总结                                                                                                        
   
  ┌─────────────────────┬────────┬──────────────────────────────────────────────────────────────────────────────────┐   
  │        任务         │  状态  │                                       修改                                       │ 
  ├─────────────────────┼────────┼──────────────────────────────────────────────────────────────────────────────────┤   
  │ 1. 转录时间戳研究   │ 已完成 │ 无需修改 — 所有转录记录都保存到 SQLite，segments_json 包含完整时间戳，SRT 导出带 │ 
  │                     │        │  HH:MM:SS,mmm --> HH:MM:SS,mmm 格式                                              │   
  ├─────────────────────┼────────┼──────────────────────────────────────────────────────────────────────────────────┤   
  │                     │        │ 根因: create_file_dialog() 的 allows_multiple_selection 参数不被当前 pywebview   │
  │ 2. OCR 添加按钮无效 │ 已修复 │ 版本支持。修复: main.py 添加 TypeError 兼容回退；OcrView.vue 添加 try/catch 和   │   
  │                     │        │ toast 错误反馈                                                                   │ 
  ├─────────────────────┼────────┼──────────────────────────────────────────────────────────────────────────────────┤   
  │ 3.                  │ 已修复 │ 根因: saveConfig() 未 await 且未调用 loadModels()。修复: SettingsView.vue 的     │ 
  │ 模型目录浏览不刷新  │        │ handlePickDirectory() 改为 await saveConfig() + await loadModels()               │   
  └─────────────────────┴────────┴──────────────────────────────────────────────────────────────────────────────────┘

```

### 📝 Commit Message

```
fix(ocr): 修复添加按钮点击无效问题

- 解决pywebview版本不支持allows_multiple_selection参数的兼容性问题
- 添加TypeError兼容回退和错误反馈toast
```

### 🚀 Release Notes

```
## 2.0.1-pre1 - 问题修复与功能验证

### ✨ 新增
- 确认转录系统完整保存时间戳信息，SRT导出支持精确格式

### 🐛 修复
- 修复OCR界面添加按钮点击无响应问题
- 修复模型目录浏览后不立即刷新的界面问题
```

## dev-2.0.1-pre2

### Feature

- 优化OCR记录的命名：为“OCR-{单个文件名}”或“OCR-{PDF文件名}”或“OCR-{多个文件连续处理中第一个文件名}”

### summary of changes:

```
Modified: main.py - ocr_process method title logic
     
New naming behavior (when user doesn't provide custom title):
     
┌───────────────────────────────────┬─────────────────────────┬────────────────────────┐
│             Scenario              │        Old Name         │        New Name        │
├───────────────────────────────────┼─────────────────────────┼────────────────────────┤
│ Single image                      │ filename                │ OCR-filename           │
├───────────────────────────────────┼─────────────────────────┼────────────────────────┤
│ Single PDF (multi-page)           │ pdfname (per page)      │ OCR-pdfname (per page) │
├───────────────────────────────────┼─────────────────────────┼────────────────────────┤
│ Batch, multiple files, 1st file   │ filename_1 / filename   │ OCR-first_filename     │
├───────────────────────────────────┼─────────────────────────┼────────────────────────┤
│ Batch, multiple files, subsequent │ filename_2 / filename_3 │ OCR-each_filename      │
├───────────────────────────────────┼─────────────────────────┼────────────────────────┤
│ Single/Sequential mode            │ OCR                     │ OCR-first_filename     │
└───────────────────────────────────┴─────────────────────────┴────────────────────────┘
     
If the user provides a custom title in the input field, it continues to use that title directly.
     
Manual test cases:
     
1. Drop a single image (e.g., receipt.jpg) in batch mode -> record title should be OCR-receipt
2. Drop a PDF (e.g., report.pdf) in batch mode -> each page record titled OCR-report
3. Drop multiple images in batch mode without custom title -> first record OCR-first_image, rest OCR-each_image
4. Drop a single image in single mode -> record title OCR-imagename
5. Drop files with custom title "My Title" -> all records use My Title as before
```

### 📝 Commit Message

```
feat(ocr): 优化OCR记录命名规则添加OCR前缀

- 更新OCR记录命名逻辑，自动添加"OCR-"前缀
- 支持单文件、PDF和多文件批处理的统一命名规范
- 保留用户自定义标题功能不变
```

### 🚀 Release Notes

```
## 2026-04-21 - OCR记录命名优化

### ✨ 新增
- OCR记录现在自动添加"OCR-"前缀，提高文件识别度
- 统一了单文件、PDF和多文件批处理的命名规则，使记录更易识别

### 💡 改进
- 保留了您自定义标题的功能，如之前输入标题仍将直接使用
```
