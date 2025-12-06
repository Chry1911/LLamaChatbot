from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from llama_cpp import Llama

app = Flask(__name__)
CORS(app)

MODEL_PATH = "./models/Phi-3-mini-4k-instruct-q4.gguf"

print("⏳ Caricamento modello Phi-3 Mini 4k...")
llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=2048,
    n_batch=512,
    n_threads=6,
    n_gpu_layers=0,
    verbose=False
)
print("✅ Modello caricato!\n")

# Prompt secondo lo standard ChatML (richiesto da Phi-3)
def build_prompt(user_message):
    return f"""<|user|>
{user_message}<|end|>
<|assistant|>
"""

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    msg = request.json.get("message", "")
    if not msg:
        return jsonify({"response": "Inserisci un messaggio valido."})

    print("👤 Utente:", msg)

    prompt = build_prompt(msg)

    output = llm(
        prompt,
        max_tokens=300,
        stop=["<|end|>"],
        temperature=0.7
    )

    reply = output["choices"][0]["text"].strip()
    print("🤖 Modello:", reply)

    return jsonify({"response": reply})

if __name__ == "__main__":
    app.run(debug=False, port=5000, host="0.0.0.0")
