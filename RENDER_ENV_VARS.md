# Environment Variables for Render.com Deployment

Set these environment variables in your Render.com service dashboard:

## Required Variables:

```bash
# WhatsApp Business API
WHATSAPP_TOKEN=EAAKgQMTmeVgBO8dtgNrpxqRLJD5rEjnvSG8H4Rf9TqmOt3hMVXNkJ4mvgnvcl2HdTir6jstbuqYukVZCu27XLQMYsqkhbE1zWin1Ei87dqiDbbn4394qzCqj6NWZBsO4HwUzsQGZBZC3bpxg5eT4tbbhiqs9lVU4uoFZCN4dQfNjkEgYKuykHB8lYzilNUZCU4YNTsXXv5GP7vmvkAyzp2eBZCAWu4vbsz8vmAZD
PHONE_NUMBER_ID=659738460554125
VERIFY_TOKEN=myverifytoken123

# Google Cloud Configuration
GOOGLE_PROJECT_ID=inhouse-vertex-final
GOOGLE_LOCATION=us-central1

# Optional (if you have Cloudinary configured)
CLOUDINARY_CLOUD_NAME=your_cloudinary_name
CLOUDINARY_API_KEY=your_cloudinary_key
CLOUDINARY_API_SECRET=your_cloudinary_secret
```

## Important Notes:

1. **Google Cloud Service Account**: Since Render.com doesn't support file uploads for service accounts, you'll need to either:
   - Use Google Cloud CLI authentication on Render (if supported)
   - Or convert the service account JSON to environment variables
   - Or use Application Default Credentials

2. **WhatsApp Token**: This token will expire periodically. When it does:
   - Get a new token from Meta Developer Console
   - Update the WHATSAPP_TOKEN variable on Render
   - The service will automatically restart

3. **Deployment**: 
   - Render.com will automatically deploy when you push to GitHub
   - Check the build logs for any issues
   - Test the /debug endpoint to verify configuration

## Deployment URL:
Your bot will be available at: `https://your-service-name.onrender.com/`

## Testing:
- Health check: `https://your-service-name.onrender.com/health`
- Configuration: `https://your-service-name.onrender.com/debug`
- Webhook URL for Meta: `https://your-service-name.onrender.com/webhook`