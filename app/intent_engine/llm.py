import os, json, urllib.request
class LLMClient:
    def __init__(self, api_url=None, api_key=None, model=None, timeout_ms=4000):
        self.api_url = api_url or os.getenv("LLM_API_URL")
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.model = model or os.getenv("LLM_MODEL","gpt-4o-mini")
        self.timeout_ms = int(os.getenv("LLM_TIMEOUT_MS", 4000))
    def available(self): return bool(self.api_url and self.api_key)
    def classify(self, system_prompt: str, message: str, extra: dict=None) -> dict:
        if not self.available(): raise RuntimeError("LLM not configured")
        payload = {"model": self.model,
                   "messages":[{"role":"system","content": system_prompt},
                               {"role":"user","content": json.dumps({"message": message, **(extra or {})}, ensure_ascii=False)}],
                   "temperature":0.1, "response_format":{"type":"json_object"}}
        req = urllib.request.Request(self.api_url, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type":"application/json","Authorization":f"Bearer {self.api_key}"}, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout_ms/1000.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
