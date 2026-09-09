"""LLM integration layer — OpenAI API, stdlib-only (zero dependencies)."""
import json
import re
import time
import ssl
import urllib.request
import urllib.error

DEFAULT_BASE = "https://api.openai.com/v1"

class LLMError(Exception):
    pass

def _retry_after_seconds(e):
    """Extract suggested retry delay from an HTTP 429 response."""
    try:
        ra = e.headers.get("Retry-After")
        if ra:
            return float(ra)
    except Exception:
        pass
    try:
        body = e.read().decode("utf-8")[:2000]
        m = re.search(r"try again in ([\d.]+)s", body, re.IGNORECASE)
        if m:
            return float(m.group(1))
    except Exception:
        pass
    return 5.0


def _post_json(url, headers, payload, timeout=120, max_retries=3):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8")[:500]
            except Exception:
                pass
            if e.code == 429 and attempt < max_retries:
                delay = _retry_after_seconds(e)
                time.sleep(delay)
                continue
            raise LLMError(f"HTTP {e.code}: {detail}") from e
        except Exception as e:
            raise LLMError(f"Network error: {e}") from e

def _chat_completion(api_key, model, messages, max_tokens, temperature, base_url=DEFAULT_BASE, max_retries=3):
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    data = _post_json(url, headers, payload, max_retries=max_retries)
    if "choices" not in data or not data["choices"]:
        raise LLMError("No choices returned")
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return content, usage

def complete(cfg, messages):
    """Returns (text, usage) from the configured LLM."""
    api_key = cfg.get("api_key", "")
    if not api_key:
        raise LLMError("No API key configured. Set OPENAI_API_KEY env var or run: dac config --set api_key sk-...")
    provider = cfg.get("provider", "openai")
    model = cfg.get("model", "gpt-4o")
    max_tokens = int(cfg.get("max_tokens", 4096))
    temperature = float(cfg.get("temperature", 0.2))
    max_retries = int(cfg.get("max_retries", 3))
    if provider == "openai":
        return _chat_completion(api_key, model, messages, max_tokens, temperature, max_retries=max_retries)
    raise LLMError(f"Unsupported provider: {provider}")

def extract_code_blocks_with_lang(text):
    """Parse ```python ... ``` (or ```bash```) blocks, returning (language, code) pairs."""
    import re
    blocks = []
    for m in re.finditer(r"```(python|py|bash|sh|zsh)?\n(.*?)```", text, re.DOTALL):
        lang = m.group(1) or ""
        if lang in ("py", "python"):
            lang = "python"
        elif lang in ("sh", "bash", "zsh"):
            lang = "bash"
        else:
            lang = "bash"
        blocks.append((lang, m.group(2).strip()))
    return blocks

def extract_code_blocks(text):
    """Parse ```python ... ``` (or ```bash```) blocks from LLM output."""
    return [code for _, code in extract_code_blocks_with_lang(text)]

def parse_json(text):
    """Try to parse JSON from LLM output, stripping markdown fences."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`").strip()
        if t.startswith("json"):
            t = t[4:].strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        # last-resort: find first { ... } block
        import re
        m = re.search(r"\{.*\}", t, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        raise LLMError("Model output was not valid JSON")
