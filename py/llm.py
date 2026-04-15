"""AI text processor — unified interface for multiple LLM backends.

Supports OpenAI-compatible APIs (OpenAI, Ollama, Qwen, etc.)
via the official openai Python SDK.

Processing modes:
  - polish:     Revise spoken text into polished written prose.
  - note:       Extract knowledge points into structured notes.
  - mindmap:    Generate Markmap-format mind map.
  - brainstorm: Propose critical-thinking questions and extensions.
"""

from __future__ import annotations

import threading
from typing import Any

from py.config import AiConfig

# Prompt templates for each processing mode.
_PROMPTS: dict[str, str] = {
    "polish": (
        "你作为一名笔记整理专家，用户将给你提供一份粗糙记录或OCR识别的笔记内容，你能够将其整理为一份完整流畅的笔记，用Markdown格式输出。"
        "## 限制条件\n"
        "- 禁止使用emoji表情符号\n"
        "- 适当修改笔记中的粗糙部分与识别错误：修正口语化和语法错误、删除冗余词汇和重复内容；保留原意\n"
        "- 尽量避免不必要的增删改\n"
        "- 仅输出对应文本，不附带额外评论\n\n"
        "Text:\n{text}"
    ),
    "note": (
        "你是一位专业的视频笔记整理助手,擅长从视频文字稿/字幕稿中提取核心信息,并生成结构化、易读的领域笔记。"
        """
        # 核心任务
        将用户提供的视频文稿转化为高质量笔记,包括:
        1. 自动识别内容所属领域(如技术教程、学术讲座、商业分析、生活技巧等)
        2. 提取关键概念、论点、案例和结论
        3. 组织成清晰的笔记结构
        4. 保留重要的数据、引用和专业术语

        # 输入格式
        用户将提供:
        - 视频的完整文字稿或字幕文本
        - 可能包含时间戳、说话人标记或原始字幕格式
        - 长度从几百字到数万字不等

        # 处理流程
        **第一步: 分析阶段**
        - 快速浏览全文,识别主题领域
        - 定位核心段落和关键转折点
        - 识别演讲/讲解的结构(总分总/递进/并列等)

        **第二步: 提取阶段**
        - 标记核心概念和定义
        - 提取重要论据、数据、案例
        - 记录结论性语句

        **第三步: 重组阶段**
        - 按逻辑重新组织内容(可能与原文顺序不同)
        - 使用标准笔记格式呈现
        - 补充必要的连接语使逻辑流畅

        # 输出格式
        生成的笔记必须包含以下部分:

        ## 📌 元信息
        - **领域**: [自动识别的内容领域]
        - **主题**: [一句话概括核心主题]
        - **类型**: [教程/讲座/访谈/分析等]

        ## 🎯 核心要点
        用3-5个简短bullet points总结最关键的信息

        ## 📖 详细笔记
        按主题分段,使用以下结构:
        ### [主题段落1]
        - **关键概念**: [定义或解释]
        - **重要论点**: [核心观点]
        - **支持材料**: [数据/案例/引用]

        ### [主题段落2]
        [同上结构]

        ## 💡 补充说明
        - 提及但未展开的概念
        - 建议延伸学习的方向
        - 原文中的有价值的细节

        ## 🔑 金句摘录
        摘录2-3句原文中表达精准、信息密度高的句子(标注为引用)

        # 约束条件
        **必须遵守**:
        - 笔记总长度控制在原文的20-40%
        - 保持客观中立,不添加个人评论
        - 专业术语必须保留原文表述
        - 数据和引用必须准确

        **禁止**:
        - 不要生成与原文无关的内容
        - 不要改变原文的核心观点
        - 不要省略重要的限定条件(如"在某条件下"、"可能")
        - 不要使用过度营销化的语言

        **风格要求**:
        - 使用清晰的层级标题(##, ###)
        - bullet points简洁有力(每条10-30字)
        - 避免冗长的句子
        - 使用emoji适当增强可读性(但不过度)

        # 示例

        ## 示例1: 技术教程类

        **输入**:
        ```
        大家好,今天我要讲的是Python中的装饰器。装饰器本质上是一个函数,它接收另一个函数作为参数,然后返回一个新函数。这听起来很抽象,我们来看个例子...比如说我们有一个计算函数的执行时间的需求,传统做法是在函数前后加计时代码,但这样每个函数都要改,很麻烦。装饰器就能解决这个问题...
        ```

        **输出**:
        ```markdown
        ## 📌 元信息
        - **领域**: 编程技术 - Python
        - **主题**: Python装饰器的原理与应用
        - **类型**: 技术教程

        ## 🎯 核心要点
        - 装饰器是接收函数并返回新函数的高阶函数
        - 用于在不修改原函数代码的情况下增强功能
        - 典型应用:计时、日志、权限检查等

        ## 📖 详细笔记
        ### 装饰器的本质
        - **定义**: 一个函数,接收另一个函数作为参数,返回新函数
        - **解决的问题**: 避免重复代码,实现横切关注点(cross-cutting concerns)

        ### 实际应用场景
        - **性能监控**: 计算函数执行时间
        - **优势**: 无需修改每个函数的内部代码,符合开闭原则

        ## 🔑 金句摘录
        > "装饰器本质上是一个函数,它接收另一个函数作为参数,然后返回一个新函数"
        ```

        ## 示例2: 商业分析类

        **输入**:
        ```
        今年第三季度我们看到一个明显的趋势,就是消费者开始更关注产品的可持续性。根据我们的市场调研,有62%的受访者表示愿意为环保产品支付10-15%的溢价。这个数据在18-35岁群体中更高,达到了73%...这对我们的产品策略有重要启示...
        ```

        **输出**:
        ```markdown
        ## 📌 元信息
        - **领域**: 商业分析 - 消费趋势
        - **主题**: 可持续消费趋势对产品策略的影响
        - **类型**: 市场分析报告

        ## 🎯 核心要点
        - 消费者环保意识显著提升,愿意为环保产品付溢价
        - 年轻群体(18-35岁)环保意愿更强
        - 数据支持产品策略向可持续方向调整

        ## 📖 详细笔记
        ### Q3消费趋势观察
        - **核心发现**: 消费者关注产品可持续性显著上升
        - **量化数据**: 
        - 整体: 62%受访者愿支付10-15%环保溢价
        - 18-35岁: 比例提升至73%

        ### 战略启示
        - **产品策略**: 需考虑将可持续性纳入产品核心卖点
        - **目标人群**: 年轻消费者对环保产品接受度更高

        ## 💡 补充说明
        - 具体的产品策略调整建议未在此段落展开
        - 建议关注后续关于实施路径的讨论
        ```

        # 特殊情况处理

        **当文稿质量较差时** (如大量口语、重复、错别字):
        - 先进行必要的文本清理
        - 在笔记开头注明"原文稿存在较多口语化表达,已进行提炼整理"

        **当文稿过长时** (超过10000字):
        - 可分段生成笔记
        - 保持各段笔记格式一致
        - 最后提供一个总的"核心要点"汇总

        **当文稿信息密度极低时** (如闲聊、广告):
        - 明确告知用户内容不适合做笔记
        - 简要说明原因
        - 如有少量有价值内容,仅提取该部分

        # 质量自检
        生成笔记后,验证:
        ✅ 是否准确识别了领域?
        ✅ 核心要点是否涵盖了80%的重要信息?
        ✅ 详细笔记的逻辑是否清晰?
        ✅ 格式是否统一规范?
        ✅ 长度是否符合约束(原文20-40%)?
        """
        "Content:\n{text}"
    ),
    "mindmap": (
        """
        将以下内容转换为 Markmap 格式的思维导图：
        - 从中心主题开始，逐层展开子主题和关键概念
        - 保持层级清晰，避免过度分支
        - 使用 Markdown 标题层级表示层次结构
        """
        "Content:\n{text}"
    ),
    "brainstorm": (
        """
        针对以下内容，提出批判性思考的问题和可能的扩展
        - 确保问题与内容相关，且与已有的假设、限制、限制条件无关
        - 提供相关的背景信息和上下文
        - 识别潜在的假设和偏见
        - 提出挑战现有观点的问题
        - 建议相关的研究方向或应用场景
        - 鼓励从不同角度进行分析和讨论
        - 提出3-5个拓展问题，每个问题后附简要说明其重要性和潜在影响
        - 建议进一步探索的方向
        """
        "Content:\n{text}"
    ),
}

