"""Print the Snowflake-format public key fingerprint from a PKCS#8 private key.

Usage:
    python fingerprint.py [path/to/rsa_key.p8]

Output: SHA256:<base64>  — paste into SF_PUBLIC_KEY_FP.
"""
import base64
import getpass
import hashlib
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization


def main() -> None:
    key_path = Path(sys.argv[1] if len(sys.argv) > 1 else "rsa_key.p8")
    pem = key_path.read_bytes()

    try:
        private_key = serialization.load_pem_private_key(pem, password=None)
    except TypeError:
        password = getpass.getpass(f"Passphrase for {key_path.name}: ").encode()
        private_key = serialization.load_pem_private_key(pem, password=password)

    public_der = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    digest = hashlib.sha256(public_der).digest()
    print("SHA256:" + base64.b64encode(digest).decode())


if __name__ == "__main__":
    main()
