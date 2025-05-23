#!/usr/bin/env python3
"""
Test different Instagram extraction methods to find what works
"""
import requests
import json
import re
from bs4 import BeautifulSoup
import time

def test_method_1_simple_meta(username):
    """Method 1: Simple meta tag extraction"""
    print(f"\n🧪 Testing Method 1: Simple meta tags for @{username}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1'
        }
        
        response = requests.get(f"https://www.instagram.com/{username}/", headers=headers, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Get meta tags
            og_title = soup.find('meta', property='og:title')
            og_description = soup.find('meta', property='og:description') 
            og_image = soup.find('meta', property='og:image')
            
            title = og_title.get('content') if og_title else 'Not found'
            description = og_description.get('content') if og_description else 'Not found'
            image = og_image.get('content') if og_image else 'Not found'
            
            print(f"Title: {title}")
            print(f"Description: {description}")
            print(f"Image: {image}")
            
            # Extract follower count from title/description
            follower_match = re.search(r'(\d+(?:,\d+)*)\s+Followers', title + ' ' + description)
            followers = int(follower_match.group(1).replace(',', '')) if follower_match else 0
            
            print(f"Followers extracted: {followers}")
            
            if title != 'Not found' or description != 'Not found':
                return {
                    'success': True,
                    'method': 'meta_tags',
                    'display_name': title.replace(' • Instagram photos and videos', '').replace(' (@', ' ('),
                    'bio': description,
                    'followers': followers,
                    'profile_pic': image if image != 'Not found' else ''
                }
        
    except Exception as e:
        print(f"Method 1 failed: {e}")
    
    return {'success': False}

def test_method_2_json_search(username):
    """Method 2: Look for JSON data in page source"""
    print(f"\n🧪 Testing Method 2: JSON extraction for @{username}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(f"https://www.instagram.com/{username}/", headers=headers, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            html = response.text
            
            # Look for specific patterns
            patterns = [
                r'"biography":"([^"]*?)"',
                r'"full_name":"([^"]*?)"',
                r'"edge_followed_by":\{"count":(\d+)\}',
                r'"profile_pic_url":"([^"]*?)"'
            ]
            
            results = {}
            for i, pattern in enumerate(patterns):
                match = re.search(pattern, html)
                if match:
                    field = ['bio', 'name', 'followers', 'pic'][i]
                    value = match.group(1)
                    if field == 'followers':
                        value = int(value)
                    elif field in ['bio', 'name']:
                        # Try to decode unicode
                        try:
                            value = value.encode('latin1').decode('unicode_escape')
                        except:
                            pass
                        value = value.replace('\\n', ' ').strip()
                    results[field] = value
                    print(f"Found {field}: {str(value)[:100]}...")
            
            if results:
                return {
                    'success': True,
                    'method': 'json_patterns',
                    'display_name': results.get('name', ''),
                    'bio': results.get('bio', ''),
                    'followers': results.get('followers', 0),
                    'profile_pic': results.get('pic', '')
                }
        
    except Exception as e:
        print(f"Method 2 failed: {e}")
    
    return {'success': False}

def test_method_3_mobile_request(username):
    """Method 3: Mobile Instagram request"""
    print(f"\n🧪 Testing Method 3: Mobile request for @{username}")
    
    try:
        headers = {
            'User-Agent': 'Instagram 219.0.0.12.117 Android (26/8.0.0; 480dpi; 1080x1920; OnePlus; ONEPLUS A6000; OnePlus6; qcom; en_US; 341778976)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        # Try different mobile URLs
        urls = [
            f"https://www.instagram.com/{username}/?__a=1",
            f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}",
            f"https://www.instagram.com/{username}/channel/?__a=1"
        ]
        
        for url in urls:
            print(f"Trying: {url}")
            try:
                response = requests.get(url, headers=headers, timeout=10)
                print(f"Status: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        print(f"Got JSON response: {type(data)}")
                        
                        # Try to extract user data
                        user_data = None
                        if 'data' in data and 'user' in data['data']:
                            user_data = data['data']['user']
                        elif 'user' in data:
                            user_data = data['user']
                        elif 'graphql' in data and 'user' in data['graphql']:
                            user_data = data['graphql']['user']
                        
                        if user_data:
                            print(f"Found user data keys: {list(user_data.keys())}")
                            return {
                                'success': True,
                                'method': 'mobile_api',
                                'display_name': user_data.get('full_name', ''),
                                'bio': user_data.get('biography', ''),
                                'followers': user_data.get('edge_followed_by', {}).get('count', 0),
                                'profile_pic': user_data.get('profile_pic_url', '')
                            }
                    except json.JSONDecodeError:
                        print("Response not JSON")
                        continue
            except Exception as e:
                print(f"URL failed: {e}")
                continue
        
    except Exception as e:
        print(f"Method 3 failed: {e}")
    
    return {'success': False}

def test_method_4_alternative_sources(username):
    """Method 4: Alternative data sources"""
    print(f"\n🧪 Testing Method 4: Alternative sources for @{username}")
    
    try:
        # Try Picuki (Instagram viewer)
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(f"https://www.picuki.com/profile/{username}", headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract from Picuki
                profile_info = soup.find('div', class_='profile-info')
                if profile_info:
                    name_elem = profile_info.find('h1')
                    bio_elem = profile_info.find('div', class_='profile-description')
                    
                    name = name_elem.text.strip() if name_elem else ''
                    bio = bio_elem.text.strip() if bio_elem else ''
                    
                    if name or bio:
                        return {
                            'success': True,
                            'method': 'picuki',
                            'display_name': name,
                            'bio': bio,
                            'followers': 0,
                            'profile_pic': ''
                        }
        except:
            pass
        
        # Try Instagram search endpoint
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(f"https://www.instagram.com/web/search/topsearch/?query={username}", headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                users = data.get('users', [])
                for user in users:
                    user_data = user.get('user', {})
                    if user_data.get('username') == username:
                        return {
                            'success': True,
                            'method': 'search_api',
                            'display_name': user_data.get('full_name', ''),
                            'bio': user_data.get('biography', ''),
                            'followers': user_data.get('follower_count', 0),
                            'profile_pic': user_data.get('profile_pic_url', '')
                        }
        except:
            pass
        
    except Exception as e:
        print(f"Method 4 failed: {e}")
    
    return {'success': False}

def main():
    username = "thepeacelily.in"
    print(f"🔍 Testing Instagram data extraction for @{username}")
    print("=" * 60)
    
    methods = [
        test_method_1_simple_meta,
        test_method_2_json_search,
        test_method_3_mobile_request,
        test_method_4_alternative_sources
    ]
    
    for method in methods:
        result = method(username)
        if result['success']:
            print(f"\n✅ SUCCESS with {result['method']}!")
            print(f"Name: {result.get('display_name', 'N/A')}")
            print(f"Bio: {result.get('bio', 'N/A')[:100]}...")
            print(f"Followers: {result.get('followers', 0)}")
            print(f"Profile Pic: {'Yes' if result.get('profile_pic') else 'No'}")
            
            return result
        else:
            print(f"❌ {method.__name__} failed")
        
        time.sleep(1)  # Rate limiting
    
    print(f"\n💔 All methods failed for @{username}")
    return {'success': False}

if __name__ == "__main__":
    main()