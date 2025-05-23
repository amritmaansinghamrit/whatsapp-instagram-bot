#!/usr/bin/env python3
from flask import Flask, request, jsonify, render_template_string
import json
import os
import requests
import re
import hashlib
import threading
import time
from datetime import datetime
from bs4 import BeautifulSoup
from PIL import Image
import io
import base64
from colorthief import ColorThief
import cloudinary
import cloudinary.uploader
import cloudinary.api
from google.cloud import aiplatform
from google.cloud import vision
import vertexai
from vertexai.preview.generative_models import GenerativeModel
import selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

app = Flask(__name__)

# Configuration from environment
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN', '').strip()
PHONE_NUMBER_ID = os.getenv('PHONE_NUMBER_ID', '').strip()
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', 'myverifytoken123').strip()
GOOGLE_PROJECT_ID = os.getenv('GOOGLE_PROJECT_ID', 'inhouse-vertex-final').strip()
GOOGLE_LOCATION = os.getenv('GOOGLE_LOCATION', 'us-central1').strip()
CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME', '').strip()
CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY', '').strip()
CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET', '').strip()

# Google Cloud Authentication Setup
def setup_google_cloud_auth():
    """Setup Google Cloud authentication with multiple fallback methods"""
    
    # Method 1: Check for service account key file (if available)
    GOOGLE_CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), 'google-service-account.json')
    if os.path.exists(GOOGLE_CREDENTIALS_PATH):
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = GOOGLE_CREDENTIALS_PATH
        print(f"✅ Using service account credentials from {GOOGLE_CREDENTIALS_PATH}")
        return True
    
    # Method 2: Check for Application Default Credentials
    try:
        from google.auth import default
        credentials, project = default()
        if project:
            print(f"✅ Using Application Default Credentials for project: {project}")
            return True
    except Exception as e:
        print(f"⚠️  Application Default Credentials not available: {e}")
    
    # Method 3: Check for Google Cloud CLI authentication
    try:
        import subprocess
        result = subprocess.run(['gcloud', 'auth', 'list', '--format=value(account)'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            print(f"✅ Using Google Cloud CLI authentication: {result.stdout.strip()}")
            return True
    except Exception as e:
        print(f"⚠️  Google Cloud CLI not available: {e}")
    
    print("❌ No Google Cloud authentication method found")
    return False

# Setup authentication
GOOGLE_AUTH_AVAILABLE = setup_google_cloud_auth()

# Configure Cloudinary
if CLOUDINARY_CLOUD_NAME:
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET
    )

# Configure Google Cloud Vertex AI
if GOOGLE_PROJECT_ID and GOOGLE_AUTH_AVAILABLE:
    try:
        vertexai.init(project=GOOGLE_PROJECT_ID, location=GOOGLE_LOCATION)
        print(f"✅ Initialized Vertex AI with project: {GOOGLE_PROJECT_ID}")
    except Exception as e:
        print(f"⚠️  Warning: Could not initialize Vertex AI: {e}")
else:
    if not GOOGLE_PROJECT_ID:
        print("⚠️  Warning: GOOGLE_PROJECT_ID not configured")
    if not GOOGLE_AUTH_AVAILABLE:
        print("⚠️  Warning: Google Cloud authentication not available")
    print("⚠️  Vertex AI will use fallback mode")

# Global vision client will be initialized per request to avoid auth issues

# Store generated websites and processing status
generated_websites = {}
processing_status = {}

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

def scrape_instagram_profile_advanced(username):
    """Advanced Instagram scraping with real post content"""
    try:
        # Setup Chrome driver for Instagram scraping
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        try:
            # Install and setup ChromeDriver with fix for ARM64 Mac
            driver_path = ChromeDriverManager().install()
            # Fix for ARM64 Mac - webdriver manager sometimes points to wrong file
            if 'THIRD_PARTY_NOTICES' in driver_path:
                import os
                driver_dir = os.path.dirname(driver_path)
                actual_driver = os.path.join(driver_dir, 'chromedriver')
                if os.path.exists(actual_driver):
                    driver_path = actual_driver
            
            service = webdriver.chrome.service.Service(driver_path)
            driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as driver_error:
            print(f"WebDriver setup error: {driver_error}")
            # Fallback to simple scraping if Chrome not available
            return scrape_instagram_simple(username)
        
        url = f"https://www.instagram.com/{username}/"
        driver.get(url)
        
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "article"))
        )
        
        # Extract profile information
        profile_data = {}
        
        try:
            # Get display name
            profile_name = driver.find_element(By.XPATH, "//h2[contains(@class, '_aa_a')]").text
            profile_data['display_name'] = profile_name
        except:
            profile_data['display_name'] = username.title()
        
        try:
            # Get bio
            bio_element = driver.find_element(By.XPATH, "//div[contains(@class, '_aa_c')]//span")
            profile_data['bio'] = bio_element.text
        except:
            profile_data['bio'] = ''
        
        try:
            # Get profile picture
            profile_pic = driver.find_element(By.XPATH, "//img[contains(@alt, 'profile picture')]").get_attribute('src')
            profile_data['profile_pic'] = profile_pic
        except:
            profile_data['profile_pic'] = None
        
        # Extract post images and captions
        posts = []
        try:
            # Scroll to load more posts
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Get post links
            post_links = driver.find_elements(By.XPATH, "//article//a[contains(@href, '/p/')]")[:9]  # Get first 9 posts
            
            for link in post_links:
                post_url = link.get_attribute('href')
                try:
                    # Get post image
                    img_element = link.find_element(By.TAG_NAME, "img")
                    img_src = img_element.get_attribute('src')
                    
                    # Navigate to post to get caption
                    driver.execute_script("window.open('');")
                    driver.switch_to.window(driver.window_handles[1])
                    driver.get(post_url)
                    
                    time.sleep(2)
                    
                    # Extract caption
                    caption = ""
                    try:
                        caption_element = driver.find_element(By.XPATH, "//article//span[contains(@class, '_aacl')]")
                        caption = caption_element.text
                    except:
                        try:
                            caption_element = driver.find_element(By.XPATH, "//meta[@property='og:description']")
                            caption = caption_element.get_attribute('content')
                        except:
                            caption = ""
                    
                    posts.append({
                        'url': post_url,
                        'image': img_src,
                        'caption': caption,
                        'alt_text': img_element.get_attribute('alt') or ''
                    })
                    
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                    
                except Exception as e:
                    print(f"Error extracting post: {e}")
                    if len(driver.window_handles) > 1:
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                    continue
                
        except Exception as e:
            print(f"Error extracting posts: {e}")
        
        driver.quit()
        
        profile_data.update({
            'username': username,
            'posts': posts,
            'post_count': len(posts)
        })
        
        return profile_data
        
    except Exception as e:
        print(f"Error in advanced scraping: {e}")
        # Fallback to simple scraping
        return scrape_instagram_simple(username)

