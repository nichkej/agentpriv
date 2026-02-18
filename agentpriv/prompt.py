def ask_human(name, args, kwargs):
    """Print call details and ask the human for y/n approval."""
    parts = [repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()]
    sig = ", ".join(parts)
    print(f"\nagentpriv: {name}({sig})")
    answer = input("Allow this call? [y/n]: ").strip().lower()
    return answer == "y"
