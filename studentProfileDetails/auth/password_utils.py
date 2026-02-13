from passlib.context import CryptContext
import re
from typing import Optional

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return pwd_context.hash(password)

def validate_password_strength(password: str) -> tuple[bool, Optional[str]]:
    """
    Validate password strength.
    Returns (is_valid, error_message)
    """
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

def generate_default_password() -> str:
    """Generate a secure default password for new users (max 72 bytes for bcrypt)."""
    import secrets
    import string
    
    # Use a shorter but still secure password to stay within bcrypt's 72-byte limit
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    # Generate 16 characters which should be well within the limit
    password = ''.join(secrets.choice(alphabet) for _ in range(16))
    
    # Ensure password meets requirements and stays within limit
    attempts = 0
    while (not validate_password_strength(password)[0] or 
           len(password.encode('utf-8')) > 72) and attempts < 10:
        password = ''.join(secrets.choice(alphabet) for _ in range(16))
        attempts += 1
    
    # If still not valid, use a simpler but secure password
    if attempts >= 10:
        password = f"Temp{secrets.randbelow(100000):05d}!"
    
    return password
