import os
import time
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-4-hydrogen"  # exact model code from Google AI Studio

st.title("🔐 AI Escape Room - Version 1")

if not API_KEY:
    st.error("GEMINI_API_KEY was not found. Check that your .env file exists in the project folder.")
    st.stop()

client = genai.Client(api_key=API_KEY)

SYSTEM_PROMPT = """
You are the Game Master of a text escape-room game. The player is locked in a library.

ROOM OBJECTS: a desk, a bookshelf, a painting, a locked drawer, and a locked door.

SECRETS (never reveal these directly; the player must discover them):
- Desk: has a letter saying "The four red books tell the drawer's number."
- Bookshelf: four red books hold handwritten numbers 4, 2, 7, 1 (in that order).
- Drawer: opens with code 4271. Inside is a note: "The door answers to the year this library was founded."
- Painting: a brass plaque reads "Founded 1893".
- Door: opens with the four-digit code 1893.

RULES:
- Describe only what the player examines. Reveal clues one at a time.
- Do not reveal codes until the player has discovered them through exploring.
- Keep replies short (2-4 sentences) and atmospheric.
- When the player opens the door with the correct code 1893, congratulate them and end your message with the exact tag [ESCAPED].
"""

INTRO = (
    "You wake up on a cold floor in a locked library. Dust hangs in the air. "
    "You can see a desk, a bookshelf, a painting, a locked drawer and a heavy door with a four-digit keypad."
)


def new_game():
    st.session_state.messages = [{"role": "assistant", "text": INTRO}]
    st.session_state.escaped = False


def ask_gemini(history):
    """Returns (reply_text, error_text). Exactly one of them is None."""
    # history[0] is the local intro; it is already included in the system prompt
    contents = [
        types.Content(
            role="user" if m["role"] == "user" else "model",
            parts=[types.Part(text=m["text"])],
        )
        for m in history[1:]
    ]
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT + "\nOpening scene: " + INTRO
    )

    last_error = None
    for attempt in range(4):
        try:
            response = client.models.generate_content(
                model=MODEL, contents=contents, config=config
            )
            if response.text:
                return response.text, None
            last_error = "The model returned an empty reply."
        except Exception as e:
            last_error = str(e)
            print("GEMINI ERROR:", last_error, flush=True)
            temporary = "503" in last_error or "429" in last_error
            if not temporary:
                break  # 404, 403 etc. will not fix themselves, so stop retrying
        if attempt < 3:
            time.sleep(2 ** attempt)  # wait 1s, 2s, 4s (exponential backoff)
    return None, last_error


if "messages" not in st.session_state:
    new_game()

with st.sidebar:
    st.header("How to play")
    st.write(
        "Type what you want to do, for example: *examine the bookshelf* or *try 1234 on the door*. "
        "Find clues, solve the puzzles and escape the library."
    )
    if st.button("Restart game"):
        new_game()
        st.rerun()

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.write(m["text"])

if st.session_state.escaped:
    st.success("🎉 You escaped! Press 'Restart game' to play again.")
else:
    user_input = st.chat_input("What do you do?")
    if user_input:
        st.session_state.messages.append({"role": "user", "text": user_input})
        with st.spinner("The Game Master is thinking..."):
            reply, error = ask_gemini(st.session_state.messages)

        if error:
            # Do not keep a failed turn in the history
            st.session_state.messages.pop()
            st.error(f"Gemini request failed. Please try again.\n\nDetails: {error}")
        else:
            if "[ESCAPED]" in reply:
                st.session_state.escaped = True
                reply = reply.replace("[ESCAPED]", "").strip()
            st.session_state.messages.append({"role": "assistant", "text": reply})
            st.rerun()
