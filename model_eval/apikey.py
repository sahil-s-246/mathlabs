import requests
import json

response = requests.get(
  url="https://openrouter.ai/api/v1/key",
  headers={
    "Authorization": f"Bearer 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"
  }
)

print(json.dumps(response.json(), indent=2))