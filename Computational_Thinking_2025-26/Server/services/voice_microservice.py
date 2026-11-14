from __future__ import annotations

import asyncio
import base64
import logging
import math
import os
import time
from collections import deque
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from typing import Awaitable, Deque, Optional, TypeVar, Union

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

load_dotenv()

logger = logging.getLogger("voice_tutor")

MODEL_NAME = "gemini-3.1-flash-live-preview"
INPUT_AUDIO_MIME_TYPE = "audio/pcm;rate=16000"

# 16 kHz, 16-bit mono PCM = 32 bytes/ms
INPUT_BYTES_PER_MS = 32.0
# Gemini Live outputs 24 kHz, 16-bit mono PCM = 48,000 bytes/sec
OUTPUT_BYTES_PER_SECOND = 48000.0

API_KEY = os.getenv("API_KEY1") or os.getenv("GEMINI_API_KEY")

INPUT_QUEUE_SIZE = int(os.getenv("VOICE_INPUT_QUEUE_SIZE", "128"))
OUTPUT_QUEUE_SIZE = int(os.getenv("VOICE_OUTPUT_QUEUE_SIZE", "256"))
BACKPRESSURE_TIMEOUT_SECONDS = float(
    os.getenv("VOICE_BACKPRESSURE_TIMEOUT_SECONDS", "10"),
)
MAX_AUDIO_FRAME_BYTES = int(
    os.getenv("VOICE_MAX_AUDIO_FRAME_BYTES", str(64 * 1024)),
)

TURN_FINALIZATION_TIMEOUT_SECONDS = 30.0

# Adaptive Server-Side VAD / Noise Gate settings
SPEECH_RMS_THRESHOLD = float(os.getenv("VOICE_SPEECH_RMS_THRESHOLD", "380.0"))
PRE_ROLL_MS = float(os.getenv("VOICE_PRE_ROLL_MS", "300.0"))
SPEECH_START_MS = float(os.getenv("VOICE_SPEECH_START_MS", "60.0"))
SILENCE_END_MS = float(os.getenv("VOICE_SILENCE_DURATION_MS", "700.0"))
NATURAL_TAIL_MS = 200.0
ECHO_GUARD_TAIL_SECONDS = float(os.getenv("VOICE_ECHO_TAIL_SECONDS", "0.12"))
ALLOW_BARGE_IN = os.getenv("VOICE_ALLOW_BARGE_IN", "0") == "1"

MAX_MEMORY_TURNS = 16
MAX_MEMORY_FIELD_CHARS = 900

VOICE_SYSTEM_PROMPT = """
You are a friendly, patient, and concise AI Computational Thinking Tutor.
Speak naturally and conversationally in English.

CRITICAL BEHAVIOR RULES:
1. Maintain natural continuity across the conversation using the [CONVERSATION_HISTORY] below.
2. Answer only the student's newest utterance—never re-answer a completed turn unless asked.
3. Keep spoken responses brief, encouraging, and directly to the point (2 to 4 sentences).
4. Guide the student step by step using Socratic questions rather than giving away the final answer immediately.
""".strip()

END_OF_SPEECH = "END_OF_SPEECH"


class BrowserClosed(Exception):
    pass


class GeminiDisconnected(Exception):
    pass


class BackpressureExceeded(Exception):
    pass


@dataclass(frozen=True)
class AudioEvent:
    turn_id: int
    data: bytes


@dataclass(frozen=True)
class EndOfSpeechEvent:
    turn_id: int


BrowserEvent = Union[AudioEvent, EndOfSpeechEvent]
T = TypeVar("T")


@dataclass
class TurnResult:
    user_text: str
    assistant_text: str
    interrupted: bool = False


def _compute_pcm16_rms(audio_bytes: bytes) -> float:
    """
    Zero-dependency 16-bit little-endian PCM RMS calculation.
    """
    valid_len = len(audio_bytes) & ~1
    if valid_len < 2:
        return 0.0

    samples = memoryview(audio_bytes)[:valid_len].cast("h")
    sample_count = len(samples)
    if sample_count == 0:
        return 0.0

    energy = sum(s * s for s in samples)
    return math.sqrt(energy / sample_count)


