import imaplib
import email
from document_reader import extract_text_from_file
from io import BytesIO

def read_emails_and_attachments(user, password):
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login(user, password)
    imap.select("inbox")

    result, messages = imap.search(None, "ALL")
    messages = messages[0].split()

    full_text = ""

    for num in messages[-5:]:  # ultime 5 email
        result, data = imap.fetch(num, "(RFC822)")
        msg = email.message_from_bytes(data[0][1])

        full_text += f"\n--- EMAIL ---\nSubject: {msg['subject']}\n\n"

        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                full_text += part.get_payload(decode=True).decode("utf-8")
            
            if part.get("Content-Disposition"):
                file_data = part.get_payload(decode=True)
                file_stream = BytesIO(file_data)
                attachment_text = extract_text_from_file(file_stream)
                full_text += f"\n--- ALLEGATO ---\n{attachment_text}"
    
    imap.logout()
    return full_text
