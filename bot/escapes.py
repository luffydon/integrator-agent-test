# bot/escapes.py
import re
from aiogram import types
from aiogram.dispatcher import Dispatcher, FSMContext

QUIT_RE = re.compile(r'^\s*(quit|exit|cancel|stop)\b', re.I)

_WIRED = False

def wire_escapes(dp: Dispatcher):
    global _WIRED
    if _WIRED:
        return
    _WIRED = True

    @dp.message_handler(commands=["cancel", "quit", "stop"], state="*")
    async def _cancel_cmd(msg: types.Message, state: FSMContext):
        await state.finish()
        await msg.reply("❎ cancelled.")

    @dp.message_handler(lambda m: QUIT_RE.match(m.text or ""), state="*")
    async def _cancel_text(msg: types.Message, state: FSMContext):
        await state.finish()
        await msg.reply("❎ cancelled.")