def scrape_instagram_simple(username):
    """Fallback simple Instagram scraping"""
    try:
        url = f"https://www.instagram.com/{username}/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract basic profile data
        profile_pic = None
        og_image = soup.find('meta', property='og:image')
        if og_image:
            profile_pic = og_image.get('content')
        
        description = soup.find('meta', property='og:description')
        bio = description.get('content', '') if description else ''
        
        title = soup.find('meta', property='og:title')
        display_name = title.get('content', username).replace(' • Instagram', '') if title else username
        
        # Extract images from page
        images = []
        img_tags = soup.find_all('img', src=True)
        for img in img_tags:
            src = img.get('src')
            if src and 'instagram' in src and 'avatar' not in src and 'scontent' in src:
                images.append({
                    'image': src,
                    'caption': img.get('alt', ''),
                    'url': f"https://instagram.com/{username}/",
                    'alt_text': img.get('alt', '')
                })
        
        return {
            'username': username,
            'display_name': display_name,
            'bio': bio,
            'profile_pic': profile_pic,
            'posts': images[:6],
            'post_count': len(images[:6])
        }
        
    except Exception as e:
        print(f"Error in simple scraping: {e}")
        return None

def extract_brand_colors(profile_pic_url):
    """Extract brand colors from profile picture"""
    try:
        if not profile_pic_url:
            return generate_default_colors()
            
        response = requests.get(profile_pic_url, timeout=10)
        if response.status_code == 200:
            image = Image.open(io.BytesIO(response.content))
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Save to temporary file for ColorThief
            temp_file = io.BytesIO()
            image.save(temp_file, format='JPEG')
            temp_file.seek(0)
            
            color_thief = ColorThief(temp_file)
            
            # Get dominant color and palette
            dominant_color = color_thief.get_color(quality=1)
            palette = color_thief.get_palette(color_count=3, quality=1)
            
            # Convert RGB to hex
            primary = f"#{dominant_color[0]:02x}{dominant_color[1]:02x}{dominant_color[2]:02x}"
            secondary = f"#{palette[1][0]:02x}{palette[1][1]:02x}{palette[1][2]:02x}"
            accent = f"#{palette[2][0]:02x}{palette[2][1]:02x}{palette[2][2]:02x}"
            
            return {
                'primary': primary,
                'secondary': secondary,
                'accent': accent
            }
    except Exception as e:
        print(f"Error extracting colors: {e}")
        
    return generate_default_colors()

