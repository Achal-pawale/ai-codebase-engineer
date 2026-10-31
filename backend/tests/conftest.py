import os

# Set a fake key BEFORE any app module is imported, so tests never
# need the real key and never call the real Gemini API.
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")