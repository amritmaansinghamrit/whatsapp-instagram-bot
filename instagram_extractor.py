#!/usr/bin/env python3
"""
Real Instagram Data Extractor
Gets actual bio, posts, and images from Instagram profiles
"""
import requests
import re
import json
from bs4 import BeautifulSoup
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def extract_real_instagram_data(username):
    """
    Extract real Instagram data using multiple methods
    Returns actual bio, posts, images, follower count
    """
    print(f"🔍 Extracting REAL data for @{username}")
    
    # Method 1: Try web scraping with requests
    data = try_requests_method(username)
    if data and data.get('success'):
        print(f"✅ Method 1 (Requests) successful: {len(data.get('posts', []))} posts")
        return data
    
    # Method 2: Try Selenium with Chrome
    data = try_selenium_method(username)
    if data and data.get('success'):
        print(f"✅ Method 2 (Selenium) successful: {len(data.get('posts', []))} posts")
        return data
    
    # Method 3: Try alternative endpoints
    data = try_alternative_endpoints(username)
    if data and data.get('success'):
        print(f"✅ Method 3 (Alternative) successful: {len(data.get('posts', []))} posts")
        return data
    
    print(f"❌ All methods failed for @{username}")
    return {'success': False, 'error': 'Could not extract Instagram data'}