def analyze_instagram_posts_with_vertex(posts, business_info):
    """Analyze Instagram posts using Google Vertex AI to detect products"""
    try:
        from google.cloud import aiplatform, vision
        import json
        
        # Check if Google Cloud is properly configured
        if not GOOGLE_PROJECT_ID or not GOOGLE_AUTH_AVAILABLE:
            print("⚠️  Google Cloud not configured, using fallback product generation")
            return generate_fallback_products(posts, business_info)
        
        # Initialize Vision API client
        try:
            vision_client = vision.ImageAnnotatorClient()
            # Test the client with a quick call to make sure billing is enabled
            print("🔍 Testing Google Cloud Vision API...")
        except Exception as auth_error:
            print(f"⚠️  Google Cloud Vision API error: {auth_error}")
            if "BILLING_DISABLED" in str(auth_error):
                print("💰 Billing needs to be enabled for Google Cloud Vision API")
                print(f"📍 Please visit: https://console.developers.google.com/billing/enable?project={GOOGLE_PROJECT_ID}")
            elif "authentication" in str(auth_error).lower():
                print("🔐 Authentication issue - please run: gcloud auth application-default login")
            print("🔄 Using fallback product generation instead")
            return generate_fallback_products(posts, business_info)
        
        products = []
        analyzed_count = 0
        
        for post in posts[:6]:  # Analyze up to 6 posts
            try:
                if not post.get('image'):
                    continue
                    
                # Download image for analysis
                response = requests.get(post['image'], timeout=10)
                if response.status_code != 200:
                    continue
                    
                image_content = response.content
                
                # Analyze image with Vision API
                image = vision.Image(content=image_content)
                
                # Detect objects
                objects = vision_client.object_localization(image=image)
                
                # Detect text
                text_detection = vision_client.text_detection(image=image)
                
                # Detect labels
                label_detection = vision_client.label_detection(image=image)
                
                # Extract product information
                detected_objects = []
                for obj in objects.localized_object_annotations:
                    if obj.score > 0.5:  # Only high confidence objects
                        detected_objects.append({
                            'name': obj.name,
                            'score': obj.score
                        })
                
                # Extract text from image
                extracted_text = ""
                if text_detection.text_annotations:
                    extracted_text = text_detection.text_annotations[0].description
                
                # Extract labels
                labels = []
                for label in label_detection.label_annotations:
                    if label.score > 0.7:
                        labels.append(label.description)
                
                # Generate product based on analysis
                product_name = ""
                product_description = ""
                price = ""
                
                # Determine product name from objects or labels
                if detected_objects:
                    product_name = detected_objects[0]['name'].title()
                elif labels:
                    # Filter for product-related labels and avoid generic terms
                    excluded_terms = ['darkness', 'light', 'shadow', 'color', 'background', 'image', 'photo', 'night', 'day', 'monochrome', 'black', 'white']
                    product_labels = [l for l in labels if any(keyword in l.lower() 
                                    for keyword in ['clothing', 'food', 'jewelry', 'bag', 'shoe', 'accessory', 'furniture', 'electronics', 'pottery', 'ceramic', 'tableware', 'baked goods', 'pastry', 'serveware', 'bowl', 'vase', 'plate'])
                                    and not any(excluded in l.lower() for excluded in excluded_terms)]
                    
                    if product_labels:
                        product_name = product_labels[0].title()
                    else:
                        # Use any non-excluded label
                        good_labels = [l for l in labels if not any(excluded in l.lower() for excluded in excluded_terms)]
                        if good_labels:
                            product_name = good_labels[0].title()
                        else:
                            # Fallback based on business type
                            business_name = business_info.get('display_name', '').lower()
                            if 'jewelry' in business_name:
                                product_name = "Handcrafted Jewelry"
                            elif 'bakery' in business_name or 'bread' in business_name:
                                product_name = "Artisan Baked Goods"
                            elif 'pottery' in business_name or 'ceramic' in business_name:
                                product_name = "Ceramic Creation"
                            else:
                                product_name = "Handmade Item"
                
                # Extract price from text or caption
                import re
                price_patterns = [r'\$(\d+(?:\.\d{2})?)', r'₹(\d+(?:,\d{3})*)', r'(\d+)\s*(?:USD|INR|dollars?|rupees?)']
                caption_text = post.get('caption', '') + " " + extracted_text
                
                for pattern in price_patterns:
                    match = re.search(pattern, caption_text, re.IGNORECASE)
                    if match:
                        price = f"₹{match.group(1)}"
                        break
                
                if not price and detected_objects:
                    # Generate estimated price based on object type
                    obj_name = detected_objects[0]['name'].lower()
                    if 'clothing' in obj_name or 'shirt' in obj_name:
                        price = "₹1,299"
                    elif 'bag' in obj_name or 'purse' in obj_name:
                        price = "₹2,499"
                    elif 'shoe' in obj_name:
                        price = "₹1,999"
                    elif 'jewelry' in obj_name:
                        price = "₹3,999"
                    else:
                        price = "₹999"
                
                # Generate product description
                if post.get('caption'):
                    # Use caption as base description
                    description_words = post['caption'][:150].split()
                    product_description = " ".join(description_words[:20])
                else:
                    # Generate description from detected elements
                    if detected_objects and labels:
                        product_description = f"High-quality {product_name.lower()} featuring {', '.join(labels[:3]).lower()}. Perfect for {business_info.get('display_name', 'your lifestyle')}."
                    elif labels:
                        product_description = f"Premium {product_name.lower()} with excellent {labels[0].lower()} quality."
                    else:
                        product_description = f"Exclusive {product_name.lower()} from {business_info.get('display_name', 'our collection')}."
                
                if product_name:
                    product = {
                        'id': f"product_{analyzed_count + 1}",
                        'name': product_name or f"Product {analyzed_count + 1}",
                        'price': price or "₹999",
                        'image': post['image'],
                        'description': product_description,
                        'detected_objects': detected_objects,
                        'labels': labels[:5],
                        'confidence': max([obj['score'] for obj in detected_objects] + [0.8])
                    }
                    products.append(product)
                    analyzed_count += 1
                    
            except Exception as e:
                print(f"Error analyzing post: {e}")
                continue
        
        # If no products detected, create default products from posts
        if not products and posts:
            for i, post in enumerate(posts[:3]):
                products.append({
                    'id': f"product_{i + 1}",
                    'name': f"Featured Product {i + 1}",
                    'price': f"₹{999 + (i * 500)}",
                    'image': post.get('image', ''),
                    'description': post.get('caption', f"Premium product from {business_info.get('display_name', 'our collection')}")[:100] + "...",
                    'detected_objects': [],
                    'labels': [],
                    'confidence': 0.8
                })
        
        return products[:6]  # Return max 6 products
        
    except Exception as e:
        print(f"Error in Vertex AI analysis: {e}")
        # Fallback to basic product generation
        return generate_fallback_products(posts, business_info)

