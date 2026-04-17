from __future__ import annotations

import asyncio
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, Request

from backend.config import settings
from integrations.telegram_client import TelegramClient
from runner.agent import ClaudeCodeAgent
from services.executor import LocalExecutor
from services.log_store import MessageLogStore
from services.sanitizer import sanitize_command

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram-laptop-agent")

app = FastAPI(title="Telegram Laptop Agent")
incoming_queue: asyncio.Queue[IncomingMessage] = asyncio.Queue()
logs = MessageLogStore()

telegram = TelegramClient(bot_token=settings.telegram_bot_token)

executor = LocalExecutor(
    allowed_root=settings.allowed_root,
    timeout_seconds=settings.command_timeout_seconds,
    max_output_chars=settings.max_output_chars,
)
allowed_commands_set = {cmd.strip() for cmd in settings.allowed_commands.split(",") if cmd.strip()}
project_root = Path(settings.allowed_root).resolve()

agent = ClaudeCodeAgent(
    project_dir=settings.allowed_root,
    max_turns=settings.max_agent_turns,
    timeout=settings.command_timeout_seconds * 20,  # generous CLI timeout
)
logger.info("Using Claude Code agent  cwd=%s  max_turns=%d", settings.allowed_root, settings.max_agent_turns)


# ── message model ────────────────────────────────────────────────────

@dataclass
class IncomingMessage:
    chat_id: int
    from_id: int
    text: str
    thread_id: int | None = None
    voice_file_id: str | None = None


# ── voice transcription ─────────────────────────────────────────────

