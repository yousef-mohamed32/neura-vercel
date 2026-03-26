from http.server import BaseHTTPRequestHandler
import json
import os
from groq import Groq

# 1. إعداد عميل Groq (تأكد من إضافة GROQ_API_KEY في إعدادات Vercel)
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)
        user_message = data.get("message", "")

        try:
            # 2. طلب الرد من Groq بنظام الـ JSON
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": """
                        You are Neura, a compassionate AI mental health assistant.
                        Analyze the user's emotion and provide a supportive response.
                        You MUST respond in a valid JSON format with exactly these keys:
                        {
                          "emotion": "choose one (Happy, Sad, Anxious, Neutral, Angry)",
                          "empathy_score": "a number from 1 to 100",
                          "response": "your empathetic reply in the same language as the user"
                        }
                        """
                    },
                    {
                        "role": "user",
                        "content": user_message,
                    }
                ],
                model="llama3-8b-8192",
                response_format={"type": "json_object"} # إجبار الموديل على إخراج JSON
            )

            # 3. استخراج النتيجة
            ai_json_response = chat_completion.choices[0].message.content
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(ai_json_response.encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write("Neura Backend is Running!".encode('utf-8'))
