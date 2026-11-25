import time

import pytest

from tests.conftest import KEYS


def chat(client, session="s1", message="What is the capital of France?", headers=None, **extra):
    return client.post("/chat", json={"session_id": session, "message": message, **extra}, headers=headers or {})


# 1
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "keys_configured": 2, "cache_enabled": True}


def test_health_reports_unhealthy_database(client):
    real = client.app.state.engine

    class Broken:
        def connect(self):
            raise RuntimeError("db down")

        def dispose(self):
            real.dispose()

    client.app.state.engine = Broken()
    r = client.get("/health")
    assert r.status_code == 503 and r.json()["status"] == "error"


# 2
def test_valid_chat_structure(client):
    r = chat(client)
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == "s1" and body["reply"].startswith("stub-reply")
    m = body["metadata"]
    assert set(m) == {"resolution_source", "model", "latency_ms", "input_tokens", "output_tokens", "key_id", "fallback_attempts"}
    assert m["resolution_source"] == "LIVE_INFERENCE"
    assert m["model"] == "openai/stub-model"
    assert m["key_id"] == "key_1" and m["fallback_attempts"] == 0
    assert m["latency_ms"] >= 0 and m["input_tokens"] > 0 and m["output_tokens"] > 0


# 3-6 validation
def test_missing_message_422(client):
    assert client.post("/chat", json={"session_id": "s1"}).status_code == 422


@pytest.mark.parametrize("msg", ["", "   \n\t "])
def test_empty_message_422(client, msg):
    assert chat(client, message=msg).status_code == 422


def test_message_too_long_422(client):
    assert chat(client, message="x" * 4001).status_code == 422
    assert chat(client, message="x" * 4000, session="long").status_code == 200


def test_missing_or_bad_session_422(client):
    assert client.post("/chat", json={"message": "hi"}).status_code == 422
    assert chat(client, session="").status_code == 422
    assert chat(client, session="s" * 129).status_code == 422