def _compact_text(value: Optional[str], max_chars: int) -> str:
    if not value:
        return ""

    text = " ".join(value.split())
    text = text.replace("[", "(").replace("]", ")")

    if len(text) <= max_chars:
        return text

    return text[: max_chars - 3].rstrip() + "..."


def _append_transcript(existing: str, incoming: Optional[str]) -> str:
    if not incoming:
        return existing

    if not existing:
        return incoming

    if len(incoming) > len(existing) and incoming.startswith(existing):
        return incoming

    if existing.endswith((" ", "\n")) or incoming.startswith(
        (" ", "\n", ".", ",", "?", "!", ";", ":", "'")
    ):
        return existing + incoming

    return f"{existing} {incoming}"


def _make_memory_entry(turn: TurnResult) -> Optional[str]:
    user_text = _compact_text(turn.user_text, MAX_MEMORY_FIELD_CHARS)
    assistant_text = _compact_text(turn.assistant_text, MAX_MEMORY_FIELD_CHARS)

    if not user_text and not assistant_text:
        return None

    user_value = user_text or "(student spoke)"
    if assistant_text:
        suffix = " (interrupted)" if turn.interrupted else ""
        assistant_value = f"{assistant_text}{suffix}"
    else:
        assistant_value = "(no completed tutor response)"

    return f"Student: {user_value}\nTutor: {assistant_value}"


def _build_system_instruction(memory: Deque[str]) -> types.Content:
    instruction = VOICE_SYSTEM_PROMPT

    if memory:
        instruction += (
            "\n\n[CONVERSATION_HISTORY]\n"
            "Below is the chronological transcript of the session so far. "
            "Use it to remember what you and the student have discussed, "
            "and respond naturally to the student's new utterance:\n\n"
            + "\n\n".join(memory)
            + "\n[/CONVERSATION_HISTORY]"
        )

    return types.Content(
        parts=[types.Part.from_text(text=instruction)],
    )


def _server_indicates_turn_complete(server_content: object) -> bool:
    if bool(getattr(server_content, "turn_complete", False)):
        return True

    status = getattr(server_content, "interaction_status", None)
    if status is None:
        return False

    candidates = {
        str(status).upper(),
        str(getattr(status, "name", "")).upper(),
        str(getattr(status, "value", "")).upper(),
    }

    return bool(
        candidates.intersection({"IDLE", "INTERACTION_STATUS_IDLE"}),
    )


async def _cancel_and_wait(task: asyncio.Task) -> None:
    if not task.done():
        task.cancel()

    await asyncio.gather(task, return_exceptions=True)


