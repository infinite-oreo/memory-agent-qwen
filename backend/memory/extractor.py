# -*- coding: utf-8 -*-
"""
[INPUT]: 依赖 langchain_openai.ChatOpenAI，依赖 config.settings，依赖标准库 json/re
[OUTPUT]: 对外提供 extract_facts(user_message, assistant_reply, profile) -> dict
[POS]: memory 模块的认知提炼器，把原始对话蒸馏为可回写的结构化事实
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""

import json
import re

from langchain_openai import ChatOpenAI

from config import settings

# ============================================================
# 抽取专用 LLM —— temperature=0, 追求确定性而非创造性
#   抽取与对话是两种认知, 故与 nodes 中的对话 LLM 分离
# ============================================================
_extractor = ChatOpenAI(
    model=settings.qwen_model,
    api_key=settings.qwen_api_key,
    base_url=settings.qwen_base_url,
    temperature=0.0,
)

_PROFILE_KEYS = ("name", "research_domain", "language_preference")

_SYSTEM_PROMPT = """你是一个严格的信息抽取器，服务于研究生的研究助手。
从用户的最新消息中，抽取值得【跨会话长期记忆】的结构化信息。

只输出 JSON，schema 如下：
{
  "profile": {
    "name": "用户姓名",
    "research_domain": "研究领域/方向",
    "language_preference": "语言偏好, 如 zh 或 en"
  },
  "preferences": [
    {"key": "偏好维度", "value": "具体偏好"}
  ],
  "memories": [
    {"text": "提炼为第三人称陈述句的事实, 每条一个独立事实, 适合语义检索", "importance": 0.5}
  ]
}

规则：
- 只抽取明确、稳定、对未来对话有用的信息；忽略寒暄、一次性提问、临时性内容。
- profile 各字段仅在用户明确透露时填写，否则置为空字符串 ""。
- memories 用简洁第三人称陈述句（例如 "用户在阅读关于对比学习的论文"）。
- importance 是 0~1 的浮点数，代表这条记忆对未来对话的长期价值：
  身份/研究方向/长期偏好等稳定核心事实给 0.8~1.0；中等程度的阶段性计划给 0.5~0.7；
  一次性好奇心/临时话题给 0.2~0.4。判断不了就给 0.5。
- 没有可抽取内容时：profile 字段全为 ""，preferences 与 memories 为空数组。
- 严禁编造未提及的信息。只输出 JSON，不要任何解释或 markdown。"""


async def extract_facts(
    user_message: str, assistant_reply: str, profile: dict | None
) -> dict:
    """
    从一轮对话中抽取结构化事实。
    返回规范化结构: {"profile": {白名单字段: 非空str}, "preferences": [{key,value}], "memories": [str]}。
    任何异常都降级为空结果，绝不阻断主流程（存储是锦上添花，不应拖垮对话）。
    """
    user_prompt = (
        f"已知用户画像（避免重复抽取）：{_profile_summary(profile)}\n\n"
        f"用户最新消息：{user_message}\n"
        f"（助手回复，仅供上下文）：{assistant_reply}"
    )
    try:
        resp = await _extractor.ainvoke(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
        )
        return _normalize(_parse_json(resp.content))
    except Exception:
        return _empty()


# ============================================================
# 内部辅助
# ============================================================
def _empty() -> dict:
    return {"profile": {}, "preferences": [], "memories": []}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _profile_summary(profile: dict | None) -> str:
    if not profile:
        return "（暂无）"
    parts = [f"{k}={profile[k]}" for k in _PROFILE_KEYS if profile.get(k)]
    prefs = profile.get("preferences") or {}
    parts += [f"{k}={v['value']}" for k, v in prefs.items()]
    return "; ".join(parts) or "（暂无）"


def _parse_json(text: str) -> dict:
    """容错解析：剥离 markdown 围栏，截取首尾花括号，失败则空。"""
    if not text:
        return {}
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*", "", text).strip().rstrip("`").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}


def _normalize(raw: dict) -> dict:
    """把 LLM 输出收敛到可信赖的形状，过滤空值与脏数据。"""
    out = _empty()

    prof = raw.get("profile") or {}
    out["profile"] = {
        k: str(prof[k]).strip()
        for k in _PROFILE_KEYS
        if isinstance(prof.get(k), str) and prof[k].strip()
    }

    for p in raw.get("preferences") or []:
        if isinstance(p, dict) and p.get("key") and p.get("value"):
            out["preferences"].append(
                {"key": str(p["key"]).strip(), "value": str(p["value"]).strip()}
            )

    for m in raw.get("memories") or []:
        if isinstance(m, dict) and isinstance(m.get("text"), str) and m["text"].strip():
            try:
                importance = _clamp01(float(m.get("importance", 0.5)))
            except (TypeError, ValueError):
                importance = 0.5
            out["memories"].append({"text": m["text"].strip(), "importance": importance})
        elif isinstance(m, str) and m.strip():  # 容错：LLM 偶尔退化为纯字符串
            out["memories"].append({"text": m.strip(), "importance": 0.5})

    return out
