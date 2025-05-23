# Instagram Basic Display API Setup Guide

## Overview
This guide sets up Instagram Basic Display API for **direct Instagram business login** (not Facebook login). Users will authenticate directly with their Instagram accounts.

## What You Get with Instagram Basic Display API
✅ **Direct Instagram login** - No Facebook account required
✅ **Real Instagram posts** - All user's media
✅ **Captions and timestamps** - Authentic content
✅ **High-quality images** - Original media URLs
✅ **No web scraping** - Official API access

❌ **Not Available**: Likes, comments, bio (requires Instagram Graph API which needs Facebook)

## Setup Steps

### 1. Configure Your Existing Instagram App

You already have:
- **App Name**: Inhouse APP-IG
- **App ID**: 29873136089000094
- **App Secret**: f29508f51c6f68cd6cc62fa908ea613b

### 2. Add Instagram Basic Display Product

1. Go to [Meta for Developers](https://developers.facebook.com/apps/29873136089000094)
2. Click "Add Product"
3. Find **"Instagram Basic Display"** and click "Set Up"

### 3. Configure Basic Display Settings

1. In your app, go to **Instagram Basic Display** → **Basic Display**
2. Click "Create New App"
3. Fill in:
   - **Display Name**: "Inhouse Instagram Bot"
   - **Purpose**: "Business catalog creation from Instagram posts"

### 4. Add OAuth Redirect URI

1. In **Instagram Basic Display** settings
2. Add **Valid OAuth Redirect URIs**:
   ```
   https://whatsapp-instagram-bot.onrender.com/instagram/callback
   ```

### 5. Add Test Users (For Development)

1. Go to **Instagram Basic Display** → **Basic Display**
2. Scroll to **"User Token Generator"**
3. Add your Instagram account as a test user
4. This allows you to test with your own account

### 6. App Review (For Production)

For public use, you'll need:
1. **App Review** from Meta
2. Submit for **instagram_graph_user_profile** and **instagram_graph_user_media** permissions
3. Provide use case: "Creating business catalogs from Instagram posts"

## Current Environment Configuration ✅

Your `.env` is already configured:
```bash
INSTAGRAM_APP_ID=29873136089000094
INSTAGRAM_APP_SECRET=f29508f51c6f68cd6cc62fa908ea613b
INSTAGRAM_REDIRECT_URI=https://whatsapp-instagram-bot.onrender.com/instagram/callback
```

## How It Works

### User Experience:
1. **Send Instagram URL** to WhatsApp bot
2. **Choose "Instagram API Access"** option
3. **Visit OAuth link** → Redirects to Instagram (not Facebook)
4. **Login with Instagram account** directly
5. **Grant permissions** to your app
6. **Get real Instagram posts** processed into catalog

### Technical Flow:
1. User visits `/instagram/auth/{username}`
2. Redirects to `https://api.instagram.com/oauth/authorize`
3. User logs in with **Instagram credentials**
4. Instagram redirects back with authorization code
5. App exchanges code for access token
6. Fetches real posts via Instagram Basic Display API

## API Limitations

### Available Data:
✅ **User Profile**: ID, username
✅ **Media**: Posts, images, videos
✅ **Captions**: Full post captions
✅ **Timestamps**: When posts were created
✅ **Media URLs**: High-quality image/video links

### Not Available:
❌ **Likes/Comments counts**: Requires Instagram Graph API
❌ **Comments text**: Requires Instagram Graph API  
❌ **Bio/Description**: Requires Instagram Graph API
❌ **Follower counts**: Requires Instagram Graph API

## Benefits vs Web Scraping

| Feature | Instagram Basic Display ✅ | Web Scraping ⚠️ |
|---------|---------------------------|------------------|
| **Authentication** | Direct Instagram login | No authentication |
| **Data Access** | All user posts | Often 0 posts (blocked) |
| **Image Quality** | Original resolution | Compressed thumbnails |
| **Reliability** | Official API | Anti-bot measures |
| **Rate Limits** | 200 requests/hour | Frequently blocked |
| **Captions** | Full captions | Limited/missing |

## Testing Steps

1. **Complete Meta app setup** above
2. **Deploy code** to Render
3. **Test with your Instagram account**:
   - Send Instagram URL to bot
   - Choose API option
   - Complete Instagram login
   - Verify real posts are retrieved

## Production Deployment

For public use:
1. **Submit for App Review** with Instagram Basic Display permissions
2. **Provide clear use case**: Business catalog creation
3. **Demo video**: Show the bot creating catalogs
4. **Privacy Policy**: Required for app review

## Why This Is Better

**Problem Solved**: You wanted real Instagram feed access without Facebook dependency.

**Solution**: Instagram Basic Display API provides:
- ✅ Direct Instagram authentication
- ✅ Real posts and captions  
- ✅ High-quality images
- ✅ No Facebook account required
- ✅ Official API (no scraping failures)

This gives you authentic Instagram content for much better AI product detection and catalog generation!