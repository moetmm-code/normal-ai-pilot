import streamlit as st
from google import genai
from google.genai import types

st.set_page_config(page_title="Research Chat", page_icon="💬")
st.title("Research Chat")
st.caption("Please have a conversation with the AI.")

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

api_key = st.secrets.get("GEMINI_API_KEY")

if not api_key:
    st.error("Researcher setup is incomplete: API key is missing.")
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

user_text = st.chat_input("Type your message here")

if user_text:
    with st.chat_message("user"):
        st.write(user_text)

    history = [
        types.Content(
            role="user" if m["role"] == "user" else "model",
            parts=[types.Part(text=m["content"])]
        )
        for m in st.session_state.messages
    ]

    with st.spinner("AI is responding..."):
        try:
            with genai.Client(api_key=api_key) as client:
                for attempt in range(3):
                    try:
                        response = client.models.generate_content(
                            model="gemini-3.8-flash",
                            contents=history + [
                                types.Content(
                                    role="user",
                                    parts=[types.Part(text=user_text)]
                                )
                            ],
                            config=types.GenerateContentConfig(
                                system_instruction=NORMAL_PROMPT
                            ),
                        )
                        break

                    except Exception as e:
                        if "503" not in str(e) or attempt == 2:
                            raise
                        time.sleep(2 ** (attempt + 1))

            answer = response.text

            if not answer:
                raise ValueError("The AI returned no text.")

        except Exception:
            st.error(
                "The AI is temporarily unavailable. "
                "Please wait a moment and try again."
            )
            st.stop()

    st.session_state.messages.extend([
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": answer}
    ])

    with st.chat_message("assistant"):
        st.write(answer)
