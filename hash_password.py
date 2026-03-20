"""
Run this script to generate hashed passwords for config.yaml.
Usage: python hash_password.py
"""
import streamlit_authenticator as stauth

passwords = input("Enter passwords separated by commas (e.g. pass1,pass2,pass3): ").split(",")
hashed = stauth.Hasher([p.strip() for p in passwords]).generate()

print("\nPaste these into config.yaml:\n")
for i, h in enumerate(hashed):
    print(f"  password {i+1}: {h}")
