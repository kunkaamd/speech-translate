"""
WebSocket proxy: Chrome extension → proxy:8001 → WLK:8000
Splits transcript into sentences, translates to Vietnamese via Ollama.
Each translated sentence becomes its own line in the extension.
"""
import asyncio
import json
import re
import httpx
import websockets
from websockets.server import serve

WLK_URL = "ws://localhost:8000/asr"
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2:3b"
MAX_DISPLAY_LINES = 5

SENTENCE_END = re.compile(r'(?<=[.!?])\s+')
NOISE = re.compile(r'\[.*?\]|>>\s*')


def clean(text: str) -> str:
    return NOISE.sub("", text).strip()


async def translate(text: str, client: httpx.AsyncClient) -> str:
    text = clean(text)
    if not text:
        return ""
    resp = await client.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "stream": False,
            "options": {"temperature": 0.1},
            "messages": [
                {"role": "system", "content": "You are a translator. Translate the user's text to Vietnamese. Reply with ONLY the Vietnamese translation. Never use Chinese, English, or any other language in your response."},
                {"role": "user", "content": text},
            ],
        },
        timeout=15,
    )
    return resp.json()["message"]["content"].strip()


async def handle(client_ws):
    print("Client connected")

    # Accumulated translated sentences (each is one display line)
    vi_sentences: list[str] = []
    # How many chars of the full transcript we've already processed
    translated_end: int = 0
    pending: bool = False
    translate_queue: asyncio.Queue = asyncio.Queue()

    # Template for a line object (speaker=1 = normal line)
    def make_line(text: str) -> dict:
        return {"speaker": 1, "text": text, "start": None, "end": None}

    async with websockets.connect(WLK_URL) as wlk_ws:
        async with httpx.AsyncClient() as http:

            async def translation_worker():
                nonlocal pending
                while True:
                    sentence = await translate_queue.get()
                    try:
                        vi = await translate(sentence, http)
                        if vi:
                            vi_sentences.append(vi)
                            print(f"  {sentence!r}\n  → {vi!r}")
                    except Exception as e:
                        print(f"  translate error: {e}")
                        vi_sentences.append(clean(sentence))
                    finally:
                        pending = False
                        translate_queue.task_done()

            asyncio.ensure_future(translation_worker())

            async def fwd_audio():
                async for msg in client_ws:
                    await wlk_ws.send(msg)

            async def fwd_transcript():
                nonlocal translated_end, pending

                async for msg in wlk_ws:
                    data = json.loads(msg)

                    # Collect full transcript from all WLK lines
                    wlk_lines = data.get("lines", [])
                    full_text = " ".join(
                        line.get("text", "").strip()
                        for line in wlk_lines
                        if line.get("text", "").strip()
                    )

                    # Find new complete sentences since last translated position
                    if not pending:
                        remaining = full_text[translated_end:]
                        parts = SENTENCE_END.split(remaining)
                        complete = parts[:-1]  # all but last (incomplete)
                        if complete:
                            sentence = " ".join(complete)
                            translated_end += len(sentence) + 1
                            pending = True
                            await translate_queue.put(sentence)

                    # Build output lines: last N translated + current partial
                    out_lines = [make_line(s) for s in vi_sentences[-MAX_DISPLAY_LINES:]]

                    # Current partial (untranslated, show in original)
                    partial = full_text[translated_end:].strip()
                    buffer_vi = data.get("buffer_transcription", "")

                    data["lines"] = out_lines
                    data["buffer_transcription"] = partial + (" " + buffer_vi if buffer_vi else "")

                    await client_ws.send(json.dumps(data))

            try:
                await asyncio.gather(fwd_audio(), fwd_transcript())
            except websockets.exceptions.ConnectionClosed:
                pass

    print("Client disconnected")


async def main():
    print("Proxy running on ws://localhost:8001")
    print(f"Model: {MODEL} | Max lines: {MAX_DISPLAY_LINES}")
    async with serve(handle, "localhost", 8001):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