def generate_fallback_products(posts, business_info):
    """Generate fallback products when AI analysis fails"""
    products = []
    for i, post in enumerate(posts[:3]):
        products.append({
            'id': f"product_{i + 1}",
            'name': f"Featured Item {i + 1}",
            'price': f"₹{1299 + (i * 300)}",
            'image': post.get('image', ''),
            'description': post.get('caption', f"Quality product from {business_info.get('display_name', 'our store')}")[:100] + "...",
            'detected_objects': [],
            'labels': [],
            'confidence': 0.6
        })
    return products

def generate_default_colors():
    """Generate default color scheme"""
    return {
        'primary': '#8A6552',
        'secondary': '#D4B996', 
        'accent': '#EEC373'
    }

def upload_image_to_cloudinary(image_url, folder="instagram_products"):
    """Upload image to Cloudinary and return URL"""
    try:
        if not CLOUDINARY_CLOUD_NAME:
            return image_url  # Return original if Cloudinary not configured
            
        response = cloudinary.uploader.upload(
            image_url,
            folder=folder,
            quality="auto",
            fetch_format="auto"
        )
        return response.get('secure_url', image_url)
    except Exception as e:
        print(f"Error uploading to Cloudinary: {e}")
        return image_url

def generate_ai_content(business_name, bio, image_urls):
    """Legacy function - now replaced by Google Vertex AI analysis"""
    # This function is deprecated - we now use analyze_instagram_posts_with_vertex() 
    # which provides real product detection from Instagram posts
    return generate_smart_mock_products(business_name, bio)

