# WhatsApp Instagram Bot Setup

## Required Setup Steps:

### 1. Get Phone Number ID
- Go to [Meta for Developers](https://developers.facebook.com)
- Select your "TestApp-WP" app
- Navigate to WhatsApp → API Setup
- Copy the Phone Number ID and update `.env` file

### 2. Setup MongoDB (Choose one):

**Option A: MongoDB Atlas (Recommended)**
- Go to [MongoDB Atlas](https://cloud.mongodb.com)
- Create free account and cluster
- Get connection string: `mongodb+srv://username:password@cluster.mongodb.net/whatsapp_bot`
- Update `MONGODB_URI` in `.env`

**Option B: Local MongoDB**
- Install MongoDB locally
- Start with: `brew services start mongodb/brew/mongodb-community`
- Use: `mongodb://localhost:27017/whatsapp_bot`

### 3. Setup Webhook
- Use ngrok for testing: `ngrok http 8080`
- Copy the https URL
- In Meta Developer Console → WhatsApp → Configuration:
  - Webhook URL: `https://your-ngrok-url.ngrok.io/webhook`
  - Verify Token: Set this in `.env` as `WEBHOOK_VERIFY_TOKEN`

### 4. Test the Bot
```bash
go run main.go
```

Your bot will respond to WhatsApp messages sent to your test number!