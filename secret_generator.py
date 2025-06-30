import secrets

# Generate a cryptographically strong random string for your JWT secret
# The recommended length for a secure secret is often 32 bytes (256 bits) or more.
# secrets.token_hex(nbytes) returns a random text string, in hexadecimal, containing nbytes random bytes.
jwt_secret = secrets.token_hex(32) 

print(f"Generated JWT Secret: {jwt_secret}")