class VoiceSession:
    """
    Manages one long-lived browser WebSocket session.
    Rotates the underlying Gemini Live connection immediately after every
    completed model turn to bypass Issue #2935 while preserving memory and
    buffered input audio.
    """

    def __init__(self, websocket: WebSocket, session_id: str) -> None:
        self.websocket = websocket
        self.session_id = session_id

        self.browser_closed = asyncio.Event()

        self.input_events: asyncio.Queue[BrowserEvent] = asyncio.Queue(
            maxsize=INPUT_QUEUE_SIZE,
        )
        self.output_audio: asyncio.Queue[bytes] = asyncio.Queue(
            maxsize=OUTPUT_QUEUE_SIZE,
        )

        # Turn IDs
        self.next_input_turn_id = 0
        self.open_input_turn_id: Optional[int] = None
        self.drop_through_turn_id = 0

        # Accurate non-cumulative browser playback clock
        self.output_playhead_monotonic = 0.0
        self.audible_playback_until_monotonic = 0.0
        self.model_generating = False

        # Self-calibrating adaptive noise gate state
        self.noise_floor_rms: Optional[float] = None
        self.calibration_ms = 0.0
        self.pre_roll_frames: Deque[bytes] = deque()
        self.pre_roll_ms = 0.0
        self.speech_active = False
        self.turn_peak_rms = 0.0
        self.consecutive_speech_ms = 0.0
        self.trailing_silence_ms = 0.0

        self.close_code = 1000

    def request_close(self, code: int) -> None:
        if self.close_code == 1000:
            self.close_code = code
        self.browser_closed.set()

    def is_model_playing(self) -> bool:
        """
        True only while Gemini is actively generating audio or while audible
        tutor speech is still playing in the browser.
        """
        if self.model_generating:
            return True
        if self.audible_playback_until_monotonic <= 0.0:
            return False
        return time.monotonic() < (
            self.audible_playback_until_monotonic + ECHO_GUARD_TAIL_SECONDS
        )

    def record_output_audio_duration(self, audio_data: bytes) -> None:
        """
        Tracks exact browser playback duration without adding ECHO_GUARD_TAIL_SECONDS
        per chunk, and ignores trailing silent PCM chunks from Gemini.
        """
        duration_sec = len(audio_data) / OUTPUT_BYTES_PER_SECOND
        now = time.monotonic()
        self.output_playhead_monotonic = (
            max(now, self.output_playhead_monotonic) + duration_sec
        )
        # Only extend echo guard for chunks containing audible speech
        if _compute_pcm16_rms(audio_data) > 100.0:
            self.audible_playback_until_monotonic = (
                self.output_playhead_monotonic
            )

    def clear_model_audio(self) -> None:
        self.model_generating = False
        self.output_playhead_monotonic = 0.0
        self.audible_playback_until_monotonic = 0.0
        while True:
            try:
                self.output_audio.get_nowait()
            except asyncio.QueueEmpty:
                return

    def _reset_gate_state(self) -> None:
        self.speech_active = False
        self.turn_peak_rms = 0.0
        self.consecutive_speech_ms = 0.0
        self.trailing_silence_ms = 0.0
        self.open_input_turn_id = None
        self.pre_roll_frames.clear()
        self.pre_roll_ms = 0.0

    def mark_turn_dropped(self, turn_id: Optional[int]) -> None:
        if turn_id is None:
            return
        self.drop_through_turn_id = max(self.drop_through_turn_id, turn_id)
        if (
            self.open_input_turn_id is not None
            and self.open_input_turn_id <= self.drop_through_turn_id
        ):
            self._reset_gate_state()

    def should_drop_turn(self, turn_id: int) -> bool:
        return turn_id <= self.drop_through_turn_id

    def _push_pre_roll(self, frame: bytes, frame_ms: float) -> None:
        self.pre_roll_frames.append(frame)
        self.pre_roll_ms += frame_ms
        while self.pre_roll_ms > PRE_ROLL_MS and len(self.pre_roll_frames) > 1:
            removed = self.pre_roll_frames.popleft()
            self.pre_roll_ms -= len(removed) / INPUT_BYTES_PER_MS

    async def _race_with_close(self, awaitable: Awaitable[T]) -> T:
        operation_task = asyncio.ensure_future(awaitable)
        closed_task = asyncio.create_task(self.browser_closed.wait())

        try:
            done, _ = await asyncio.wait(
                (operation_task, closed_task),
                return_when=asyncio.FIRST_COMPLETED,
            )
            if closed_task in done:
                raise BrowserClosed
            return operation_task.result()
        finally:
            await _cancel_and_wait(operation_task)
            await _cancel_and_wait(closed_task)

    async def _put_or_close(
        self,
        target_queue: asyncio.Queue,
        value: object,
    ) -> None:
        if self.browser_closed.is_set():
            raise BrowserClosed

        try:
            target_queue.put_nowait(value)
            return
        except asyncio.QueueFull:
            pass

        blocked_put = self._race_with_close(target_queue.put(value))
        if BACKPRESSURE_TIMEOUT_SECONDS <= 0:
            await blocked_put
            return

        try:
            await asyncio.wait_for(
                blocked_put,
                timeout=BACKPRESSURE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError as exc:
            raise BackpressureExceeded("Realtime queue remained full") from exc

    async def _next_input_event(self) -> BrowserEvent:
        try:
            return self.input_events.get_nowait()
        except asyncio.QueueEmpty:
            return await self._race_with_close(self.input_events.get())

    async def put_input_event(self, event: BrowserEvent) -> None:
        await self._put_or_close(self.input_events, event)

    async def put_output_audio(self, audio_data: bytes) -> None:
        self.record_output_audio_duration(audio_data)
        await self._put_or_close(self.output_audio, audio_data)

    async def _process_incoming_pcm(self, audio_bytes: bytes) -> None:
        """
        Self-calibrating noise gate & peak-relative VAD.
        Automatically opens on human speech and automatically closes when
        speech drops back to ambient room level, so muting is never required.
        """
        frame_ms = max(len(audio_bytes) / INPUT_BYTES_PER_MS, 1.0)
        rms = _compute_pcm16_rms(audio_bytes)

        # 1. Calibrate ambient noise floor on the very first 200ms of audio
        if self.noise_floor_rms is None:
            self.noise_floor_rms = max(rms, 80.0)
        elif self.calibration_ms < 200.0 and not self.speech_active:
            self.calibration_ms += frame_ms
            self.noise_floor_rms = 0.75 * self.noise_floor_rms + 0.25 * rms
            self._push_pre_roll(audio_bytes, frame_ms)
            return

        # 2. Suppress speaker echo while tutor audio is playing in the browser
        if self.is_model_playing() and not ALLOW_BARGE_IN:
            if self.speech_active and self.open_input_turn_id is not None:
                finished_turn_id = self.open_input_turn_id
                self._reset_gate_state()
                await self.put_input_event(
                    EndOfSpeechEvent(turn_id=finished_turn_id),
                )
            else:
                self._reset_gate_state()
            return

        noise_floor = min(max(self.noise_floor_rms, 80.0), 2500.0)
        start_threshold = max(SPEECH_RMS_THRESHOLD, noise_floor * 2.1)
        keep_threshold = max(SPEECH_RMS_THRESHOLD * 0.65, noise_floor * 1.45)

        if not self.speech_active:
            if rms >= start_threshold:
                self.consecutive_speech_ms += frame_ms
                self.turn_peak_rms = max(self.turn_peak_rms, rms)
                self._push_pre_roll(audio_bytes, frame_ms)

                if self.consecutive_speech_ms >= SPEECH_START_MS:
                    self.speech_active = True
                    self.trailing_silence_ms = 0.0
                    self.next_input_turn_id += 1
                    self.open_input_turn_id = self.next_input_turn_id

                    if self.is_model_playing() and ALLOW_BARGE_IN:
                        self.clear_model_audio()

                    while self.pre_roll_frames:
                        pre_frame = self.pre_roll_frames.popleft()
                        await self.put_input_event(
                            AudioEvent(
                                turn_id=self.open_input_turn_id,
                                data=pre_frame,
                            ),
                        )
                    self.pre_roll_ms = 0.0
            else:
                self.consecutive_speech_ms = 0.0
                self.turn_peak_rms = 0.0
                # Adapt ambient noise floor during non-speech
                alpha = 0.12 if rms < self.noise_floor_rms else 0.03
                self.noise_floor_rms = (
                    (1.0 - alpha) * self.noise_floor_rms + alpha * rms
                )
                self._push_pre_roll(audio_bytes, frame_ms)
            return

        # 3. Speech is active: use both floor threshold and peak-relative drop
        assert self.open_input_turn_id is not None
        if rms > self.turn_peak_rms:
            self.turn_peak_rms = rms
        else:
            # Gentle peak decay across long sentences
            self.turn_peak_rms = max(
                self.turn_peak_rms * 0.995,
                start_threshold,
            )

        dynamic_keep_threshold = max(
            keep_threshold,
            self.turn_peak_rms * 0.30,
        )

        if rms >= dynamic_keep_threshold:
            self.trailing_silence_ms = 0.0
            await self.put_input_event(
                AudioEvent(turn_id=self.open_input_turn_id, data=audio_bytes),
            )
            return

        # 4. User stopped speaking (energy dropped back toward ambient floor)
        self.trailing_silence_ms += frame_ms
        # Slowly adapt noise floor toward the quiet post-speech level
        self.noise_floor_rms = 0.96 * self.noise_floor_rms + 0.04 * rms

        if self.trailing_silence_ms <= NATURAL_TAIL_MS:
            payload = audio_bytes
        else:
            payload = b"\x00" * len(audio_bytes)

        await self.put_input_event(
            AudioEvent(turn_id=self.open_input_turn_id, data=payload),
        )

        if self.trailing_silence_ms >= SILENCE_END_MS:
            finished_turn_id = self.open_input_turn_id
            self._reset_gate_state()
            await self.put_input_event(
                EndOfSpeechEvent(turn_id=finished_turn_id),
            )

    async def browser_reader(self) -> None:
        try:
            while not self.browser_closed.is_set():
                message = await self.websocket.receive()

                if message.get("type") == "websocket.disconnect":
                    return

                if message.get("type") != "websocket.receive":
                    continue

                raw_audio = message.get("bytes")
                if raw_audio is not None:
                    audio_bytes = bytes(raw_audio)
                    if not audio_bytes:
                        continue

                    if len(audio_bytes) > MAX_AUDIO_FRAME_BYTES:
                        logger.warning(
                            "Audio frame too large session=%s bytes=%d",
                            self.session_id,
                            len(audio_bytes),
                        )
                        self.request_close(1009)
                        return

                    await self._process_incoming_pcm(audio_bytes)
                    continue

                text = message.get("text")
                if text == END_OF_SPEECH and self.open_input_turn_id is not None:
                    finished_turn_id = self.open_input_turn_id
                    self._reset_gate_state()
                    await self.put_input_event(
                        EndOfSpeechEvent(turn_id=finished_turn_id),
                    )

        except BrowserClosed:
            pass
        except BackpressureExceeded:
            logger.warning(
                "Input backpressure exceeded session=%s",
                self.session_id,
            )
            self.request_close(1013)
        except WebSocketDisconnect:
            pass
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Browser reader failed session=%s", self.session_id)
        finally:
            self.browser_closed.set()

    async def browser_writer(self) -> None:
        try:
            while not self.browser_closed.is_set():
                audio_data = await self._race_with_close(
                    self.output_audio.get(),
                )

                if BACKPRESSURE_TIMEOUT_SECONDS > 0:
                    await asyncio.wait_for(
                        self.websocket.send_bytes(audio_data),
                        timeout=BACKPRESSURE_TIMEOUT_SECONDS,
                    )
                else:
                    await self.websocket.send_bytes(audio_data)

        except BrowserClosed:
            pass
        except asyncio.TimeoutError:
            logger.warning(
                "Browser output backpressure exceeded session=%s",
                self.session_id,
            )
            self.request_close(1013)
        except WebSocketDisconnect:
            pass
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Browser writer failed session=%s", self.session_id)
        finally:
            self.browser_closed.set()

    def _build_live_config(
        self,
        memory: Deque[str],
    ) -> types.LiveConnectConfig:
        return types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            system_instruction=_build_system_instruction(memory),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            thinking_config=types.ThinkingConfig(thinking_level="minimal"),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=False,
                    start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
                    end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
                    prefix_padding_ms=200,
                    silence_duration_ms=550,
                ),
            ),
        )

    async def run_gemini_connection(
        self,
        sdk_client: genai.Client,
        memory: Deque[str],
    ) -> TurnResult:
        """
        Processes exactly one completed turn per Gemini connection, then returns
        immediately so session_supervisor pre-connects the next fresh session
        while the browser is still playing the tutor's response.
        """
        active_turn_id: Optional[int] = None
        config = self._build_live_config(memory)

        try:
            async with sdk_client.aio.live.connect(
                model=MODEL_NAME,
                config=config,
            ) as session:
                logger.info(
                    "Gemini connection opened session=%s memory_turns=%d",
                    self.session_id,
                    len(memory),
                )

                async def send_loop() -> None:
                    nonlocal active_turn_id
                    saw_audio = False

                    while True:
                        event = await self._next_input_event()

                        if isinstance(event, AudioEvent):
                            turn_id = event.turn_id
                            if self.should_drop_turn(turn_id):
                                continue

                            active_turn_id = turn_id
                            await session.send_realtime_input(
                                audio=types.Blob(
                                    data=event.data,
                                    mime_type=INPUT_AUDIO_MIME_TYPE,
                                ),
                            )
                            saw_audio = True
                            continue

                        if isinstance(event, EndOfSpeechEvent):
                            turn_id = event.turn_id
                            if self.should_drop_turn(turn_id):
                                continue

                            if not saw_audio:
                                continue

                            active_turn_id = turn_id
                            await session.send_realtime_input(
                                audio_stream_end=True,
                            )
                            # Keep loop alive in case the user adds another phrase
                            # before Gemini begins its turn; receive_loop will
                            # finish and cancel send_loop as soon as the turn completes.
                            saw_audio = False

                async def receive_loop() -> TurnResult:
                    input_final_text = ""
                    input_interim_text = ""
                    assistant_text = ""
                    fallback_model_text = ""
                    interrupted = False

                    async for message in session.receive():
                        if getattr(message, "go_away", None) is not None:
                            logger.info(
                                "Gemini sent GoAway session=%s",
                                self.session_id,
                            )
                            continue

                        server_content = getattr(
                            message,
                            "server_content",
                            None,
                        )
                        if server_content is None:
                            continue

                        input_transcription = getattr(
                            server_content,
                            "input_transcription",
                            None,
                        )
                        if input_transcription is not None:
                            input_final_text = _append_transcript(
                                input_final_text,
                                getattr(input_transcription, "text", None),
                            )

                        interim_transcription = getattr(
                            server_content,
                            "interim_input_transcription",
                            None,
                        )
                        if interim_transcription is not None:
                            input_interim_text = _append_transcript(
                                input_interim_text,
                                getattr(interim_transcription, "text", None),
                            )

                        output_transcription = getattr(
                            server_content,
                            "output_transcription",
                            None,
                        )
                        if output_transcription is not None:
                            assistant_text = _append_transcript(
                                assistant_text,
                                getattr(output_transcription, "text", None),
                            )

                        if bool(getattr(server_content, "interrupted", False)):
                            if ALLOW_BARGE_IN:
                                interrupted = True
                                self.clear_model_audio()

                        model_turn = getattr(server_content, "model_turn", None)
                        if model_turn is not None and not interrupted:
                            self.model_generating = True

                            for part in getattr(model_turn, "parts", []) or []:
                                if not bool(getattr(part, "thought", False)):
                                    text_part = getattr(part, "text", None)
                                    if text_part:
                                        fallback_model_text = _append_transcript(
                                            fallback_model_text,
                                            text_part,
                                        )

                                inline_data = getattr(part, "inline_data", None)
                                if inline_data is None:
                                    continue

                                audio_data = getattr(inline_data, "data", None)
                                if not audio_data:
                                    continue

                                if isinstance(audio_data, str):
                                    try:
                                        audio_data = base64.b64decode(audio_data)
                                    except Exception:
                                        continue

                                if isinstance(
                                    audio_data,
                                    (bytes, bytearray, memoryview),
                                ):
                                    await self.put_output_audio(bytes(audio_data))

                        if _server_indicates_turn_complete(server_content):
                            self.model_generating = False
                            return TurnResult(
                                user_text=input_final_text or input_interim_text,
                                assistant_text=(
                                    ""
                                    if interrupted
                                    else (assistant_text or fallback_model_text)
                                ),
                                interrupted=interrupted,
                            )

                    raise GeminiDisconnected(
                        "Gemini receive stream ended without turn completion",
                    )

                send_task = asyncio.create_task(
                    send_loop(),
                    name=f"gemini-send-{self.session_id}",
                )
                receive_task = asyncio.create_task(
                    receive_loop(),
                    name=f"gemini-receive-{self.session_id}",
                )

                try:
                    done, _ = await asyncio.wait(
                        (send_task, receive_task),
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    if receive_task in done:
                        return receive_task.result()

                    send_task.result()
                    return await asyncio.wait_for(
                        receive_task,
                        timeout=TURN_FINALIZATION_TIMEOUT_SECONDS,
                    )
                finally:
                    self.model_generating = False
                    await _cancel_and_wait(send_task)
                    await _cancel_and_wait(receive_task)

        finally:
            self.mark_turn_dropped(active_turn_id)

    async def session_supervisor(self, sdk_client: genai.Client) -> None:
        memory: Deque[str] = deque(maxlen=MAX_MEMORY_TURNS)
        reconnect_delay = 0.25

        try:
            while not self.browser_closed.is_set():
                try:
                    turn = await self.run_gemini_connection(
                        sdk_client,
                        memory,
                    )

                    memory_entry = _make_memory_entry(turn)
                    if memory_entry:
                        memory.append(memory_entry)

                    # Rotate immediately (0s sleep) while browser plays audio
                    reconnect_delay = 0.25

                except BrowserClosed:
                    return

                except asyncio.CancelledError:
                    raise

                except BackpressureExceeded:
                    logger.warning(
                        "Output backpressure exceeded session=%s",
                        self.session_id,
                    )
                    self.request_close(1013)
                    return

                except Exception as exc:
                    if self.browser_closed.is_set():
                        return

                    self.clear_model_audio()
                    logger.warning(
                        "Gemini connection ended; reconnecting in %.2fs "
                        "session=%s error=%r",
                        reconnect_delay,
                        self.session_id,
                        exc,
                    )

                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2.0, 3.0)

        finally:
            self.browser_closed.set()


