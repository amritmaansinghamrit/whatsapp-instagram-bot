#!/usr/bin/env python3
from flask import Flask, request, jsonify, render_template_string
import json
import os
import requests
import re
import hashlib
from datetime import datetime

app = Flask(__name__)

# WhatsApp credentials from environment
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN', '').strip()
PHONE_NUMBER_ID = os.getenv('PHONE_NUMBER_ID', '').strip()
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', 'myverifytoken123').strip()

# Store generated websites in memory (in production, use a database)
generated_websites = {}

def extract_instagram_username(url):
    """Extract Instagram username from URL"""
    patterns = [
        r'instagram\.com/([^/?#]+)',
        r'instagram\.com/([^/?#\s]+)',
        r'@([a-zA-Z0-9._]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            username = match.group(1).strip('/')
            # Clean username
            username = re.sub(r'[^a-zA-Z0-9._]', '', username)
            return username
    return None

def generate_catalog_website(instagram_username, profile_data, products):
    """Generate a custom catalog website from template"""
    # Since we can't read from file system easily, we'll embed the template
    template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{STORE_NAME}} - {{STORE_TAGLINE}}</title>
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600;700&family=Montserrat:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary-color: {{PRIMARY_COLOR}};
            --secondary-color: {{SECONDARY_COLOR}};
            --accent-color: {{ACCENT_COLOR}};
            --text-color: #2B2B2B;
            --text-light: #FFFFFF;
            --background: #FAFAFA;
            --card-bg: #FFFFFF;
            --whatsapp-color: #25D366;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Montserrat', sans-serif;
            color: var(--text-color);
            line-height: 1.6;
            background-color: var(--background);
        }
        
        h1, h2, h3, h4, h5 {
            font-family: 'Cormorant Garamond', serif;
            font-weight: 600;
            margin-bottom: 1rem;
        }
        
        .container {
            width: 100%;
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 15px;
        }
        
        header {
            background-color: var(--card-bg);
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            position: sticky;
            top: 0;
            z-index: 1000;
        }
        
        .header-inner {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 15px 0;
        }
        
        .logo {
            display: flex;
            align-items: center;
        }
        
        .logo-circle {
            width: 48px;
            height: 48px;
            background-color: var(--primary-color);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--text-light);
            font-family: 'Cormorant Garamond', serif;
            font-size: 20px;
            margin-right: 10px;
        }
        
        .logo-text {
            font-family: 'Cormorant Garamond', serif;
            font-size: 22px;
            font-weight: 600;
        }
        
        .whatsapp-button {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background-color: var(--whatsapp-color);
            color: var(--text-light);
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: 500;
            font-size: 14px;
            text-decoration: none;
        }
        
        .hero {
            background: linear-gradient(135deg, var(--secondary-color), var(--primary-color));
            padding: 60px 0;
            text-align: center;
            min-height: 450px;
            display: flex;
            align-items: center;
        }
        
        .hero-title {
            font-size: 42px;
            margin-bottom: 20px;
            color: var(--text-light);
        }
        
        .hero-subtitle {
            font-size: 18px;
            max-width: 600px;
            margin: 0 auto 30px;
            color: var(--text-light);
        }
        
        .cta-button {
            background-color: var(--accent-color);
            color: var(--text-color);
            padding: 12px 32px;
            border-radius: 6px;
            font-weight: 500;
            font-size: 16px;
            border: none;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .section-title {
            text-align: center;
            margin: 50px 0 30px;
            position: relative;
            font-size: 32px;
        }
        
        .section-title:after {
            content: '';
            display: block;
            width: 60px;
            height: 3px;
            background-color: var(--primary-color);
            margin: 10px auto 0;
        }
        
        .product-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 30px;
            margin-bottom: 50px;
        }
        
        .product-card {
            background-color: var(--card-bg);
            border-radius: 6px;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            transition: all 0.3s ease;
        }
        
        .product-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.12);
        }
        
        .product-image {
            width: 100%;
            height: 280px;
            object-fit: cover;
        }
        
        .product-info {
            padding: 20px;
        }
        
        .product-name {
            font-weight: 500;
            margin-bottom: 8px;
            font-size: 18px;
        }
        
        .product-price {
            color: var(--primary-color);
            font-weight: 600;
            margin-bottom: 12px;
            font-size: 20px;
        }
        
        .product-description {
            font-size: 14px;
            color: var(--text-color);
            margin-bottom: 20px;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        
        .whatsapp-order {
            width: 100%;
            padding: 10px;
            background-color: var(--whatsapp-color);
            color: var(--text-light);
            border: none;
            border-radius: 6px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            text-decoration: none;
        }
        
        .whatsapp-order:hover {
            background-color: #20b954;
        }
        
        footer {
            background-color: var(--primary-color);
            color: var(--text-light);
            padding: 60px 0 20px;
            margin-top: 60px;
        }
        
        .footer-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 30px;
            margin-bottom: 30px;
        }
        
        .footer-title {
            font-size: 18px;
            margin-bottom: 15px;
            color: var(--text-light);
        }
        
        .footer-link {
            color: rgba(255,255,255,0.8);
            margin-bottom: 10px;
            display: block;
            text-decoration: none;
            transition: all 0.3s ease;
        }
        
        .footer-contact {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 15px;
            color: rgba(255,255,255,0.8);
        }
        
        .footer-bottom {
            text-align: center;
            padding-top: 20px;
            border-top: 1px solid rgba(255,255,255,0.1);
            font-size: 14px;
            color: rgba(255,255,255,0.6);
        }
        
        .powered-by {
            color: var(--accent-color);
            text-decoration: none;
            font-weight: 500;
        }
        
        @media (max-width: 768px) {
            .product-grid { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); }
            .product-image { height: 180px; }
            .hero-title { font-size: 32px; }
            .hero-subtitle { font-size: 16px; }
            .section-title { font-size: 28px; }
        }
    </style>
