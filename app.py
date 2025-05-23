#!/usr/bin/env python3
from flask import Flask, request, jsonify, render_template_string, redirect, session, url_for
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
import subprocess
import tempfile
import shutil

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Configuration from environment
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN', '').strip()
PHONE_NUMBER_ID = os.getenv('PHONE_NUMBER_ID', '').strip()
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', 'myverifytoken123').strip()
GOOGLE_PROJECT_ID = os.getenv('GOOGLE_PROJECT_ID', 'inhouse-vertex-final').strip()
GOOGLE_LOCATION = os.getenv('GOOGLE_LOCATION', 'us-central1').strip()
CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME', '').strip()
CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY', '').strip()
CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET', '').strip()

# Instagram Graph API Configuration
INSTAGRAM_APP_ID = os.getenv('INSTAGRAM_APP_ID', '').strip()
INSTAGRAM_APP_SECRET = os.getenv('INSTAGRAM_APP_SECRET', '').strip()
INSTAGRAM_REDIRECT_URI = os.getenv('INSTAGRAM_REDIRECT_URI', 'https://whatsapp-instagram-bot.onrender.com/instagram/callback').strip()

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

# Store Instagram access tokens (in production, use a proper database)
instagram_tokens = {}

def get_instagram_auth_url(username):
    """Generate Instagram OAuth authorization URL for Instagram Business Login"""
    if not INSTAGRAM_APP_ID:
        return None
    
    # Instagram Basic Display API OAuth URL (direct Instagram login)
    auth_url = f"https://api.instagram.com/oauth/authorize?client_id={INSTAGRAM_APP_ID}&redirect_uri={INSTAGRAM_REDIRECT_URI}&scope=user_profile,user_media&response_type=code&state={username}"
    return auth_url

def exchange_code_for_token(code):
    """Exchange authorization code for access token"""
    if not INSTAGRAM_APP_ID or not INSTAGRAM_APP_SECRET:
        return None
    
    token_url = "https://api.instagram.com/oauth/access_token"
    data = {
        'client_id': INSTAGRAM_APP_ID,
        'client_secret': INSTAGRAM_APP_SECRET,
        'grant_type': 'authorization_code',
        'redirect_uri': INSTAGRAM_REDIRECT_URI,
        'code': code
    }
    
    try:
        response = requests.post(token_url, data=data)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Token exchange failed: {response.text}")
            return None
    except Exception as e:
        print(f"Error exchanging code for token: {e}")
        return None

def get_long_lived_token(short_token):
    """Convert short-lived token to long-lived token"""
    if not INSTAGRAM_APP_SECRET:
        return short_token
    
    exchange_url = f"https://graph.instagram.com/access_token?grant_type=ig_exchange_token&client_secret={INSTAGRAM_APP_SECRET}&access_token={short_token}"
    
    try:
        response = requests.get(exchange_url)
        if response.status_code == 200:
            data = response.json()
            return data.get('access_token', short_token)
        else:
            print(f"Long-lived token exchange failed: {response.text}")
            return short_token
    except Exception as e:
        print(f"Error getting long-lived token: {e}")
        return short_token

def fetch_instagram_profile_api(access_token):
    """Fetch Instagram profile data using Basic Display API (Instagram Business Login)"""
    try:
        # Get user profile using Instagram Basic Display API
        profile_url = f"https://graph.instagram.com/me?fields=id,username,media_count&access_token={access_token}"
        profile_response = requests.get(profile_url)
        
        if profile_response.status_code != 200:
            print(f"Profile fetch failed: {profile_response.text}")
            return None
        
        profile_data = profile_response.json()
        
        # Get user media using Instagram Basic Display API
        media_url = f"https://graph.instagram.com/me/media?fields=id,caption,media_type,media_url,thumbnail_url,timestamp&access_token={access_token}"
        media_response = requests.get(media_url)
        
        if media_response.status_code != 200:
            print(f"Media fetch failed: {media_response.text}")
            return profile_data
        
        media_data = media_response.json()
        posts = []
        
        for item in media_data.get('data', []):
            post = {
                'id': item.get('id'),
                'image': item.get('media_url') or item.get('thumbnail_url'),
                'caption': item.get('caption', ''),
                'timestamp': item.get('timestamp'),
                'likes': 0,  # Not available in Basic Display API
                'comments': 0,  # Not available in Basic Display API
                'media_type': item.get('media_type', 'IMAGE')
            }
            posts.append(post)
        
        profile_data['posts'] = posts
        profile_data['post_count'] = len(posts)
        profile_data['display_name'] = profile_data.get('username', '').title()
        profile_data['bio'] = ''  # Not available in Basic Display API
        
        return profile_data
        
    except Exception as e:
        print(f"Error fetching Instagram data via Basic Display API: {e}")
        return None

