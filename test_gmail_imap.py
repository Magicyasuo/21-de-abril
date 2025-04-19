import imaplib
from functools import partial
from imap_tools import MailBox, AND

# Configuración
IMAP_SERVER = 'imap.gmail.com'
IMAP_PORT = 993
EMAIL_ACCOUNT = 'hospitalsararecolombia@gmail.com'
EMAIL_PASSWORD = 'nrqxthjfdfejjipz'  # Contraseña de aplicación SIN espacios

# Conexión segura
mailbox = MailBox(IMAP_SERVER)
mailbox._factory = partial(imaplib.IMAP4_SSL, IMAP_SERVER, IMAP_PORT)
mailbox.login(EMAIL_ACCOUNT, EMAIL_PASSWORD, initial_folder='INBOX')

# Buscar correos donde el remitente sea ingdiegoter1998@gmail.com
for msg in mailbox.fetch(AND(from_='ingdiegoter1998@gmail.com')):
    print("Asunto:", msg.subject)
    print("De:", msg.from_)
    print("Fecha:", msg.date)
    print("Cuerpo:")
    print(msg.text.strip())
    print("---")

mailbox.logout()
