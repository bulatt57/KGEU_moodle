# KGEU_moodle
# Перед использованием нужно сгенерировать ключ:
**from cryptography.fernet import Fernet\
key = Fernet.generate_key()\
print(key.decode())**
# Потом сохраняем его в системную переменную через cmd или терминал:
**setx ENCRYPTION_KEY "ваш_ключ" (в Windows)\
export ENCRYPTION_KEY="ваш_ключ" (в Linux)**
