# ai_service/check_models.py
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

print("🔍 Listing available models via google.genai Client...\n")

try:
    import requests
    key = os.getenv("GOOGLE_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    resp = requests.get(url)
    data = resp.json()
    
    if "models" in data:
        for m in data["models"]:
            if "generateContent" in m.get("supportedGenerationMethods", []):
                print(f"✅ GENERATE: {m['name']}")
            if "embedContent" in m.get("supportedGenerationMethods", []):
                print(f"🔹 EMBED:    {m['name']}")
    else:
        print(f"❌ Error listing models: {data}")

except Exception as e:
    print(f"❌ Error: {e}")

# python ai_service/check_models.py