def generate_smart_mock_products(business_name, bio):
    """Generate intelligent mock products based on business analysis"""
    business_lower = business_name.lower()
    bio_lower = bio.lower()
    
    # Detect business type
    if any(word in business_lower + bio_lower for word in ['food', 'cake', 'bakery', 'restaurant', 'cafe']):
        return [
            {"name": "Signature Chocolate Cake", "price": "1299", "description": "Rich, moist chocolate cake with premium cocoa and fresh cream frosting."},
            {"name": "Artisan Cookies Box", "price": "599", "description": "Handcrafted cookies made with organic ingredients, perfect for gifting."},
            {"name": "Fresh Fruit Tart", "price": "899", "description": "Seasonal fresh fruits on vanilla custard with crispy pastry base."},
            {"name": "Custom Birthday Cake", "price": "1899", "description": "Personalized birthday cake with your choice of flavors and decorations."}
        ]
    elif any(word in business_lower + bio_lower for word in ['jewelry', 'earring', 'necklace', 'ring', 'silver', 'gold']):
        return [
            {"name": "Silver Statement Earrings", "price": "1599", "description": "Handcrafted sterling silver earrings with intricate traditional designs."},
            {"name": "Gold-Plated Necklace", "price": "2299", "description": "Elegant gold-plated necklace perfect for special occasions."},
            {"name": "Oxidized Silver Ring", "price": "899", "description": "Vintage-style oxidized silver ring with detailed craftsmanship."},
            {"name": "Pearl Drop Earrings", "price": "1299", "description": "Classic pearl drop earrings that complement any outfit beautifully."}
        ]
    elif any(word in business_lower + bio_lower for word in ['fashion', 'clothing', 'dress', 'shirt', 'wear']):
        return [
            {"name": "Embroidered Kurta", "price": "1899", "description": "Traditional embroidered kurta with modern cut and comfortable fit."},
            {"name": "Designer Cotton Dress", "price": "1599", "description": "Flowy cotton dress with unique prints, perfect for casual outings."},
            {"name": "Handwoven Scarf", "price": "799", "description": "Soft handwoven scarf in vibrant colors, ideal for all seasons."},
            {"name": "Ethnic Palazzo Set", "price": "2199", "description": "Comfortable palazzo set with matching dupatta in premium fabric."}
        ]
    elif any(word in business_lower + bio_lower for word in ['art', 'craft', 'handmade', 'pottery', 'ceramic']):
        return [
            {"name": "Handmade Ceramic Vase", "price": "1299", "description": "Beautiful ceramic vase with unique glaze patterns, perfect for home decor."},
            {"name": "Wooden Wall Art", "price": "1899", "description": "Intricate wooden wall art piece carved by skilled artisans."},
            {"name": "Macrame Plant Hanger", "price": "599", "description": "Handwoven macrame plant hanger that adds boho charm to any space."},
            {"name": "Clay Tea Set", "price": "1599", "description": "Traditional clay tea set including teapot and 4 cups, perfect for tea lovers."}
        ]
    else:
        # Generic products
        return [
            {"name": "Premium Gift Box", "price": "1299", "description": "Curated gift box with handpicked items perfect for special occasions."},
            {"name": "Artisan Special", "price": "999", "description": "Our signature handcrafted item made with attention to detail."},
            {"name": "Limited Edition Item", "price": "1599", "description": "Exclusive limited edition piece from our latest collection."},
            {"name": "Custom Creation", "price": "1899", "description": "Personalized item crafted specifically according to your preferences."}
        ]

