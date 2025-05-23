package handlers

import (
	"context"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/sirupsen/logrus"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/bson/primitive"
	"go.mongodb.org/mongo-driver/mongo"

	"whatsapp-instagram-bot/internal/bot"
	"whatsapp-instagram-bot/internal/database"
	"whatsapp-instagram-bot/internal/models"
	"whatsapp-instagram-bot/internal/scraper"
)

type WebhookHandler struct {
	whatsappBot       *bot.WhatsAppBot
	instagramScraper  *scraper.InstagramScraper
	db                *mongo.Database
	usersCollection   *mongo.Collection
	catalogsCollection *mongo.Collection
	productsCollection *mongo.Collection
}

func NewWebhookHandler(whatsappBot *bot.WhatsAppBot, instagramScraper *scraper.InstagramScraper, db *mongo.Database) *WebhookHandler {
	return &WebhookHandler{
		whatsappBot:        whatsappBot,
		instagramScraper:   instagramScraper,
		db:                 db,
		usersCollection:    database.GetCollection("users"),
		catalogsCollection: database.GetCollection("catalogs"),
		productsCollection: database.GetCollection("products"),
	}
}

// VerifyWebhook handles webhook verification
func (h *WebhookHandler) VerifyWebhook(c *gin.Context) {
	verifyToken := c.Query("hub.verify_token")
	challenge := c.Query("hub.challenge")
	mode := c.Query("hub.mode")

	// Get verify token from environment
	expectedToken := os.Getenv("WEBHOOK_VERIFY_TOKEN")

	logrus.WithFields(logrus.Fields{
		"mode":         mode,
		"verify_token": verifyToken,
		"expected":     expectedToken,
	}).Info("Webhook verification attempt")

	if mode == "subscribe" && verifyToken == expectedToken {
		logrus.Info("Webhook verified successfully")
		c.String(http.StatusOK, challenge)
		return
	}

	logrus.Warn("Webhook verification failed")
	c.Status(http.StatusForbidden)
}

// HandleWebhook processes incoming WhatsApp messages
func (h *WebhookHandler) HandleWebhook(c *gin.Context) {
	logrus.Info("Webhook received!")
	
	var webhookData models.WhatsAppMessage

	if err := c.ShouldBindJSON(&webhookData); err != nil {
		logrus.WithError(err).Error("Failed to parse webhook data")
		c.Status(http.StatusBadRequest)
		return
	}

	logrus.WithField("data", webhookData).Info("Webhook data received")

	// Process each entry in the webhook
	for _, entry := range webhookData.Entry {
		for _, change := range entry.Changes {
			if change.Field == "messages" {
				logrus.Info("Processing messages from webhook")
				// Process messages directly from the webhook data
				for _, message := range change.Value.Messages {
					logrus.WithFields(logrus.Fields{
						"from": message.From,
						"type": message.Type,
					}).Info("Processing individual message")
					
					if message.Type == "text" && message.Text != nil {
						logrus.WithField("text_body", message.Text.Body).Info("Processing text message")
						go h.handleTextMessage(message.From, message.Text.Body, change.Value.Contacts)
					}
				}
			}
		}
	}

	c.Status(http.StatusOK)
}


// handleTextMessage processes text messages from users
func (h *WebhookHandler) handleTextMessage(from, messageBody string, contacts []struct {
	Profile struct {
		Name string `json:"name"`
	} `json:"profile"`
	WAID string `json:"wa_id"`
}) {
	messageBody = strings.TrimSpace(strings.ToLower(messageBody))
	
	logrus.WithFields(logrus.Fields{
		"from":    from,
		"message": messageBody,
	}).Info("Processing text message")

	// Get or create user
	user, err := h.getOrCreateUser(from, contacts)
	if err != nil {
		logrus.WithError(err).Error("Failed to get or create user")
		h.whatsappBot.SendErrorMessage(from, "general")
		return
	}

	// Handle message based on content and user state
	if h.isGreeting(messageBody) {
		h.handleGreeting(user)
	} else if h.isInstagramURL(messageBody) {
		h.handleInstagramURL(user, messageBody)
	} else if user.State.WaitingForURL {
		h.handleInstagramURL(user, messageBody)
	} else if messageBody == "start" {
		h.handleStart(user)
	} else {
		h.handleUnknownMessage(user)
	}
}