</head>
<body>
    <header>
        <div class="container">
            <div class="header-inner">
                <div class="logo">
                    <div class="logo-circle">{{LOGO_INITIALS}}</div>
                    <div class="logo-text">{{STORE_NAME}}</div>
                </div>
                <div class="actions">
                    <a href="https://wa.me/{{WHATSAPP_NUMBER}}" class="whatsapp-button" target="_blank">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                            <path d="M13.601 2.326A7.854 7.854 0 0 0 7.994 0C3.627 0 .068 3.558.064 7.926c0 1.399.366 2.76 1.057 3.965L0 16l4.204-1.102a7.933 7.933 0 0 0 3.79.965h.004c4.368 0 7.926-3.558 7.93-7.93A7.898 7.898 0 0 0 13.6 2.326zM7.994 14.521a6.573 6.573 0 0 1-3.356-.92l-.24-.144-2.494.654.666-2.433-.156-.251a6.56 6.56 0 0 1-1.007-3.505c0-3.626 2.957-6.584 6.591-6.584a6.56 6.56 0 0 1 4.66 1.931 6.557 6.557 0 0 1 1.928 4.66c-.004 3.639-2.961 6.592-6.592 6.592z"/>
                        </svg>
                        <span>Contact on WhatsApp</span>
                    </a>
                </div>
            </div>
        </div>
    </header>

    <section class="hero">
        <div class="container">
            <h1 class="hero-title">{{HERO_TITLE}}</h1>
            <p class="hero-subtitle">{{HERO_SUBTITLE}}</p>
            <button class="cta-button" onclick="document.getElementById('products').scrollIntoView({behavior: 'smooth'})">{{CTA_TEXT}}</button>
        </div>
    </section>

    <section class="products" id="products">
        <div class="container">
            <h2 class="section-title">{{PRODUCTS_TITLE}}</h2>
            <div class="product-grid">
                {{PRODUCTS_HTML}}
            </div>
        </div>
    </section>

    <footer>
        <div class="container">
            <div class="footer-grid">
                <div>
                    <h3 class="footer-title">{{STORE_NAME}}</h3>
                    <p>{{STORE_TAGLINE}}</p>
                </div>
                <div>
                    <h3 class="footer-title">Quick Links</h3>
                    <a href="#" class="footer-link">Home</a>
                    <a href="#products" class="footer-link">Products</a>
                    <a href="{{INSTAGRAM_URL}}" target="_blank" class="footer-link">Instagram</a>
                </div>
                <div>
                    <h3 class="footer-title">Contact Us</h3>
                    <div class="footer-contact">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                            <path d="M13.601 2.326A7.854 7.854 0 0 0 7.994 0C3.627 0 .068 3.558.064 7.926c0 1.399.366 2.76 1.057 3.965L0 16l4.204-1.102a7.933 7.933 0 0 0 3.79.965h.004c4.368 0 7.926-3.558 7.93-7.93A7.898 7.898 0 0 0 13.6 2.326zM7.994 14.521a6.573 6.573 0 0 1-3.356-.92l-.24-.144-2.494.654.666-2.433-.156-.251a6.56 6.56 0 0 1-1.007-3.505c0-3.626 2.957-6.584 6.591-6.584a6.56 6.56 0 0 1 4.66 1.931 6.557 6.557 0 0 1 1.928 4.66c-.004 3.639-2.961 6.592-6.592 6.592z"/>
                        </svg>
                        <span>{{CONTACT_PHONE}}</span>
                    </div>
                    <div class="footer-contact">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                            <path d="M8 16s6-5.686 6-10A6 6 0 0 0 2 6c0 4.314 6 10 6 10zm0-7a3 3 0 1 1 0-6 3 3 0 0 1 0 6z"/>
                        </svg>
                        <span>{{CONTACT_LOCATION}}</span>
                    </div>
                </div>
            </div>
            <div class="footer-bottom">
                <p>&copy; 2025 {{STORE_NAME}}. All rights reserved. | Powered by <a href="https://inhouseapp.in" class="powered-by">InHouse</a></p>
            </div>
        </div>
    </footer>
