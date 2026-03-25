import os
import json
import re
from http.server import BaseHTTPRequestHandler
import urllib.request

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyC5KqtJZR2gJKJLz9zzY4cLmgQcTjQFP5M")

DOCTORS = [
    {"id": 1, "name": "Dr. Sara El-Masry", "spec": "Psychiatrist & CBT Therapist", "emoji": "👩‍⚕️", "tags": ["Anxiety", "Depression", "Trauma"], "rating": 4.9, "avail": "Tomorrow 10am"},
    {"id": 2, "name": "Dr. Karim Hassan", "spec": "Clinical Psychologist", "emoji": "👨‍⚕️", "tags": ["Grief", "Divorce", "Life Changes"], "rating": 4.8, "avail": "Today 4pm"},
    {"id": 3, "name": "Dr. Nour Abdelaziz", "spec": "Family & Couples Therapist", "emoji": "👩‍⚕️", "tags": ["Relationships", "Stress", "Burnout"], "rating": 4.7, "avail": "Thu 2pm"},
    {"id": 4, "name": "Dr. Ahmed Sallam", "spec": "Psychiatrist — Severe Cases", "emoji": "👨‍⚕️", "tags": ["Severe Depression", "Crisis", "PTSD"], "rating": 4.9, "avail": "Mon 9am"},
]

DOCTOR_PASSWORD = os.environ.get("DOCTOR_PASSWORD", "neura2024")
CRISIS_WORDS = ['suicide','kill myself','end my life','want to die','self harm','overdose','انتحار','اقتل نفسي']
DOCTOR_WORDS = ['doctor','دكتور','psychiatrist','therapist','معالج','طبيب','appointment','موعد','حجز','specialist','اخصائي']
bookings = []

def call_gemini(system_prompt, messages):
    if not GEMINI_API_KEY:
        return None, "GEMINI_API_KEY not set"
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 800, "temperature": 0.7}
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        return data["candidates"][0]["content"]["parts"][0]["text"], None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read().decode()}"
    except Exception as e:
        return None, str(e)

def build_system(is_arabic, needs_ref):
    lang = "Arabic" if is_arabic else "English"
    ref = "\nNOTE: Gently suggest speaking with a mental health professional." if needs_ref else ""
    return f"""You are Neura, a warm compassionate AI mental health support assistant.
CRITICAL: Reply ONLY in {lang}. Never mix languages.
- Warm, empathetic, like a caring therapist
- 2-4 sentences max
- End with one gentle follow-up question
- Never diagnose. Always validate feelings first.{ref}"""

def detect_emotion(text):
    t = text.lower()
    if re.search(r'suicid|انتحار', t): return 'grief'
    if re.search(r'depress|hopeless|حزين|اكتئاب', t): return 'sadness'
    if re.search(r'anxi|panic|قلق', t): return 'anxiety'
    if re.search(r'angry|anger|غضب', t): return 'anger'
    if re.search(r'alone|lonely|وحيد', t): return 'loneliness'
    return 'neutral'

class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass

    def send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        if self.path == '/api/doctors':
            self.send_json(200, DOCTORS)
        elif self.path == '/api/health':
            self.send_json(200, {"status": "ok", "key_set": bool(GEMINI_API_KEY)})
        else:
            self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length))

            if self.path == '/api/chat':
               messages = body.get('messages', [])
               message = messages[-1]['content'].strip() if messages else body.get('message', '').strip()
                if not message:
                    self.send_json(400, {"error": "No message"})
                    return
                is_arabic = bool(re.search(r'[\u0600-\u06FF]', message))
                crisis = any(w in message.lower() for w in CRISIS_WORDS)
                wants_doctor = any(w in message.lower() for w in DOCTOR_WORDS)
                needs_ref = bool(re.search(r'severe|crisis|abuse|suicid|divorce|passed away|انتحار', message.lower()))
                conv = body.get('history', [])[-8:] + [{"role": "user", "content": message}]
                reply, error = call_gemini(build_system(is_arabic, needs_ref), conv)
                if error:
                    self.send_json(500, {"error": error})
                    return
                self.send_json(200, {
                    "reply": reply,
                    "meta": {"empathy": 75, "emotion": detect_emotion(message), "insight": "", "rag_used": False},
                    "crisis": crisis,
                    "wants_doctor": wants_doctor,
                    "language": "ar" if is_arabic else "en",
                    "rag_count": 0
                })

            elif self.path == '/api/book':
                b = {**body, "id": len(bookings)+1, "doctor": next((d for d in DOCTORS if d['id']==body.get('doctor_id')), None)}
                bookings.append(b)
                self.send_json(200, {"success": True, "booking": b})

            elif self.path == '/api/doctor/login':
                ok = body.get('password') == DOCTOR_PASSWORD
                self.send_json(200 if ok else 401, {"success": ok})

            elif self.path == '/api/doctor/reports':
                if body.get('password') == DOCTOR_PASSWORD:
                    self.send_json(200, {"reports": bookings})
                else:
                    self.send_json(401, {"error": "Unauthorized"})
            else:
                self.send_json(404, {"error": "Not found"})

        except Exception as e:
            self.send_json(500, {"error": str(e)})