def generate_mock_products():
    """Fallback mock products"""
    return [
        {"name": "Handcrafted Item", "price": "999", "description": "Beautiful handcrafted item made with care and attention to detail."},
        {"name": "Artisan Special", "price": "1299", "description": "Special artisan creation that showcases traditional craftsmanship."},
        {"name": "Premium Collection", "price": "1599", "description": "Premium quality item from our exclusive collection."}
    ]

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
    business_name = profile_data.get('display_name') or profile_data.get('full_name') or instagram_username.title().replace('_', ' ').replace('.', ' ')
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
        '{{PRIMARY_COLOR}}': profile_data.get('colors', {}).get('primary', primary_color),
        '{{SECONDARY_COLOR}}': profile_data.get('colors', {}).get('secondary', secondary_color),
        '{{ACCENT_COLOR}}': profile_data.get('colors', {}).get('accent', accent_color),
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

def process_instagram_async(username, phone_number):
    """Process Instagram profile asynchronously with advanced AI analysis"""
    try:
        processing_status[username] = "scraping"
        print(f"🔄 Starting advanced processing for @{username}")
        
        # Step 1: Advanced Instagram scraping with real posts
        profile_data = scrape_instagram_profile_advanced(username)
        if not profile_data:
            send_whatsapp_message(phone_number, f"❌ Could not access Instagram profile @{username}. Please check the username and try again.")
            return
        
        processing_status[username] = "extracting_colors"
        
        # Step 2: Extract brand colors from profile picture
        colors = extract_brand_colors(profile_data.get('profile_pic'))
        profile_data['colors'] = colors
        
        processing_status[username] = "analyzing_posts"
        
        # Step 3: Analyze posts with Google Vertex AI for product detection
        ai_products = analyze_instagram_posts_with_vertex(
            profile_data.get('posts', []), 
            profile_data
        )
        
        processing_status[username] = "uploading_images"
        
        # Step 4: Upload images to Cloudinary and create final product data
        products = []
        
        for i, product in enumerate(ai_products):
            # Upload product image to Cloudinary for faster loading
            optimized_image_url = upload_image_to_cloudinary(
                product['image'], 
                f"instagram_{username}/products"
            )
            
            products.append({
                'name': product['name'],
                'price': product['price'], 
                'description': product['description'],
                'image': optimized_image_url,
                'confidence': product.get('confidence', 0.8),
                'detected_objects': product.get('detected_objects', []),
                'labels': product.get('labels', [])
            })
        
        processing_status[username] = "generating_website"
        
        # Step 5: Generate website with dynamic content
        website_data = {
            'username': username,
            'display_name': profile_data['display_name'],
            'bio': profile_data['bio'],
            'profile_pic': profile_data['profile_pic'],
            'colors': colors,
            'post_count': profile_data.get('post_count', 0)
        }
        
        html_content = generate_catalog_website(username, website_data, products)
        
        # Step 6: Save website
        catalog_url = save_catalog_website(username, html_content)
        
        processing_status[username] = "completed"
        
        # Step 7: Send completion message with AI analysis details
        ai_confidence = sum(p.get('confidence', 0.8) for p in products) / len(products) if products else 0.8
        
        completion_msg = f"""✅ Your AI-powered minisite is ready!

🏪 Business: {profile_data['display_name']}
📦 Products: {len(products)} items detected from your posts
🎨 Brand colors extracted from your profile picture
🤖 AI analyzed {profile_data.get('post_count', 0)} Instagram posts
🌐 Website: {catalog_url}

✨ Features included:
• Real Instagram content analysis with Google Vertex AI
• Dynamic product detection from your posts
• Automatic brand color extraction
• AI-generated product descriptions
• Professional product showcase  
• WhatsApp order integration
• Mobile-responsive design
• Analysis confidence: {ai_confidence:.1%}

Share your link: {catalog_url}

Your customers can browse real products from your Instagram and order directly via WhatsApp! 🚀"""

        send_whatsapp_message(phone_number, completion_msg)
        
        print(f"✅ Completed processing for @{username}")
        
    except Exception as e:
        print(f"❌ Error processing @{username}: {e}")
        error_msg = f"❌ Sorry, there was an error creating your minisite for @{username}. Please try again or contact support."
        send_whatsapp_message(phone_number, error_msg)
        processing_status[username] = "failed"

