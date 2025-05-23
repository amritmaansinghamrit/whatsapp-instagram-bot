# Instagram Graph API Setup Guide

## Overview
This guide will help you set up Instagram Graph API access to get real Instagram business content including posts, captions, and comments as reviews.

## Prerequisites
- Instagram Business or Creator account
- Facebook Page connected to the Instagram account
- Meta Developer account

## Step 1: Create Facebook App

1. Go to [Meta for Developers](https://developers.facebook.com/)
2. Click "My Apps" → "Create App"
3. Choose "Business" as app type
4. Fill in app details:
   - App Name: "InHouse Instagram Bot"
   - Contact Email: Your email
   - Business Account: Select or create one

## Step 2: Add Instagram Graph API

1. In your app dashboard, click "Add Product"
2. Find "Instagram Graph API" and click "Set Up"
3. In the left sidebar, go to Instagram Graph API → Quickstart

## Step 3: Configure OAuth Settings

1. Go to "App Settings" → "Basic"
2. Add the following to "App Domains":
   ```
   whatsapp-instagram-bot.onrender.com
   ```
3. Under "Website", add:
   ```
   https://whatsapp-instagram-bot.onrender.com
   ```

## Step 4: Set OAuth Redirect URIs

1. Go to Instagram Graph API → Settings
2. Add OAuth Redirect URI:
   ```
   https://whatsapp-instagram-bot.onrender.com/instagram/callback
   ```

## Step 5: Get App Credentials

1. Go to "App Settings" → "Basic"
2. Copy the following values:
   - **App ID** → Use for `INSTAGRAM_APP_ID`
   - **App Secret** → Use for `INSTAGRAM_APP_SECRET`

## Step 6: Update Environment Variables

Update your `.env` file with the credentials:

```bash
# Instagram Graph API Configuration
INSTAGRAM_APP_ID=your_app_id_here
INSTAGRAM_APP_SECRET=your_app_secret_here
INSTAGRAM_REDIRECT_URI=https://whatsapp-instagram-bot.onrender.com/instagram/callback
```

## Step 7: Instagram Account Requirements

For the API to work, Instagram accounts must:
- Be Business or Creator accounts (not personal)
- Be connected to a Facebook Page
- Have granted permissions to your app

## Step 8: API Permissions

The app requests these permissions:
- `user_profile`: Basic profile information
- `user_media`: Access to user's media (posts)

## Step 9: Testing the Integration

1. Deploy your updated app to Render
2. Send an Instagram URL to your WhatsApp bot
3. Choose "Instagram API Access" option
4. Complete the OAuth flow by visiting the provided link
5. Grant permissions to your app
6. Wait for the bot to process the real Instagram data

## API Limitations

### Instagram Graph API Limitations:
- Only works with Business/Creator accounts
- Requires Facebook Page connection
- Limited to 200 requests per hour per user
- Bio content requires additional permissions
- Some data (follower count, etc.) requires Instagram Business permissions

### Data Available:
✅ Real posts and captions
✅ Post images and videos
✅ Post timestamps
✅ Like counts
✅ Comment counts
✅ Comments text (as reviews)
✅ Media types (image/video)

### Data Not Available (with basic permissions):
❌ Bio/description (requires additional permissions)
❌ Follower/following counts (requires Instagram Business permissions)
❌ Profile picture (requires additional permissions)
❌ Stories (different API)

## Troubleshooting

### Common Issues:

1. **"App not configured" error**
   - Check that `INSTAGRAM_APP_ID` and `INSTAGRAM_APP_SECRET` are set
   - Verify the app is properly configured in Meta Developer Console

2. **OAuth redirect error**
   - Ensure the redirect URI exactly matches what's configured in your app
   - Check that the domain is added to App Domains

3. **"User not authorized" error**
   - The Instagram account must be a Business or Creator account
   - The account must be connected to a Facebook Page
   - The user must complete the OAuth flow

4. **"Token exchange failed"**
   - Check your app secret is correct
   - Ensure the authorization code hasn't expired (it's only valid for 10 minutes)

## Benefits of API vs Web Scraping

### Instagram Graph API ✅
- **Real data**: Authentic posts, captions, and comments
- **No rate limiting**: Within API limits (200/hour)
- **High quality images**: Original resolution media URLs
- **Comments as reviews**: Real user feedback
- **Reliable**: Official API, won't break
- **Better product detection**: More data for AI analysis

### Web Scraping ⚠️
- **Limited data**: Anti-bot measures block scraping
- **Unreliable**: Often returns 0 posts
- **Lower quality**: Compressed images
- **No comments**: Can't access user reviews
- **Fragile**: Instagram changes break functionality

## Next Steps

1. Complete the Meta Developer app setup
2. Update your environment variables
3. Deploy to Render
4. Test with a real Instagram Business account
5. The bot will now offer both options and recommend API access for better results