"""Verify persistent model-call history and deterministic reuse without a provider."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brain.model_gateway import ModelGateway


def main() -> None:
    calls: list[dict] = []

    def transport(request: dict) -> str:
        calls.append(request)
        if request["messages"][-1]["content"] == "fail":
            raise RuntimeError("synthetic provider failure")
        return '{"ok": true}'

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        journal = root / "brain" / "state" / "model_calls.jsonl"
        gateway = ModelGateway(root, transport=transport)
        first = gateway.complete(
            stage="test.stage",
            request_id="turn-1",
            json_mode=True,
            messages=[{"role": "user", "content": "same request"}],
        )
        second = gateway.complete(
            stage="test.stage",
            request_id="turn-2",
            json_mode=True,
            messages=[{"role": "user", "content": "same request"}],
        )
        restarted = ModelGateway(root, transport=transport).complete(
            stage="test.stage",
            request_id="turn-3",
            json_mode=True,
            messages=[{"role": "user", "content": "same request"}],
        )
        failed = False
        try:
            gateway.complete(stage="test.failure", messages=[{"role": "user", "content": "fail"}])
        except RuntimeError:
            failed = True
        records = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
        assertions = {
            "first_provider_call": first.reused is False,
            "same_process_reused": second.reused is True,
            "restart_reused": restarted.reused is True,
            "provider_called_once_for_success": len(calls) == 2,
            "failure_raised": failed,
            "success_recorded": any(item["status"] == "succeeded" and item["request"]["messages"] for item in records),
            "failure_recorded": any(item["status"] == "failed" and item["error_type"] == "RuntimeError" for item in records),
            "no_api_key_recorded": all("api_key" not in json.dumps(item).casefold() for item in records),
        }
        if not all(assertions.values()):
            raise AssertionError(assertions)
        result = {"status": "passed", **assertions}
        (ROOT / "trial" / "29_model_gateway_result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
