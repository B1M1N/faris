from flask import Flask, render_template, request, jsonify
import openai
import time

# Set up Flask app
app = Flask(__name__)

# OpenAI API key (Replace with your actual API key)
OPENAI_API_KEY = "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"
ASSISTANT_ID = "asst_FDuUSbtE6aPgnDdUYV1lKgyE"

# Initialize OpenAI client
openai.api_key = OPENAI_API_KEY

def get_assistant_response(user_input):
    """Send a message to the assistant and retrieve the response"""
    try:
        # Create a new thread (one per session)
        thread = openai.beta.threads.create()
        thread_id = thread.id

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

        # Wait for response
        while run.status not in ["completed", "failed"]:
            time.sleep(1)
            run = openai.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id,
            )

        # Fetch response
        messages = openai.beta.threads.messages.list(thread_id=thread_id)
        for message in reversed(messages.data):
            if message.role == "assistant":
                return "\n".join(block.text.value for block in message.content if hasattr(block, "text"))

    except Exception as e:
        return f"❌ Error: {e}"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message", "")
    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    assistant_reply = get_assistant_response(user_message)
    return jsonify({"response": assistant_reply})

if __name__ == "__main__":
    app.run(debug=True)
