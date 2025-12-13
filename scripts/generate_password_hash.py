#!/usr/bin/env python3
"""
Helper script to generate bcrypt password hash for CMS_PASSWORD_HASH environment variable.

Usage:
    python3 generate_password_hash.py "your-password"

Or run interactively:
    python3 generate_password_hash.py
"""

import sys
import getpass
try:
    import bcrypt
except ImportError:
    print("Error: bcrypt is not installed. Install it with: pip install bcrypt")
    sys.exit(1)

def generate_hash(password):
    """Generate bcrypt hash for a password."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

if __name__ == "__main__":
    if len(sys.argv) > 1:
        password = sys.argv[1]
    else:
        password = getpass.getpass("Enter password: ")
        password_confirm = getpass.getpass("Confirm password: ")
        if password != password_confirm:
            print("Error: Passwords do not match!")
            sys.exit(1)
    
    if not password:
        print("Error: Password cannot be empty!")
        sys.exit(1)
    
    hash_value = generate_hash(password)
    print("\n" + "="*70)
    print("Generated bcrypt hash:")
    print("="*70)
    print(hash_value)
    print("="*70)
    print("\nAdd this to your .env file:")
    print(f"CMS_PASSWORD_HASH={hash_value}")
    print("\nNote: If CMS_PASSWORD_HASH is set, CMS_PASSWORD will be ignored.")
