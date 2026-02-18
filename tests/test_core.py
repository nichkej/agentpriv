import asyncio
import inspect
from unittest.mock import patch

import pytest

from agentpriv import AgentPrivDenied, guard, guard_all


# --- helpers ---

def read_messages():
    return ["msg1", "msg2"]

def send_message(channel, text):
    return f"sent to {channel}: {text}"

def delete_channel(name):
    return f"deleted {name}"

def delete_repo(name):
    return f"deleted repo {name}"

async def async_read():
    return "async result"

async def async_delete(name):
    return f"async deleted {name}"


# --- guard() ---

class TestGuardAllow:
    def test_runs_normally(self):
        safe = guard(read_messages, policy="allow")
        assert safe() == read_messages()

    def test_passes_args(self):
        safe = guard(send_message, policy="allow")
        assert safe("general", text="hello") == send_message("general", text="hello")


class TestGuardDeny:
    def test_raises(self):
        safe = guard(delete_channel, policy="deny")
        with pytest.raises(AgentPrivDenied, match="denied by policy"):
            safe("general")

    def test_never_calls_function(self):
        calls = []
        def tracked():
            calls.append(1)
        safe = guard(tracked, policy="deny")
        with pytest.raises(AgentPrivDenied):
            safe()
        assert calls == []


class TestGuardAsk:
    @patch("agentpriv.core.ask_human", return_value=True)
    def test_approved(self, mock_ask):
        safe = guard(send_message, policy="ask")
        assert safe("general", text="hi") == send_message("general", text="hi")
        mock_ask.assert_called_once_with("send_message", ("general",), {"text": "hi"})

    @patch("agentpriv.core.ask_human", return_value=False)
    def test_denied(self, _):
        safe = guard(send_message, policy="ask")
        with pytest.raises(AgentPrivDenied, match="denied by human"):
            safe("general", text="hi")


class TestGuardAsync:
    def test_allow(self):
        safe = guard(async_read, policy="allow")
        assert inspect.iscoroutinefunction(safe)
        assert asyncio.run(safe()) == asyncio.run(async_read())

    def test_deny(self):
        safe = guard(async_delete, policy="deny")
        assert inspect.iscoroutinefunction(safe)
        with pytest.raises(AgentPrivDenied):
            asyncio.run(safe("general"))

    @patch("agentpriv.core.ask_human", return_value=True)
    def test_ask_approved(self, _):
        safe = guard(async_read, policy="ask")
        assert asyncio.run(safe()) == asyncio.run(async_read())


# --- guard_all() ---

class TestGuardAll:
    def _make_tools(self, policy):
        return guard_all(
            [read_messages, send_message, delete_channel, delete_repo],
            policy=policy,
        )

    def test_deny_pattern(self):
        tools = self._make_tools({"delete_*": "deny", "*": "allow"})
        assert tools[0]() == read_messages()
        with pytest.raises(AgentPrivDenied):
            tools[2]("general")

    @patch("agentpriv.core.ask_human", return_value=True)
    def test_ask_pattern(self, _):
        tools = self._make_tools({"send_*": "ask", "*": "allow"})
        assert tools[1]("general", text="hi") == send_message("general", text="hi")

    def test_no_match_defaults_to_deny(self):
        tools = self._make_tools({"send_*": "allow"})
        with pytest.raises(AgentPrivDenied):
            tools[0]()

    def test_specific_pattern_wins(self):
        tools = self._make_tools({
            "delete_channel": "allow",
            "delete_*": "deny",
            "*": "allow",
        })
        assert tools[2]("general") == delete_channel("general")
        with pytest.raises(AgentPrivDenied):
            tools[3]("myrepo")

    def test_default_policy_is_ask(self):
        tools = guard_all([read_messages])
        with patch("agentpriv.core.ask_human", return_value=False):
            with pytest.raises(AgentPrivDenied):
                tools[0]()


# --- on_deny="return" ---

class TestOnDenyReturn:
    def test_deny_returns_string(self):
        safe = guard(delete_channel, policy="deny", on_deny="return")
        result = safe("general")
        assert isinstance(result, str)
        assert "denied by policy" in result

    @patch("agentpriv.core.ask_human", return_value=False)
    def test_ask_denied_returns_string(self, _):
        safe = guard(send_message, policy="ask", on_deny="return")
        result = safe("general", text="hi")
        assert isinstance(result, str)
        assert "denied by human" in result

    def test_async_deny_returns_string(self):
        safe = guard(async_delete, policy="deny", on_deny="return")
        result = asyncio.run(safe("general"))
        assert isinstance(result, str)
        assert "denied by policy" in result


# --- edge cases ---

class TestEdgeCases:
    def test_invalid_policy(self):
        with pytest.raises(ValueError):
            guard(read_messages, policy="yolo")

    def test_invalid_policy_in_dict(self):
        with pytest.raises(ValueError):
            guard_all([read_messages], policy={"*": "yolo"})

    def test_invalid_on_deny(self):
        with pytest.raises(ValueError):
            guard(read_messages, policy="deny", on_deny="explode")

    def test_preserves_function_name(self):
        safe = guard(send_message, policy="allow")
        assert safe.__name__ == "send_message"

    def test_preserves_docstring(self):
        def documented():
            """My doc."""
            pass
        safe = guard(documented, policy="allow")
        assert safe.__doc__ == "My doc."