def fetch_instagram_comments(media_id, access_token, limit=10):
    """Fetch comments for a specific Instagram post"""
    try:
        comments_url = f"https://graph.instagram.com/{media_id}/comments?fields=id,text,timestamp,username&limit={limit}&access_token={access_token}"
        response = requests.get(comments_url)
        
        if response.status_code == 200:
            return response.json().get('data', [])
        else:
            print(f"Comments fetch failed: {response.text}")
            return []
    except Exception as e:
        print(f"Error fetching comments: {e}")
        return []

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
    """Advanced Instagram scraping with multiple fallback methods"""
    try:
        print(f"🔄 Starting Instagram scraping for {username}")
        
        # Method 1: Try instagram-scraper library first
        print("📚 Trying instagram-scraper library...")
        profile_data = scrape_instagram_with_library(username)
        if profile_data and len(profile_data.get('posts', [])) > 0:
            print(f"✅ Instagram-scraper successful: {len(profile_data['posts'])} posts")
            return profile_data
        
        print("⚠️ Instagram-scraper failed, trying Selenium...")
        
        # Method 2: Fallback to Selenium scraping
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

def get_real_instagram_data(username):
    """Get real Instagram bio, name, and follower data"""
    try:
        url = f'https://www.instagram.com/{username}/'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            html_content = response.text
            
            # Extract bio
            bio_patterns = [
                r'"biography":"([^"]*?)"',
                r'"biography": "([^"]*?)"',
                r'biography":"([^"]*?)"'
            ]
            
            # Extract full name
            name_patterns = [
                r'"full_name":"([^"]*?)"',
                r'"full_name": "([^"]*?)"', 
                r'full_name":"([^"]*?)"'
            ]
            
            # Extract follower count
            follower_patterns = [
                r'"edge_followed_by":\{"count":(\d+)\}',
                r'edge_followed_by":\{"count":(\d+)\}'
            ]
            
            # Search for bio
            bio = ''
            for pattern in bio_patterns:
                match = re.search(pattern, html_content)
                if match:
                    bio = match.group(1)
                    # Decode Unicode escapes safely
                    try:
                        bio = bio.encode('latin1').decode('unicode_escape')
                    except:
                        # If Unicode decoding fails, just clean up what we have
                        bio = bio.replace('\\n', ' ').replace('\\', '')
                    bio = bio.strip()
                    break
            
            # Search for full name  
            full_name = ''
            for pattern in name_patterns:
                match = re.search(pattern, html_content)
                if match:
                    full_name = match.group(1)
                    try:
                        full_name = full_name.encode('latin1').decode('unicode_escape')
                    except:
                        full_name = full_name.replace('\\', '')
                    full_name = full_name.strip()
                    break
            
            # Search for follower count
            followers = 0
            for pattern in follower_patterns:
                match = re.search(pattern, html_content)
                if match:
                    followers = int(match.group(1))
                    break
            
            print(f"✅ Real Instagram data for @{username}:")
            print(f"   Name: {full_name}")
            print(f"   Bio: {bio}")
            print(f"   Followers: {followers}")
            
            return {
                'bio': bio,
                'full_name': full_name,
                'followers': followers,
                'username': username,
                'success': True
            }
        
        return {'success': False}
        
    except Exception as e:
        print(f"❌ Error getting real Instagram data: {e}")
        return {'success': False}

