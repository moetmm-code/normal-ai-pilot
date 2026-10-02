import json
import re
import time
import uuid
from datetime import datetime, timezone
from urllib.request import Request, urlopen

import streamlit as st
from google import genai
from google.genai import types

st.set_page_config(page_title="Research Chat", page_icon="💬")

NORMAL_PROMPT = """
You are an AI assistant having a natural conversation with a university student.

The student may discuss academic stress, time management, everyday concerns,
or minor interpersonal problems.

Respond naturally and appropriately to the student's messages.
Use your usual conversational style without adopting any specially prescribed
controlling, directive, or autonomy-supportive interpersonal style.

Base your responses only on information provided within the current
experimental conversation. Do not rely on prior conversations.
"""

LIMIT = 30 * 60
CHECKPOINTS = (5, 10, 15, 20)

OPTIONS = (
    "1 — ไม่อยากสนทนาต่อเลย",
    "2 — ไม่ค่อยอยากสนทนาต่อ",
    "3 — เฉย ๆ",
    "4 — อยากสนทนาต่อ",
    "5 — อยากสนทนาต่อมาก",
)


def setting(name, default=""):
    try:
        return st.secrets.get(name, default)
    except (FileNotFoundError, KeyError):
        return default


TEST_MODE = bool(setting("TEST_MODE", False))
ENDPOINT = setting("RESEARCH_ENDPOINT")
TOKEN = setting("RESEARCH_TOKEN")
POST_FORM = setting("POST_FORM_URL")
DEBRIEF = setting("DEBRIEF_TEXT_TH")
MODEL = setting("GEMINI_MODEL", "gemini-3.8-flash")

if "study" not in st.session_state:
    st.session_state.study = None

s = st.session_state.study


def elapsed():
    if s["ended_seconds"] is not None:
        return s["ended_seconds"]

    return min(
        LIMIT,
        max(0.0, time.monotonic() - s["start_clock"]),
    )


def payload():
    # Only metadata is saved; no conversation content.
    return {
        "schema_version": 1,
        "session_id": s["session_id"],
        "participant_code": s["code"],
        "condition": "normal",
        "started_at_utc": s["started_at"],
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed(), 1),
        "participant_message_count": s["count"],
        "continuation": s["answers"],
        "ended": s["ended_seconds"] is not None,
        "end_reason": s["end_reason"],
        "options_version": "draft_5point_v1",
        "revision": s["revision"],
    }


def save(force=False):
    now = time.monotonic()

    if not force and now - s["last_save_attempt"] < 15:
        return

    s["last_save_attempt"] = now

    if TEST_MODE:
        s["save_ok"] = False
        return

    s["revision"] += 1

    try:
        body = json.dumps({
            "token": TOKEN,
            "data": payload(),
        }).encode()

        request = Request(
            ENDPOINT,
            data=body,
            headers={"Content-Type": "application/json"},
        )

        with urlopen(request, timeout=8) as response:
            result = json.loads(response.read())

        s["save_ok"] = result.get("ok") is True

    except Exception:
        s["save_ok"] = False


def finish(reason):
    if s["ended_seconds"] is None:
        s["ended_seconds"] = elapsed()
        s["end_reason"] = reason
        s["messages"] = []
        save(force=True)


st.title("Research Chat")

if TEST_MODE:
    st.warning(
        "โหมดทดสอบ: ไม่มีการส่งหรือบันทึกข้อมูลการวิจัย"
    )

if s is None:
    if not setting("GEMINI_API_KEY"):
        st.error("Researcher setup: GEMINI_API_KEY is missing.")
        st.stop()

    if not TEST_MODE:
        missing = [
            key
            for key in (
                "RESEARCH_ENDPOINT",
                "RESEARCH_TOKEN",
                "POST_FORM_URL",
                "DEBRIEF_TEXT_TH",
                "CONTINUATION_OPTIONS_CONFIRMED",
            )
            if not setting(key)
        ]

        if missing:
            st.error(
                "Researcher setup required: " + ", ".join(missing)
            )
            st.stop()

    st.write(
        "กรุณาสนทนากับ AI "
        "คุณสามารถยุติการสนทนาได้ทุกเมื่อ "
        "และระบบจะสิ้นสุดการส่งข้อความใหม่เมื่อครบ 30 นาที"
    )

    with st.form("entry"):
        st.write(
            "กรุณากรอกหมายเลขผู้เข้าร่วมที่ผู้วิจัยแจ้งให้ทราบ "
            "โดยใช้หมายเลขเดียวกับเอกสารยินยอม"
        )
        st.caption(
            "กรุณาใช้ตัวเลข 0–9 แบบครึ่งความกว้าง (เช่น 001) "
            "โดยไม่เว้นวรรคและไม่ใช้ตัวเลขไทย"
        )

        code = st.text_input(
            "หมายเลขผู้เข้าร่วมที่ได้รับจากผู้วิจัย",
            placeholder="เช่น 001",
        )
        begin = st.form_submit_button("เริ่มการสนทนา")

    if begin:
        code = code.strip()

        if not re.fullmatch(r"[0-9]{1,64}", code):
            st.error(
                "กรุณากรอกหมายเลขที่ผู้วิจัยแจ้งให้ทราบ "
                "โดยใช้ตัวเลข 0–9 แบบครึ่งความกว้าง "
                "และไม่เว้นวรรค (เช่น 001)"
            )
        else:
            st.session_state.study = {
                "session_id": str(uuid.uuid4()),
                "code": code,
                "start_clock": time.monotonic(),
                "started_at": datetime.now(timezone.utc).isoformat(),
                "count": 0,
                "messages": [],
                "answers": [],
                "ended_seconds": None,
                "end_reason": None,
                "last_save_attempt": 0.0,
                "save_ok": False,
                "revision": 0,
            }
            st.rerun()

    st.stop()


