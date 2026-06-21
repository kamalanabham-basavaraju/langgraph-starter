from pathlib import Path

from app.integrations.enterpro.client import EnterProClient


def test_enterpro_cli_command_receives_prompt_file_and_project_path(tmp_path: Path):
    marker = tmp_path / "marker.txt"
    command = (
        'python -c "import pathlib,sys; '
        "pathlib.Path(sys.argv[2], 'marker.txt').write_text("
        "pathlib.Path(sys.argv[1]).read_text() + '|' + sys.argv[3], encoding='utf-8')"
        '" "{prompt_file}" "{project_path}" "{workspace_id}"'
    )
    client = EnterProClient(
        url=None,
        api_key="secret",
        command=command,
        workspace_id="workspace-1",
        timeout=10,
    )

    result = client.execute("Fix profile validation", tmp_path)

    assert result["mode"] == "cli"
    assert result["exit_code"] == 0
    assert marker.read_text(encoding="utf-8") == "Fix profile validation|workspace-1"


def test_enterpro_default_cli_command_uses_enter_headless_mode(tmp_path: Path):
    client = EnterProClient(
        url=None,
        api_key="secret",
        command=None,
        workspace_id="10000087268",
        timeout=10,
    )

    args = client._command_args("Fix profile validation", tmp_path / "prompt.md", tmp_path)

    assert args == [
        "enter",
        "-p",
        "Fix profile validation",
        "-permission-mode",
        "acceptEdits",
        "-output-format",
        "json",
        "-api-key",
        "secret",
        "-workspace-id",
        "10000087268",
    ]
    assert client._redacted_command(args)[2] == "***"
    assert client._redacted_command(args)[8] == "***"


def test_enterpro_default_cli_command_uses_workspace_name_when_not_numeric(tmp_path: Path):
    client = EnterProClient(
        url=None,
        api_key=None,
        command=None,
        workspace_id="bokadaman's Workspace",
        timeout=10,
    )

    args = client._command_args("Fix profile validation", tmp_path / "prompt.md", tmp_path)

    assert args[-2:] == ["-workspace", "bokadaman's Workspace"]