</body>
</html>"""
    
    # Extract business name from Instagram data
    business_name = profile_data.get('full_name', instagram_username.title().replace('_', ' ').replace('.', ' '))
    if not business_name or business_name == instagram_username:
        business_name = instagram_username.title().replace('_', ' ').replace('.', ' ')
    
    # Generate logo initials
    words = business_name.split()
    logo_initials = ''.join([word[0].upper() for word in words[:2]]) if len(words) >= 2 else business_name[:2].upper()
    
    # Generate color scheme based on business name
    hash_object = hashlib.md5(business_name.encode())
    hash_hex = hash_object.hexdigest()
    
    # Generate colors from hash
    primary_color = f"#{hash_hex[0:2]}{hash_hex[2:4]}{hash_hex[4:6]}"
    secondary_color = f"#{hash_hex[6:8]}{hash_hex[8:10]}{hash_hex[10:12]}"
    accent_color = f"#{hash_hex[12:14]}{hash_hex[14:16]}{hash_hex[16:18]}"
    
    # Generate products HTML
    products_html = ""
    for product in products:
        whatsapp_message = f"Hi! I'm interested in {product['name']} (₹{product['price']}) from your Instagram catalog."
        whatsapp_url = f"https://wa.me/{PHONE_NUMBER_ID.replace('+', '')}?text={requests.utils.quote(whatsapp_message)}"
        
        products_html += f"""
        <div class="product-card">
            <img src="{product['image']}" alt="{product['name']}" class="product-image">
            <div class="product-info">
                <h3 class="product-name">{product['name']}</h3>
                <div class="product-price">₹{product['price']}</div>
                <p class="product-description">{product['description']}</p>
                <a href="{whatsapp_url}" class="whatsapp-order" target="_blank">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                        <path d="M13.601 2.326A7.854 7.854 0 0 0 7.994 0C3.627 0 .068 3.558.064 7.926c0 1.399.366 2.76 1.057 3.965L0 16l4.204-1.102a7.933 7.933 0 0 0 3.79.965h.004c4.368 0 7.926-3.558 7.93-7.93A7.898 7.898 0 0 0 13.6 2.326zM7.994 14.521a6.573 6.573 0 0 1-3.356-.92l-.24-.144-2.494.654.666-2.433-.156-.251a6.56 6.56 0 0 1-1.007-3.505c0-3.626 2.957-6.584 6.591-6.584a6.56 6.56 0 0 1 4.66 1.931 6.557 6.557 0 0 1 1.928 4.66c-.004 3.639-2.961 6.592-6.592 6.592z"/>
                    </svg>
                    Order on WhatsApp
                </a>
            </div>
        </div>
        """
    
    # Replace template variables
    replacements = {
        '{{STORE_NAME}}': business_name,
        '{{STORE_TAGLINE}}': profile_data.get('bio', 'Handcrafted with love and precision'),
        '{{LOGO_INITIALS}}': logo_initials,
        '{{PRIMARY_COLOR}}': primary_color,
        '{{SECONDARY_COLOR}}': secondary_color,
        '{{ACCENT_COLOR}}': accent_color,
        '{{WHATSAPP_NUMBER}}': PHONE_NUMBER_ID.replace('+', ''),
        '{{HERO_TITLE}}': f"Welcome to {business_name}",
        '{{HERO_SUBTITLE}}': profile_data.get('bio', 'Discover our unique collection of handcrafted items'),
        '{{CTA_TEXT}}': 'Shop Now',
        '{{PRODUCTS_TITLE}}': 'Our Collection',
        '{{PRODUCTS_HTML}}': products_html,
        '{{INSTAGRAM_URL}}': f"https://instagram.com/{instagram_username}",
        '{{CONTACT_PHONE}}': f"+91 {PHONE_NUMBER_ID}",
        '{{CONTACT_LOCATION}}': 'India | Worldwide shipping'
    }
    
    # Apply replacements
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, str(value))
    
    return template

def save_catalog_website(instagram_username, html_content):
    """Save the generated website to memory (in production, save to database/file server)"""
    catalog_url = f"https://whatsapp-instagram-bot.onrender.com/catalog/{instagram_username}"
    
    # Store in memory for now
    generated_websites[instagram_username] = html_content
    
    print(f"📄 Generated catalog website for {instagram_username}")
    print(f"🔗 Available at: {catalog_url}")
    
    return catalog_url

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
        print(f"🔄 Attempting to send message to {to}")
        print(f"🔗 URL: {url}")
        print(f"📦 Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(url, headers=headers, json=payload)
        print(f"📤 Response status: {response.status_code}")
        print(f"📄 Response body: {response.text}")
        
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
                                    
                                    print(f"📱 Message from {from_number}: '{text_body}'")
                                    print(f"🤖 Processing message type: {message.get('type')}")
                                    
                                    # Bot logic
                                    if 'hi' in text_body or 'hello' in text_body:
                                        print(f"🎯 Detected greeting: '{text_body}'")
                                        welcome_msg = """🎉 Welcome to In-House Bot!

