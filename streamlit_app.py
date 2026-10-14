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
