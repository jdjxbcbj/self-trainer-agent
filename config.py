# -*- coding: utf-8 -*-
"""
config.py - 全局配置

所有模块统一从这里读取配置，避免配置散落在各处。
用户只需要在这里填写自己的 API Key 即可从「模拟评分」切换到「真实 LLM 评分」。
"""

# ===== LLM 相关配置 =====
# DeepSeek API Key：先读环境变量 LLM_API_KEY，再尝试加载本地 .env 文件（dotenv）。
# .env 已被 .gitignore 排除（勿提交）；.env.example 是模板（只含占位符，不含真 key）。
import os

try:
    from dotenv import load_dotenv
    load_dotenv()  # 读取项目根目录 .env（若存在），不覆盖已设置的环境变量
except ImportError:
    pass  # 未装 python-dotenv 时退化为「仅读环境变量」，不影响规则兜底

LLM_API_KEY = os.environ.get("LLM_API_KEY", "")

# DeepSeek API 地址（DeepSeek 兼容 OpenAI 协议，直接用 openai 库调用即可）
LLM_BASE_URL = "https://api.deepseek.com"

# 使用的模型名
LLM_MODEL = "deepseek-chat"

# LLM 兜底开关（默认关）：Phase 4 B1。默认 False 走规则路径（瞬时）；
# 设 LLM_FALLBACK_ENABLED=1 才启用 LLM 兜底（有 key 用 LLM、无 key 回退规则）。
LLM_FALLBACK_ENABLED = os.environ.get("LLM_FALLBACK_ENABLED", "").strip().lower() in ("1", "true", "yes", "on")

# ===== 评分相关配置 =====
# 总分范围
SCORE_MIN = 0
SCORE_MAX = 100

# 默认取最近几条对话历史作为评分上下文
DEFAULT_HISTORY_LIMIT = 10
