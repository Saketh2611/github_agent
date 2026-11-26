import json
import time
import httpx

from src.config import settings


class OllamaLLM:
    def __init__(self):
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model

    def invoke(self, prompt: str, system: str = "", temperature: float = 0.2, max_tokens: int = 4096) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(3):
            try:
                with httpx.Client(timeout=120.0) as client:
                    response = client.post(
                        f"{self.base_url}/api/chat",
                        json={
                            "model": self.model,
                            "messages": messages,
                            "stream": False,
                            "options": {
                                "temperature": temperature,
                                "num_predict": max_tokens,
                            },
                        },
                    )
                response.raise_for_status()
                return response.json()["message"]["content"]
            except (httpx.HTTPError, KeyError, ValueError) as e:
                if attempt < 2:
                    time.sleep(2)
                else:
                    raise RuntimeError(
                        f"Could not reach Ollama at {self.base_url}. "
                        "Ensure Ollama is running and the model is installed."
                    ) from e

    def invoke_json(self, prompt: str, system: str = "", temperature: float = 0.1) -> dict:
        system_with_json = (system + "\n\n" if system else "") + (
            "You MUST respond with valid JSON only. No markdown, no explanation, no extra text. "
            "Ensure all strings are properly escaped (no raw newlines inside strings)."
        )
        for attempt in range(3):
            raw = self.invoke(prompt, system=system_with_json, temperature=temperature)
            try:
                return _parse_json_response(raw)
            except (json.JSONDecodeError, ValueError):
                if attempt == 2:
                    raise
                temperature = min(temperature + 0.1, 0.5)


def _parse_json_response(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Try to extract the first JSON object from the response
    start = cleaned.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in LLM response: {raw[:200]}")
    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(cleaned)):
        c = cleaned[i]
        if escape_next:
            escape_next = False
            continue
        if c == "\\" and in_string:
            escape_next = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                candidate = cleaned[start:i + 1]
                return _try_parse(candidate)
    candidate = cleaned[start:]
    return _try_parse(candidate)


def _try_parse(candidate: str) -> dict:
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    fixed = _fix_json(candidate)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError as e:
        pos = e.pos if hasattr(e, 'pos') and e.pos else None
        if pos and pos > 20:
            truncated = fixed[:pos].rstrip().rstrip(',')
            open_braces = truncated.count('{') - truncated.count('}')
            open_brackets = truncated.count('[') - truncated.count(']')
            truncated += ']' * open_brackets + '}' * open_braces
            try:
                return json.loads(truncated)
            except json.JSONDecodeError:
                pass
        raise


def _fix_json(s: str) -> str:
    import re
    # Strip trailing commas
    s = re.sub(r',\s*([}\]])', r'\1', s)
    # Remove control chars except whitespace
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', s)
    # Remove JS concat expressions ("string" + expr) by walking character-by-character
    s = _strip_js_concats(s)
    # Escape unescaped special chars inside JSON string values
    result = []
    in_str = False
    i = 0
    while i < len(s):
        c = s[i]
        if not in_str:
            result.append(c)
            if c == '"':
                in_str = True
        else:
            if c == '\\':
                result.append(c)
                if i + 1 < len(s):
                    i += 1
                    result.append(s[i])
            elif c == '"':
                result.append(c)
                in_str = False
            elif c == '\n':
                result.append('\\n')
            elif c == '\r':
                result.append('\\r')
            elif c == '\t':
                result.append('\\t')
            else:
                result.append(c)
        i += 1
    return ''.join(result)


def _strip_js_concats(s: str) -> str:
    result = []
    i = 0
    in_string = False
    while i < len(s):
        c = s[i]
        if not in_string:
            if c == '"':
                in_string = True
                result.append(c)
            else:
                result.append(c)
        else:
            if c == '\\':
                result.append(c)
                if i + 1 < len(s):
                    i += 1
                    result.append(s[i])
            elif c == '"':
                result.append(c)
                in_string = False
                # Check if followed by ` + ` (JS concatenation)
                j = i + 1
                while j < len(s) and s[j] in ' \t':
                    j += 1
                if j < len(s) and s[j] == '+':
                    # Skip the entire expression until we find a valid JSON continuation
                    end_pos = _skip_js_expression(s, j + 1)
                    i = end_pos + 1
                    continue
            else:
                result.append(c)
        i += 1
    return ''.join(result)


def _skip_js_expression(s: str, start: int) -> int:
    depth_paren = 0
    depth_brace = 0
    depth_bracket = 0
    in_str_single = False
    in_str_double = False
    in_str_backtick = False
    i = start
    while i < len(s):
        c = s[i]
        if in_str_single:
            if c == '\\':
                i += 1
            elif c == "'":
                in_str_single = False
        elif in_str_double:
            if c == '\\':
                i += 1
            elif c == '"':
                in_str_double = False
        elif in_str_backtick:
            if c == '\\':
                i += 1
            elif c == '`':
                in_str_backtick = False
        else:
            if c == "'":
                in_str_single = True
            elif c == '"':
                in_str_double = True
            elif c == '`':
                in_str_backtick = True
            elif c == '(':
                depth_paren += 1
            elif c == ')':
                if depth_paren > 0:
                    depth_paren -= 1
                else:
                    pass  # unmatched ) in JS expression, skip it
            elif c == '{':
                depth_brace += 1
            elif c == '[':
                depth_bracket += 1
            elif c == '}':
                if depth_brace > 0:
                    depth_brace -= 1
                else:
                    return i - 1
            elif c == ']':
                if depth_bracket > 0:
                    depth_bracket -= 1
                else:
                    return i - 1
            elif c == ',' and depth_paren == 0 and depth_brace == 0 and depth_bracket == 0:
                return i - 1
            elif c == '\n':
                # Check if next non-whitespace line starts a new JSON key
                j = i + 1
                while j < len(s) and s[j] in ' \t':
                    j += 1
                if j < len(s) and s[j] == '"' and depth_paren == 0:
                    return i - 1
        i += 1
    return len(s) - 1


def _create_llm():
    return OllamaLLM()


llm = _create_llm()