// isGreeting checks if message is a greeting
func (h *WebhookHandler) isGreeting(message string) bool {
	greetings := []string{"hi", "hello", "hey", "start", "help"}
	for _, greeting := range greetings {
		if strings.Contains(message, greeting) {
			return true
		}
	}
	return false
}

// isInstagramURL checks if message contains Instagram URL
func (h *WebhookHandler) isInstagramURL(message string) bool {
	return strings.Contains(message, "instagram.com") || strings.Contains(message, "instagram")
}

// handleGreeting sends welcome message
func (h *WebhookHandler) handleGreeting(user *models.User) {
	err := h.whatsappBot.SendWelcomeMessage(user.PhoneNumber)
	if err != nil {
		logrus.WithError(err).Error("Failed to send welcome message")
		return
	}

	// Update user state
	user.State.Step = "welcomed"
	user.State.WaitingForURL = true
	h.updateUser(user)
}

// handleStart asks for Instagram URL
func (h *WebhookHandler) handleStart(user *models.User) {
	err := h.whatsappBot.SendInstagramURLRequest(user.PhoneNumber)
	if err != nil {
		logrus.WithError(err).Error("Failed to send Instagram URL request")
		return
	}

	// Update user state
	user.State.Step = "waiting_for_url"
	user.State.WaitingForURL = true
	h.updateUser(user)
}

// handleInstagramURL processes Instagram URL and starts scraping
func (h *WebhookHandler) handleInstagramURL(user *models.User, message string) {
	// Validate Instagram URL
	validURL, err := h.instagramScraper.ValidateInstagramURL(message)
	if err != nil {
		logrus.WithError(err).Error("Invalid Instagram URL")
		h.whatsappBot.SendErrorMessage(user.PhoneNumber, "invalid_url")
		return
	}

	// Send processing message
	err = h.whatsappBot.SendProcessingMessage(user.PhoneNumber, validURL)
	if err != nil {
		logrus.WithError(err).Error("Failed to send processing message")
		return
	}

	// Update user state
	user.State.Step = "processing"
	user.State.InstagramURL = validURL
	user.State.WaitingForURL = false
	h.updateUser(user)

	// Start scraping in goroutine
	go h.processInstagramProfile(user, validURL)
}

