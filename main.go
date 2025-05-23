package main

import (
	"log"
	"os"

	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
	"github.com/sirupsen/logrus"

	"whatsapp-instagram-bot/internal/bot"
	"whatsapp-instagram-bot/internal/config"
	"whatsapp-instagram-bot/internal/database"
	"whatsapp-instagram-bot/internal/handlers"
	"whatsapp-instagram-bot/internal/scraper"
)

func init() {
	// Load environment variables
	if err := godotenv.Load(); err != nil {
		logrus.Warn("No .env file found, using system environment variables")
	}

	// Setup logging
	logrus.SetFormatter(&logrus.JSONFormatter{})
	logrus.SetLevel(logrus.InfoLevel)
}

func main() {
	// Load configuration
	cfg := config.Load()

	// Initialize database
	db, err := database.Connect(cfg.MongoURI, cfg.DatabaseName)
	if err != nil {
		log.Fatal("Failed to connect to database:", err)
	}
	defer database.Disconnect()

	// Initialize services
	instagramScraper := scraper.NewInstagramScraper()
	whatsappBot := bot.NewWhatsAppBot(cfg.WhatsAppToken, cfg.PhoneNumberID)
	
	// Initialize handlers
	webhookHandler := handlers.NewWebhookHandler(whatsappBot, instagramScraper, db)

	// Setup Gin router
	router := gin.Default()
	
	// Middleware
	router.Use(gin.Logger())
	router.Use(gin.Recovery())

	// Add middleware to log all requests
	router.Use(func(c *gin.Context) {
		logrus.WithFields(logrus.Fields{
			"method": c.Request.Method,
			"path":   c.Request.URL.Path,
			"query":  c.Request.URL.RawQuery,
		}).Info("Incoming request")
		c.Next()
	})

	// Webhook routes
	router.GET(cfg.WebhookEndpoint, webhookHandler.VerifyWebhook)
	router.POST(cfg.WebhookEndpoint, webhookHandler.HandleWebhook)

	// Health check
	router.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "healthy"})
	})

	// Start server
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	logrus.WithField("port", port).Info("Starting WhatsApp Instagram Bot server")
	if err := router.Run(":" + port); err != nil {
		log.Fatal("Failed to start server:", err)
	}
}