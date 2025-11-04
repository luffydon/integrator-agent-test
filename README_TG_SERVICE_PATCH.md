# Telegram Add-Service Bridge (no auth, add-only) — v2

Endpoint:
  POST /telegram/services/add
Body:
  { "text": "/addservice { \"service\": { \"name\": \"Margherita Pizza\", \"category\": \"food\", \"options\": [\"restaurant\", \"delivery\"], \"price\": 120000 } }" }

Or fenced:
  { "text": "/addservice\n```json\n{ \"service\": { \"name\": \"Margherita Pizza\", \"category\": \"food\", \"options\": [\"restaurant\", \"delivery\"], \"price\": 120000 } }\n```" }

Returns: ServiceAddResult
Requires present in repo:
  - app/models/service_add.py
  - app/services/service_store.py

Security: no header auth; restrict via network controls.
