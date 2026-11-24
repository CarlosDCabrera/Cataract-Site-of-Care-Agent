import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

names = [m.name.replace("models/", "") for m in client.models.list()
         if "flash" in m.name or "pro" in m.name]
for name in names:
    try:
        r = client.models.generate_content(model=name, contents="Reply with the word OK.")
        print(f"OK    {name}: {r.text.strip()[:20]}")
    except Exception as e:
        print(f"FAIL  {name}: {str(e)[:80]}")