# 7
def test_history_saved(client):
    reply = chat(client, session="h1", message="Hello there").json()["reply"]
    r = client.get("/sessions/h1/messages")
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["content"] == "Hello there" and "metadata" not in msgs[0]
    assert msgs[1]["content"] == reply
    assert msgs[1]["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert msgs[1]["metadata"]["input_tokens"] > 0 and msgs[1]["metadata"]["output_tokens"] > 0


# 8
def test_multi_turn_preserves_context(client):
    r1 = chat(client, session="mt", message="first").json()
    r2 = chat(client, session="mt", message="second").json()
    assert "history=1" in r1["reply"]
    assert "history=3" in r2["reply"]  # user, assistant, new user
    # input tokens are per-request (grow with history) and output tokens only count this reply
    assert r2["metadata"]["input_tokens"] > r1["metadata"]["input_tokens"]
    assert r2["metadata"]["output_tokens"] == len(r2["reply"].split())
    msgs = client.get("/sessions/mt/messages").json()["messages"]
    assert [m["content"] for m in msgs if m["role"] == "user"] == ["first", "second"]


def test_system_prompt_counts_as_input_but_is_not_returned(client):
    plain = chat(client, session="sp1", message="hi there").json()
    with_sys = chat(client, session="sp2", message="hi there", system_prompt="You are a pirate who speaks tersely").json()
    assert with_sys["metadata"]["input_tokens"] > plain["metadata"]["input_tokens"]
    msgs = client.get("/sessions/sp2/messages").json()["messages"]
    assert all(m["role"] != "system" for m in msgs) and len(msgs) == 2


# 9
def test_sessions_isolated(client):
    chat(client, session="A", message="alpha")
    r = chat(client, session="B", message="beta").json()
    assert "history=1" in r["reply"]
    assert [m["content"] for m in client.get("/sessions/A/messages").json()["messages"]][0] == "alpha"
    assert len(client.get("/sessions/B/messages").json()["messages"]) == 2


# 10-12 cache
def test_cache_hit_across_sessions(client, provider):
    first = chat(client, session="c1", message="cache me please").json()
    second = chat(client, session="c2", message="cache me please").json()
    assert first["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert second["metadata"]["resolution_source"] == "LLM_CACHE"          # 10
    assert second["reply"] == first["reply"]                                # 11 (reply contains a per-call uuid)
    assert second["metadata"]["input_tokens"] == first["metadata"]["input_tokens"]    # 12
    assert second["metadata"]["output_tokens"] == first["metadata"]["output_tokens"]
    assert second["metadata"]["key_id"] is None and second["metadata"]["fallback_attempts"] == 0
    assert len(provider.calls()) == 1  # provider was contacted exactly once


def test_cache_hit_is_faster_and_persisted(client):
    first = chat(client, session="f1", message="speed test").json()
    second = chat(client, session="f2", message="speed test").json()
    assert second["metadata"]["latency_ms"] <= first["metadata"]["latency_ms"]
    stored = client.get("/sessions/f2/messages").json()["messages"][1]["metadata"]
    assert stored["resolution_source"] == "LLM_CACHE"


def test_cache_never_crosses_different_input(client, provider):
    chat(client, session="d1", message="same text")
    other_msg = chat(client, session="d2", message="different text").json()
    other_sys = chat(client, session="d3", message="same text", system_prompt="Be brief").json()
    assert other_msg["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert other_sys["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    # same message but different history must also miss
    chat(client, session="d4", message="intro")
    diff_hist = chat(client, session="d4", message="same text").json()
    assert diff_hist["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert len(provider.calls()) == 5


def test_cache_can_be_disabled(make_client):
    c = make_client(cache_enabled=False)
    assert c.get("/health").json()["cache_enabled"] is False
    chat(c, session="n1", message="x")
    assert chat(c, session="n2", message="x").json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"


# 13-14 real (non-simulated) failover
def test_real_first_key_failure_falls_back(client, provider):
    provider.set_failing({KEYS[0]: 429})
    r = chat(client, message="real failover")
    assert r.status_code == 200
    m = r.json()["metadata"]
    assert m["key_id"] == "key_2" and m["fallback_attempts"] == 1
    assert provider.calls() == [KEYS[0], KEYS[1]]


@pytest.mark.parametrize("status", [429, 500, 502, 503])
def test_each_failure_status_triggers_fallback(client, provider, status):
    provider.set_failing({KEYS[0]: status})
    m = chat(client, message=f"status {status}").json()["metadata"]
    assert m["key_id"] == "key_2" and m["fallback_attempts"] == 1


def test_third_key_used_when_two_fail(make_client, provider):
    c = make_client(llm_api_keys="test-key-1,test-key-2,test-key-3")
    provider.set_failing({"test-key-1": 429, "test-key-2": 503})
    m = chat(c, message="three keys").json()["metadata"]
    assert m["key_id"] == "key_3" and m["fallback_attempts"] == 2


# 15-16
def test_all_keys_fail_503_and_not_stored(client, provider):
    provider.set_failing({k: 429 for k in KEYS})
    r = chat(client, session="fail1", message="doomed")
    assert r.status_code == 503
    assert r.json() == {"detail": "all providers unavailable"}
    assert "stub failure" not in r.text and "test-key" not in r.text
    assert client.get("/sessions/fail1/messages").status_code == 404  # nothing stored


def test_failed_request_does_not_pollute_existing_history(client, provider):
    chat(client, session="keep", message="ok one")
    provider.set_failing({k: 500 for k in KEYS})
    assert chat(client, session="keep", message="will fail").status_code == 503
    assert len(client.get("/sessions/keep/messages").json()["messages"]) == 2


def test_non_retryable_provider_error_is_502_without_trying_all_keys(client, provider):
    provider.set_failing({KEYS[0]: 400})
    r = chat(client, message="bad request")
    assert r.status_code == 502 and r.json() == {"detail": "provider rejected the request"}
    assert provider.calls() == [KEYS[0]]


# 17
def test_unknown_session_404_json(client):
    r = client.get("/sessions/nope/messages")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")
    assert r.json() == {"detail": "session not found"}


# 18 failure simulation
def test_simulation_key_1_429(client, provider):
    r = chat(client, message="sim 429", headers={"X-Simulate-Failure": "key_1=429"})
    assert r.status_code == 200
    m = r.json()["metadata"]
    assert m["key_id"] == "key_2" and m["fallback_attempts"] == 1 and m["resolution_source"] == "LIVE_INFERENCE"
    assert provider.calls() == [KEYS[1]]  # key_1 never really called; key_2 produced a real response


def test_simulation_key_1_500(client):
    r = chat(client, message="sim 500", headers={"X-Simulate-Failure": "key_1=500"})
    assert r.status_code == 200 and r.json()["metadata"]["key_id"] == "key_2"


def test_simulation_all_keys_503_not_stored(client):
    r = chat(client, session="simall", message="sim all", headers={"X-Simulate-Failure": "*=429"})
    assert r.status_code == 503 and r.json() == {"detail": "all providers unavailable"}
    assert client.get("/sessions/simall/messages").status_code == 404


def test_simulation_key_1_and_key_2(client):
    r = chat(client, message="both", headers={"X-Simulate-Failure": "key_1=429,key_2=500"})
    assert r.status_code == 503


def test_simulation_is_not_bypassed_by_cache(client):
    chat(client, session="x1", message="cached then simulated")  # populates cache
    r = chat(client, session="x2", message="cached then simulated", headers={"X-Simulate-Failure": "key_1=429"})
    m = r.json()["metadata"]
    assert m["resolution_source"] == "LIVE_INFERENCE" and m["key_id"] == "key_2" and m["fallback_attempts"] == 1
    r = chat(client, session="x3", message="cached then simulated", headers={"X-Simulate-Failure": "*=429"})
    assert r.status_code == 503


def test_simulation_affects_only_current_request(client):
    chat(client, session="o1", message="only once", headers={"X-Simulate-Failure": "*=429"})
    r = chat(client, session="o2", message="only once")
    assert r.status_code == 200 and r.json()["metadata"]["key_id"] == "key_1"


def test_simulation_ignored_when_disabled(make_client):
    c = make_client(enable_failure_simulation=False)
    r = chat(c, message="no sim", headers={"X-Simulate-Failure": "*=429"})
    assert r.status_code == 200 and r.json()["metadata"]["key_id"] == "key_1"


def test_simulation_invalid_header_422(client):
    assert chat(client, headers={"X-Simulate-Failure": "key_1=418"}).status_code == 422
    assert chat(client, headers={"X-Simulate-Failure": "key_9=429"}).status_code == 422


# misc
def test_real_failing_key_enters_cooldown_and_is_tried_last(make_client, provider):
    c = make_client(key_cooldown_seconds=60)
    provider.set_failing({KEYS[0]: 429})
    chat(c, message="cool 1")
    provider.set_failing({})
    r = chat(c, message="cool 2").json()["metadata"]
    assert r["key_id"] == "key_2" and r["fallback_attempts"] == 0  # key_1 deprioritised, not an attempt


def test_cors_and_json_errors(client):
    r = client.options("/chat", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST",
                                         "Access-Control-Request-Headers": "content-type,x-simulate-failure"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert client.get("/nonexistent").headers["content-type"].startswith("application/json")


def test_startup_config_errors(provider, tmp_path):
    from app.config import ConfigError, Settings
    from app.main import create_app
    from fastapi.testclient import TestClient
    with pytest.raises(ConfigError) as e:
        with TestClient(create_app(Settings(_env_file=None, llm_api_keys="", database_url=f"sqlite:///{tmp_path}/x.db"))):
            pass
    assert "LLM_API_KEYS" in str(e.value)


def test_api_keys_never_in_responses_or_logs(client, caplog, provider):
    provider.set_failing({KEYS[0]: 500})
    r = chat(client, message="secret check")
    assert "test-key" not in r.text
    assert "test-key" not in caplog.text
