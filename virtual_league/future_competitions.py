"""Placeholders for competitions intentionally left out of stage 1."""

TODO_COMPETITIONS = [
    "promotion_relegation_playoffs",
    "final_round",
]


def todo_messages() -> list[str]:
    return [f"TODO: implement {name}" for name in TODO_COMPETITIONS]