I help creative entrepreneurs turn their Instagram profiles into professional product catalogs.

Simply send me your Instagram profile URL and I'll create a beautiful catalog of your products automatically!

📸 Send me your Instagram URL to get started!"""
                                        send_whatsapp_message(from_number, welcome_msg)
                                    
                                    elif 'instagram.com' in text_body or '@' in text_body:
                                        print(f"🔍 Processing Instagram URL: {text_body}")
                                        
                                        # Extract Instagram username
                                        instagram_username = extract_instagram_username(text_body)
                                        
                                        if not instagram_username:
                                            error_msg = "❌ Could not extract Instagram username from the URL. Please send a valid Instagram profile URL like:\n\n• https://instagram.com/yourbusiness\n• @yourbusiness"
                                            send_whatsapp_message(from_number, error_msg)
                                            continue
                                        
                                        processing_msg = f"🔄 Processing Instagram profile: @{instagram_username}\n\nI'm analyzing your posts and creating your custom catalog website. This may take a few moments..."
                                        send_whatsapp_message(from_number, processing_msg)
                                        
                                        # Mock Instagram profile data
                                        profile_data = {
                                            'username': instagram_username,
                                            'full_name': instagram_username.title().replace('_', ' ').replace('.', ' '),
                                            'bio': 'Handcrafted items made with love and precision'
                                        }
                                        
                                        # Mock product data 
                                        mock_products = [
                                            {
                                                'name': 'Handmade Ceramic Mug',
                                                'price': '899',
                                                'image': 'https://images.unsplash.com/photo-1544787219-7f47ccb76574?w=400&h=400&fit=crop',
                                                'description': 'Beautiful handcrafted ceramic mug, perfect for your morning coffee.'
                                            },
                                            {
                                                'name': 'Woven Basket',
                                                'price': '1299',
                                                'image': 'https://images.unsplash.com/photo-1586864387967-d02ef85d93e8?w=400&h=400&fit=crop',
                                                'description': 'Natural fiber woven basket, ideal for storage and home decor.'
                                            },
                                            {
                                                'name': 'Artisan Candle',
                                                'price': '599',
                                                'image': 'https://images.unsplash.com/photo-1602874801006-91715cc7e3b1?w=400&h=400&fit=crop',
                                                'description': 'Hand-poured soy candle with natural essential oils.'
                                            }
                                        ]
                                        
                                        # Generate catalog website
                                        html_content = generate_catalog_website(instagram_username, profile_data, mock_products)
                                        
                                        if html_content:
                                            # Save website (in production, this would actually save the file)
                                            catalog_url = save_catalog_website(instagram_username, html_content)
                                            
                                            completion_msg = f"""✅ Your catalog website is ready!

