# agentpriv

sudo for AI agents - allow, deny, or ask before any tool runs.

AI agents run tools autonomously, but some calls are too risky to run unchecked. agentpriv gives you a permission layer to control what goes through.

## Why

- **One place** - guard a tool once, every agent using it gets the same rule
- **Gradual trust** - start on `"ask"`, promote to `"allow"` as you gain confidence
- **Visibility** - every blocked or prompted call is printed with full arguments, so you see exactly what the agent is trying to do
- **Framework agnostic** - plain wrapper around your functions, so it works with any agent framework or none at all

## Install

```
pip install agentpriv
```

## Quick start

```python
from agentpriv import guard, guard_all, AgentPrivDenied

safe_send = guard(send_message, policy="ask")

tools = guard_all(
    [read_messages, send_message, delete_channel],
    policy={
        "delete_*": "deny",
        "send_*":   "ask",
        "*":        "allow",
    }
)
```

## Three modes

| Mode      | What happens                                                      |
| --------- | ----------------------------------------------------------------- |
| `"allow"` | Runs normally, no interruption                                    |
| `"deny"`  | Raises `AgentPrivDenied` immediately, the function never executes |
| `"ask"`   | Pauses, shows the call in your terminal, waits for y/n            |

```
agentpriv: send_message(channel='general', text='deploying now')
Allow this call? [y/n]: y   # runs the function
Allow this call? [y/n]: n   # raises AgentPrivDenied
```

## `on_deny` - raise or return

By default, denied calls raise `AgentPrivDenied`. When using frameworks, set `on_deny="return"` so the LLM sees the denial as a tool result instead of crashing:

```python
# Plain Python - raises exception
safe = guard(delete_channel, policy="deny")

# Frameworks - returns error string to the LLM
safe = guard(delete_channel, policy="deny", on_deny="return")
```

## Works with any framework

Guard first, then pass to your framework as usual:

**OpenAI Agents SDK**

```python
safe_delete = function_tool(guard(delete_db, policy="ask", on_deny="return"))
agent = Agent(name="Demo", tools=[safe_delete])
```

**LangChain / LangGraph**

```python
safe_delete = tool(guard(delete_db, policy="ask", on_deny="return"))
agent = create_agent(model=llm, tools=[safe_delete])
```

**PydanticAI**

```python
agent = Agent("openai:gpt-4o", tools=[guard(delete_db, policy="ask", on_deny="return")])
```

**CrewAI**

```python
safe_delete = tool("Delete DB")(guard(delete_db, policy="ask", on_deny="return"))
agent = Agent(role="DBA", tools=[safe_delete])
```

## Policy matching

- Patterns use glob syntax (`fnmatch`) against the function's `__name__`
- More specific patterns win over wildcards (`delete_channel` > `delete_*` > `*`)
- If a function doesn't match any pattern, it defaults to `"deny"` - so forgetting a rule blocks the call rather than silently allowing it. Use `"*": "allow"` as a catch-all to opt out

## License

MIT
