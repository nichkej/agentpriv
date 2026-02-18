import functools
import inspect
from fnmatch import fnmatch

from .exceptions import AgentPrivDenied
from .prompt import ask_human

VALID_POLICIES = ("allow", "deny", "ask")


def _resolve_policy(name, policy):
    """
    Resolve which policy applies to a function name.

    If policy is a string, return it directly.
    If policy is a dict, find the best matching pattern.
    More specific patterns (fewer wildcards / longer) win over broad ones.
    Falls back to "deny" if nothing matches.
    """
    if isinstance(policy, str):
        if policy not in VALID_POLICIES:
            raise ValueError(f"Invalid policy {policy!r}, must be one of {VALID_POLICIES}")
        return policy

    best_policy = "deny"
    best_specificity = float("-inf")

    for pattern, pol in policy.items():
        if pol not in VALID_POLICIES:
            raise ValueError(f"Invalid policy {pol!r} for pattern {pattern!r}")
        if fnmatch(name, pattern):
            # specificity = number of non-wildcard characters
            specificity = len(pattern.replace("*", "").replace("?", ""))
            if specificity > best_specificity:
                best_specificity = specificity
                best_policy = pol

    return best_policy


def guard(fn, policy="ask", on_deny="raise"):
    """
    Wrap a callable with a permission policy.

    Returns a new callable with the same signature that checks the policy
    before executing. Supports both sync and async functions.

    on_deny controls what happens when a call is denied:
      - "raise": raise AgentPrivDenied (default, good for plain Python)
      - "return": return an error string (good for frameworks like PydanticAI,
        LangChain, etc. where the LLM sees the tool result)
    """
    if on_deny not in ("raise", "return"):
        raise ValueError(f"Invalid on_deny {on_deny!r}, must be 'raise' or 'return'")

    resolved = _resolve_policy(fn.__name__, policy)

    def _denied(reason):
        msg = f"Call to {fn.__name__}() denied by {reason}"
        if on_deny == "return":
            return msg
        raise AgentPrivDenied(msg)

    if inspect.iscoroutinefunction(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            if resolved == "deny":
                return _denied("policy")
            if resolved == "ask" and not ask_human(fn.__name__, args, kwargs):
                return _denied("human")
            return await fn(*args, **kwargs)
    else:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if resolved == "deny":
                return _denied("policy")
            if resolved == "ask" and not ask_human(fn.__name__, args, kwargs):
                return _denied("human")
            return fn(*args, **kwargs)

    return wrapper


def guard_all(fns, policy=None):
    """
    Wrap a list of callables with a policy dict.

    Policy is a dict mapping glob patterns to policy strings.
    Returns a list of wrapped callables in the same order.
    """
    if policy is None:
        policy = {"*": "ask"}
    return [guard(fn, policy) for fn in fns]