def save_catalog_website(instagram_username, html_content):
    """Save the generated website to memory (in production, save to database/file server)"""
    catalog_url = f"https://whatsapp-instagram-bot.onrender.com/catalog/{instagram_username}"
    
    # Store in memory for now
    generated_websites[instagram_username] = html_content
    
    print(f"📄 Generated catalog website for {instagram_username}")
    print(f"🔗 Available at: {catalog_url}")
    
    return catalog_url

def send_whatsapp_message(to, message):
    """Send a WhatsApp message with improved error handling"""
    if not WHATSAPP_TOKEN:
        print("❌ WhatsApp token not configured")
        return False
        
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
        
        response = requests.post(url, headers=headers, json=payload)
        print(f"📤 Response status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Message sent successfully")
            return True
        else:
            print(f"❌ Failed to send message: {response.text}")
            
            # Check for token expiration
            if "Session has expired" in response.text or "access token" in response.text.lower():
                print("🔄 WhatsApp token has expired!")
                print("📝 Please get a new token from: https://developers.facebook.com/")
                print("💡 Then set: export WHATSAPP_TOKEN='your_new_token'")
            
            return False
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
                                        
                                        # Check if already processing
                                        if instagram_username in processing_status and processing_status[instagram_username] != "completed":
                                            status_msg = f"⏳ Your minisite for @{instagram_username} is already being created. Please wait a moment..."
                                            send_whatsapp_message(from_number, status_msg)
                                            continue
                                        
                                        # Send processing message with timeline
                                        processing_msg = f"""🚀 Creating your AI-powered minisite for @{instagram_username}

⏱️ Estimated time: 2-3 minutes

What I'm doing:
🔍 Advanced Instagram profile scraping with real posts
🎨 Extracting brand colors from your profile picture  
🤖 Analyzing your posts with Google Vertex AI for product detection
📸 Processing Instagram images to identify products
💡 Generating smart product descriptions based on visual analysis
☁️ Optimizing and uploading images to cloud storage
🌐 Building your dynamic custom website

Using cutting-edge AI to create a truly personalized experience!
I'll notify you when it's ready! Please wait..."""
                                        
                                        send_whatsapp_message(from_number, processing_msg)
                                        
                                        # Start async processing
                                        thread = threading.Thread(
                                            target=process_instagram_async, 
                                            args=(instagram_username, from_number)
                                        )
                                        thread.daemon = True
                                        thread.start()
                                    
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
        "generated_sites": list(generated_websites.keys()),
        "processing_status": processing_status,
        "cloudinary_configured": bool(CLOUDINARY_CLOUD_NAME),
        "google_project_id": GOOGLE_PROJECT_ID,
        "google_auth_available": GOOGLE_AUTH_AVAILABLE,
        "vertex_ai_location": GOOGLE_LOCATION,
        "google_project_number": "340700288264"
    })

@app.route('/status/<username>')
def check_status(username):
    """Check processing status for a username"""
    status = processing_status.get(username, "not_found")
    return jsonify({
        "username": username,
        "status": status,
        "catalog_ready": username in generated_websites
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