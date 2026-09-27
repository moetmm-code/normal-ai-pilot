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

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

user_text = st.chat_input("Type your message here")

if user_text:
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except (KeyError, FileNotFoundError):
        st.error("Researcher setup is incomplete: API key is missing.")
        st.stop()

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

            answer = response.text
            if not answer:
                raise ValueError("The AI returned no text.")

        except Exception as e:
            st.error("Could not get a response.")
            st.exception(e)
            st.stop()

    st.session_state.messages.extend([
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": answer}
    ])
    st.rerun()
