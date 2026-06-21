from pathlib import Path
from types import SimpleNamespace

from app.integrations.git.client import GitClient


def test_push_branch_uses_token_auth_without_leaking_token(monkeypatch, tmp_path: Path):
    captured = {}

    def fake_run(args, cwd, text, capture_output, check):
        captured.update(
            {
                "args": args,
                "cwd": cwd,
                "text": text,
                "capture_output": capture_output,
                "check": check,
            }
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("app.integrations.git.client.subprocess.run", fake_run)

    GitClient(tmp_path).push_branch("ai/test-branch", "secret-token")

    assert captured["cwd"] == tmp_path
    assert captured["args"][0:2] == ["git", "-c"]
    assert "secret-token" not in " ".join(captured["args"])
    assert captured["args"][-4:] == ["push", "--set-upstream", "origin", "ai/test-branch"]
