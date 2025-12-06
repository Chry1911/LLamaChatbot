import os
import json
import uuid
import time
import threading
from queue import Queue, Empty
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from llama_cpp import Llama

# ---------------------------------------------------
# CONFIGURAZIONE
# ---------------------------------------------------
MODELS_DIR = "./models"
MODEL_FILENAME = "Phi-3-mini-4k-instruct-q4.gguf"
MODEL_PATH = os.path.join(MODELS_DIR, MODEL_FILENAME)
CONV_FILE = "conversations.json"

# Streaming
stream_queues = {}
stream_threads = {}

# File conversazioni
if not os.path.exists(CONV_FILE):
    with open(CONV_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f)

# Caricamento modello
print("⏳ Caricamento modello...")
llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=4096,
    n_threads=6,
    n_batch=256,
    n_gpu_layers=0,
    verbose=False
)
print("✅ Modello caricato!")

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

# ---------------------------------------------------
# FUNZIONI DI STORAGE
# ---------------------------------------------------
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
    convs[conv_id]["messages"].append({
        "role": role,
        "text": text,
        "ts": time.time()
    })
    save_conversations(convs)

# ---------------------------------------------------
# FILTRO DOMANDE INFORMATICHE
# ---------------------------------------------------
ALLOWED_KEYWORDS = [
    "software", "programmazione", "python", "javascript", "java", "c++", "c#", "rust",
    "react", "next.js", "node", "backend", "frontend", "full stack", "database", "sql",
    "mysql", "postgres", "mongodb", "server", "linux", "windows", "ubuntu",
    "docker", "kubernetes", "devops", "ci/cd", "git", "github", "gitlab",
    "network", "rete", "tcp", "udp", "http", "tls", "api",
    "ai", "intelligenza artificiale", "llm", "machine learning",
    "hardware", "cpu", "gpu", "ram", "ssd",
]

REFUSAL_MESSAGE = "Mi dispiace, posso rispondere solo a domande di ambito informatico."

def is_informatics_question(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in ALLOWED_KEYWORDS)

# ---------------------------------------------------
# STREAMING MODELLO
# ---------------------------------------------------
def generate_and_stream(conv_id, prompt, stop_event):
    q = stream_queues.get(conv_id)
    if q is None:
        return

    try:
        out = llm(prompt, max_tokens=400, temperature=0.7)
        text = out["choices"][0]["text"].strip()
        append_message(conv_id, "assistant", text)

        # Streaming chunk-by-chunk
        chunk_size = 12
        for i in range(0, len(text), chunk_size):
            if stop_event.is_set():
                break
            q.put({"type": "token", "text": text[i:i+chunk_size]})
            time.sleep(0.03)

        q.put({"type": "done"})

    except Exception as e:
        q.put({"type": "error", "text": str(e)})

# ---------------------------------------------------
# ROUTES
# ---------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/static/<path:p>")
def static_files(p):
    return send_from_directory("static", p)

@app.route("/conversations", methods=["GET"])
def get_conversations():
    convs = load_conversations()
    sorted_list = sorted(
        [
            {
                "id": k,
                "title": v["title"],
                "last_ts": v["messages"][-1]["ts"] if v["messages"] else 0
            }
            for k, v in convs.items()
        ],
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
    title = (request.json or {}).get("title", "Nuova chat")
    conv_id = create_conversation(title)
    return jsonify({"id": conv_id})

@app.route("/send", methods=["POST"])
def send_message():
    data = request.json or {}
    conv_id = data.get("conv_id") or create_conversation()
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "empty message"}), 400

    append_message(conv_id, "user", message)
    return jsonify({"conv_id": conv_id})

# ---------------------------------------------------
# STREAMING /start_stream
# ---------------------------------------------------
@app.route("/start_stream", methods=["POST"])
def start_stream():
    data = request.json or {}
    conv_id = data.get("conv_id") or create_conversation()

    convs = load_conversations()
    history = convs.get(conv_id, {}).get("messages", [])
    last_user_msg = history[-1]["text"] if history else ""

    # ❗ CONTROLLO PRIMA DEL MODELLO
    if not is_informatics_question(last_user_msg):
        q = Queue()
        stream_queues[conv_id] = q

        def stream_refusal():
            text = REFUSAL_MESSAGE
            chunk_size = 12
            for i in range(0, len(text), chunk_size):
                q.put({"type": "token", "text": text[i:i+chunk_size]})
                time.sleep(0.03)
            q.put({"type": "done"})
            append_message(conv_id, "assistant", text)

        threading.Thread(target=stream_refusal, daemon=True).start()
        return jsonify({"conv_id": conv_id})

    # Domanda informatica → usa il modello
    SYSTEM_PROMPT = """
Sei un assistente specializzato esclusivamente in ambito informatico.
Rispondi sempre in modo tecnico, conciso e accurato.
"""

    prompt_parts = [f"System: {SYSTEM_PROMPT}"]
    for m in history:
        if m["role"] == "user":
            prompt_parts.append("User: " + m["text"])
        else:
            prompt_parts.append("Assistant: " + m["text"])
    prompt = "\n".join(prompt_parts) + "\nAssistant:"

    # Queue
    if conv_id not in stream_queues:
        stream_queues[conv_id] = Queue()
    else:
        try:
            while True:
                stream_queues[conv_id].get_nowait()
        except Empty:
            pass

    stop_event = threading.Event()
    t = threading.Thread(target=generate_and_stream, args=(conv_id, prompt, stop_event), daemon=True)
    stream_threads[conv_id] = {"thread": t, "stop": stop_event}
    t.start()

    return jsonify({"conv_id": conv_id})

# ---------------------------------------------------
# EVENTS STREAM
# ---------------------------------------------------
@app.route("/events/<conv_id>")
def events(conv_id):
    def gen():
        q = stream_queues.get(conv_id)
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
                yield "data: " + json.dumps({"type": "done"}) + "\n\n"
                break

            yield "data: " + json.dumps(item, ensure_ascii=False) + "\n\n"
            if item.get("type") in ("done", "error"):
                break

    return app.response_class(gen(), mimetype="text/event-stream")

# ---------------------------------------------------
# AVVIO SERVER
# ---------------------------------------------------
if __name__ == "__main__":
    if not os.path.exists(MODELS_DIR):
        os.makedirs(MODELS_DIR)
    app.run(debug=False, port=5000, host="0.0.0.0")
