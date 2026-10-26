"""Shared domain constants."""

from typing import Literal, get_args

# The four event categories used by both meetings and contest subcontest signups.
Category = Literal[
    "Number Sense",
    "General Mathematics",
    "Calculator Applications",
    "General Science",
]
CATEGORIES = get_args(Category)

CATEGORY_EMOJIS = {
    "Number Sense": "🔢",
    "General Mathematics": "➗",
    "Calculator Applications": "🧮",
    "General Science": "🔬",
}

__all__ = ["CATEGORIES", "CATEGORY_EMOJIS", "Category"]
