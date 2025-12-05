# LLamaChatbot

LLamaChatbot è un progetto di esempio per eseguire un chatbot locale basato su modelli LLaMa/varianti compatibili. Questo README descrive come installare, configurare e usare il progetto su macchine Windows (comandi equivalenti per Linux/macOS sono indicati dove rilevante).

## Caratteristiche
- Integrazione locale con modelli LLaMa-compatibili
- Semplice interfaccia a riga di comando e/o API REST (se presente nel progetto)
- Istruzioni per installazione, download dei pesi e avvio

## Requisiti
- Python 3.8+ (consigliato 3.10+)
- Pip
- Spazio su disco adeguato per i pesi del modello (da alcuni GB a decine di GB a seconda del modello)
- GPU con driver appropriati è opzionale ma consigliata per prestazioni migliori


## Installazione (locale)
1. Clona il repository (o usa la cartella locale):
   - git clone <repository-url> c:\Users\chris\Desktop\LLama
2. Crea e attiva un ambiente virtuale:
   - Windows:
     - python -m venv .venv
     - .venv\Scripts\activate
   - macOS/Linux:
     - python3 -m venv .venv
     - source .venv/bin/activate
3. Installa dipendenze:
   - pip install -r requirements.txt
   (Se non esiste requirements.txt, installare manualmente le librerie necessarie come transformers, torch, ollama/ggml wrapper ecc.)

## Pesos del modello
I pesi dei modelli non sono inclusi nel repository. Segui questi passi:
1. Scarica un modello LLaMa-compatibile dal sito o archivio autorizzato (rispetta la licenza del modello).
2. Posiziona i file del modello nella cartella del progetto, ad esempio:
   - c:\Users\chris\Desktop\LLama\models\nome_modello
3. Aggiorna la configurazione (file di config o variabile d'ambiente) per puntare a quella cartella.

Nota: Alcuni modelli richiedono conversione in formati specifici (GGML, quantizzati, ecc.). Segui le istruzioni del fornitore del modello.

## Configurazione
Esempio variabili d'ambiente (Windows PowerShell):
- $env:MODEL_PATH = "c:\Users\chris\Desktop\LLama\models\nome_modello"
- $env:PORT = "5000"

Oppure modifica il file di configurazione del progetto (es. config.yaml, .env).

## Avvio
Comandi di avvio tipici (adattare ai file reali del progetto):
- Avvio CLI:
  - python run.py --model-path "%MODEL_PATH%"
- Avvio server API:
  - python app.py --model "%MODEL_PATH%" --port 5000

Esempio curl (se è presente un server HTTP):
- curl -X POST http://localhost:5000/generate -H "Content-Type: application/json" -d "{\"prompt\":\"Ciao, come stai?\"}"

## Esempi d'uso
- Prompt interattivo (CLI): lancia lo script di conversazione e scrivi direttamente i prompt.
- API: invia richieste POST a /generate o endpoint simili con payload JSON: { "prompt": "...", "max_tokens": 200 }

## Note sulle prestazioni
- GPU drastically improves inference speed; con CPU l'esecuzione può essere lenta per modelli grandi.
- Considera la quantizzazione per ridurre memoria e aumentare velocità (es. 8-bit/4-bit) se supportato.

## Troubleshooting
- Errore memoria OOM: usa un modello più piccolo o attiva quantizzazione.
- Modello non carica: verifica percorso MODEL_PATH e formato dei file.
- Dipendenze non trovate: controlla requirements.txt e reinstalla con pip.

## Contribuire
- Apri issue per bug o feature request.
- Invia pull request con modifiche e descrizione chiara.
- Mantieni il codice leggibile e documentato.

## Licenza
- Inserisci qui la licenza del progetto (es. MIT, Apache-2.0) e qualsiasi informazione relativa ai pesi del modello (licenza separata).
- Assicurati di rispettare le licenze dei modelli e delle librerie utilizzate.

## Ringraziamenti
- Grazie alle community che forniscono modelli e strumenti open-source che rendono possibili progetti come questo.

