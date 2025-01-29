import openai
import time

# Set your OpenAI API key
OPENAI_API_KEY = "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"

# Your Assistant ID from OpenAI
ASSISTANT_ID = "asst_FDuUSbtE6aPgnDdUYV1lKgyE"

# Initialize OpenAI client
openai.api_key = OPENAI_API_KEY

def chat_with_assistant():
    """Function to interact with the OpenAI assistant via terminal"""
    try:
        # Create a new thread
        thread = openai.beta.threads.create()
        thread_id = thread.id

        print("\n🤖 ChatGPT Assistant Terminal Test")
        print("Type 'exit' to quit.\n")

        while True:
            user_input = input("You: ")

            if user_input.lower() == "exit":
                print("\n👋 Exiting chat. Goodbye!\n")
                break

            # Send message to assistant
            openai.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=user_input,
            )

            # Run the assistant
            run = openai.beta.threads.runs.create_and_poll(
                thread_id=thread_id,
                assistant_id=ASSISTANT_ID,
            )

            # Wait for the response
            while run.status not in ["completed", "failed"]:
                time.sleep(1)
                run = openai.beta.threads.runs.retrieve(
                    thread_id=thread_id,
                    run_id=run.id,
                )

            # Fetch the assistant's response
            messages = openai.beta.threads.messages.list(thread_id=thread_id)
            for message in reversed(messages.data):
                if message.role == "assistant":
                    # Extract text properly
                    response_text = "\n".join(block.text.value for block in message.content if hasattr(block, "text"))
                    print(f"🤖 Assistant: {response_text}\n")
                    break

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    chat_with_assistant()
