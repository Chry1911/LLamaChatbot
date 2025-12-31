import os
from flask import Blueprint, request, jsonify
from document_reader import extract_text_from_file

# Crea il blueprint
pdf_bp = Blueprint('pdf', __name__)

# Variabile globale per il modello (verrà impostata da app.py)
llm_model = None

def set_llm_model(model):
    """Imposta il modello LLaMA da usare"""
    global llm_model
    llm_model = model

def generate_summary_with_llama(text, max_length=500):
    """Genera riassunto usando il modello già caricato"""
    if llm_model is None:
        raise Exception("Modello LLaMA non inizializzato")
    
    # Limita il testo a 2000 caratteri per evitare overflow
    text_sample = text[:2000] if len(text) > 2000 else text
    
    prompt = f"""<|system|>
Sei un assistente che crea riassunti chiari e concisi di documenti in italiano.
<|end|>
<|user|>
Leggi questo documento e fornisci un riassunto dettagliato in italiano (minimo 100 parole):

{text_sample}
<|end|>
<|assistant|>
Riassunto:"""
    
    try:
        output = llm_model(
            prompt, 
            max_tokens=400,
            temperature=0.5,
            top_p=0.9,
            repeat_penalty=1.1,
            stop=["<|end|>", "\n\n\n"]
        )
        
        summary = output['choices'][0]['text'].strip()
        
        # Fallback se il riassunto è vuoto
        if not summary or len(summary) < 20:
            summary = f"Documento di {len(text)} caratteri. Contenuto principale: {text[:300]}..."
        
        return summary
        
    except Exception as e:
        print(f"Errore generazione riassunto: {e}")
        return f"Impossibile generare riassunto automatico. Testo estratto: {text[:500]}..."

@pdf_bp.route('/pdf/summary', methods=['POST'])
def summarize_pdf():
    """Carica PDF/DOCX e genera riassunto con LLaMA"""
    if 'file' not in request.files:
        return jsonify({'error': 'Nessun file caricato'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'Nome file vuoto'}), 400
    
    try:
        # Usa document_reader per estrarre il testo
        text = extract_text_from_file(file)
        
        if not text or text == "Formato non supportato.":
            return jsonify({'error': 'Impossibile estrarre testo dal file'}), 400
        
        # Genera riassunto
        summary = generate_summary_with_llama(text, max_length=500)
        
        return jsonify({
            'success': True,
            'summary': summary,
            'original_length': len(text),
            'filename': file.filename
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500