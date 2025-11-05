# Telegram Add-Service Bridge — Renamed Commands (add-only, no auth)

Use these commands in Telegram to avoid Stage-A's built-in /addservice wizard:
  - /svcjsonadd
  - /svcadd
  - /svcjson

Example message (inline JSON):
  /svcjsonadd { "service": { "name": "Margherita Pizza", "category": "food", "options": ["restaurant","delivery"], "price": 120000, "currency": "VND", "location": {"city":"Da Nang"}, "metadata": {"promo":"2for1"} } }

Example message (fenced JSON):
  /svcjsonadd
  ```json
  { "service": { "name": "Margherita Pizza", "category": "food", "options": ["restaurant","delivery"], "price": 120000, "currency": "VND", "location": {"city":"Da Nang"}, "metadata": {"promo":"2for1"} } }
  ```

Bridge endpoint:
  POST /telegram/services/add
  Content-Type: application/json
  Body: { "text": "<raw Telegram message>", "chat_id": "<id optional>" }

Response on success: ServiceAddResult JSON with fields id, slug, stored_path, message.

Requirements:
  - app/models/service_add.py  (contains ServiceAddRequest, ServiceAddResult)
  - app/services/service_store.py  (contains ServiceStore with put())