def scrape_instagram_with_library(username, max_posts=10):
    """Scrape Instagram using instagram-scraper library"""
    try:
        print(f"🔍 Using instagram-scraper library for {username}")
        
        # Create temporary directory for downloads
        with tempfile.TemporaryDirectory() as temp_dir:
            # Run instagram-scraper command
            cmd = [
                'instagram-scraper',
                username,
                '--maximum', str(max_posts),
                '--destination', temp_dir,
                '--retain-username',
                '--media-metadata',
                '--comments',
                '--no-interactive'
            ]
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                
                if result.returncode != 0:
                    print(f"Instagram-scraper failed: {result.stderr}")
                    return None
                
                # Parse the downloaded data
                user_dir = os.path.join(temp_dir, username)
                if not os.path.exists(user_dir):
                    print(f"No data downloaded for {username}")
                    return None
                
                profile_data = {
                    'username': username,
                    'display_name': username.title(),
                    'bio': '',
                    'profile_pic_url': '',
                    'posts': [],
                    'post_count': 0
                }
                
                # Look for JSON metadata files
                posts = []
                for file in os.listdir(user_dir):
                    if file.endswith('.json'):
                        try:
                            with open(os.path.join(user_dir, file), 'r') as f:
                                post_data = json.load(f)
                                
                            # Extract post information
                            post = {
                                'image': post_data.get('display_url', ''),
                                'caption': post_data.get('edge_media_to_caption', {}).get('edges', [{}])[0].get('node', {}).get('text', ''),
                                'timestamp': post_data.get('taken_at_timestamp', ''),
                                'likes': post_data.get('edge_liked_by', {}).get('count', 0),
                                'comments': post_data.get('edge_media_to_comment', {}).get('count', 0)
                            }
                            posts.append(post)
                            
                        except Exception as e:
                            print(f"Error parsing JSON file {file}: {e}")
                            continue
                
                # Also look for downloaded images
                image_files = [f for f in os.listdir(user_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                
                # If we have fewer posts from JSON, add image files
                if len(posts) < len(image_files):
                    for i, img_file in enumerate(image_files[:max_posts]):
                        if i >= len(posts):
                            posts.append({
                                'image': os.path.join(user_dir, img_file),
                                'caption': f'Post {i+1}',
                                'timestamp': '',
                                'likes': 0,
                                'comments': 0
                            })
                
                profile_data['posts'] = posts[:max_posts]
                profile_data['post_count'] = len(posts[:max_posts])
                
                print(f"✅ Instagram-scraper found {len(posts)} posts for {username}")
                return profile_data
                
            except subprocess.TimeoutExpired:
                print(f"Instagram-scraper timed out for {username}")
                return None
            except Exception as e:
                print(f"Error running instagram-scraper: {e}")
                return None
                
    except Exception as e:
        print(f"Error in instagram-scraper method: {e}")
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
    """Generate intelligent fallback products when AI analysis fails"""
    # Use intelligent business analysis even for fallback
    smart_products = generate_smart_mock_products(
        business_info.get('display_name', 'Business'), 
        business_info.get('bio', '')
    )
    
    products = []
    
    # If we have posts, use their images; otherwise use placeholder images
    for i, smart_product in enumerate(smart_products):
        if i < len(posts) and posts[i].get('image'):
            image_url = posts[i]['image']
        else:
            # Use business-type appropriate placeholder images
            business_name = business_info.get('display_name', '').lower()
            bio = business_info.get('bio', '').lower()
            combined = business_name + ' ' + bio
            
            if any(word in combined for word in ['plant', 'lily', 'flower', 'garden']):
                image_url = f"https://images.unsplash.com/photo-1416879595882-3373a0480b5b?w=400&h=400&fit=crop"
            elif any(word in combined for word in ['jewelry', 'gold', 'silver', 'ring']):
                image_url = f"https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?w=400&h=400&fit=crop"
            elif any(word in combined for word in ['food', 'cake', 'bakery']):
                image_url = f"https://images.unsplash.com/photo-1578985545062-69928b1d9587?w=400&h=400&fit=crop"
            elif any(word in combined for word in ['fashion', 'clothing', 'dress']):
                image_url = f"https://images.unsplash.com/photo-1434389677669-e08b4cac3105?w=400&h=400&fit=crop"
            else:
                image_url = f"https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=400&h=400&fit=crop"
        
        products.append({
            'id': f"product_{i + 1}",
            'name': smart_product['name'],
            'price': smart_product['price'],
            'image': image_url,
            'description': smart_product['description'],
            'detected_objects': [],
            'labels': [],
            'confidence': 0.7  # Higher confidence for intelligent generation
        })
    
    return products[:4]  # Return max 4 products

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
    """Generate highly intelligent products based on detailed business analysis"""
    business_lower = business_name.lower()
    bio_lower = bio.lower()
    combined_text = business_lower + " " + bio_lower
    
    # Enhanced business type detection with more keywords
    business_types = {
        'plants_nursery': ['plant', 'nursery', 'garden', 'lily', 'peace lily', 'flower', 'bloom', 'botanical', 'green', 'indoor plants'],
        'food_bakery': ['food', 'cake', 'bakery', 'restaurant', 'cafe', 'kitchen', 'cook', 'bake', 'sweet', 'pastry'],
        'jewelry': ['jewelry', 'jewellery', 'earring', 'necklace', 'ring', 'silver', 'gold', 'diamond', 'pearl', 'bracelet'],
        'fashion': ['fashion', 'clothing', 'dress', 'shirt', 'wear', 'style', 'boutique', 'apparel', 'textile'],
        'arts_crafts': ['art', 'craft', 'handmade', 'pottery', 'ceramic', 'creative', 'artist', 'design', 'decor'],
        'beauty_wellness': ['beauty', 'spa', 'skin', 'cosmetic', 'wellness', 'massage', 'therapy', 'salon'],
        'home_decor': ['home', 'decor', 'interior', 'furniture', 'decoration', 'living', 'room', 'house'],
        'fitness': ['fitness', 'gym', 'yoga', 'health', 'workout', 'exercise', 'training', 'wellness'],
        'technology': ['tech', 'computer', 'software', 'digital', 'app', 'website', 'mobile', 'gadget']
    }
    
    # Detect primary business type
    detected_type = 'general'
    max_matches = 0
    
    for biz_type, keywords in business_types.items():
        matches = sum(1 for keyword in keywords if keyword in combined_text)
        if matches > max_matches:
            max_matches = matches
            detected_type = biz_type
    
    # Generate products based on detected business type
    if detected_type == 'plants_nursery':
        return [
            {"name": "Peace Lily Plant", "price": "899", "description": "Beautiful indoor peace lily plant that purifies air and brings tranquility to your space."},
            {"name": "Monstera Deliciosa", "price": "1299", "description": "Stunning large-leaf monstera plant, perfect for modern home decor."},
            {"name": "Snake Plant Collection", "price": "699", "description": "Set of 3 snake plants in decorative pots, ideal for beginners."},
            {"name": "Ceramic Plant Pot Set", "price": "599", "description": "Handcrafted ceramic pots in various sizes, perfect for your green friends."},
            {"name": "Plant Care Kit", "price": "399", "description": "Complete plant care kit with fertilizer, tools, and care instructions."}
        ]
    elif detected_type == 'food_bakery':
        return [
            {"name": "Signature Chocolate Cake", "price": "1299", "description": "Rich, moist chocolate cake with premium cocoa and fresh cream frosting."},
            {"name": "Artisan Cookies Box", "price": "599", "description": "Handcrafted cookies made with organic ingredients, perfect for gifting."},
            {"name": "Fresh Fruit Tart", "price": "899", "description": "Seasonal fresh fruits on vanilla custard with crispy pastry base."},
            {"name": "Custom Birthday Cake", "price": "1899", "description": "Personalized birthday cake with your choice of flavors and decorations."}
        ]
    elif detected_type == 'jewelry':
        return [
            {"name": "Silver Statement Earrings", "price": "1599", "description": "Handcrafted sterling silver earrings with intricate traditional designs."},
            {"name": "Gold-Plated Necklace", "price": "2299", "description": "Elegant gold-plated necklace perfect for special occasions."},
            {"name": "Oxidized Silver Ring", "price": "899", "description": "Vintage-style oxidized silver ring with detailed craftsmanship."},
            {"name": "Pearl Drop Earrings", "price": "1299", "description": "Classic pearl drop earrings that complement any outfit beautifully."}
        ]
    elif detected_type == 'fashion':
        return [
            {"name": "Designer Kurti", "price": "1599", "description": "Elegant designer kurti with modern prints and comfortable fit."},
            {"name": "Cotton Palazzo Set", "price": "1299", "description": "Comfortable cotton palazzo with matching dupatta in trendy colors."},
            {"name": "Silk Scarf Collection", "price": "799", "description": "Premium silk scarves in vibrant patterns, perfect for any season."},
            {"name": "Ethnic Jewelry Set", "price": "999", "description": "Traditional jewelry set that complements ethnic wear beautifully."}
        ]
    elif detected_type == 'arts_crafts':
        return [
            {"name": "Handmade Ceramic Vase", "price": "1299", "description": "Beautiful ceramic vase with unique glaze patterns, perfect for home decor."},
            {"name": "Wooden Wall Art", "price": "1899", "description": "Intricate wooden wall art piece carved by skilled artisans."},
            {"name": "Macrame Plant Hanger", "price": "599", "description": "Handwoven macrame plant hanger that adds boho charm to any space."},
            {"name": "Clay Tea Set", "price": "1599", "description": "Traditional clay tea set including teapot and 4 cups, perfect for tea lovers."}
        ]
    elif detected_type == 'beauty_wellness':
        return [
            {"name": "Organic Face Care Set", "price": "1299", "description": "Complete organic skincare set with cleanser, toner, and moisturizer."},
            {"name": "Herbal Hair Oil", "price": "599", "description": "Natural herbal hair oil for nourishment and healthy growth."},
            {"name": "Aromatherapy Candles", "price": "799", "description": "Set of relaxing aromatherapy candles for stress relief and ambiance."},
            {"name": "Natural Body Scrub", "price": "899", "description": "Exfoliating body scrub made with natural ingredients for smooth skin."}
        ]
    elif detected_type == 'home_decor':
        return [
            {"name": "Decorative Wall Mirror", "price": "1599", "description": "Elegant decorative mirror that enhances any room's aesthetic."},
            {"name": "Cushion Cover Set", "price": "899", "description": "Set of 4 designer cushion covers in matching patterns and colors."},
            {"name": "Table Lamp", "price": "1299", "description": "Modern table lamp with adjustable brightness, perfect for reading."},
            {"name": "Wall Art Canvas", "price": "999", "description": "Beautiful canvas art piece that adds personality to your walls."}
        ]
    else:
        # Enhanced generic products with business name integration
        business_adj = "Premium" if "premium" in combined_text else "Handcrafted" if any(word in combined_text for word in ["handmade", "craft", "artisan"]) else "Exclusive"
        
        return [
            {"name": f"{business_adj} Collection Item", "price": "1299", "description": f"Signature {business_adj.lower()} item from {business_name}, made with attention to detail."},
            {"name": f"{business_name} Special", "price": "999", "description": f"Our most popular item, carefully crafted to meet our customers' expectations."},
            {"name": f"Limited Edition {business_adj}", "price": "1599", "description": f"Exclusive limited edition piece from our latest {business_name} collection."},
            {"name": f"Custom {business_adj} Creation", "price": "1899", "description": f"Personalized item from {business_name}, crafted specifically according to your preferences."}
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

def process_smart_business_analysis(username, phone_number):
    """Process business using real Instagram data + smart AI analysis"""
    print(f"🎯 FUNCTION CALLED: process_smart_business_analysis for @{username} phone: {phone_number}")
    try:
        processing_status[username] = "analyzing"
        print(f"🧠 Starting smart business analysis for @{username}")
        
        # Get real Instagram data first
        try:
            real_data = get_real_instagram_data(username)
            print(f"📊 Real data result: {real_data}")
        except Exception as instagram_error:
            print(f"❌ Instagram data extraction failed: {instagram_error}")
            real_data = {'success': False}
        
        if real_data.get('success'):
            # Use real data
            business_info = {
                'name': real_data.get('full_name') or username.replace('.', ' ').replace('_', ' ').title(),
                'bio': real_data.get('bio') or f'Quality products from {username}',
                'username': username,
                'follower_count': real_data.get('followers', 0),
                'following_count': 0,
                'post_count': 0
            }
            print(f"✅ Using real Instagram data: {business_info['name']}")
        else:
            # Fallback to username analysis
            business_info = {
                'name': username.replace('.', ' ').replace('_', ' ').title(),
                'bio': f'Quality products from {username}',
                'username': username,
                'follower_count': 0,
                'following_count': 0,
                'post_count': 0
            }
            print(f"⚠️ Using fallback data: {business_info['name']}")
        
        # Detect business type from real data
        business_type = detect_business_type(business_info)
        business_info['business_type'] = business_type
        
        print(f"🎯 Detected business type: {business_type}")
        
        # Generate industry-appropriate colors
        colors = generate_business_colors(business_type)
        
        # Generate smart products using AI
        try:
            if VERTEX_AI_AVAILABLE:
                print(f"🤖 Using Vertex AI for product generation")
                products = analyze_business_with_vertex(username, business_info)
            else:
                print(f"📝 Using fallback product generation")
                products = generate_smart_mock_products(business_info['name'], business_info['bio'])
            
            print(f"🛍️ Generated {len(products)} products")
        except Exception as product_error:
            print(f"❌ Product generation failed: {product_error}")
            # Fallback to simple products
            products = [
                {
                    'name': f'{business_info["name"]} Special',
                    'price': '₹299',
                    'description': 'Premium quality product from our collection',
                    'image': 'https://via.placeholder.com/300x300/cccccc/333333?text=Product'
                },
                {
                    'name': f'{business_info["name"]} Premium',
                    'price': '₹499',
                    'description': 'Top-tier product with excellent quality',
                    'image': 'https://via.placeholder.com/300x300/cccccc/333333?text=Product'
                }
            ]
        
        # Create profile data structure
        profile_data = {
            'username': username,
            'display_name': business_info['name'],
            'bio': business_info['bio'],
            'profile_pic_url': '',
            'posts': [],
            'post_count': 0,
            'source': 'smart_analysis'
        }
        
        # Generate website
        try:
            print(f"🌐 Generating website for {username}")
            html_content = generate_catalog_website(username, profile_data, products)
            print(f"📄 Website generated, length: {len(html_content)} characters")
            
            catalog_url = save_catalog_website(username, html_content)
            print(f"💾 Website saved at: {catalog_url}")
        except Exception as website_error:
            print(f"❌ Website generation failed: {website_error}")
            # Create a simple fallback website
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head><title>{business_info['name']}</title></head>
            <body>
                <h1>{business_info['name']}</h1>
                <p>{business_info['bio']}</p>
                <div>
                    {''.join([f'<div><h3>{p["name"]}</h3><p>{p["price"]}</p></div>' for p in products])}
                </div>
            </body>
            </html>
            """
            catalog_url = save_catalog_website(username, html_content)
        
        # Store results
        generated_websites[username] = {
            'html': html_content,
            'products': products,
            'profile': profile_data,
            'timestamp': datetime.now(),
            'colors': colors,
            'source': 'smart_analysis'
        }
        
        processing_status[username] = 'completed'
        
        # Send completion message
        catalog_url = f"https://whatsapp-instagram-bot.onrender.com/catalog/{username}"
        completion_message = f"""🎉 Your website is ready!

📱 {catalog_url}

✨ {len(products)} products added
🛍️ Share this link with your customers!

Want updates? Send me your Instagram again anytime!"""
        
        send_whatsapp_message(phone_number, completion_message)
        print(f"✅ Smart analysis completed for {username}")
        
    except Exception as e:
        print(f"❌ Error in smart business analysis: {e}")
        processing_status[username] = 'failed'
        
        # Clear the failed status after sending error message
        import time
        def clear_failed_status():
            time.sleep(10)  # Wait 10 seconds then clear
            if username in processing_status and processing_status[username] == 'failed':
                del processing_status[username]
        
        threading.Thread(target=clear_failed_status, daemon=True).start()
        
        error_msg = f"😅 Oops! Something went wrong with @{username}. Try sending it again!"
        send_whatsapp_message(phone_number, error_msg)

def detect_business_type(business_info):
    """Detect business type from real Instagram data"""
    bio_lower = business_info['bio'].lower()
    name_lower = business_info['name'].lower()
    username_lower = business_info['username'].lower()
    
    # Combine all text for analysis
    all_text = f"{bio_lower} {name_lower} {username_lower}"
    
    if any(word in all_text for word in ['crochet', 'handmade', 'macrame', 'crafts', 'gifts', 'accessories', 'aesthetic', 'bouquet']):
        return 'Handmade Crafts & Gifts'
    elif any(word in all_text for word in ['plant', 'nursery', 'garden', 'flower', 'green', 'lily']):
        return 'Plant Nursery'
    elif any(word in all_text for word in ['fashion', 'boutique', 'clothing', 'style', 'wear', 'dress']):
        return 'Fashion & Clothing'
    elif any(word in all_text for word in ['food', 'cafe', 'restaurant', 'kitchen', 'bakery', 'cook']):
        return 'Food & Beverage'
    elif any(word in all_text for word in ['beauty', 'cosmetic', 'makeup', 'skincare', 'salon', 'spa']):
        return 'Beauty & Cosmetics'
    elif any(word in all_text for word in ['tech', 'software', 'digital', 'app', 'web', 'code']):
        return 'Technology'
    elif any(word in all_text for word in ['art', 'design', 'creative', 'studio', 'gallery']):
        return 'Art & Design'
    elif any(word in all_text for word in ['jewelry', 'jewellery', 'rings', 'necklace', 'earrings']):
        return 'Jewelry'
    elif any(word in all_text for word in ['home', 'decor', 'furniture', 'interior']):
        return 'Home & Decor'
    else:
        return 'General Business'

def generate_business_colors(business_type):
    """Generate appropriate colors based on detected business type"""
    
    # Color schemes for different business types
    if business_type == 'Handmade Crafts & Gifts':
        return {
            'primary': '#E91E63',     # Pink
            'secondary': '#FCE4EC',   # Light Pink
            'accent': '#AD1457'       # Dark Pink
        }
    elif business_type == 'Plant Nursery':
        return {
            'primary': '#228B22',     # Forest Green
            'secondary': '#90EE90',   # Light Green
            'accent': '#32CD32'       # Lime Green
        }
    elif business_type == 'Fashion & Clothing':
        return {
            'primary': '#FF1493',     # Deep Pink
            'secondary': '#FFB6C1',   # Light Pink
            'accent': '#C71585'       # Medium Violet Red
        }
    elif business_type == 'Food & Beverage':
        return {
            'primary': '#D2691E',     # Chocolate
            'secondary': '#F4A460',   # Sandy Brown
            'accent': '#FF6347'       # Tomato
        }
    elif business_type == 'Beauty & Cosmetics':
        return {
            'primary': '#DA70D6',     # Orchid
            'secondary': '#DDA0DD',   # Plum
            'accent': '#BA55D3'       # Medium Orchid
        }
    elif business_type == 'Technology':
        return {
            'primary': '#4169E1',     # Royal Blue
            'secondary': '#87CEEB',   # Sky Blue
            'accent': '#1E90FF'       # Dodger Blue
        }
    elif business_type == 'Art & Design':
        return {
            'primary': '#9C27B0',     # Purple
            'secondary': '#E1BEE7',   # Light Purple
            'accent': '#6A1B9A'       # Dark Purple
        }
    elif business_type == 'Jewelry':
        return {
            'primary': '#FFD700',     # Gold
            'secondary': '#FFF8DC',   # Cornsilk
            'accent': '#B8860B'       # Dark Goldenrod
        }
    elif business_type == 'Home & Decor':
        return {
            'primary': '#8B4513',     # Saddle Brown
            'secondary': '#DEB887',   # Burlywood
            'accent': '#A0522D'       # Sienna
        }
    else:
        # Default professional colors
        return {
            'primary': '#2C3E50',     # Dark Blue Grey
            'secondary': '#3498DB',   # Blue
            'accent': '#E74C3C'       # Red
        }

def analyze_business_with_vertex(username, business_info):
    """Use Vertex AI to analyze business and generate relevant products"""
    try:
        if not VERTEX_AI_AVAILABLE:
            return generate_smart_mock_products(business_info['name'], business_info['bio'])
        
        # Create business analysis prompt
        prompt = f"""
        Analyze this business and generate 6-8 relevant products:
        
        Business Name: {business_info['name']}
        Instagram Handle: @{username}
        
        Based on the business name and handle, determine:
        1. What type of business this is
        2. What products they likely sell
        3. Generate specific product names with descriptions
        
        Create realistic products with:
        - Product name
        - Price range appropriate for the business type
        - Brief description (2-3 sentences)
        - Product category
        
        Format as JSON array with objects containing: name, price, description, category
        """
        
        model = GenerativeModel("gemini-pro")
        response = model.generate_content(prompt)
        
        if response and response.text:
            try:
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\[.*\]', response.text, re.DOTALL)
                if json_match:
                    products_data = json.loads(json_match.group())
                    
                    products = []
                    for item in products_data:
                        product = {
                            'name': item.get('name', 'Product'),
                            'price': item.get('price', '$25'),
                            'description': item.get('description', 'Quality product'),
                            'image': 'https://via.placeholder.com/300x300/cccccc/333333?text=Product'
                        }
                        products.append(product)
                    
                    return products[:8]  # Limit to 8 products
            except:
                pass
        
        # Fallback to smart mock products
        return generate_smart_mock_products(business_info['name'], business_info['bio'])
        
    except Exception as e:
        print(f"Error in Vertex AI business analysis: {e}")
        return generate_smart_mock_products(business_info['name'], business_info['bio'])

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

@app.route('/instagram/auth/<username>')
def instagram_auth(username):
    """Initiate Instagram OAuth flow"""
    auth_url = get_instagram_auth_url(username)
    if auth_url:
        return redirect(auth_url)
    else:
        return jsonify({'error': 'Instagram app not configured'}), 500

@app.route('/instagram/callback')
def instagram_callback():
    """Handle Instagram OAuth callback"""
    code = request.args.get('code')
    state = request.args.get('state')  # This contains the username
    error = request.args.get('error')
    
    if error:
        return f"Instagram authorization failed: {error}", 400
    
    if not code or not state:
        return "Missing authorization code or state", 400
    
    # Exchange code for token
    token_data = exchange_code_for_token(code)
    if not token_data:
        return "Failed to exchange code for token", 500
    
    access_token = token_data.get('access_token')
    if access_token:
        # Convert to long-lived token
        long_lived_token = get_long_lived_token(access_token)
        
        # Store token for this username
        instagram_tokens[state] = long_lived_token
        
        # Now process the Instagram account with the API
        threading.Thread(
            target=process_instagram_with_api,
            args=(state, long_lived_token)
        ).start()
        
        return f"""
        <html>
        <body>
            <h2>Instagram Authorization Successful!</h2>
            <p>Processing {state}'s Instagram account...</p>
            <p>You will receive a WhatsApp message when your catalog is ready.</p>
            <script>
                setTimeout(() => window.close(), 3000);
            </script>
        </body>
        </html>
        """
    else:
        return "Failed to get access token", 500

def process_instagram_with_api(username, access_token):
    """Process Instagram account using the Graph API"""
    try:
        print(f"🔄 Processing {username} with Instagram API...")
        
        # Fetch real Instagram data using API
        profile_data = fetch_instagram_profile_api(access_token)
        if not profile_data:
            print(f"❌ Failed to fetch Instagram data for {username}")
            return
        
        print(f"✅ Fetched {len(profile_data.get('posts', []))} posts from {username}")
        
        # Enhance posts with comments for review data
        posts_with_comments = []
        for post in profile_data.get('posts', [])[:10]:  # Limit to first 10 posts
            comments = fetch_instagram_comments(post['id'], access_token, limit=5)
            post['comments'] = comments
            posts_with_comments.append(post)
        
        profile_data['posts'] = posts_with_comments
        
        # Continue with existing processing pipeline
        business_info = {
            'name': profile_data.get('display_name', username.title()),
            'bio': profile_data.get('bio', ''),
            'username': username,
            'follower_count': 0,  # Not available in basic API
            'following_count': 0,  # Not available in basic API
            'post_count': profile_data.get('media_count', len(posts_with_comments))
        }
        
        # Extract colors from profile picture if available
        profile_pic_url = None
        if posts_with_comments:
            profile_pic_url = posts_with_comments[0].get('image')
        
        if profile_pic_url:
            colors = extract_brand_colors(profile_pic_url)
        else:
            colors = generate_default_colors()
        
        # Analyze posts with Vertex AI
        if VERTEX_AI_AVAILABLE:
            products = analyze_instagram_posts_with_vertex(posts_with_comments, business_info)
        else:
            products = generate_smart_mock_products(business_info['name'], business_info['bio'])
        
        # Generate website
        html_content = generate_catalog_website(username, profile_data, products)
        save_catalog_website(username, html_content)
        
        # Store in global dict
        generated_websites[username] = {
            'html': html_content,
            'products': products,
            'profile': profile_data,
            'timestamp': datetime.now(),
            'colors': colors,
            'source': 'instagram_api'
        }
        
        processing_status[username] = 'completed'
        
        # Send completion message via WhatsApp
        catalog_url = f"https://whatsapp-instagram-bot.onrender.com/catalog/{username}"
        completion_message = f"🎉 Your Instagram catalog is ready!\n\n📱 View: {catalog_url}\n\n✨ Generated from real Instagram content using official API"
        
        # Note: We'd need the phone number to send the message
        # This would require storing the phone number during the auth process
        print(f"✅ Catalog ready for {username}: {catalog_url}")
        
    except Exception as e:
        print(f"❌ Error processing {username} with API: {e}")
        processing_status[username] = 'failed'

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
                                        welcome_msg = """🎉 Hi! I create free product catalogs for your business!

Just send me your Instagram username (like @yourbusiness) and I'll make you a beautiful website in 30 seconds! 

Try it now! 📸"""
                                        send_whatsapp_message(from_number, welcome_msg)
                                    
                                    elif 'instagram.com' in text_body or '@' in text_body:
                                        print(f"🔍 Processing Instagram URL: {text_body}")
                                        
                                        # Extract Instagram username
                                        instagram_username = extract_instagram_username(text_body)
                                        
                                        if not instagram_username:
                                            error_msg = "🤔 I need your Instagram username! \n\nTry: @yourbusiness or https://instagram.com/yourbusiness"
                                            send_whatsapp_message(from_number, error_msg)
                                            continue
                                        
                                        # Check if already processing
                                        if instagram_username in processing_status and processing_status[instagram_username] != "completed":
                                            status_msg = f"⏳ Already working on @{instagram_username}! Almost done..."
                                            send_whatsapp_message(from_number, status_msg)
                                            continue
                                        
                                        # Start smart analysis immediately - no complex choices
                                        processing_msg = f"""🚀 Creating your catalog for @{instagram_username}...

⏱️ Just 30 seconds! 

Building your beautiful website now! ✨"""
                                        
                                        send_whatsapp_message(from_number, processing_msg)
                                        
                                        # Start smart processing immediately
                                        print(f"🚀 About to start processing thread for {instagram_username}")
                                        thread = threading.Thread(
                                            target=process_smart_business_analysis, 
                                            args=(instagram_username, from_number)
                                        )
                                        thread.daemon = True
                                        thread.start()
                                        print(f"🔥 Processing thread started for {instagram_username}")
                                    
                                    else:
                                        help_msg = """🤔 I didn't understand that.

Send me your Instagram username (like @yourbusiness) and I'll create your free catalog! 

Try: @thepeacelily.in"""
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

@app.route('/reset/<username>')
def reset_status(username):
    """Reset processing status for a username (debug endpoint)"""
    if username in processing_status:
        old_status = processing_status[username]
        del processing_status[username]
        return jsonify({
            "username": username,
            "old_status": old_status,
            "action": "reset",
            "message": f"Reset processing status for @{username}"
        })
    else:
        return jsonify({
            "username": username,
            "action": "no_reset_needed", 
            "message": f"No processing status found for @{username}"
        })

@app.route('/catalog/<username>')
def serve_catalog(username):
    """Serve generated catalog websites"""
    if username in generated_websites:
        # Return only the HTML content, not the entire JSON object
        website_data = generated_websites[username]
        if isinstance(website_data, dict) and 'html' in website_data:
            return website_data['html']
        else:
            # If it's just HTML string (old format)
            return website_data
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