@st.fragment(run_every="1s")
def chat_screen():
    if elapsed() >= LIMIT and s["ended_seconds"] is None:
        finish("time_limit")

    save()

    seconds = int(elapsed())
    left, right = st.columns(2)

    left.metric(
        "เวลาที่ใช้สนทนา",
        f"{seconds // 60:02d}:{seconds % 60:02d}",
    )
    right.metric(
        "จำนวนข้อความที่คุณส่ง",
        s["count"],
    )

    if not TEST_MODE and not s["save_ok"]:
        st.warning(
            "ยังส่งข้อมูลการวิจัยไม่สำเร็จ "
            "ระบบจะลองอีกครั้ง "
            "กรุณาอย่าปิดหน้านี้ "
            "และแจ้งผู้วิจัยหากยังพบข้อความนี้"
        )

        if st.button("ลองส่งข้อมูลอีกครั้ง"):
            save(force=True)
            st.rerun()

    if s["ended_seconds"] is not None:
        st.success("การสนทนาสิ้นสุดแล้ว")

        if POST_FORM:
            st.link_button(
                "ไปยังแบบสอบถามหลังการสนทนา (แบบฟอร์ม ②)",
                POST_FORM,
            )
        else:
            st.info(
                "Researcher setup: POST_FORM_URL is not configured."
            )

        st.subheader("คำอธิบายหลังการเข้าร่วมการวิจัย")

        if DEBRIEF:
            st.write(DEBRIEF)
        else:
            st.info(
                "Researcher setup: the debriefing text is not configured."
            )

        return

    for message in s["messages"]:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    recorded = {
        a["scheduled_minute"]
        for a in s["answers"]
    }

    due = next(
        (
            m
            for m in CHECKPOINTS
            if m not in recorded and elapsed() >= m * 60
        ),
        None,
    )

    if due is not None and not any(
        a["value"] is None for a in s["answers"]
    ):
        st.toast(
            "กรุณาตอบคำถามเกี่ยวกับการสนทนาต่อ",
            icon="📋",
        )

        s["answers"].append({
            "scheduled_minute": due,
            "shown_at_seconds": round(elapsed(), 1),
            "answered_at_seconds": None,
            "value": None,
        })
        save(force=True)

    pending = next(
        (
            a
            for a in s["answers"]
            if a["value"] is None
        ),
        None,
    )

    if pending is not None:
        minute = pending["scheduled_minute"]

        st.info("คุณต้องการสนทนากับ AI ต่อหรือไม่?")
        st.caption(
            "ไม่ว่าคุณจะเลือกคำตอบใด "
            "ระบบจะไม่ยุติการสนทนาโดยอัตโนมัติ"
        )

        choice = st.radio(
            "เลือกคำตอบ",
            OPTIONS,
            index=None,
            key=f"continuation_{minute}",
        )

        if st.button(
            "บันทึกคำตอบ",
            key=f"answer_{minute}",
        ):
            if choice is None:
                st.warning("กรุณาเลือกคำตอบ")

            elif elapsed() >= LIMIT:
                finish("time_limit")
                st.rerun()

            else:
                pending["value"] = OPTIONS.index(choice) + 1
                pending["answered_at_seconds"] = round(
                    elapsed(), 1
                )
                save(force=True)
                st.rerun()

    st.divider()

    if st.button(
        "🛑 จบการสนทนาและไปยังแบบสอบถาม ②",
        key="end_conversation",
        type="primary",
        use_container_width=True,
    ):
        finish("participant_stopped")
        st.rerun()

    st.caption(
        "หากต้องการจบการสนทนา กรุณากดปุ่มด้านบน "
        "ก่อนปิดหน้านี้ เพื่อบันทึกเวลาสิ้นสุดการสนทนา "
        "จากนั้นกดปุ่มไปยังแบบสอบถามในหน้าถัดไป"
    )

    text = st.chat_input("พิมพ์ข้อความที่นี่")

    if text:
        if elapsed() >= LIMIT:
            finish("time_limit")
            st.rerun()

        s["count"] += 1

        history = [
            types.Content(
                role=(
                    "user"
                    if m["role"] == "user"
                    else "model"
                ),
                parts=[
                    types.Part(text=m["content"])
                ],
            )
            for m in s["messages"]
        ]

        s["messages"].append({
            "role": "user",
            "content": text,
        })

        save(force=True)

        try:
            with st.spinner("AI กำลังตอบ..."):
                with genai.Client(
                    api_key=setting("GEMINI_API_KEY"),
                    http_options=types.HttpOptions(
                        timeout=45000
                    ),
                ) as client:
                    response = client.models.generate_content(
                        model=MODEL,
                        contents=history + [
                            types.Content(
                                role="user",
                                parts=[
                                    types.Part(text=text)
                                ],
                            )
                        ],
                        config=types.GenerateContentConfig(
                            system_instruction=NORMAL_PROMPT,
                        ),
                    )

                answer = response.text

                if not answer:
                    raise ValueError("Empty answer")

            if elapsed() < LIMIT:
                s["messages"].append({
                    "role": "assistant",
                    "content": answer,
                })

        except Exception:
            st.warning(
                "ไม่สามารถรับคำตอบจาก AI ได้ในขณะนี้ "
                "คุณสามารถส่งข้อความใหม่"
                "หรือยุติการสนทนาได้"
            )

            if elapsed() < LIMIT:
                return

        if elapsed() >= LIMIT:
            finish("time_limit")

        st.rerun()


chat_screen()
