# -*- coding: utf-8 -*-
"""
config.py - 全局配置

所有模块统一从这里读取配置，避免配置散落在各处。
用户只需要在这里填写自己的 API Key 即可从「模拟评分」切换到「真实 LLM 评分」。
"""

# ===== LLM 相关配置 =====
# DeepSeek API Key，优先从环境变量 LLM_API_KEY 读取，读不到则为空字符串（模拟评分模式）。
# 设置方式（Windows PowerShell）：$env:LLM_API_KEY = "sk-xxxx"
# 用户填写后（例如 "sk-xxxx"），评分Agent会调用真实 DeepSeek API 打分。
import os

LLM_API_KEY = os.environ.get("LLM_API_KEY", "")

# DeepSeek API 地址（DeepSeek 兼容 OpenAI 协议，直接用 openai 库调用即可）
LLM_BASE_URL = "https://api.deepseek.com"

# 使用的模型名
LLM_MODEL = "deepseek-chat"

# ===== 评分相关配置 =====
# 总分范围
SCORE_MIN = 0
SCORE_MAX = 100

# 默认取最近几条对话历史作为评分上下文
DEFAULT_HISTORY_LIMIT = 10
