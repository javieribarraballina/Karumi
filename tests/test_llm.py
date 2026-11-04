import pytest
from backend.atlas import llm


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)


def test_second_call_hits_cache(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "_call", lambda *a: calls.append(a) or "hi")
    assert llm.ask("q") == "hi"
    assert llm.ask("q") == "hi"
    assert len(calls) == 1


def test_different_model_or_image_is_a_different_key(monkeypatch, tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(b"x")
    calls = []
    monkeypatch.setattr(llm, "_call", lambda *a: calls.append(a) or "r")
    llm.ask("q")
    llm.ask("q", model="sonnet")
    llm.ask("q", image_path=str(img))
    assert len(calls) == 3


def test_retries_once_then_succeeds(monkeypatch):
    n = {"c": 0}

    def flaky(*a):
        n["c"] += 1
        if n["c"] == 1:
            raise RuntimeError("rate limit")
        return "ok"

    monkeypatch.setattr(llm, "_call", flaky)
    assert llm.ask("q") == "ok"


def test_fails_after_second_error_and_does_not_cache(monkeypatch):
    def boom(*a):
        raise RuntimeError("down")

    monkeypatch.setattr(llm, "_call", boom)
    with pytest.raises(RuntimeError):
        llm.ask("q")
    monkeypatch.setattr(llm, "_call", lambda *a: "later")
    assert llm.ask("q") == "later"


def test_call_sends_image_block(monkeypatch, tmp_path):
    img = tmp_path / "a.png"
    img.write_bytes(b"png")
    sent = {}

    class Msg:
        content = [type("B", (), {"text": "answer"})()]

    class Client:
        class messages:
            @staticmethod
            def create(**kw):
                sent.update(kw)
                return Msg()

    monkeypatch.setattr(llm, "_client", lambda: Client)
    assert llm._call("p", str(img), "haiku") == "answer"
    assert sent["model"] == "claude-haiku-5-5"
    assert sent["messages"][0]["content"][0]["type"] == "image"
