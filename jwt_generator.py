# Install PyJWT if not installed:
# pip install pyjwt

import jwt
from datetime import datetime, timedelta, timezone

# Your secret key (keep this private!)
SECRET_KEY = "global-connector-dev-secret-key"

# Data you want to include in JWT (payload)
payload = {
    "user_id": 1,
    "username": "unique",
}

# Generate JWT
token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

# Ensure token is a string (for PyJWT <2.0)
if isinstance(token, bytes):
    token = token.decode('utf-8')

print("Your JWT token:")
print(token)

# Decode JWT (to verify)
decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
print("\nDecoded payload:")
print(decoded)
