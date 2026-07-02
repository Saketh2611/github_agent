import json
import time

from src.config import settings


class GroqLLM:
    def __init__(self):
        from groq import Groq
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.groq_model

    def invoke(self, prompt: str, system: str = "", temperature: float = 0.2, max_tokens: int = 4096) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content
            except Exception as e:
                if attempt < 2 and ("503" in str(e) or "unavailable" in str(e).lower() or "rate" in str(e).lower()):
                    time.sleep(2)
                else:
                    raise

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


class BedrockLLM:
    def __init__(self):
        import boto3
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        self.model_id = settings.bedrock_model_id

    def invoke(self, prompt: str, system: str = "", temperature: float = 0.2, max_tokens: int = 4096) -> str:
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        body = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": 0.9,
        }
        if system:
            body["system"] = [{"type": "text", "text": system}]

        response = self.client.invoke_model(
            modelId=self.model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]

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
    if settings.groq_api_key:
        return GroqLLM()
    if settings.aws_access_key_id:
        return BedrockLLM()
    raise RuntimeError("No LLM configured. Set GROQ_API_KEY or AWS credentials in .env")


llm = _create_llm()
