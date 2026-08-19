"""Shape-agnostic smoke test.

Proves config + logging load and the entry point's `main()` returns 0.
Replace with real tests as the project grows. The http-service shape
overwrites this file with a FastAPI TestClient version — see
shapes/http-service/tests/test_health.py.
"""

from src.main import main


def test_main_runs_and_returns_zero() -> None:
    assert main() == 0
