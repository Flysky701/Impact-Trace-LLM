"""Multi-provider LLM adapter with strict source-anchor verification and graceful fallback."""
import json
import re
import time
import httpx

from .models import SystemSetting
from .security import timestamp

PROVIDERS = {"openai_compatible", "gemini", "anthropic"}

PRESETS = [
    {"id": "deepseek", "label": "DeepSeek", "provider": "openai_compatible",
     "base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
    {"id": "openai", "label": "OpenAI / 通用兼容", "provider": "openai_compatible",
     "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    {"id": "siliconflow", "label": "硅基流动", "provider": "openai_compatible",
     "base_url": "https://api.siliconflow.cn/v1", "model": "deepseek-ai/DeepSeek-V3"},
    {"id": "qwen", "label": "通义千问", "provider": "openai_compatible",
     "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    {"id": "gemini", "label": "Google Gemini", "provider": "gemini",
     "base_url": "https://generativelanguage.googleapis.com/v1beta", "model": "gemini-2.5-flash"},
    {"id": "anthropic", "label": "Claude", "provider": "anthropic",
     "base_url": "https://api.anthropic.com/v1", "model": "claude-sonnet-4-5"},
]


class LLMError(RuntimeError):
    pass


def mask_key(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) <= 8:
        return "••••••••"
    return f"{value[:4]}••••{value[-4:]}"


def get_llm_config(db, settings) -> dict:
    stored = {
        row.key: row.value
        for row in db.query(SystemSetting).filter(
            SystemSetting.key.in_(("llm_provider", "llm_base_url", "llm_api_key", "llm_model"))
        )
    }
    provider = stored.get("llm_provider") or settings.llm_provider or "openai_compatible"
    if provider not in PROVIDERS:
        provider = "openai_compatible"
    return {
        "provider": provider,
        "base_url": (stored.get("llm_base_url") or settings.llm_base_url or "https://api.deepseek.com/v1").strip(),
        "api_key": (stored["llm_api_key"] if "llm_api_key" in stored else settings.llm_api_key or "").strip(),
        "model": (stored.get("llm_model") or settings.llm_model or "deepseek-chat").strip(),
    }


def public_llm_config(cfg: dict) -> dict:
    return {
        "provider": cfg["provider"],
        "base_url": cfg["base_url"],
        "model": cfg["model"],
        "configured": bool(cfg["api_key"]),
        "masked_key": mask_key(cfg["api_key"]),
        "presets": PRESETS,
    }


def save_llm_config(db, settings, provider: str, base_url: str, model: str,
                    api_key: str | None = None, clear_key: bool = False) -> dict:
    if provider not in PROVIDERS:
        raise LLMError("不支持的模型接口类型。")
    if not base_url.strip() or not base_url.strip().startswith(("http://", "https://")):
        raise LLMError("请填写以 http:// 或 https:// 开头的接口地址。")
    if not model.strip():
        raise LLMError("请填写模型名称。")
    current = get_llm_config(db, settings)
    next_key = "" if clear_key else (api_key.strip() if api_key and api_key.strip() else current["api_key"])
    updates = {
        "llm_provider": provider.strip(),
        "llm_base_url": base_url.strip().rstrip("/"),
        "llm_model": model.strip(),
        "llm_api_key": next_key,
    }
    now = timestamp()
    for key, value in updates.items():
        row = db.get(SystemSetting, key)
        if row:
            row.value = value
            row.updated_at = now
        else:
            db.add(SystemSetting(key=key, value=value, updated_at=now))
    db.commit()
    return get_llm_config(db, settings)


def _openai_url(base_url: str) -> str:
    clean = base_url.rstrip("/")
    if clean.endswith("/chat/completions"):
        return clean
    if re.search(r"/v\d+(?:beta\d*)?$", clean) or clean.endswith("/compatible-mode/v1"):
        return f"{clean}/chat/completions"
    return f"{clean}/v1/chat/completions"


def call_llm(cfg: dict, system_prompt: str, user_prompt: str,
             temperature: float = 0.2, timeout: float = 65.0) -> str:
    api_key = cfg.get("api_key", "").strip()
    if not api_key:
        raise LLMError("尚未配置 API Key，请先在右上角「AI 模型设置」中填入密钥。")
    provider = cfg.get("provider", "openai_compatible")
    model = cfg.get("model", "deepseek-chat")
    base = cfg.get("base_url", "").rstrip("/")
    try:
        if provider == "gemini":
            root = base if "/models" not in base else base.split("/models", 1)[0]
            if not re.search(r"/v1(?:beta)?$", root):
                root = f"{root}/v1beta"
            url = f"{root}/models/{model}:generateContent"
            resp = httpx.post(
                url,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json={
                    "systemInstruction": {"parts": [{"text": system_prompt}]},
                    "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                    "generationConfig": {"temperature": temperature},
                },
                timeout=timeout,
            )
        elif provider == "anthropic":
            url = base if base.endswith("/messages") else (f"{base}/messages" if base.endswith("/v1") else f"{base}/v1/messages")
            resp = httpx.post(
                url,
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "max_tokens": 4096,
                    "temperature": temperature,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                },
                timeout=timeout,
            )
        else:
            url = _openai_url(base)
            resp = httpx.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "temperature": temperature,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
                timeout=timeout,
            )
    except httpx.TimeoutException as exc:
        raise LLMError("模型响应超时，请稍后重试或切换更快的模型。") from exc
    except httpx.HTTPError as exc:
        raise LLMError("无法连接模型接口，请检查接口地址与本机网络。") from exc

    if resp.status_code in (401, 403):
        raise LLMError("API Key 认证失败或无权限，请核对密钥与接口地址。")
    if resp.status_code == 429:
        raise LLMError("模型调用触发限流或额度不足，请稍后再试。")
    if resp.status_code >= 400:
        detail = resp.text[:160].strip()
        raise LLMError(f"模型服务返回错误（HTTP {resp.status_code}）：{detail or '请检查模型名称与地址'}")

    try:
        payload = resp.json()
        if provider == "gemini":
            parts = payload["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts).strip()
        if provider == "anthropic":
            return "".join(b.get("text", "") for b in payload["content"] if b.get("type") == "text").strip()
        return str(payload["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise LLMError("模型返回格式无法解析，请确认接口兼容所选协议。") from exc


def extract_json(raw: str) -> dict:
    cleaned = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.S)
    if fence:
        cleaned = fence.group(1)
    else:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            cleaned = cleaned[start:end + 1]
    try:
        parsed = json.loads(cleaned)
    except ValueError as exc:
        raise LLMError("模型未返回有效的结构化 JSON 结果。") from exc
    if not isinstance(parsed, dict):
        raise LLMError("模型返回根节点不是 JSON 对象。")
    return parsed


def sanitize_anchors(items, valid_paths: set[str]) -> list[dict]:
    if not isinstance(items, list):
        return []
    verified = []
    for item in items[:6]:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).strip()
        if path not in valid_paths:
            continue
        line = max(1, int(item.get("line") or 1))
        end = max(line, int(item.get("end") or line))
        verified.append({
            "path": path,
            "line": line,
            "end": end,
            "label": str(item.get("label") or path.rsplit("/", 1)[-1])[:120],
        })
    return verified


def test_connection(cfg: dict) -> dict:
    started = time.monotonic()
    reply = call_llm(
        cfg,
        "你是连通性检测助手。",
        "请只回复两个字母：OK",
        temperature=0.0,
        timeout=20.0,
    )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    return {"ok": True, "model": cfg["model"], "latency_ms": elapsed_ms, "reply": reply[:60]}


def generate_overview_with_llm(cfg: dict, context_pack: dict, valid_paths: set[str], fallback: dict) -> dict:
    system_prompt = (
        "你是一位极其擅长把复杂代码讲成大白话的首席软件导览员。"
        "你的读者是刚接触这个仓库的人（可能是审阅者或懂一点逻辑但不想看生涩术语的协作者）。"
        "严格遵守以下铁律：\n"
        "1. 第一层展示文字（headline、narrative、roles.title、roles.subtitle、roleFlows.action、storylines.title、storylines.steps.what/why）"
        "绝对禁止出现具体类名、函数名、包名、import、UML术语！必须用人人能懂的业务角色和动作语言描述程序怎么流动。\n"
        "2. 在 plainHow / howPlain 字段用通俗中文解释底层代码大概是怎么配合实现的。\n"
        "3. anchors 只能引用输入数据中真实存在的 path 和行号，绝不能编造路径。\n"
        "4. 只输出纯 JSON 对象，结构包含：headline(字符串), narrative(字符串), "
        "roles(数组: id,title,subtitle,plainHow,anchors), "
        "roleFlows(数组: from,to,action,detail), "
        "storylines(数组: id,title,when,outcome,steps[数组: stepNo,what,why,howPlain,moduleId,anchors]), "
        "hotspots(数组: id,title,whyHard,splitIdea,severity,metrics,moduleId,anchors)。"
    )
    raw = call_llm(cfg, system_prompt, json.dumps(context_pack, ensure_ascii=False))
    parsed = extract_json(raw)

    result = dict(fallback)
    result["sourceMode"] = "llm"
    result["modelName"] = cfg["model"]
    if isinstance(parsed.get("headline"), str) and parsed["headline"].strip():
        result["headline"] = parsed["headline"].strip()[:240]
    if isinstance(parsed.get("narrative"), str) and parsed["narrative"].strip():
        result["narrative"] = parsed["narrative"].strip()[:600]

    fallback_roles = {r["id"]: r for r in fallback.get("roles", [])}
    if isinstance(parsed.get("roles"), list) and parsed["roles"]:
        merged_roles = []
        for idx, item in enumerate(parsed["roles"][:8]):
            if not isinstance(item, dict):
                continue
            rid = str(item.get("id") or f"role-{idx + 1}")
            base_role = fallback_roles.get(rid, {})
            anchors = sanitize_anchors(item.get("anchors"), valid_paths) or base_role.get("anchors", [])
            merged_roles.append({
                "id": rid,
                "title": str(item.get("title") or base_role.get("title") or rid)[:60],
                "subtitle": str(item.get("subtitle") or base_role.get("subtitle") or "")[:160],
                "plainHow": str(item.get("plainHow") or base_role.get("plainHow") or "")[:400],
                "fileCount": base_role.get("fileCount", 0),
                "lineCount": base_role.get("lineCount", 0),
                "anchors": anchors,
            })
        if merged_roles:
            result["roles"] = merged_roles

    valid_role_ids = {r["id"] for r in result["roles"]}
    if isinstance(parsed.get("roleFlows"), list) and parsed["roleFlows"]:
        flows = []
        for item in parsed["roleFlows"][:12]:
            if not isinstance(item, dict):
                continue
            src, dst = str(item.get("from", "")), str(item.get("to", ""))
            if src in valid_role_ids and dst in valid_role_ids and src != dst and item.get("action"):
                flows.append({
                    "from": src,
                    "to": dst,
                    "action": str(item["action"])[:60],
                    "detail": str(item.get("detail") or "")[:200],
                })
        if flows:
            result["roleFlows"] = flows

    if isinstance(parsed.get("storylines"), list) and parsed["storylines"]:
        stories = []
        for idx, st in enumerate(parsed["storylines"][:5]):
            if not isinstance(st, dict) or not st.get("title") or not isinstance(st.get("steps"), list):
                continue
            steps = []
            for s_idx, step in enumerate(st["steps"][:7]):
                if not isinstance(step, dict) or not step.get("what"):
                    continue
                steps.append({
                    "stepNo": s_idx + 1,
                    "what": str(step["what"])[:100],
                    "why": str(step.get("why") or "")[:160],
                    "howPlain": str(step.get("howPlain") or "")[:350],
                    "moduleId": str(step.get("moduleId") or ""),
                    "anchors": sanitize_anchors(step.get("anchors"), valid_paths),
                })
            if steps:
                stories.append({
                    "id": str(st.get("id") or f"story-{idx + 1}"),
                    "title": str(st["title"])[:80],
                    "when": str(st.get("when") or "")[:140],
                    "outcome": str(st.get("outcome") or "")[:160],
                    "steps": steps,
                })
        if stories:
            result["storylines"] = stories

    if isinstance(parsed.get("hotspots"), list) and parsed["hotspots"]:
        hotspots = []
        for idx, hp in enumerate(parsed["hotspots"][:6]):
            if not isinstance(hp, dict) or not hp.get("title"):
                continue
            base_hp = fallback["hotspots"][idx] if idx < len(fallback.get("hotspots", [])) else {}
            anchors = sanitize_anchors(hp.get("anchors"), valid_paths) or base_hp.get("anchors", [])
            hotspots.append({
                "id": str(hp.get("id") or f"hotspot-{idx + 1}"),
                "title": str(hp["title"])[:90],
                "whyHard": str(hp.get("whyHard") or base_hp.get("whyHard") or "")[:300],
                "splitIdea": str(hp.get("splitIdea") or base_hp.get("splitIdea") or "")[:320],
                "severity": hp.get("severity") if hp.get("severity") in ("high", "medium", "low") else base_hp.get("severity", "medium"),
                "metrics": str(hp.get("metrics") or base_hp.get("metrics") or "")[:80],
                "moduleId": str(hp.get("moduleId") or base_hp.get("moduleId") or ""),
                "anchors": anchors,
            })
        if hotspots:
            result["hotspots"] = hotspots

    return result


def explain_change_with_llm(cfg: dict, change_pack: dict, valid_paths: set[str]) -> dict:
    system_prompt = (
        "你是一位资深的团队代码审阅搭档。请用大白话向提交者和审阅者解释这次代码变更：\n"
        "1. 先不堆砌类名，直接说清楚：这次动了哪块业务能力、修改前后程序的运行步骤有什么不同。\n"
        "2. 对照提交者的修改意图（若有），指出审阅者最该核对的边界风险与回归测试重点。\n"
        "3. anchors 只能引用输入变更中真实存在的 path 与行号。\n"
        "只输出纯 JSON 对象：{headline, beforeVsAfter, riskPoints:[{title,detail,anchors}], testSuggestions:[字符串]}。"
    )
    raw = call_llm(cfg, system_prompt, json.dumps(change_pack, ensure_ascii=False))
    parsed = extract_json(raw)
    risks = []
    for item in (parsed.get("riskPoints") or [])[:5]:
        if isinstance(item, dict) and item.get("title"):
            risks.append({
                "title": str(item["title"])[:100],
                "detail": str(item.get("detail") or "")[:320],
                "anchors": sanitize_anchors(item.get("anchors"), valid_paths),
            })
    tests = [str(x)[:160] for x in (parsed.get("testSuggestions") or [])[:5] if isinstance(x, str) and x.strip()]
    return {
        "mode": "llm",
        "model": cfg["model"],
        "headline": str(parsed.get("headline") or "已完成变更白话解读")[:220],
        "beforeVsAfter": str(parsed.get("beforeVsAfter") or "")[:600],
        "riskPoints": risks,
        "testSuggestions": tests,
    }


def answer_question_with_llm(cfg: dict, question_pack: dict, valid_paths: set[str]) -> dict:
    system_prompt = (
        "你是当前代码仓库的随身导览与维护顾问。请根据提供的仓库结构、源码片段、调用关系和历史避坑便签，"
        "先用通俗直白的语言回答用户问题（讲清程序流怎么走、职责在哪），再给出需要关注的实现位置。"
        "若现有证据不足以确定某件事，请诚实说明“根据当前静态证据尚不能完全确定”，不要编造不存在的文件。"
        "只输出纯 JSON 对象：{answer: 字符串, keyPoints: [字符串], anchors: [{path, line, end, label}]}。"
    )
    raw = call_llm(cfg, system_prompt, json.dumps(question_pack, ensure_ascii=False))
    parsed = extract_json(raw)
    points = [str(x)[:200] for x in (parsed.get("keyPoints") or [])[:5] if isinstance(x, str) and x.strip()]
    return {
        "mode": "llm",
        "model": cfg["model"],
        "answer": str(parsed.get("answer") or "已根据仓库上下文整理如下线索。")[:1500],
        "keyPoints": points,
        "anchors": sanitize_anchors(parsed.get("anchors"), valid_paths),
    }