async def transcribe_voice(file_id: str) -> str:
    """Download a Telegram voice file and transcribe it via speech_recognition."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ogg_path = Path(tmpdir) / "voice.ogg"
        wav_path = Path(tmpdir) / "voice.wav"

        ok = await telegram.download_file(file_id, ogg_path)
        if not ok:
            return "[could not download voice message]"

        # Convert OGG→WAV via ffmpeg
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-i", str(ogg_path), "-ar", "16000", "-ac", "1", str(wav_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        if proc.returncode != 0 or not wav_path.exists():
            return "[ffmpeg conversion failed — is ffmpeg installed?]"

        # Transcribe
        try:
            import speech_recognition as sr  # type: ignore[import-untyped]
        except ImportError:
            return "[speech_recognition not installed — run: pip install SpeechRecognition]"

        recognizer = sr.Recognizer()
        with sr.AudioFile(str(wav_path)) as source:
            audio = recognizer.record(source)

        try:
            return recognizer.recognize_google(audio)  # type: ignore[no-any-return]
        except sr.UnknownValueError:
            return "[could not understand audio]"
        except sr.RequestError as e:
            return f"[speech recognition error: {e}]"


# ── session key helper ───────────────────────────────────────────────

def _session_key(chat_id: int, thread_id: int | None) -> str:
    """Unique key for agent session: uses thread_id when in a topic."""
    if thread_id is not None:
        return f"{chat_id}:{thread_id}"
    return str(chat_id)


# ── long-response → PDF ─────────────────────────────────────────────

def _text_to_pdf(text: str, dest: Path) -> None:
    """Write *text* to a simple PDF at *dest* using fpdf2."""
    from fpdf import FPDF  # type: ignore[import-untyped]

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Courier", size=9)
    for line in text.split("\n"):
        pdf.multi_cell(0, 4, line)
    pdf.output(str(dest))


async def _send_response(
    chat_id: int,
    text: str,
    *,
    thread_id: int | None = None,
) -> None:
    """Send text as message; if it exceeds the threshold, send as a PDF instead."""
    if len(text) <= settings.pdf_threshold:
        await telegram.send_message(chat_id, text, thread_id=thread_id)
        return

    # Long response → generate PDF and send as document
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "response.pdf"
        _text_to_pdf(text, pdf_path)
        # Still send a short preview
        preview = text[: 300].rstrip() + "\n\n… (full response attached as PDF)"
        await telegram.send_message(chat_id, preview, thread_id=thread_id)
        await telegram.send_document(chat_id, pdf_path, caption="📄 Full response", thread_id=thread_id)


@app.on_event("startup")
async def startup() -> None:
    asyncio.create_task(worker())


async def worker() -> None:
    while True:
        msg = await incoming_queue.get()
        chat_id = msg.chat_id
        thread_id = msg.thread_id
        try:
            # Transcribe voice if needed
            text = msg.text
            if msg.voice_file_id:
                await telegram.send_message(chat_id, "🎙️ Transcribing voice…", thread_id=thread_id)
                text = await transcribe_voice(msg.voice_file_id)
                if text.startswith("["):
                    await telegram.send_message(chat_id, text, thread_id=thread_id)
                    continue
                await telegram.send_message(chat_id, f"🎙️ \"{text}\"", thread_id=thread_id)

            # Acknowledge receipt immediately
            await telegram.send_message(chat_id, "Got it ✓", thread_id=thread_id)

            # Show typing indicator while agent is working
            stop_typing = asyncio.Event()

            async def _typing_loop() -> None:
                elapsed = 0
                while not stop_typing.is_set():
                    try:
                        await telegram.send_chat_action(chat_id, thread_id=thread_id)
                    except Exception:
                        pass
                    await asyncio.sleep(5)
                    elapsed += 5
                    if elapsed % 30 == 0 and not stop_typing.is_set():
                        try:
                            await telegram.send_message(
                                chat_id,
                                f"\u23f3 Still working... ({elapsed}s)",
                                thread_id=thread_id,
                            )
                        except Exception:
                            pass

            typing_task = asyncio.create_task(_typing_loop())
            try:
                response, files = await dispatch_message(chat_id, text, thread_id)
            finally:
                stop_typing.set()
                typing_task.cancel()
            logs.add("out", chat_id, response)
            await _send_response(chat_id, response, thread_id=thread_id)

            # Send files extracted from agent response or /file command
            for fp in files:
                await telegram.send_document(chat_id, Path(fp), caption=f"📎 {Path(fp).name}", thread_id=thread_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to process message")
            error_message = f"❌ Internal error: {exc}"
            logs.add("out", chat_id, error_message)
            await telegram.send_message(chat_id, error_message, thread_id=thread_id)
        finally:
            incoming_queue.task_done()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook")
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(default=None)) -> dict[str, bool]:
    if settings.telegram_webhook_secret and x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        logger.warning("Rejected webhook request: invalid secret token")
        return {"ok": True}

    payload = await request.json()
    msg = extract_message(payload)
    if not msg:
        return {"ok": True}

    logs.add("in", msg.chat_id, msg.text or "(voice)")

    if msg.chat_id != settings.telegram_chat_id:
        logger.info("Ignoring unauthorized chat_id=%s", msg.chat_id)
        return {"ok": True}

    await incoming_queue.put(msg)
    return {"ok": True}


def extract_message(payload: dict[str, Any]) -> IncomingMessage | None:
    message = payload.get("message") or payload.get("edited_message")
    if not message:
        return None

    chat = message.get("chat", {})
    sender = message.get("from", {})
    if "id" not in chat or "id" not in sender:
        return None

    chat_id = int(chat["id"])
    from_id = int(sender["id"])
    thread_id = message.get("message_thread_id")

    # Voice message
    voice = message.get("voice") or message.get("audio")
    if voice and "file_id" in voice:
        caption = (message.get("caption") or "").strip()
        return IncomingMessage(
            chat_id=chat_id,
            from_id=from_id,
            text=caption,
            thread_id=thread_id,
            voice_file_id=voice["file_id"],
        )

    # Text message
    text = message.get("text")
    if not isinstance(text, str):
        return None

    return IncomingMessage(
        chat_id=chat_id,
        from_id=from_id,
        text=text.strip(),
        thread_id=thread_id,
    )


async def dispatch_message(chat_id: int, text: str, thread_id: int | None = None) -> tuple[str, list[str]]:
    """Returns (response_text, list_of_files_to_send)."""
    skey = _session_key(chat_id, thread_id)

    if text.startswith("/status"):
        return "✅ Server is running and webhook is active.", []

    if text.startswith("/logs"):
        return logs.tail(15), []

    if text.startswith("/new"):
        name = text[4:].strip() or "New session"
        # Try to create a forum topic for the new session
        new_thread = await telegram.create_forum_topic(chat_id, name)
        if new_thread is not None:
            new_skey = _session_key(chat_id, new_thread)
            agent.new_session(new_skey)
            return f"🔄 Created topic \"{name}\". Switch to it to continue.", []
        # Fallback: just reset session in current context
        agent.new_session(skey)
        return "🔄 New conversation started. What would you like to do?", []

    if text.startswith("/file"):
        raw_path = text[5:].strip()
        if not raw_path:
            return "Usage: /file <path>  — sends you the file", []
        fp = Path(raw_path).expanduser().resolve()
        if not fp.exists() or not fp.is_file():
            return f"❌ File not found: {raw_path}", []
        return f"📎 Sending {fp.name}", [str(fp)]

    if text.startswith("/run"):
        command = text[4:].strip()
        if not command:
            return "Usage: /run <command>", []
        ok, reason = sanitize_command(command, allowed_commands_set)
        if not ok:
            return f"❌ Blocked: {reason}", []
        output = await executor.run_command(command)
        return f"🧠 Executed:\n`{command}`\n\n{output}", []

    # Everything else → Claude Code agent (with conversation memory)
    response, files = await agent.run(text, skey)
    return response, files