def try_requests_method(username):
    """Method 1: Advanced requests-based scraping"""
    try:
        # Use different user agents to avoid detection
        user_agents = [
            'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
        
        for user_agent in user_agents:
            headers = {
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            session = requests.Session()
            session.headers.update(headers)
            
            # Try different URLs
            urls = [
                f"https://www.instagram.com/{username}/",
                f"https://instagram.com/{username}/",
                f"https://www.instagram.com/{username}/?__a=1",
            ]
            
            for url in urls:
                try:
                    response = session.get(url, timeout=15)
                    if response.status_code == 200:
                        data = parse_instagram_html(response.text, username)
                        if data and data.get('success'):
                            return data
                except:
                    continue
                    
                time.sleep(1)  # Rate limiting
            
    except Exception as e:
        print(f"Requests method failed: {e}")
    
    return {'success': False}

def parse_instagram_html(html_content, username):
    """Parse Instagram HTML to extract real data"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract data from various sources in the HTML
        profile_data = {
            'username': username,
            'display_name': '',
            'bio': '',
            'follower_count': 0,
            'following_count': 0,
            'post_count': 0,
            'profile_pic_url': '',
            'posts': [],
            'success': False
        }
        
        # Method 1: Look for JSON data in script tags
        scripts = soup.find_all('script', type='text/javascript')
        for script in scripts:
            if script.string and ('window._sharedData' in script.string or 'window.__additionalDataLoaded' in script.string):
                try:
                    # Extract JSON from script
                    json_text = script.string
                    
                    # Find JSON data patterns
                    patterns = [
                        r'window\._sharedData\s*=\s*({.*?});',
                        r'window\.__additionalDataLoaded\([^,]+,\s*({.*?})\)',
                        r'"ProfilePage":\[({.*?})\]'
                    ]
                    
                    for pattern in patterns:
                        match = re.search(pattern, json_text, re.DOTALL)
                        if match:
                            try:
                                data = json.loads(match.group(1))
                                extracted = extract_from_json_data(data, username)
                                if extracted['success']:
                                    return extracted
                            except:
                                continue
                                
                except Exception as e:
                    continue
        
        # Method 2: Look for meta tags
        og_title = soup.find('meta', property='og:title')
        if og_title:
            title = og_title.get('content', '')
            # Extract follower info from title
            follower_match = re.search(r'(\d+(?:,\d+)*)\s+Followers', title)
            if follower_match:
                profile_data['follower_count'] = int(follower_match.group(1).replace(',', ''))
                profile_data['display_name'] = title.split(' •')[0].strip()
        
        og_description = soup.find('meta', property='og:description')
        if og_description:
            profile_data['bio'] = og_description.get('content', '')
        
        og_image = soup.find('meta', property='og:image')
        if og_image:
            profile_data['profile_pic_url'] = og_image.get('content', '')
        
        # Method 3: Look for specific patterns in HTML
        # Extract posts from image tags
        images = soup.find_all('img')
        posts = []
        
        for img in images:
            src = img.get('src', '')
            alt = img.get('alt', '')
            
            # Filter for actual post images
            if ('scontent' in src and 
                'cdninstagram' in src and 
                'p' in src.split('/') and 
                not any(x in src for x in ['profile', 'avatar', 'story'])):
                
                posts.append({
                    'image': src,
                    'caption': alt,
                    'timestamp': '',
                    'likes': 0,
                    'comments': 0
                })
        
        if posts:
            profile_data['posts'] = posts[:12]  # Limit to 12 posts
            profile_data['post_count'] = len(posts)
            profile_data['success'] = True
        
        # If we got some meaningful data, return it
        if (profile_data['bio'] or 
            profile_data['display_name'] or 
            profile_data['posts'] or 
            profile_data['follower_count'] > 0):
            profile_data['success'] = True
            return profile_data
            
    except Exception as e:
        print(f"HTML parsing failed: {e}")
    
    return {'success': False}

def extract_from_json_data(json_data, username):
    """Extract profile data from Instagram JSON"""
    try:
        profile_data = {
            'username': username,
            'success': False
        }
        
        # Navigate through different JSON structures
        user_data = None
        
        # Try different paths in the JSON
        if 'entry_data' in json_data and 'ProfilePage' in json_data['entry_data']:
            user_data = json_data['entry_data']['ProfilePage'][0]['graphql']['user']
        elif 'user' in json_data:
            user_data = json_data['user']
        elif 'data' in json_data and 'user' in json_data['data']:
            user_data = json_data['data']['user']
        
        if user_data:
            profile_data.update({
                'display_name': user_data.get('full_name', ''),
                'bio': user_data.get('biography', ''),
                'follower_count': user_data.get('edge_followed_by', {}).get('count', 0),
                'following_count': user_data.get('edge_follow', {}).get('count', 0),
                'post_count': user_data.get('edge_owner_to_timeline_media', {}).get('count', 0),
                'profile_pic_url': user_data.get('profile_pic_url', ''),
                'posts': []
            })
            
            # Extract posts
            posts_data = user_data.get('edge_owner_to_timeline_media', {}).get('edges', [])
            posts = []
            
            for post_edge in posts_data[:12]:  # Limit to 12 posts
                post = post_edge.get('node', {})
                
                caption_edges = post.get('edge_media_to_caption', {}).get('edges', [])
                caption = ''
                if caption_edges:
                    caption = caption_edges[0].get('node', {}).get('text', '')
                
                posts.append({
                    'image': post.get('display_url', ''),
                    'caption': caption,
                    'timestamp': post.get('taken_at_timestamp', ''),
                    'likes': post.get('edge_liked_by', {}).get('count', 0),
                    'comments': post.get('edge_media_to_comment', {}).get('count', 0)
                })
            
            profile_data['posts'] = posts
            profile_data['success'] = True
            return profile_data
            
    except Exception as e:
        print(f"JSON extraction failed: {e}")
    
    return {'success': False}

def try_selenium_method(username):
    """Method 2: Selenium-based extraction"""
    try:
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(f"https://www.instagram.com/{username}/")
        
        # Wait for content to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "article"))
        )
        
        # Extract data using Selenium
        profile_data = {
            'username': username,
            'posts': [],
            'success': False
        }
        
        # Get profile name
        try:
            name_element = driver.find_element(By.XPATH, "//h2")
            profile_data['display_name'] = name_element.text
        except:
            pass
        
        # Get bio
        try:
            bio_element = driver.find_element(By.XPATH, "//div[contains(@class, '-vDIg')]/span")
            profile_data['bio'] = bio_element.text
        except:
            pass
        
        # Get follower count
        try:
            followers_element = driver.find_element(By.XPATH, "//a[contains(@href, '/followers/')]/span")
            followers_text = followers_element.get_attribute('title') or followers_element.text
            profile_data['follower_count'] = parse_number(followers_text)
        except:
            pass
        
        # Get posts
        try:
            post_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/p/')]")[:12]
            
            for link in post_links:
                try:
                    # Get image from link
                    img = link.find_element(By.TAG_NAME, "img")
                    profile_data['posts'].append({
                        'image': img.get_attribute('src'),
                        'caption': img.get_attribute('alt', ''),
                        'timestamp': '',
                        'likes': 0,
                        'comments': 0
                    })
                except:
                    continue
        except:
            pass
        
        driver.quit()
        
        # Check if we got meaningful data
        if (profile_data.get('display_name') or 
            profile_data.get('bio') or 
            profile_data.get('posts')):
            profile_data['success'] = True
            return profile_data
            
    except Exception as e:
        print(f"Selenium method failed: {e}")
        try:
            driver.quit()
        except:
            pass
    
    return {'success': False}

def try_alternative_endpoints(username):
    """Method 3: Try alternative Instagram endpoints"""
    try:
        # Try different Instagram endpoints
        endpoints = [
            f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}",
            f"https://www.instagram.com/web/search/topsearch/?query={username}",
            f"https://www.instagram.com/{username}/?__a=1&__d=dis",
        ]
        
        headers = {
            'User-Agent': 'Instagram 10.26.0 (iPhone7,2; iOS 10_1_1; en_US; en-US; scale=2.00; gamut=normal; 750x1334)',
            'Accept': '*/*',
            'Accept-Language': 'en-US',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        for endpoint in endpoints:
            try:
                response = requests.get(endpoint, headers=headers, timeout=10)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        extracted = extract_from_json_data(data, username)
                        if extracted['success']:
                            return extracted
                    except:
                        # Try parsing as HTML if JSON fails
                        data = parse_instagram_html(response.text, username)
                        if data and data.get('success'):
                            return data
            except:
                continue
                
    except Exception as e:
        print(f"Alternative endpoints failed: {e}")
    
    return {'success': False}

def parse_number(text):
    """Parse follower/following numbers (handles K, M suffixes)"""
    try:
        text = text.replace(',', '').replace(' ', '')
        if 'K' in text:
            return int(float(text.replace('K', '')) * 1000)
        elif 'M' in text:
            return int(float(text.replace('M', '')) * 1000000)
        else:
            return int(text)
    except:
        return 0

if __name__ == "__main__":
    # Test the extractor
    username = "thepeacelily.in"
    result = extract_real_instagram_data(username)
    
    if result['success']:
        print(f"\n✅ SUCCESS for @{username}:")
        print(f"Name: {result.get('display_name', 'N/A')}")
        print(f"Bio: {result.get('bio', 'N/A')[:100]}...")
        print(f"Followers: {result.get('follower_count', 0)}")
        print(f"Posts: {len(result.get('posts', []))}")
    else:
        print(f"\n❌ FAILED for @{username}")
        print(f"Error: {result.get('error', 'Unknown error')}")