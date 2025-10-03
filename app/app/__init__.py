from __future__ import annotations

# Register default message policy validators at app import time
try:
    from app.utils.message_policy import register_default_policy
    register_default_policy()
except Exception:
    # Avoid import failures blocking app startup
    pass