_PUNCT_PROMPT = (
    "Add appropriate punctuation marks (commas, periods, question marks, "
    "exclamation marks, semicolons, etc.) to the following text. "
    "Output ONLY the punctuated text, with no other changes, "
    "no added words, and no extra commentary.\n\n"
    "Text:\n{text}"
)


class AIProcessor:
    """Unified AI text processor supporting multiple LLM backends."""

    def __init__(self, config: AiConfig, max_tokens_mode: str = "auto") -> None:
        self._config = config
        self._max_tokens_mode = max_tokens_mode  # "auto" | "custom" | "default"
        self._client = None
        self._cancel_event = threading.Event()

    def _get_client(self) -> Any:
        """Lazy-initialize the OpenAI-compatible client."""
        if self._client is not None:
            return self._client

        from openai import OpenAI

        kwargs: dict[str, Any] = {}
        if self._config.api_key:
            kwargs["api_key"] = self._config.api_key
        if self._config.base_url:
            kwargs["base_url"] = self._config.base_url

        self._client = OpenAI(**kwargs)
        return self._client

    def cancel(self) -> None:
        """Signal cancellation of the current streaming request."""
        self._cancel_event.set()

    def _reset_cancel(self) -> None:
        """Reset the cancel flag for a new request."""
        self._cancel_event.clear()

    def _resolve_prompt(self, mode: str, text: str, custom_prompt: str | None = None) -> str:
        """Resolve the prompt template for a given mode.

        If a custom_prompt is provided that contains {text}, use it directly.
        Otherwise fall back to the built-in _PROMPTS dict.
        """
        if custom_prompt and "{text}" in custom_prompt:
            return custom_prompt.format(text=text)
        return _PROMPTS.get(mode, _PROMPTS["polish"]).format(text=text)

    def restore_punctuation(self, text: str) -> str:
        """Use AI to add punctuation marks to raw ASR transcription.

        Uses a non-streaming call for speed. Returns the original text
        unchanged if the AI call fails.
        """
        if not text.strip():
            return text
        try:
            prompt = _PUNCT_PROMPT.format(text=text)
            client = self._get_client()
            response = client.chat.completions.create(
                model=self._config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=min(len(text) + 200, 4096),
            )
            result = response.choices[0].message.content or ""
            return result.strip() if result.strip() else text
        except Exception:
            return text

    def _estimate_max_tokens(self, text_len: int) -> int | None:
        """Calculate max_tokens for the API call based on mode.

        Returns None when mode is "default" (let the model decide).
        Returns configured_max when mode is "custom".
        Returns auto-estimated value when mode is "auto".

        For Chinese text, 1 character ~= 1.5 tokens on average.
        """
        if self._max_tokens_mode == "default":
            return None
        if self._max_tokens_mode == "custom":
            return self._config.max_tokens
        # "auto" mode
        configured_max = self._config.max_tokens
        if text_len < 500:
            estimated = text_len * 3
        elif text_len < 3000:
            estimated = text_len * 2
        elif text_len < 10000:
            estimated = int(text_len * 1.5)
        else:
            estimated = text_len
        return max(2048, min(estimated, configured_max))

    def _build_create_kwargs(self, prompt: str, stream: bool = False) -> dict[str, Any]:
        """Build kwargs for the OpenAI chat completions create call."""
        max_tokens = self._estimate_max_tokens(len(prompt))
        kwargs: dict[str, Any] = {
            "model": self._config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self._config.temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if stream:
            kwargs["stream"] = True
        return kwargs

    def process(self, text: str, mode: str, custom_prompt: str | None = None) -> tuple[str, bool]:
        """Process text non-streamingly. Returns (result_text, was_truncated)."""
        prompt = self._resolve_prompt(mode, text, custom_prompt)

        client = self._get_client()
        response = client.chat.completions.create(**self._build_create_kwargs(prompt))
        result = response.choices[0].message.content or ""
        truncated = response.choices[0].finish_reason == "length"
        return result, truncated

    def process_stream(self, text: str, mode: str, on_token: Any, custom_prompt: str | None = None) -> tuple[str, bool]:
        """Process text with streaming. Calls on_token(chunk) for each token.

        Returns (full_text, was_truncated).
        Checks self._cancel_event between chunks for cancellation support.
        """
        self._reset_cancel()
        prompt = self._resolve_prompt(mode, text, custom_prompt)

        client = self._get_client()
        stream = client.chat.completions.create(**self._build_create_kwargs(prompt, stream=True))

        full = ""
        finish_reason = "stop"
        try:
            for chunk in stream:
                if self._cancel_event.is_set():
                    break
                delta = chunk.choices[0].delta.content
                if delta:
                    full += delta
                    on_token(delta)
                if chunk.choices[0].finish_reason:
                    finish_reason = chunk.choices[0].finish_reason
        finally:
            stream.close()

        truncated = finish_reason == "length"
        return full, truncated

    def continue_stream(self, previous_output: str, mode: str, on_token: Any, custom_prompt: str | None = None) -> tuple[str, bool]:
        """Continue AI output from where it was truncated.

        Sends a follow-up message asking the AI to continue from the
        last sentence boundary of the previous output.
        """
        self._reset_cancel()

        # Find the last sentence boundary to continue from
        last_period = max(previous_output.rfind("."), previous_output.rfind("。"), previous_output.rfind("!"), previous_output.rfind("？"))
        if last_period > 0:
            context = previous_output[:last_period + 1]
        else:
            context = previous_output

        continue_prompt = (
            "You were in the middle of generating content and were cut off. "
            "Here is what you have produced so far:\n\n"
            f"{context}\n\n"
            "Please CONTINUE from where you left off. Do NOT repeat what was already written. "
            "Start directly from the next sentence/section."
        )

        client = self._get_client()
        kwargs: dict[str, Any] = {
            "model": self._config.model,
            "messages": [{"role": "user", "content": continue_prompt}],
            "temperature": self._config.temperature,
            "stream": True,
        }
        # For continuation, respect the max_tokens_mode:
        # "default" -> no limit, "auto" -> full configured max, "custom" -> configured value
        if self._max_tokens_mode != "default":
            kwargs["max_tokens"] = self._config.max_tokens

        stream = client.chat.completions.create(**kwargs)

        full = ""
        finish_reason = "stop"
        try:
            for chunk in stream:
                if self._cancel_event.is_set():
                    break
                delta = chunk.choices[0].delta.content
                if delta:
                    full += delta
                    on_token(delta)
                if chunk.choices[0].finish_reason:
                    finish_reason = chunk.choices[0].finish_reason
        finally:
            stream.close()

        truncated = finish_reason == "length"
        return full, truncated
