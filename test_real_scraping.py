#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import re
import json
import time

def get_instagram_real_data(username):
    """Get real Instagram data that actually works"""
    try:
        # Method 1: Try to get basic profile info from public API-like endpoints
        url = f"https://www.instagram.com/{username}/"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=15)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract from meta tags (this usually works)
            profile_data = {}
            
            # Profile picture from og:image
            og_image = soup.find('meta', property='og:image')
            if og_image:
                profile_data['profile_pic_url'] = og_image.get('content')
                print(f"✅ Profile pic: {profile_data['profile_pic_url']}")
            
            # Bio from description
            og_description = soup.find('meta', property='og:description')
            if og_description:
                desc = og_description.get('content', '')
                # Instagram descriptions often contain follower info
                profile_data['bio'] = desc
                print(f"✅ Description: {desc}")
                
                # Extract follower count from description if present
                followers_match = re.search(r'(\d+(?:,\d+)*)\s*Followers', desc)
                if followers_match:
                    followers_str = followers_match.group(1).replace(',', '')
                    profile_data['followers'] = int(followers_str)
                    print(f"✅ Followers: {profile_data['followers']}")
            
            # Try to get display name from title
            og_title = soup.find('meta', property='og:title')
            if og_title:
                title = og_title.get('content', '')
                # Remove Instagram suffix
                display_name = title.replace(' • Instagram photos and videos', '').replace(' (@', ' (').strip()
                if display_name and display_name != username:
                    profile_data['display_name'] = display_name
                    print(f"✅ Display name: {display_name}")
            
            # Look for JSON-LD structured data
            json_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get('@type') == 'Organization':
                        if 'name' in data:
                            profile_data['display_name'] = data['name']
                            print(f"✅ JSON-LD name: {data['name']}")
                        if 'description' in data:
                            profile_data['bio'] = data['description']
                            print(f"✅ JSON-LD bio: {data['description']}")
                except:
                    continue
            
            # Try alternative methods for post images
            # Look for images that might be posts
            images = soup.find_all('img')
            post_images = []
            
            for img in images:
                src = img.get('src', '')
                alt = img.get('alt', '')
                
                # Instagram post images usually have specific patterns
                if ('scontent' in src and 
                    'cdninstagram' in src and 
                    not 'profile' in src and
                    not 'avatar' in src):
                    post_images.append({
                        'image': src,
                        'caption': alt,
                        'timestamp': '',
                        'likes': 0,
                        'comments': 0
                    })
            
            if post_images:
                profile_data['posts'] = post_images[:6]  # Limit to 6 posts
                print(f"✅ Found {len(post_images)} post images")
            
            profile_data['username'] = username
            profile_data['post_count'] = len(post_images)
            
            return profile_data
            
        else:
            print(f"❌ Failed to fetch: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def create_business_from_real_data(username):
    """Create business profile using whatever real data we can get"""
    
    # Get real Instagram data
    real_data = get_instagram_real_data(username)
    
    if real_data:
        print(f"\n✅ SUCCESS! Got real data for @{username}")
        
        # Use real data where available, smart defaults elsewhere
        business_data = {
            'username': username,
            'display_name': real_data.get('display_name', username.replace('.', ' ').replace('_', ' ').title()),
            'bio': real_data.get('bio', f'Quality products from {username}'),
            'profile_pic_url': real_data.get('profile_pic_url', ''),
            'followers': real_data.get('followers', 0),
            'posts': real_data.get('posts', []),
            'post_count': real_data.get('post_count', 0)
        }
        
        # Generate products based on real bio/name with better detection
        bio_lower = business_data['bio'].lower()
        name_lower = business_data['display_name'].lower()
        username_lower = username.lower()
        
        # Combine all text for analysis
        all_text = f"{bio_lower} {name_lower} {username_lower}"
        
        if any(word in all_text for word in ['crochet', 'handmade', 'macrame', 'crafts', 'gifts', 'accessories', 'aesthetic']):
            business_type = 'Handmade Crafts & Gifts'
        elif any(word in all_text for word in ['plant', 'nursery', 'garden', 'flower', 'green']):
            business_type = 'Plant Nursery'
        elif any(word in all_text for word in ['fashion', 'boutique', 'clothing', 'style', 'wear', 'dress']):
            business_type = 'Fashion & Clothing'
        elif any(word in all_text for word in ['food', 'cafe', 'restaurant', 'kitchen', 'bakery', 'cook']):
            business_type = 'Food & Beverage'
        elif any(word in all_text for word in ['beauty', 'cosmetic', 'makeup', 'skincare', 'salon', 'spa']):
            business_type = 'Beauty & Cosmetics'
        elif any(word in all_text for word in ['tech', 'software', 'digital', 'app', 'web', 'code']):
            business_type = 'Technology'
        elif any(word in all_text for word in ['art', 'design', 'creative', 'studio', 'gallery']):
            business_type = 'Art & Design'
        elif any(word in all_text for word in ['jewelry', 'jewellery', 'rings', 'necklace', 'earrings']):
            business_type = 'Jewelry'
        elif any(word in all_text for word in ['home', 'decor', 'furniture', 'interior']):
            business_type = 'Home & Decor'
        else:
            business_type = 'General Business'
        
        business_data['business_type'] = business_type
        
        print(f"🎯 Detected business type: {business_type}")
        print(f"📸 Profile pic: {'✅' if business_data['profile_pic_url'] else '❌'}")
        print(f"📝 Bio: {business_data['bio'][:50]}...")
        print(f"📱 Posts: {len(business_data['posts'])}")
        
        return business_data
        
    else:
        print(f"❌ Could not get real data for @{username}")
        return None

if __name__ == "__main__":
    # Test with thepeacelily.in
    result = create_business_from_real_data('thepeacelily.in')
    
    if result:
        print(f"\n🎉 FINAL RESULT:")
        print(json.dumps(result, indent=2))
    else:
        print(f"\n❌ FAILED to get real data")