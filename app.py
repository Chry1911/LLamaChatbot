import os
import json
import uuid
import time
import threading
from queue import Queue, Empty
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from llama_cpp import Llama

# Config
MODELS_DIR = "./models"
MODEL_FILENAME = "Phi-3-mini-4k-instruct-q4.gguf"   # metti qui il tuo file compatibile
MODEL_PATH = os.path.join(MODELS_DIR, MODEL_FILENAME)
CONV_FILE = "conversations.json"

# In-memory queues for streaming: conv_id -> Queue
stream_queues = {}
stream_threads = {}

# Ensure conversations file exists
if not os.path.exists(CONV_FILE):
    with open(CONV_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f)

# Load model
print("⏳ Caricamento modello...")
llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=2048,
    n_batch=256,
    n_threads=6,
    n_gpu_layers=0,
    verbose=False
)
print("✅ Modello caricato!")

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)


# --- Conversation storage helpers ---
def load_conversations():
    with open(CONV_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_conversations(data):
    with open(CONV_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def create_conversation(title="New chat"):
    convs = load_conversations()
    conv_id = str(uuid.uuid4())
    convs[conv_id] = {"title": title, "messages": []}
    save_conversations(convs)
    return conv_id


def append_message(conv_id, role, text):
    convs = load_conversations()
    if conv_id not in convs:
        convs[conv_id] = {"title": "Chat", "messages": []}
    convs[conv_id]["messages"].append({"role": role, "text": text, "ts": time.time()})
    save_conversations(convs)


# --- Streaming generation (background thread) ---
def generate_and_stream(conv_id, prompt, stop_event):
    """
    Generates response with the model synchronously, then streams it chunk-by-chunk
    into stream_queues[conv_id]. This simulates token-by-token streaming.
    If llama-cpp-python supports streaming callbacks, replace this implementation
    with a real callback that pushes tokens as they arrive.
    """
    q = stream_queues.get(conv_id)
    if q is None:
        return

    try:
        # generate full response (blocking)
        out = llm(prompt, max_tokens=400, temperature=0.7)
        text = out.get("choices", [{}])[0].get("text", "").strip()
        # append to conversation immediately (as assistant partial)
        append_message(conv_id, "assistant", text)

        # stream the text in small chunks to give token-like feel
        chunk_size = 12  # characters per chunk; tweak for speed/quality
        for i in range(0, len(text), chunk_size):
            if stop_event.is_set():
                break
            chunk = text[i : i + chunk_size]
            q.put({"type": "token", "text": chunk})
            time.sleep(0.03)  # small delay to simulate streaming

        # indicate end
        q.put({"type": "done"})
    except Exception as e:
        q.put({"type": "error", "text": str(e)})


# --- Routes ---
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/static/<path:p>")
def static_files(p):
    return send_from_directory("static", p)


@app.route("/conversations", methods=["GET"])
def get_conversations():
    convs = load_conversations()
    # sort by last message ts
    sorted_list = sorted(
        [{"id": k, "title": v["title"], "last_ts": (v["messages"][-1]["ts"] if v["messages"] else 0)} for k, v in convs.items()],
        key=lambda x: x["last_ts"],
        reverse=True,
    )
    return jsonify(sorted_list)


@app.route("/conversation/<conv_id>", methods=["GET"])
def get_conversation(conv_id):
    convs = load_conversations()
    if conv_id not in convs:
        return jsonify({"error": "not found"}), 404
    return jsonify(convs[conv_id])


@app.route("/conversation", methods=["POST"])
def new_conversation():
    data = request.json or {}
    title = data.get("title", "Nuova chat")
    conv_id = create_conversation(title)
    return jsonify({"id": conv_id})


@app.route("/send", methods=["POST"])
def send_message():
    """
    Simple endpoint: append a user message and return conversation id.
    For streaming generation, client should call /start_stream.
    """
    data = request.json or {}
    conv_id = data.get("conv_id") or create_conversation()
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "empty message"}), 400

    append_message(conv_id, "user", message)
    return jsonify({"conv_id": conv_id})


@app.route("/start_stream", methods=["POST"])
def start_stream():
    """
    Starts background generation thread for the given conversation id + prompt.
    Returns conv_id used for EventSource streaming.
    """
    data = request.json or {}
    conv_id = data.get("conv_id") or create_conversation()
    # build prompt using system instructions + conversation history + last user message
    convs = load_conversations()
    history = convs.get(conv_id, {}).get("messages", [])
    # Build a helpful system instruction (personalize as needed)
    system_prompt = (
        "You are a helpful, concise assistant. Answer in Italian unless user asks otherwise. "
        "When giving code, format it appropriately. Do not fabricate facts. "
    )

    # Compose chat-style prompt (simple)
    # We keep it short to avoid extremely long prompts for 128k models
    prompt_parts = [f"System: {system_prompt}"]
    for m in history:
        role = m["role"]
        text = m["text"]
        if role == "user":
            prompt_parts.append(f"User: {text}")
        else:
            prompt_parts.append(f"Assistant: {text}")
    prompt = "\n".join(prompt_parts) + "\nAssistant:"

    # create a queue and thread
    if conv_id not in stream_queues or stream_queues[conv_id] is None:
        stream_queues[conv_id] = Queue()
    else:
        # drain old queue
        while True:
            try:
                stream_queues[conv_id].get_nowait()
            except Empty:
                break

    stop_event = threading.Event()
    t = threading.Thread(target=generate_and_stream, args=(conv_id, prompt, stop_event), daemon=True)
    stream_threads[conv_id] = {"thread": t, "stop": stop_event}
    t.start()

    return jsonify({"conv_id": conv_id})


@app.route("/events/<conv_id>")
def events(conv_id):
    """
    Server-Sent Events endpoint. Client should open EventSource to this URL.
    We will stream JSON-encoded events.
    """
    def gen():
        q = stream_queues.get(conv_id)
        # if no queue, wait up to a bit for generator to be prepared
        timeout_wait = 0
        while q is None and timeout_wait < 5:
            time.sleep(0.1)
            timeout_wait += 0.1
            q = stream_queues.get(conv_id)

        if q is None:
            yield "data: " + json.dumps({"type": "error", "text": "no stream queue"}) + "\n\n"
            return

        while True:
            try:
                item = q.get(timeout=60)
            except Empty:
                # timeout -> close stream
                yield "data: " + json.dumps({"type": "done"}) + "\n\n"
                break
            yield "data: " + json.dumps(item, ensure_ascii=False) + "\n\n"
            if item.get("type") in ("done", "error"):
                break

    return app.response_class(gen(), mimetype="text/event-stream")


if __name__ == "__main__":
    # ensure models dir exists
    if not os.path.exists(MODELS_DIR):
        os.makedirs(MODELS_DIR)
    app.run(debug=False, port=5000, host="0.0.0.0")
