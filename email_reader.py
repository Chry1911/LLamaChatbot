from flask import Blueprint, request, jsonify
import imaplib
import email
from email.header import decode_header
import re
from datetime import datetime

email_bp = Blueprint('email', __name__)

# Configurazione IMAP per provider comuni
IMAP_SERVERS = {
    'gmail': 'imap.gmail.com',
    'outlook': 'outlook.office365.com',
    'yahoo': 'imap.mail.yahoo.com',
    'icloud': 'imap.mail.me.com',
}

def clean_text(text):
    """Pulisce il testo rimuovendo caratteri speciali"""
    if text:
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    return ""

def decode_mime_words(s):
    """Decodifica header MIME"""
    if not s:
        return ""
    decoded = decode_header(s)
    result = []
    for text, encoding in decoded:
        if isinstance(text, bytes):
            try:
                result.append(text.decode(encoding or 'utf-8', errors='ignore'))
            except:
                result.append(text.decode('utf-8', errors='ignore'))
        else:
            result.append(str(text))
    return ' '.join(result)

def get_email_body(msg):
    """Estrae il corpo dell'email"""
    body = ""
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            
            if "attachment" not in content_disposition:
                if content_type == "text/plain":
                    try:
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
                    except:
                        pass
                elif content_type == "text/html" and not body:
                    try:
                        html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        # Rimuovi tag HTML basilari
                        body = re.sub('<[^<]+?>', '', html_body)
                    except:
                        pass
    else:
        try:
            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        except:
            body = str(msg.get_payload())
    
    return clean_text(body)

def connect_imap(email_address, password, provider=None):
    """Connette al server IMAP"""
    try:
        # Determina il server IMAP
        if provider and provider in IMAP_SERVERS:
            imap_server = IMAP_SERVERS[provider]
        else:
            # Prova a indovinare dal dominio
            domain = email_address.split('@')[1].lower()
            if 'gmail' in domain:
                imap_server = IMAP_SERVERS['gmail']
            elif 'outlook' in domain or 'hotmail' in domain:
                imap_server = IMAP_SERVERS['outlook']
            elif 'yahoo' in domain:
                imap_server = IMAP_SERVERS['yahoo']
            elif 'icloud' in domain or 'me.com' in domain:
                imap_server = IMAP_SERVERS['icloud']
            else:
                return None, "Provider email non supportato"
        
        # Connetti
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_address, password)
        return mail, None
        
    except imaplib.IMAP4.error as e:
        return None, f"Errore di autenticazione: {str(e)}"
    except Exception as e:
        return None, f"Errore di connessione: {str(e)}"

@email_bp.route('/email/connect', methods=['POST'])
def test_connection():
    """Testa la connessione email"""
    data = request.json
    email_address = data.get('email')
    password = data.get('password')
    provider = data.get('provider')
    
    if not email_address or not password:
        return jsonify({'error': 'Email e password richiesti'}), 400
    
    mail, error = connect_imap(email_address, password, provider)
    
    if error:
        return jsonify({'error': error}), 401
    
    try:
        mail.select('INBOX')
        status, messages = mail.search(None, 'ALL')
        num_emails = len(messages[0].split())
        mail.close()
        mail.logout()
        
        return jsonify({
            'success': True,
            'message': 'Connessione riuscita',
            'total_emails': num_emails
        }), 200
    except Exception as e:
        return jsonify({'error': f'Errore lettura inbox: {str(e)}'}), 500