🏪 Business: {profile_data['full_name']}
📦 Products found: {len(mock_products)}
🌐 Website: {catalog_url}

Your Instagram profile has been converted into a beautiful e-commerce website! Customers can now browse your products and order directly via WhatsApp.

Features included:
• Responsive design for all devices
• WhatsApp order integration
• Professional product showcase
• Custom branding and colors

Share your link: {catalog_url}"""
                                            
                                            send_whatsapp_message(from_number, completion_msg)
                                        else:
                                            error_msg = "❌ Sorry, there was an error generating your catalog website. Please try again later."
                                            send_whatsapp_message(from_number, error_msg)
                                    
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

@app.route('/debug')
def debug():
    return jsonify({
        "whatsapp_token_set": bool(WHATSAPP_TOKEN),
        "phone_number_id": PHONE_NUMBER_ID,
        "verify_token": VERIFY_TOKEN,
        "token_length": len(WHATSAPP_TOKEN) if WHATSAPP_TOKEN else 0,
        "generated_sites": list(generated_websites.keys())
    })

@app.route('/catalog/<username>')
def serve_catalog(username):
    """Serve generated catalog websites"""
    if username in generated_websites:
        return generated_websites[username]
    else:
        return '''
        <html>
        <head><title>Catalog Not Found</title></head>
        <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
            <h1>Catalog Not Found</h1>
            <p>The catalog for @{} was not found.</p>
            <p>Send an Instagram URL to <a href="https://wa.me/{}">our WhatsApp bot</a> to generate a catalog!</p>
        </body>
        </html>
        '''.format(username, PHONE_NUMBER_ID), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"🔥 Starting WhatsApp Instagram Bot on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)