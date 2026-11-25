"""HTTP dashboard smoke test covering patrol launch and analyst queries."""

import json
import threading
import time
from urllib.request import Request, urlopen

from src.web_ui import create_server


def test_dashboard_serves_ui_runs_patrol_and_answers_questions(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(
        "src.web_ui._database_path", lambda: tmp_path / "dashboard.db"
    )
    monkeypatch.setattr(
        "src.web_ui.DEFAULT_ALERT_LOG", tmp_path / "alerts.log"
    )
    server = create_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        with urlopen(base_url, timeout=3) as response:
            page = response.read().decode("utf-8")
        assert "Patrol overview" in page
        assert "Start patrol" in page
        assert "Patrol overview" in page
        assert "Event register" in page
        with urlopen(f"{base_url}/healthz", timeout=3) as response:
            assert json.load(response) == {"status": "ok"}

        request = Request(
            f"{base_url}/api/run",
            data=json.dumps({"speed": 0}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=3) as response:
            assert response.status == 202

        state = {}
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with urlopen(f"{base_url}/api/state", timeout=3) as response:
                state = json.load(response)
            if state["run"]["state"] in {"completed", "failed"}:
                break
            time.sleep(0.05)

        assert state["run"]["state"] == "completed"
        assert state["frames"] == 50
        assert state["alert_count"] == 7
        assert state["frames_list"]

        request = Request(
            f"{base_url}/api/ask",
            data=json.dumps({"question": "How many times did the F150 enter today?"}).encode(
                "utf-8"
            ),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=3) as response:
            answer = json.load(response)["answer"]
        assert "entered 2 times" in answer
    finally:
        server.shutdown()
        server.dashboard.close()
        server.server_close()
        thread.join(timeout=3)