@email_bp.route('/email/list', methods=['POST'])
def list_emails():
    """Lista le email recenti"""
    data = request.json
    email_address = data.get('email')
    password = data.get('password')
    provider = data.get('provider')
    limit = data.get('limit', 10)  # Numero di email da recuperare
    
    if not email_address or not password:
        return jsonify({'error': 'Credenziali mancanti'}), 400
    
    mail, error = connect_imap(email_address, password, provider)
    
    if error:
        return jsonify({'error': error}), 401
    
    try:
        mail.select('INBOX')
        
        # Cerca tutte le email
        status, messages = mail.search(None, 'ALL')
        email_ids = messages[0].split()
        
        # Prendi le ultime N email
        email_ids = email_ids[-limit:]
        email_ids.reverse()  # Più recenti prima
        
        emails_list = []
        
        for email_id in email_ids:
            try:
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        # Estrai informazioni
                        subject = decode_mime_words(msg.get('Subject', 'Senza oggetto'))
                        from_addr = decode_mime_words(msg.get('From', ''))
                        date_str = msg.get('Date', '')
                        
                        # Parse data
                        try:
                            date_obj = email.utils.parsedate_to_datetime(date_str)
                            date_formatted = date_obj.strftime('%d/%m/%Y %H:%M')
                        except:
                            date_formatted = date_str
                        
                        emails_list.append({
                            'id': email_id.decode(),
                            'subject': subject,
                            'from': from_addr,
                            'date': date_formatted,
                            'has_attachments': any(part.get_content_disposition() == 'attachment' 
                                                   for part in msg.walk())
                        })
            except Exception as e:
                print(f"Errore parsing email {email_id}: {e}")
                continue
        
        mail.close()
        mail.logout()
        
        return jsonify({
            'success': True,
            'emails': emails_list,
            'total': len(emails_list)
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Errore recupero email: {str(e)}'}), 500

@email_bp.route('/email/read', methods=['POST'])
def read_email():
    """Legge il contenuto completo di un'email"""
    data = request.json
    email_address = data.get('email')
    password = data.get('password')
    provider = data.get('provider')
    email_id = data.get('email_id')
    
    if not all([email_address, password, email_id]):
        return jsonify({'error': 'Parametri mancanti'}), 400
    
    mail, error = connect_imap(email_address, password, provider)
    
    if error:
        return jsonify({'error': error}), 401
    
    try:
        mail.select('INBOX')
        
        status, msg_data = mail.fetch(email_id, '(RFC822)')
        
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                # Estrai tutte le informazioni
                subject = decode_mime_words(msg.get('Subject', 'Senza oggetto'))
                from_addr = decode_mime_words(msg.get('From', ''))
                to_addr = decode_mime_words(msg.get('To', ''))
                date_str = msg.get('Date', '')
                
                try:
                    date_obj = email.utils.parsedate_to_datetime(date_str)
                    date_formatted = date_obj.strftime('%d/%m/%Y %H:%M')
                except:
                    date_formatted = date_str
                
                # Estrai corpo
                body = get_email_body(msg)
                
                # Lista allegati
                attachments = []
                for part in msg.walk():
                    if part.get_content_disposition() == 'attachment':
                        filename = part.get_filename()
                        if filename:
                            attachments.append({
                                'filename': decode_mime_words(filename),
                                'size': len(part.get_payload(decode=True))
                            })
                
                mail.close()
                mail.logout()
                
                return jsonify({
                    'success': True,
                    'email': {
                        'subject': subject,
                        'from': from_addr,
                        'to': to_addr,
                        'date': date_formatted,
                        'body': body[:5000],  # Limita a 5000 caratteri
                        'body_length': len(body),
                        'attachments': attachments
                    }
                }), 200
        
        return jsonify({'error': 'Email non trovata'}), 404
        
    except Exception as e:
        return jsonify({'error': f'Errore lettura email: {str(e)}'}), 500

@email_bp.route('/email/summarize', methods=['POST'])
def summarize_email():
    """Legge un'email e genera un riassunto con LLaMA"""
    data = request.json
    email_address = data.get('email')
    password = data.get('password')
    provider = data.get('provider')
    email_id = data.get('email_id')
    
    if not all([email_address, password, email_id]):
        return jsonify({'error': 'Parametri mancanti'}), 400
    
    # Prima leggi l'email
    mail, error = connect_imap(email_address, password, provider)
    
    if error:
        return jsonify({'error': error}), 401
    
    try:
        mail.select('INBOX')
        status, msg_data = mail.fetch(email_id, '(RFC822)')
        
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                subject = decode_mime_words(msg.get('Subject', ''))
                from_addr = decode_mime_words(msg.get('From', ''))
                body = get_email_body(msg)
                
                mail.close()
                mail.logout()
                
                # Genera riassunto con LLaMA
                # TODO: Integra qui il tuo modello LLaMA
                email_text = f"Oggetto: {subject}\nDa: {from_addr}\n\nContenuto:\n{body[:3000]}"
                
                prompt = f"""Analizza questa email e fornisci un riassunto conciso in italiano:

{email_text}

Riassunto:"""
                
                # PLACEHOLDER - Sostituisci con il tuo modello
                summary = "Riassunto dell'email generato da LLaMA. Integra qui il tuo modello."
                
                return jsonify({
                    'success': True,
                    'summary': summary,
                    'subject': subject,
                    'from': from_addr
                }), 200
        
        return jsonify({'error': 'Email non trovata'}), 404
        
    except Exception as e:
        return jsonify({'error': f'Errore: {str(e)}'}), 500