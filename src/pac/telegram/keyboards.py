from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

CALLBACK_REDISTRIBUTE_RECALC = "redistribute:recalculate"


def pac_plan_keyboard() -> InlineKeyboardMarkup:
    """Build inline keyboard for PAC plan messages."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔄 Recalculate",
                    callback_data=CALLBACK_REDISTRIBUTE_RECALC,
                ),
            ],
        ]
    )
