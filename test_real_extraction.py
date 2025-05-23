#!/usr/bin/env python3
"""Quick test of the real Instagram extraction"""

import requests
from bs4 import BeautifulSoup
import re
import json

def test_instagram_extraction(username):
    """Test the real Instagram extraction with debug output"""
    print(f"🔍 TESTING EXTRACTION for @{username}")
    
    user_agents = [
        'Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15'
    ]
    
    for i, user_agent in enumerate(user_agents):
        try:
            headers = {
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            print(f"\n🔄 Attempt {i+1}/3 with user agent: {user_agent[:50]}...")
            response = requests.get(f"https://www.instagram.com/{username}/", headers=headers, timeout=20)
            print(f"📡 Response status: {response.status_code}")
            print(f"📏 Response length: {len(response.text)} characters")
            
            if response.status_code == 200 and len(response.text) > 1000:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Debug: Print all meta tags to see what we have
                meta_tags = soup.find_all('meta')
                print(f"🔍 Found {len(meta_tags)} meta tags")
                
                # Get meta tags
                og_title = soup.find('meta', property='og:title')
                og_description = soup.find('meta', property='og:description') 
                og_image = soup.find('meta', property='og:image')
                
                title = og_title.get('content') if og_title else ''
                description = og_description.get('content') if og_description else ''
                image = og_image.get('content') if og_image else ''
                
                print(f"📊 Title: '{title}'")
                print(f"📊 Description: '{description}'")
                print(f"📊 Image: '{image[:100]}...'")
                
                if title and description:
                    # Extract real data from meta tags
                    display_name = title.replace(' • Instagram photos and videos', '').replace(' • Instagram', '').replace(' (@', ' (')
                    if '(' in display_name:
                        display_name = display_name.split(' (')[0].strip()
                    
                    # Extract follower count from title or description  
                    follower_match = re.search(r'(\d+(?:,\d+)*)\s+Followers', title + ' ' + description)
                    followers = int(follower_match.group(1).replace(',', '')) if follower_match else 0
                    
                    # Extract posts count from description
                    posts_match = re.search(r'(\d+(?:,\d+)*)\s+Posts', description)
                    post_count = int(posts_match.group(1).replace(',', '')) if posts_match else 0
                    
                    print(f"\n✅ EXTRACTED SUCCESSFULLY:")
                    print(f"   Name: {display_name}")
                    print(f"   Followers: {followers:,}")
                    print(f"   Posts: {post_count}")
                    
                    return True
                else:
                    print(f"⚠️ No meta data found, trying next user agent...")
                    continue
            else:
                print(f"⚠️ Bad response or too short, trying next user agent...")
                continue
                
        except Exception as e:
            print(f"❌ Error with user agent {i+1}: {e}")
            continue
    
    print(f"❌ All extraction attempts failed")
    return False

if __name__ == "__main__":
    # Test with the known working account
    success = test_instagram_extraction("thepeacelily.in")
    if success:
        print(f"\n🎉 SUCCESS: Extraction is working!")
    else:
        print(f"\n💔 FAILED: Extraction not working")