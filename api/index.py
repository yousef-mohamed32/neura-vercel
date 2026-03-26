from http.server import BaseHTTPRequestHandler
import json
import os
from groq import Groq

# سحب المفتاح من Vercel Environment Variables
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data)
            user_input = data.get("message", "")

            # طلب الرد من Llama 3 بنظام JSON Mode
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": """
                        You are Neura, a mental health AI assistant. 
                        Respond ONLY in a JSON object with:
                        - "emotion": (Happy, Sad, Anxious, Neutral, Angry)
                        - "empathy_score": (integer 1-100)
                        - "response": (Supportive message in user's language)
                        """
                    },
                    {"role": "user", "content": user_input}
                ],
                model="llama3-8b-8192",
                response_format={"type": "json_object"}
            )

            result = chat_completion.choices[0].message.content
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(result.encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    # لضمان عدم وجود مشاكل CORS
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