async def run_voice_session(websocket: WebSocket) -> None:
    session_id = f"{id(websocket):x}"
    sdk_client: genai.Client = websocket.app.state.genai_client

    session = VoiceSession(
        websocket=websocket,
        session_id=session_id,
    )

    tasks = [
        asyncio.create_task(
            session.browser_reader(),
            name=f"browser-reader-{session_id}",
        ),
        asyncio.create_task(
            session.browser_writer(),
            name=f"browser-writer-{session_id}",
        ),
        asyncio.create_task(
            session.session_supervisor(sdk_client),
            name=f"gemini-supervisor-{session_id}",
        ),
    ]

    try:
        await session.browser_closed.wait()
    finally:
        session.browser_closed.set()

        for task in tasks:
            await _cancel_and_wait(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for task, result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.error(
                    "Voice task failed session=%s task=%s error=%r",
                    session_id,
                    task.get_name(),
                    result,
                )

        with suppress(Exception):
            await websocket.close(code=session.close_code)

        logger.info("Voice session cleanup complete session=%s", session_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not API_KEY:
        raise RuntimeError("API_KEY1 or GEMINI_API_KEY is not configured")

    sdk_client = genai.Client(api_key=API_KEY)
    app.state.genai_client = sdk_client

    try:
        yield
    finally:
        with suppress(Exception):
            await sdk_client.aio.aclose()
        with suppress(Exception):
            sdk_client.close()


app = FastAPI(
    title="Voice Tutor",
    lifespan=lifespan,
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket) -> None:
    await websocket.accept()

    try:
        await run_voice_session(websocket)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Voice WebSocket endpoint failed")
        with suppress(Exception):
            await websocket.close(code=1011)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
    )