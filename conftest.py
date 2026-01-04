import os

# Set required environment variables before any module imports
os.environ.setdefault("API_ENDPOINT", "http://test-api-endpoint")
os.environ.setdefault("AUTH_ENDPOINT", "http://test-auth-endpoint")
os.environ.setdefault("CROM_CLIENT_ID", "test-client-id")
os.environ.setdefault("CROM_CLIENT_SECRET", "test-client-secret")
