# -*- coding: utf-8 -*-
"""
llm.py - LLM 调用封装（DeepSeek，OpenAI 兼容协议）

统一封装「真实 LLM 兜底」的调用入口，供 roleplay / review 的 enable_llm_fallback 分支复用。

设计原则（与 PLAN §9 决策 #1 对齐）：
- 规则库优先：所有 Agent 默认走确定性规则，LLM 只是可选的「更自然」增强。
- 兜底安全：任何一步失败（未配 key / 未装 openai / 网络异常 / 解析失败 / 空返回）
  都返回 None，调用方据此回退到规则结果，绝不因 LLM 失败中断主流程。

Python 3.9 兼容：类型注解用 typing.Optional。
"""

import sys
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import config


def _build_client():
    """懒加载 OpenAI 客户端（未安装 openai 库时抛 ImportError，由调用方捕获）。"""
    from openai import OpenAI

    return OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)


def call_deepseek(system_prompt: str, user_prompt: str) -> Optional[str]:
    """
    调一次 DeepSeek chat 补全，成功返回纯文本，任何失败返回 None。

    返回 None 的场景：未配置 key / 未安装 openai / 调用异常 / 返回为空。
    调用方把 None 视为「回退规则结果」的信号。
    """
    if not config.LLM_API_KEY:
        print("[LLM] 未配置 LLM_API_KEY，跳过 LLM 兜底（回退规则）")
        return None

    try:
        client = _build_client()
    except ImportError:
        print("[LLM] 未安装 openai 库，跳过 LLM 兜底（回退规则）")
        return None

    try:
        resp = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
        )
        text = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        print(f"[LLM] 调用失败，回退规则：{e}")
        return None

    if not text:
        print("[LLM] 返回为空，回退规则")
        return None
    return text
