import json
from pathlib import Path
from moss_ci.runner.cli_backend import CLIBackend


def _write_session(path: Path, tool_uses: list[dict]):
    """Write a fake Moss session jsonl with the given tool_use blocks.

    Mimics Moss's session format: one line, a state_replace record whose
    messages include assistant turns with Anthropic-style tool_use blocks.
    """
    messages = []
    for tu in tool_uses:
        messages.append({
            "role": "assistant",
            "content": [{"type": "tool_use", "name": tu["name"], "input": tu["input"]}],
        })
    rec = {"type": "state_replace", "messages": messages}
    path.write_text(json.dumps(rec), encoding="utf-8")


class TestParseToolCalls:
    def test_extracts_single_tool_call(self, tmp_path):
        sess = tmp_path / "s1.jsonl"
        _write_session(sess, [{"name": "read_file", "input": {"path": "x.json"}}])
        calls = CLIBackend._parse_tool_calls(sess)
        assert calls == [{"tool": "read_file", "args": {"path": "x.json"}}]

    def test_extracts_multiple_in_order(self, tmp_path):
        # tool_sequence needs the calls in invocation order — verify it.
        sess = tmp_path / "s2.jsonl"
        _write_session(sess, [
            {"name": "read_file", "input": {"path": "in.json"}},
            {"name": "write_file", "input": {"path": "out.json", "content": "x"}},
            {"name": "exec", "input": {"command": "ls"}},
        ])
        calls = CLIBackend._parse_tool_calls(sess)
        assert [c["tool"] for c in calls] == ["read_file", "write_file", "exec"]
        assert calls[1]["args"] == {"path": "out.json", "content": "x"}

    def test_ignores_non_tool_use_blocks(self, tmp_path):
        # assistant text + tool_result blocks must not be mistaken for tool calls
        sess = tmp_path / "s3.jsonl"
        sess.write_text(json.dumps({
            "type": "state_replace",
            "messages": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": [
                    {"type": "text", "text": "thinking..."},
                    {"type": "tool_use", "name": "read_file", "input": {"path": "a"}},
                    {"type": "tool_result", "tool_use_id": "x", "content": "..."},
                ]},
            ],
        }), encoding="utf-8")
        calls = CLIBackend._parse_tool_calls(sess)
        assert calls == [{"tool": "read_file", "args": {"path": "a"}}]

    def test_missing_file_returns_empty(self, tmp_path):
        assert CLIBackend._parse_tool_calls(tmp_path / "nope.jsonl") == []

    def test_malformed_json_line_skipped(self, tmp_path):
        sess = tmp_path / "s4.jsonl"
        sess.write_text("not json\n" + json.dumps({
            "type": "state_replace",
            "messages": [{"role": "assistant", "content": [
                {"type": "tool_use", "name": "exec", "input": {"command": "pwd"}}]}],
        }), encoding="utf-8")
        calls = CLIBackend._parse_tool_calls(sess)
        assert calls == [{"tool": "exec", "args": {"command": "pwd"}}]


class TestExtractToolCallsNewSession:
    def test_only_new_session_is_parsed(self, tmp_path):
        # Two pre-existing sessions + one new one: only the new one is parsed,
        # so a stale tool-call history doesn't leak into this run's result.
        sessions_dir = tmp_path / ".moss" / "sessions"
        sessions_dir.mkdir(parents=True)
        _write_session(sessions_dir / "old1.jsonl", [{"name": "read_file", "input": {"path": "OLD"}}])
        _write_session(sessions_dir / "old2.jsonl", [{"name": "exec", "input": {"command": "OLD"}}])
        before = CLIBackend._list_sessions(sessions_dir)
        _write_session(sessions_dir / "new1.jsonl", [{"name": "read_file", "input": {"path": "NEW"}}])
        backend = CLIBackend(moss_command="moss")
        calls = backend._extract_tool_calls(str(tmp_path), before)
        assert len(calls) == 1
        assert calls[0]["args"]["path"] == "NEW"

    def test_no_session_dir_returns_empty(self, tmp_path):
        backend = CLIBackend(moss_command="moss")
        # no .moss/sessions in cwd -> no crash, empty
        assert backend._extract_tool_calls(str(tmp_path), set()) == []
