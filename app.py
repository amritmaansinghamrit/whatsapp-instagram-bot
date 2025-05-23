#!/usr/bin/env python3
from flask import Flask, request, jsonify
import json
import os
import requests
from datetime import datetime

app = Flask(__name__)

# WhatsApp credentials from environment
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN', '').strip()
PHONE_NUMBER_ID = os.getenv('PHONE_NUMBER_ID', '').strip()
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', 'myverifytoken123').strip()

def send_whatsapp_message(to, message):
    """Send a WhatsApp message"""
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        'Authorization': f'Bearer {WHATSAPP_TOKEN}',
        'Content-Type': 'application/json'
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"📤 Message sent to {to}: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return False

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Webhook verification
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        print(f"🔍 Webhook verification: mode={mode}, token={token}")
        
        if mode == 'subscribe' and token == VERIFY_TOKEN:
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
            
            # Process WhatsApp messages
            if data and 'entry' in data:
                for entry in data['entry']:
                    for change in entry.get('changes', []):
                        if change.get('field') == 'messages':
                            value = change.get('value', {})
                            messages = value.get('messages', [])
                            
                            for message in messages:
                                if message.get('type') == 'text':
                                    from_number = message.get('from')
                                    text_body = message.get('text', {}).get('body', '').lower().strip()
                                    
                                    print(f"📱 Message from {from_number}: {text_body}")
                                    
                                    # Bot logic
                                    if 'hi' in text_body or 'hello' in text_body:
                                        welcome_msg = """🎉 Welcome to In-House Bot!

I help creative entrepreneurs turn their Instagram profiles into professional product catalogs.

Simply send me your Instagram profile URL and I'll create a beautiful catalog of your products automatically!

📸 Send me your Instagram URL to get started!"""
                                        send_whatsapp_message(from_number, welcome_msg)
                                    
                                    elif 'instagram.com' in text_body:
                                        processing_msg = f"🔄 Processing your Instagram profile: {text_body}\n\nI'm analyzing your posts and extracting product information. This may take a few moments..."
                                        send_whatsapp_message(from_number, processing_msg)
                                        
                                        # Simulate processing
                                        completion_msg = "✅ Your product catalog is ready!\n\n🏪 Business: Your Instagram Business\n📦 Products found: 3\n\nYour Instagram posts have been converted into a professional product catalog!"
                                        send_whatsapp_message(from_number, completion_msg)
                                    
                                    else:
                                        help_msg = """🤔 I didn't understand that.

Send me:
• "hi" or "hello" to begin
• Your Instagram profile URL to create a catalog

How can I help you today?"""
                                        send_whatsapp_message(from_number, help_msg)
            
        except Exception as e:
            print(f"❌ Error processing webhook: {e}")
        
        return jsonify({"status": "received"})

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route('/')
def home():
    return jsonify({
        "message": "WhatsApp Instagram Bot is running!",
        "endpoints": ["/webhook", "/health"],
        "status": "active"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"🔥 Starting WhatsApp Instagram Bot on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)