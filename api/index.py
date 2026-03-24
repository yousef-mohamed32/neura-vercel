import os
import json
import re
from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.error

RAG_DATA = []
try:
    rag_path = os.path.join(os.path.dirname(__file__), '..', 'rag_data.json')
    with open(rag_path, encoding='utf-8') as f:
        RAG_DATA = json.load(f)
except Exception as e:
    print(f"RAG load error: {e}")

DOCTORS = [
    {"id": 1, "name": "Dr. Sara El-Masry", "spec": "Psychiatrist & CBT Therapist", "emoji": "👩‍⚕️", "tags": ["Anxiety", "Depression", "Trauma"], "rating": 4.9, "reviews": 128, "avail": "Tomorrow 10am"},
    {"id": 2, "name": "Dr. Karim Hassan", "spec": "Clinical Psychologist", "emoji": "👨‍⚕️", "tags": ["Grief", "Divorce", "Life Changes"], "rating": 4.8, "reviews": 94, "avail": "Today 4pm"},
    {"id": 3, "name": "Dr. Nour Abdelaziz", "spec": "Family & Couples Therapist", "emoji": "👩‍⚕️", "tags": ["Relationships", "Stress", "Burnout"], "rating": 4.7, "reviews": 76, "avail": "Thu 2pm"},
    {"id": 4, "name": "Dr. Ahmed Sallam", "spec": "Psychiatrist — Severe Cases", "emoji": "👨‍⚕️", "tags": ["Severe Depression", "Crisis", "PTSD"], "rating": 4.9, "reviews": 210, "avail": "Mon 9am"},
]

DOCTOR_PASSWORD = os.environ.get("DOCTOR_PASSWORD", "neura2024")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
CRISIS_WORDS = ['suicide','kill myself','end my life','want to die','self harm','hurt myself','overdose','انتحار','اقتل نفسي']
DOCTOR_WORDS = ['doctor','دكتور','psychiatrist','therapist','معالج','طبيب','appointment','موعد','حجز','specialist','اخصائي']
bookings = []

def tokenize(text):
    return re.sub(r'[^a-z0-9\u0600-\u06ff\s]', ' ', text.lower()).split()

def retrieve_rag(query, top_k=3):
    words = set(w for w in tokenize(query) if len(w) > 3)
    if not words: return []
    scored = []
    for doc in RAG_DATA:
        score = len(words & set(tokenize(doc['c'])))
        if score > 0: scored.append((score, doc))
    scored.sort(key=lambda x: -x[0])
    return [d for _, d in scored[:top_k]]

def call_gemini(system_prompt, messages):
    if not GEMINI_API_KEY: return None, "GEMINI_API_KEY not configured"
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
    except Exception as e:
        return None, str(e)

def build_system(rag_ctx, is_arabic, needs_ref):
    lang = "Arabic" if is_arabic else "English"
    rag_str = ("\n\nREAL THERAPIST INSIGHTS:\n" + "\n".join(f'{i+1}. Patient: "{d["c"][:100]}" → Therapist: "{d["r"][:100]}"' for i, d in enumerate(rag_ctx))) if rag_ctx else ""
    ref_str = "\n\nNOTE: Gently suggest speaking with a mental health professional." if needs_ref else ""
    return f"""You are Neura, a warm compassionate AI mental health support assistant.
CRITICAL: Reply ONLY in {lang}. Never mix languages.
- Warm, empathetic, 2-4 sentences, end with a follow-up question
- After response add: [META:{{"empathy":SCORE,"emotion":"EMOTION","insight":"TEXT","rag_used":BOOL}}]{ref_str}{rag_str}"""

def detect_emotion(text):
    t = text.lower()
    if re.search(r'suicid|انتحار', t): return 'grief'
    if re.search(r'depress|hopeless|حزين|اكتئاب', t): return 'sadness'
    if re.search(r'anxi|panic|قلق', t): return 'anxiety'
    if re.search(r'angry|anger|غضب', t): return 'anger'
    if re.search(r'alone|lonely|وحيد', t): return 'loneliness'
    if re.search(r'grief|فقدان', t): return 'grief'
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
        if self.path == '/api/doctors': self.send_json(200, DOCTORS)
        elif self.path == '/api/health': self.send_json(200, {"status": "ok", "rag_count": len(RAG_DATA)})
        else: self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(content_length))

        if self.path == '/api/chat':
            message = body.get('message', '').strip()
            if not message: self.send_json(400, {"error": "No message"}); return
            is_arabic = bool(re.search(r'[\u0600-\u06FF]', message))
            crisis = any(w in message.lower() for w in CRISIS_WORDS)
            wants_doctor = any(w in message.lower() for w in DOCTOR_WORDS)
            needs_ref = bool(re.search(r'severe|crisis|abuse|suicid|divorce|passed away|انتحار', message.lower()))
            rag_ctx = retrieve_rag(message)
            conv = body.get('history', [])[-8:] + [{"role": "user", "content": message}]
            reply, error = call_gemini(build_system(rag_ctx, is_arabic, needs_ref), conv)
            if error: self.send_json(500, {"error": error}); return
            meta = {"empathy": 70, "emotion": detect_emotion(message), "insight": "", "rag_used": len(rag_ctx) > 0}
            m = re.search(r'\[META:(\{.*?\})\]', reply, re.DOTALL)
            if m:
                try: meta = {**meta, **json.loads(m.group(1))}
                except: pass
                reply = reply[:m.start()].strip()
            self.send_json(200, {"reply": reply, "meta": meta, "crisis": crisis, "wants_doctor": wants_doctor, "language": "ar" if is_arabic else "en", "rag_count": len(rag_ctx)})

        elif self.path == '/api/book':
            b = {**body, "id": len(bookings)+1, "doctor": next((d for d in DOCTORS if d['id']==body.get('doctor_id')), None)}
            bookings.append(b)
            self.send_json(200, {"success": True, "booking": b})

        elif self.path == '/api/doctor/login':
            self.send_json(200 if body.get('password')==DOCTOR_PASSWORD else 401, {"success": body.get('password')==DOCTOR_PASSWORD})

        elif self.path == '/api/doctor/reports':
            if body.get('password')==DOCTOR_PASSWORD: self.send_json(200, {"reports": bookings})
            else: self.send_json(401, {"error": "Unauthorized"})

        else: self.send_json(404, {"error": "Not found"})
