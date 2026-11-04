"""The only place that talks to a model. Every response is cached on disk."""
import base64
import hashlib
import json
from pathlib import Path

CACHE_DIR = Path(".cache/llm")
MODELS = {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5"}


def _client():
    import anthropic

    return anthropic.Anthropic()  # reads ANTHROPIC_API_KEY


def _call(prompt: str, image_path: str | None, model: str) -> str:
    content = []
    if image_path:
        raw = Path(image_path).read_bytes()
        mime = "image/jpeg" if raw[:3] == b"\xff\xd8\xff" else "image/png"
        content.append({"type": "image", "source": {"type": "base64", "media_type": mime,
                                                    "data": base64.b64encode(raw).decode()}})
    content.append({"type": "text", "text": prompt})
    msg = _client().messages.create(
        model=MODELS.get(model, model), max_tokens=1024, messages=[{"role": "user", "content": content}]
    )
    return msg.content[0].text


def ask(prompt: str, image_path: str | None = None, model: str = "haiku") -> str:
    img = Path(image_path).read_bytes() if image_path else b""
    key = hashlib.sha256(prompt.encode() + b"\0" + img + b"\0" + model.encode()).hexdigest()
    f = CACHE_DIR / f"{key}.json"
    if f.exists():
        return json.loads(f.read_text())["text"]
    try:
        text = _call(prompt, image_path, model)
    except Exception:
        text = _call(prompt, image_path, model)  # one retry; a second failure propagates
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"text": text}))
    return text
