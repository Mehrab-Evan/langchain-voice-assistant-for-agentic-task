"""
Diamond Kebab — unified server

One process, one event loop, one brain:
  - HTTP API + web chat UI  (FastAPI)
  - Telegram bot            (python-telegram-bot, long polling)

Run:
    python server.py

Do NOT run this with `--reload` or multiple workers. Each copy would open its
own polling connection and Telegram answers the second one with
"Conflict: terminated by other getUpdates request".
To iterate on web code with reload, set TELEGRAM_ENABLED=0 and run the bot
separately.
"""

from __future__ import annotations

import os
import sys
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "1") != "0"
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
MAX_MESSAGE_CHARS = 4000
FRONTEND_FILES = ("front_end.html", "index.html")


# ==================================================================
# Shared brain — loaded once, used by both the web API and the bot
# ==================================================================

_llm = None
_llm_error: Optional[str] = None
_reset_history = None


def _load_llm() -> None:
    global _llm, _llm_error, _reset_history
    if _llm is not None or _llm_error is not None:
        return
    try:
        from user_response_from_llm import user_response_from_llm
        _llm = user_response_from_llm
    except Exception:
        _llm_error = traceback.format_exc()
        print("\n--- Failed to import user_response_from_llm ---")
        print(_llm_error)
        return
    try:
        from user_response_from_llm import reset_user_history
        _reset_history = reset_user_history
    except Exception:
        _reset_history = None


async def ask_llm(session_id: str, message: str) -> str:
    """The one call site for the model. Blocking, so it runs in a worker thread.

    This matters more than it used to: the bot and the web server now share an
    event loop, so a synchronous LLM call on the loop would freeze both.
    """
    _load_llm()
    if _llm is None:
        raise RuntimeError("LLM module failed to import; see server log.")
    return await run_in_threadpool(_llm, session_id, message)


def new_session_id() -> str:
    # Prefixed so web sessions can't collide with Telegram chat ids (integers).
    return "web:" + uuid.uuid4().hex[:16]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ==================================================================
# Telegram side
# ==================================================================

telegram_app = None          # the PTB Application, once built
telegram_error: Optional[str] = None


def build_telegram_app():
    """Construct the PTB Application. No network I/O happens here."""
    from telegram import Update
    from telegram.ext import (
        Application,
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
    )

    from import_credential import TELEGRAM_BOT_TOKEN
    from telegram_prettier import (
        escape_html_outside_tags,
        format_for_telegram,
        split_message,
    )

    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Welcome to Diamond Kebab. Ask about the menu, or just tell me "
            "what you're hungry for."
        )

    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Your original registered the Python builtin `help` here, which isn't
        # a coroutine and doesn't take (update, context) — /help raised on use.
        await update.message.reply_text(
            "Just type what you want and I'll sort it out.\n"
            "/start — say hello\n"
            "/help — this message"
        )

    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.message.chat.id
        user_message = update.message.text or ""
        if not user_message.strip():
            return

        try:
            ans = await ask_llm(str(chat_id), user_message)
        except Exception:
            traceback.print_exc()
            await update.message.reply_text(
                "The kitchen didn't answer. Try that again in a moment."
            )
            return

        # Telegram-specific formatting stays on this side only; the web UI
        # renders the raw text itself.
        safe = escape_html_outside_tags(format_for_telegram(ans))
        for tag in ("<br>", "<br/>", "<br />"):
            safe = safe.replace(tag, "\n")

        for chunk in split_message(safe):
            await update.message.reply_text(chunk, parse_mode="HTML")

    async def on_error(update, context):
        print("Telegram error on update", update)
        traceback.print_exception(
            type(context.error), context.error, context.error.__traceback__
        )

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    application.add_error_handler(on_error)
    return application


# ==================================================================
# Lifespan — starts the bot alongside the web server, stops it cleanly
# ==================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    global telegram_app, telegram_error

    _load_llm()
    if _llm_error:
        print("WARNING: model not loaded. Web chat returns 503; the bot will "
              "apologise to users until this is fixed.")

    if TELEGRAM_ENABLED:
        try:
            telegram_app = build_telegram_app()
            # run_polling() would try to own the event loop and install signal
            # handlers. These four steps are what it does internally, minus
            # the loop management, so uvicorn stays in charge.
            await telegram_app.initialize()
            await telegram_app.start()
            await telegram_app.updater.start_polling(
                poll_interval=1.0,
                drop_pending_updates=True,
            )
            me = await telegram_app.bot.get_me()
            print("Telegram bot polling as @" + (me.username or "unknown"))
        except Exception:
            telegram_error = traceback.format_exc()
            telegram_app = None
            print("\n--- Telegram bot failed to start (web API unaffected) ---")
            print(telegram_error)
    else:
        print("Telegram disabled (TELEGRAM_ENABLED=0).")

    print("Web UI on http://%s:%d" % (HOST, PORT))

    try:
        yield
    finally:
        if telegram_app is not None:
            print("Stopping Telegram bot...")
            try:
                if telegram_app.updater.running:
                    await telegram_app.updater.stop()
                await telegram_app.stop()
                await telegram_app.shutdown()
            except Exception:
                traceback.print_exc()


app = FastAPI(title="Diamond Kebab", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================================================================
# Web API
# ==================================================================

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    created_at: str


class SessionResponse(BaseModel):
    session_id: str


@app.get("/api/health")
async def health():
    _load_llm()
    return {
        "status": "ok" if _llm_error is None else "llm_import_failed",
        "python": sys.version.split()[0],
        "llm_loaded": _llm is not None,
        "llm_error": _llm_error,
        "telegram": "polling" if telegram_app is not None
                    else ("disabled" if not TELEGRAM_ENABLED else "failed"),
        "telegram_error": telegram_error,
        "time": now_iso(),
    }


@app.post("/api/session", response_model=SessionResponse)
async def create_session():
    return SessionResponse(session_id=new_session_id())


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    message = (payload.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is empty.")
    if len(message) > MAX_MESSAGE_CHARS:
        raise HTTPException(status_code=400, detail="Message is too long.")

    _load_llm()
    if _llm is None:
        raise HTTPException(
            status_code=503,
            detail="The model isn't loaded. Check the server log.",
        )

    session_id = payload.session_id or new_session_id()

    try:
        reply = await ask_llm(session_id, message)
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502, detail="The kitchen didn't answer: " + str(exc)
        ) from exc

    if not isinstance(reply, str) or not reply.strip():
        raise HTTPException(status_code=502, detail="Empty reply from the model.")

    return ChatResponse(
        session_id=session_id, reply=reply.strip(), created_at=now_iso()
    )


@app.delete("/api/session/{session_id}", response_model=SessionResponse)
async def clear_session(session_id: str):
    _load_llm()
    if _reset_history is not None:
        try:
            await run_in_threadpool(_reset_history, session_id)
        except Exception:
            traceback.print_exc()
    return SessionResponse(session_id=new_session_id())


@app.get("/")
async def index():
    for name in FRONTEND_FILES:
        page = BASE_DIR / name
        if page.exists():
            return FileResponse(page)
    raise HTTPException(
        status_code=404,
        detail="No front_end.html or index.html next to server.py.",
    )


# ==================================================================

if __name__ == "__main__":
    import uvicorn

    print("Python", sys.version.split()[0], "| serving from", BASE_DIR)
    uvicorn.run(app, host=HOST, port=PORT)