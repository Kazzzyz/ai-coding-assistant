import time
import streamlit as st

from backend import (
    llm_classification,
    non_relevant,
    extract_code,
    execute_code,
)

st.set_page_config(
    page_title="AI Coding Assistant",
    page_icon="💻",
    layout="centered",
)

st.title("AI Coding Assistant")


# Session state

if "messages" not in st.session_state:
    st.session_state.messages = []

if "waiting_for_solution" not in st.session_state:
    st.session_state.waiting_for_solution = False

if "failed_query" not in st.session_state:
    st.session_state.failed_query = None

if "generated_code" not in st.session_state:
    st.session_state.generated_code = None

if "execution_result" not in st.session_state:
    st.session_state.execution_result = None



# Simple streaming helper

def stream_text(text):
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.01)



# Sidebar

with st.sidebar:
    st.subheader("Conversation")

    if st.button("Clear Conversation"):
        st.session_state.messages = []
        st.session_state.waiting_for_solution = False
        st.session_state.failed_query = None
        st.session_state.generated_code = None
        st.session_state.execution_result = None
        st.rerun()



# Display previous messages

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])



# User input

prompt = st.chat_input("Ask anything about coding!")

if prompt:
    # Save and display user message
    st.session_state.messages.append({
        "role": "user",
        "content": prompt
    })

    with st.chat_message("user"):
        st.markdown(prompt)

    # Clear old execution output when a new message is sent
    st.session_state.execution_result = None

    
    # If we are waiting for the user's solution
    
    if st.session_state.waiting_for_solution:
        response = non_relevant(
            st.session_state.failed_query,
            prompt
        )

        st.session_state.waiting_for_solution = False
        st.session_state.failed_query = None
        st.session_state.generated_code = None

    
    # Normal chatbot flow
    
    else:
        response, intent = llm_classification(prompt)

        # Safety guard in case backend returns None
        if response is None:
            response = "Something went wrong while processing your request."

        # Make sure response is text before using "in"
        if not isinstance(response, str):
            response = str(response)

        
        # Retrieval was not relevant
        
        if response == "NEED_USER_SOLUTION":
            st.session_state.waiting_for_solution = True
            st.session_state.failed_query = prompt
            st.session_state.generated_code = None

            response = (
                "I couldn't find sufficiently relevant knowledge for your request. "
                "Please provide the correct solution or a useful reference so I can "
                "store it in the knowledge base for future interactions."
            )

        
        # Normal assistant response
        
        else:
            if intent == "GENERATE" and "```python" in response:
                st.session_state.generated_code = extract_code(response)
            else:
                st.session_state.generated_code = None

    # Final safety guard
    if response is None:
        response = "Something went wrong while processing your request."

    if not isinstance(response, str):
        response = str(response)

    # Display assistant response
    with st.chat_message("assistant"):
        st.write_stream(stream_text(response))

    # Save assistant response
    st.session_state.messages.append({
        "role": "assistant",
        "content": response
    })



# Code execution

if st.session_state.generated_code:
    st.divider()
    st.subheader("Code Execution")

    if st.button("Execute Code"):
        st.session_state.execution_result = execute_code(
            st.session_state.generated_code
        )

    if st.session_state.execution_result is not None:
        result = st.session_state.execution_result

        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")

        if stdout:
            st.markdown("**Standard Output**")
            st.code(stdout, language="text")

        if stderr:
            st.markdown("**Standard Error**")
            st.code(stderr, language="text")

        if not stdout and not stderr:
            st.info("The code executed successfully but produced no output.")
