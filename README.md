# WhatsApp Instagram Bot

A Go-based WhatsApp Business bot that automatically scrapes Instagram profiles and creates product catalogs for creative entrepreneurs.

## Features

- 🤖 **WhatsApp Business Integration**: Responds to messages via WhatsApp Business API
- 📸 **Instagram Scraping**: Extracts product information from Instagram profiles
- 📦 **Product Catalog Creation**: Automatically generates structured product catalogs
- 💾 **MongoDB Storage**: Persistent storage for users, catalogs, and products
- ⚡ **Real-time Processing**: Instant responses and background processing
- 🔒 **Webhook Security**: Secure webhook verification and handling

## How It Works

1. **User Interaction**: Users send "hi" to the WhatsApp bot
2. **Instagram URL Request**: Bot asks for Instagram profile URL
3. **Profile Scraping**: Bot scrapes the Instagram profile for product posts
4. **Catalog Generation**: Extracts product names, descriptions, prices, and images
5. **Delivery**: Sends structured product catalog back to user

## Prerequisites

- Go 1.21 or higher
- MongoDB database
- WhatsApp Business API access
- Facebook Developer Account

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd whatsapp-instagram-bot
   ```

2. **Install dependencies**:
   ```bash
   go mod tidy
   ```

3. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

4. **Configure environment variables**:
   ```env
   # WhatsApp Business API Configuration
   WHATSAPP_TOKEN=your_whatsapp_business_api_token
   WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
   VERIFY_TOKEN=your_webhook_verify_token

   # MongoDB Configuration
   MONGODB_URI=mongodb://localhost:27017
   MONGODB_DATABASE=whatsapp_bot

   # Server Configuration
   PORT=8080
   WEBHOOK_ENDPOINT=/webhook
   ```

## WhatsApp Business API Setup

1. **Create Facebook App**:
   - Go to [Facebook Developers](https://developers.facebook.com/)
   - Create a new app with WhatsApp Business API

2. **Get Access Token**:
   - Navigate to WhatsApp > API Setup
   - Copy your temporary access token
   - For production, create a permanent token

3. **Configure Webhook**:
   - Set webhook URL: `https://yourdomain.com/webhook`
   - Set verify token (match with .env file)
   - Subscribe to messages webhook field

4. **Phone Number**:
   - Add and verify your WhatsApp Business phone number
   - Note the Phone Number ID

## Running the Bot

1. **Start MongoDB** (if running locally):
   ```bash
   mongod
   ```

2. **Run the bot**:
   ```bash
   go run main.go
   ```

3. **For development with auto-reload**:
   ```bash
   # Install air for live reloading
   go install github.com/cosmtrek/air@latest
   air
   ```

## API Endpoints

- `GET /webhook` - Webhook verification
- `POST /webhook` - Message handling
- `GET /health` - Health check

## Database Schema

### Users Collection
```json
{
  "_id": "ObjectId",
  "phone_number": "string",
  "name": "string",
  "state": {
    "step": "string",
    "instagram_url": "string",
    "catalog_id": "string",
    "waiting_for_url": "boolean"
  },
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

### Product Catalogs Collection
```json
{
  "_id": "ObjectId",
  "user_id": "ObjectId",
  "instagram_url": "string",
  "business_name": "string",
  "product_count": "number",
  "status": "string",
  "created_at": "timestamp",
  "completed_at": "timestamp"
}
```

### Products Collection
```json
{
  "_id": "ObjectId",
  "user_id": "ObjectId",
  "catalog_id": "string",
  "name": "string",
  "description": "string",
  "price": "string",
  "image_url": "string",
  "post_url": "string",
  "created_at": "timestamp"
}
```

## Bot Conversation Flow

1. **Greeting**: User sends "hi", "hello", or "start"
   ```
   User: hi
   Bot: 🎉 Welcome to In-House Bot! Send me your Instagram URL...
   ```

2. **Instagram URL**: User provides Instagram profile URL
   ```
   User: https://instagram.com/mybusiness
   Bot: 🔄 Processing your Instagram profile...
   ```

3. **Processing**: Bot scrapes and creates catalog
   ```
   Bot: ✅ Your product catalog is ready!
        🏪 Business: My Business
        📦 Products found: 15
   ```

## Features in Detail

### Instagram Scraping
- Validates Instagram URLs
- Extracts profile information
- Identifies product posts
- Extracts pricing from captions
- Downloads product images
- Handles rate limiting

### Product Extraction
- Uses regex patterns to find prices
- Extracts product names from captions
- Identifies hashtags for categorization
- Handles multiple image posts
- Filters out non-product content

### WhatsApp Integration
- Handles text messages
- Sends rich formatted responses
- Manages conversation state
- Provides error handling
- Supports emoji and formatting

## Development

### Project Structure
```
whatsapp-instagram-bot/
├── main.go                 # Application entry point
├── internal/
│   ├── config/            # Configuration management
│   ├── database/          # MongoDB connection
│   ├── bot/              # WhatsApp bot logic
│   ├── handlers/         # Webhook handlers
│   ├── scraper/          # Instagram scraping
│   └── models/           # Data models
├── go.mod                # Go modules
├── .env.example          # Environment template
└── README.md            # Documentation
```

### Adding New Features

1. **New Message Types**: Extend `handleTextMessage` function
2. **Additional Scrapers**: Implement new scrapers in `internal/scraper`
3. **Database Models**: Add new models in `internal/models`
4. **API Endpoints**: Add routes in `main.go`

## Production Deployment

### Using Docker
```dockerfile
FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY . .
RUN go mod download
RUN go build -o main .

FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /app/main .
CMD ["./main"]
```

### Environment Setup
- Use production MongoDB (MongoDB Atlas recommended)
- Set up proper SSL certificates
- Configure webhook with HTTPS URL
- Set up monitoring and logging
- Use environment-specific configurations

### Scaling Considerations
- Implement Redis for session management
- Use message queues for heavy processing
- Add rate limiting for Instagram requests
- Implement caching for frequently accessed data
- Set up horizontal scaling with load balancers

## Troubleshooting

### Common Issues

1. **Webhook Verification Failed**:
   - Check verify token matches between Facebook and .env
   - Ensure webhook URL is accessible from internet
   - Verify HTTPS is properly configured

2. **Instagram Scraping Fails**:
   - Instagram may block requests - implement proper delays
   - Use rotating user agents
   - Handle private profiles gracefully

3. **WhatsApp API Errors**:
   - Check access token validity
   - Verify phone number ID is correct
   - Ensure proper message formatting

### Logging
- All operations are logged with structured logging
- Check logs for detailed error information
- Use log levels: Debug, Info, Warn, Error

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature-name`
3. Commit changes: `git commit -am 'Add feature'`
4. Push to branch: `git push origin feature-name`
5. Submit pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in the repository
- Contact the development team
- Check the troubleshooting section

---

Built with ❤️ for creative entrepreneurs transforming their Instagram into business catalogs.