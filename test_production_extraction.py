#!/usr/bin/env python3
"""Test Instagram extraction to see what's happening in production"""

import requests
from bs4 import BeautifulSoup
import re
import json
import urllib.request
import urllib.parse
import time
import random

def test_all_methods(username):
    """Test all 5 extraction methods to see which ones work"""
    print(f"🔍 TESTING ALL METHODS for @{username}")
    
    # Method 1: Web profile info endpoint
    print(f"\n🔄 Method 1: Web profile info endpoint")
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.instagram.com/',
            'X-Requested-With': 'XMLHttpRequest'
        })
        
        # Get main page to establish session
        main_response = session.get('https://www.instagram.com/', timeout=10)
        print(f"📡 Main page status: {main_response.status_code}")
        
        # Extract CSRF token
        csrf_token = 'missing'
        if 'csrftoken' in session.cookies:
            csrf_token = session.cookies['csrftoken']
        print(f"🔑 CSRF token: {csrf_token}")
        
        # Try the web profile info endpoint
        profile_url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
        session.headers.update({
            'X-CSRFToken': csrf_token,
            'X-Instagram-AJAX': '1007614317'
        })
        
        response = session.get(profile_url, timeout=15)
        print(f"📡 Profile API status: {response.status_code}")
        print(f"📏 Response length: {len(response.text)}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"✅ Got JSON data!")
                print(f"📊 Data keys: {list(data.keys())}")
                if 'data' in data and 'user' in data['data']:
                    user = data['data']['user']
                    print(f"👤 User: {user.get('full_name', 'No name')}")
                    print(f"📝 Bio: {user.get('biography', 'No bio')[:100]}")
                    print(f"👥 Followers: {user.get('edge_followed_by', {}).get('count', 0)}")
                    return True
            except json.JSONDecodeError:
                print(f"❌ Not JSON response")
                
    except Exception as e:
        print(f"❌ Method 1 failed: {e}")
    
    # Method 2: Alternative endpoints
    print(f"\n🔄 Method 2: Alternative endpoints")
    endpoints = [
        f"https://www.instagram.com/{username}/?__a=1&__d=dis",
        f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}",
        f"https://www.instagram.com/{username}/?__a=1"
    ]
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1',
        'Accept': 'application/json,text/javascript,*/*;q=0.01',
        'Accept-Language': 'en-US,en;q=0.9'
    })
    
    for endpoint in endpoints:
        try:
            print(f"🔄 Trying: {endpoint}")
            response = session.get(endpoint, timeout=15)
            print(f"📡 Status: {response.status_code}, Length: {len(response.text)}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"✅ Got JSON from alternative endpoint!")
                    return True
                except:
                    print(f"⚠️ Not JSON")
        except Exception as e:
            print(f"❌ Failed: {e}")
    
    # Method 3: HTML scraping
    print(f"\n🔄 Method 3: HTML scraping")
    try:
        user_agents = [
            'Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
        
        for i, user_agent in enumerate(user_agents):
            headers = {
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            print(f"🔄 HTML attempt {i+1} with: {user_agent[:50]}...")
            response = requests.get(f"https://www.instagram.com/{username}/", headers=headers, timeout=20)
            print(f"📡 Status: {response.status_code}, Length: {len(response.text)}")
            
            if response.status_code == 200 and len(response.text) > 1000:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Check meta tags
                og_title = soup.find('meta', property='og:title')
                og_description = soup.find('meta', property='og:description')
                
                title = og_title.get('content') if og_title else ''
                description = og_description.get('content') if og_description else ''
                
                print(f"📊 Title: '{title}'")
                print(f"📊 Description: '{description[:100]}...'")
                
                if title and description and 'Instagram' in title:
                    print(f"✅ Got real Instagram meta data!")
                    
                    # Extract data
                    display_name = title.replace(' • Instagram photos and videos', '').replace(' (@', ' (')
                    if '(' in display_name:
                        display_name = display_name.split(' (')[0].strip()
                    
                    follower_match = re.search(r'(\d+(?:,\d+)*)\s+Followers', description)
                    followers = int(follower_match.group(1).replace(',', '')) if follower_match else 0
                    
                    print(f"👤 Name: {display_name}")
                    print(f"👥 Followers: {followers:,}")
                    
                    if display_name and followers > 0:
                        return True
                else:
                    print(f"⚠️ No Instagram meta data found")
            else:
                print(f"⚠️ Bad response")
                
    except Exception as e:
        print(f"❌ Method 3 failed: {e}")
    
    # Method 4: urllib
    print(f"\n🔄 Method 4: urllib method")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        
        req = urllib.request.Request(f"https://www.instagram.com/{username}/", headers=headers)
        
        with urllib.request.urlopen(req, timeout=20) as response:
            html_content = response.read().decode('utf-8')
            print(f"📡 urllib response length: {len(html_content)}")
            
            if len(html_content) > 1000:
                soup = BeautifulSoup(html_content, 'html.parser')
                
                og_title = soup.find('meta', property='og:title')
                og_description = soup.find('meta', property='og:description')
                
                title = og_title.get('content') if og_title else ''
                description = og_description.get('content') if og_description else ''
                
                print(f"📊 urllib Title: '{title}'")
                print(f"📊 urllib Description: '{description[:100]}...'")
                
                if title and 'Instagram' in title:
                    print(f"✅ urllib method worked!")
                    return True
                    
    except Exception as e:
        print(f"❌ Method 4 failed: {e}")
    
    print(f"\n❌ ALL METHODS FAILED")
    return False

if __name__ == "__main__":
    # Test with the known account
    success = test_all_methods("thepeacelily.in")
    if success:
        print(f"\n🎉 SUCCESS: At least one method is working!")
    else:
        print(f"\n💔 COMPLETE FAILURE: All extraction methods blocked")