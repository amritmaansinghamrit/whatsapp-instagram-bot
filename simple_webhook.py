#!/usr/bin/env python3
from flask import Flask, request, jsonify
import json
from datetime import datetime

app = Flask(__name__)

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Webhook verification
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        print(f"🔍 Webhook verification: mode={mode}, token={token}")
        
        if mode == 'subscribe' and token == 'myverifytoken123':
            print("✅ Webhook verified!")
            return challenge
        else:
            print("❌ Webhook verification failed")
            return 'Forbidden', 403
    
    if request.method == 'POST':
        print("🚀 WEBHOOK RECEIVED!")
        print(f"⏰ Time: {datetime.now()}")
        print(f"📦 Headers: {dict(request.headers)}")
        
        try:
            data = request.get_json()
            print(f"📄 Data: {json.dumps(data, indent=2)}")
        except Exception as e:
            print(f"❌ Error parsing JSON: {e}")
            print(f"📄 Raw data: {request.get_data()}")
        
        return jsonify({"status": "received"})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    print("🔥 Starting Python webhook server...")
    app.run(host='0.0.0.0', port=8080, debug=True)