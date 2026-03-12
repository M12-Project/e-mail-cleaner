import imaplib
import email
from email.header import decode_header
import datetime

# ---------------------------------------------------------
# KONFIGURATION
# ---------------------------------------------------------

CONFIG = {
    "imap_server": "imap.web.de",
    "email": "DEINE_MAIL@web.de",
    "password": "DEIN_PASSWORT",

    # Ordner, die automatisch komplett geleert werden sollen
    "auto_clean_folders": ["Spam", "Trash", "Newsletter"],

    # Absender, die niemals gelöscht werden dürfen
    "whitelist": [
        "chef@firma.de",
        "support@wichtig.de"
    ],

    # Absender, die immer gelöscht werden sollen
    "blacklist": [
        "spam@scam.com",
        "newsletter@promo.de"
    ],

    # Betreff-Filter (löschen wenn Betreff diese Wörter enthält)
    "subject_keywords": [
        "Gewonnen",
        "Rechnung",
        "Gratis",
        "Casino"
    ],

    # Alter in Tagen (älter als X Tage löschen)
    "max_age_days": 30
}


# ---------------------------------------------------------
# HILFSFUNKTIONEN
# ---------------------------------------------------------

def decode_subject(raw_subject):
    if raw_subject is None:
        return ""
    decoded, encoding = decode_header(raw_subject)[0]
    if isinstance(decoded, bytes):
        return decoded.decode(encoding or "utf-8", errors="ignore")
    return decoded


def get_email_date(msg):
    date_tuple = email.utils.parsedate_tz(msg["Date"])
    if date_tuple:
        return datetime.datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
    return None


# ---------------------------------------------------------
# HAUPTKLASSE
# ---------------------------------------------------------

class EmailCleaner:
    def __init__(self, config):
        self.config = config
        self.mail = imaplib.IMAP4_SSL(config["imap_server"])
        self.mail.login(config["email"], config["password"])

    def clean(self):
        print("Starte Reinigung...")

        # 1) Automatische Ordner leeren
        for folder in self.config["auto_clean_folders"]:
            self.clean_folder(folder)

        # 2) INBOX nach Regeln filtern
        self.apply_rules("INBOX")

        print("Reinigung abgeschlossen.")

    def clean_folder(self, folder):
        print(f"Leere Ordner: {folder}")
        try:
            self.mail.select(folder)
            status, data = self.mail.search(None, "ALL")
            for msg_id in data[0].split():
                self.mail.store(msg_id, "+FLAGS", "\\Deleted")
            self.mail.expunge()
        except:
            print(f"Ordner {folder} existiert nicht.")

    def apply_rules(self, folder):
        print(f"Prüfe Regeln in: {folder}")
        self.mail.select(folder)

        status, data = self.mail.search(None, "ALL")
        msg_ids = data[0].split()

        for msg_id in msg_ids:
            status, msg_data = self.mail.fetch(msg_id, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])

            from_addr = msg.get("From", "").lower()
            subject = decode_subject(msg.get("Subject"))
            mail_date = get_email_date(msg)

            # Regel 1: Whitelist → niemals löschen
            if any(w.lower() in from_addr for w in self.config["whitelist"]):
                continue

            # Regel 2: Blacklist → immer löschen
            if any(b.lower() in from_addr for b in self.config["blacklist"]):
                self.delete(msg_id, reason="Blacklist")
                continue

            # Regel 3: Betreff enthält bestimmte Wörter
            if any(keyword.lower() in subject.lower() for keyword in self.config["subject_keywords"]):
                self.delete(msg_id, reason="Betreff-Filter")
                continue

            # Regel 4: Alter > X Tage
            if mail_date:
                age_days = (datetime.datetime.now() - mail_date).days
                if age_days > self.config["max_age_days"]:
                    self.delete(msg_id, reason=f"Alter > {self.config['max_age_days']} Tage")
                    continue

    def delete(self, msg_id, reason):
        print(f"Lösche Mail {msg_id.decode()} → Grund: {reason}")
        self.mail.store(msg_id, "+FLAGS", "\\Deleted")
        self.mail.expunge()

# ---------------------------------------------------------
# START
# ---------------------------------------------------------

if __name__ == "__main__":
    cleaner = EmailCleaner(CONFIG)
    cleaner.clean()