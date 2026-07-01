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
            "You MUST respond with valid JSON only. No markdown, no explanation, no extra text."
        )
        raw = self.invoke(prompt, system=system_with_json, temperature=temperature)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        return json.loads(cleaned)


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
            "You MUST respond with valid JSON only. No markdown, no explanation, no extra text."
        )
        raw = self.invoke(prompt, system=system_with_json, temperature=temperature)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        return json.loads(cleaned)


def _create_llm():
    if settings.groq_api_key:
        return GroqLLM()
    if settings.aws_access_key_id:
        return BedrockLLM()
    raise RuntimeError("No LLM configured. Set GROQ_API_KEY or AWS credentials in .env")


llm = _create_llm()
