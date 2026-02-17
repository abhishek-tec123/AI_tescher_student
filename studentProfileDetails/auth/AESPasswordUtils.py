# from cryptography.fernet import Fernet
# import os
# from dotenv import load_dotenv

# load_dotenv()

# # AES key (store in .env)
# AES_KEY = os.environ.get("AES_KEY")
# print("using ASE key : ",AES_KEY)
# if not AES_KEY:
#     AES_KEY = Fernet.generate_key()
#     print("Generated AES_KEY:", AES_KEY.decode())  # Save securely!
# fernet = Fernet(AES_KEY)

# def encrypt_password(password: str) -> str:
#     """Encrypt password for storage in password_hash field."""
#     return fernet.encrypt(password.encode()).decode()

# def decrypt_password(encrypted_password: str) -> str:
#     """Decrypt stored password_hash."""
#     return fernet.decrypt(encrypted_password.encode()).decode()

from cryptography.fernet import Fernet
import os
import re
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
# ---------------------------
# AES KEY (store in .env)
# ---------------------------
AES_KEY = os.environ.get("AES_KEY")

if not AES_KEY:
    raise ValueError("AES_KEY not found in environment variables")

fernet = Fernet(AES_KEY.encode() if isinstance(AES_KEY, str) else AES_KEY)


# ---------------------------
# Encryption / Decryption
# ---------------------------
def encrypt_password(password: str) -> str:
    return fernet.encrypt(password.encode()).decode()


def decrypt_password(encrypted_password: str) -> str:
    return fernet.decrypt(encrypted_password.encode()).decode()


# ---------------------------
# Password validation
# ---------------------------
def validate_password_strength(password: str) -> tuple[bool, Optional[str]]:
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character"
    return True, None


# ---------------------------
# Default password generator
# ---------------------------
def generate_default_password() -> str:
    import secrets
    import string

    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(16))
    return password
