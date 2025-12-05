from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from ctransformers import AutoModelForCausalLM

app = Flask(__name__)
CORS(app)

model_path = "./models/Phi-3-mini-128k-instruct-Q4_0.gguf"

print("⏳ Caricamento modello Phi-3 Mini...")
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    model_type="phi3",
    gpu_layers=0,
    threads=4,
    max_new_tokens=400,
    temperature=0.7
)
print("✅ Modello caricato!")

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    msg = request.json.get("message", "")
    if not msg:
        return jsonify({"response": "Inserisci un messaggio valido."})

    print("👤 Utente:", msg)
    reply = model(msg)
    print("🤖 Modello:", reply)

    return jsonify({"response": reply})

if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0")