// processInstagramProfile scrapes Instagram and creates catalog
func (h *WebhookHandler) processInstagramProfile(user *models.User, instagramURL string) {
	// Create catalog record
	catalog := &models.ProductCatalog{
		UserID:       user.ID,
		InstagramURL: instagramURL,
		Status:       "processing",
		CreatedAt:    time.Now(),
	}

	result, err := h.catalogsCollection.InsertOne(context.Background(), catalog)
	if err != nil {
		logrus.WithError(err).Error("Failed to create catalog")
		h.whatsappBot.SendErrorMessage(user.PhoneNumber, "general")
		return
	}

	catalogID := result.InsertedID.(primitive.ObjectID).Hex()

	// Scrape Instagram profile
	profile, err := h.instagramScraper.ScrapeProfile(instagramURL)
	if err != nil {
		logrus.WithError(err).Error("Failed to scrape Instagram profile")
		h.whatsappBot.SendErrorMessage(user.PhoneNumber, "scraping_failed")
		
		// Update catalog status to failed
		h.catalogsCollection.UpdateOne(
			context.Background(),
			bson.M{"_id": result.InsertedID},
			bson.M{"$set": bson.M{"status": "failed"}},
		)
		return
	}

	// Extract products
	products := h.instagramScraper.ExtractProducts(profile, user.ID.Hex(), catalogID)
	if len(products) == 0 {
		logrus.Warn("No products found in Instagram profile")
		h.whatsappBot.SendErrorMessage(user.PhoneNumber, "no_products")
		return
	}

	// Save products to database
	var productDocs []interface{}
	for _, product := range products {
		productDocs = append(productDocs, product)
	}

	_, err = h.productsCollection.InsertMany(context.Background(), productDocs)
	if err != nil {
		logrus.WithError(err).Error("Failed to save products")
		h.whatsappBot.SendErrorMessage(user.PhoneNumber, "general")
		return
	}

	// Update catalog
	completedAt := time.Now()
	_, err = h.catalogsCollection.UpdateOne(
		context.Background(),
		bson.M{"_id": result.InsertedID},
		bson.M{"$set": bson.M{
			"status":       "completed",
			"business_name": profile.FullName,
			"product_count": len(products),
			"completed_at":  &completedAt,
		}},
	)
	if err != nil {
		logrus.WithError(err).Error("Failed to update catalog")
	}

	// Send completion message
	err = h.whatsappBot.SendCatalogComplete(user.PhoneNumber, len(products), profile.FullName)
	if err != nil {
		logrus.WithError(err).Error("Failed to send completion message")
	}

	// Update user state
	user.State.Step = "completed"
	user.State.CatalogID = catalogID
	user.State.WaitingForURL = false
	h.updateUser(user)

	logrus.WithFields(logrus.Fields{
		"user_id":       user.ID.Hex(),
		"catalog_id":    catalogID,
		"product_count": len(products),
		"business_name": profile.FullName,
	}).Info("Catalog created successfully")
}

// handleUnknownMessage responds to unrecognized messages
func (h *WebhookHandler) handleUnknownMessage(user *models.User) {
	message := `🤔 I didn't understand that.

Send me:
• "hi" or "start" to begin
• Your Instagram profile URL to create a catalog

How can I help you today?`

	err := h.whatsappBot.SendTextMessage(user.PhoneNumber, message)
	if err != nil {
		logrus.WithError(err).Error("Failed to send unknown message response")
	}
}

// getOrCreateUser retrieves or creates a user record
func (h *WebhookHandler) getOrCreateUser(phoneNumber string, contacts []struct {
	Profile struct {
		Name string `json:"name"`
	} `json:"profile"`
	WAID string `json:"wa_id"`
}) (*models.User, error) {
	var user models.User

	err := h.usersCollection.FindOne(
		context.Background(),
		bson.M{"phone_number": phoneNumber},
	).Decode(&user)

	if err == mongo.ErrNoDocuments {
		// Create new user
		name := phoneNumber
		for _, contact := range contacts {
			if contact.WAID == phoneNumber && contact.Profile.Name != "" {
				name = contact.Profile.Name
				break
			}
		}

		user = models.User{
			PhoneNumber: phoneNumber,
			Name:        name,
			State: models.ConversationState{
				Step:          "new",
				WaitingForURL: false,
			},
			CreatedAt: time.Now(),
			UpdatedAt: time.Now(),
		}

		result, err := h.usersCollection.InsertOne(context.Background(), user)
		if err != nil {
			return nil, err
		}

		user.ID = result.InsertedID.(primitive.ObjectID)
	} else if err != nil {
		return nil, err
	}

	return &user, nil
}

// updateUser updates user record in database
func (h *WebhookHandler) updateUser(user *models.User) {
	user.UpdatedAt = time.Now()
	_, err := h.usersCollection.UpdateOne(
		context.Background(),
		bson.M{"_id": user.ID},
		bson.M{"$set": user},
	)
	if err != nil {
		logrus.WithError(err).WithField("user_id", user.ID.Hex()).Error("Failed to update user")
	}
}