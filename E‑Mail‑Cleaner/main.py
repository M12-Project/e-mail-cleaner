import imaplib
import email
from email.header import decode_header
import datetime

# ---------------------------------------------------------
# KONFIGURATION
# ---------------------------------------------------------

CONFIG = {
    "IMAP_Server": "imap.web.de",
    "SMTP-Server": "smtp.web.de",
    "email": "....@web.de",
    "password": "......",

    # Ordner, die automatisch komplett geleert werden sollen
    "auto_clean_folders": ["Spam", "INBOX"],

    # Absender, die niemals gelöscht werden dürfen
    "whitelist": [
        "msa@communication.microsoft.com"
    ],

    # Absender, die immer gelöscht werden sollen
    "blacklist": [
        "neu@mailings.web.de",
        "mailbox@newsletter.emp.de",
        "support@casinonic.com",
        "no-reply@mail.instagram.com",
        "close_friend_updates@facebookmail.com",
        "azure@infoemails.microsoft.com",
        "mailout@blackmagic-design.com",
        "news@updates.ubisoft.com",
        "noreply@steampowered.com"
    ],

    # Betreff-Filter (löschen wenn Betreff diese Wörter enthält)
    "subject_keywords": [
        "Gewonnen",
        "Gratis",
        "Casino",
        "Sale",
        "Store",
        "Wochenende"
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
        self.mail = imaplib.IMAP4_SSL(config["IMAP_Server"])
        self.mail.login(config["email"], config["password"])

        # Ordnerliste abrufen
        self.folder_map = self.get_folder_map()

    # Alle IMAP-Ordner abrufen und in ein Dictionary packen
    def get_folder_map(self):
        status, folders = self.mail.list()
        folder_map = {}

        for f in folders:
            decoded = f.decode()
            # Beispiel: (\\HasNoChildren) "/" "INBOX.Newsletter"
            name = decoded.split(' "/" ')[-1].strip('"')
            folder_map[name.lower()] = name

        print("\nGefundene IMAP-Ordner:")
        for k, v in folder_map.items():
            print(" →", v)

        return folder_map

    # Ordnernamen automatisch korrekt auflösen
    def resolve_folder(self, name):
        key = name.lower()
        return self.folder_map.get(key, None)

    def clean(self):
        print("\nStarte Reinigung...\n")

        # 1) Automatische Ordner leeren
        for folder in self.config["auto_clean_folders"]:
            resolved = self.resolve_folder(folder)
            if resolved:
                self.clean_folder(resolved)
            else:
                print(f"Ordner '{folder}' wurde nicht gefunden!")

        # 2) INBOX nach Regeln filtern
        self.apply_rules("INBOX")

        print("\nReinigung abgeschlossen.")

    def clean_folder(self, folder):
        print(f"Leere Ordner: {folder}")
        try:
            self.mail.select(folder)
            status, data = self.mail.search(None, "ALL")
            for msg_id in data[0].split():
                self.mail.store(msg_id, "+FLAGS", "\\Deleted")
            self.mail.expunge()
        except Exception as e:
            print(f"Fehler beim Leeren von {folder}: {e}")

    def apply_rules(self, folder):
        print(f"\nPrüfe Regeln in: {folder}")
        self.mail.select(folder)

        status, data = self.mail.search(None, "ALL")
        msg_ids = data[0].split()

        for msg_id in msg_ids:
            status, msg_data = self.mail.fetch(msg_id, "(RFC822)")

            # Fehlerhafte oder leere Mails überspringen
            if not msg_data or not msg_data[0]:
                print(f"Überspringe beschädigte Mail {msg_id.decode()}")
                continue

            try:
                msg = email.message_from_bytes(msg_data[0][1])
            except:
                print(f"Kann Mail {msg_id.decode()} nicht lesen – übersprungen.")
                continue

            from_addr = msg.get("From", "").lower()
            subject = decode_subject(msg.get("Subject"))
            mail_date = get_email_date(msg)

            # Regel 1: Whitelist
            if any(w.lower() in from_addr for w in self.config["whitelist"]):
                continue

            # Regel 2: Blacklist
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