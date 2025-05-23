package bot

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/sirupsen/logrus"
)

type WhatsAppBot struct {
	token         string
	phoneNumberID string
	baseURL       string
}

type TextMessage struct {
	MessagingProduct string `json:"messaging_product"`
	To               string `json:"to"`
	Type             string `json:"type"`
	Text             struct {
		Body string `json:"body"`
	} `json:"text"`
}

type TemplateMessage struct {
	MessagingProduct string `json:"messaging_product"`
	To               string `json:"to"`
	Type             string `json:"type"`
	Template         struct {
		Name     string `json:"name"`
		Language struct {
			Code string `json:"code"`
		} `json:"language"`
	} `json:"template"`
}

func NewWhatsAppBot(token, phoneNumberID string) *WhatsAppBot {
	return &WhatsAppBot{
		token:         token,
		phoneNumberID: phoneNumberID,
		baseURL:       "https://graph.facebook.com/v22.0",
	}
}

// SendTextMessage sends a text message to a WhatsApp user
func (w *WhatsAppBot) SendTextMessage(to, message string) error {
	msg := TextMessage{
		MessagingProduct: "whatsapp",
		To:               to,
		Type:             "text",
	}
	msg.Text.Body = message

	return w.sendMessage(msg)
}

// SendWelcomeMessage sends a welcome message to new users
func (w *WhatsAppBot) SendWelcomeMessage(to string) error {
	welcomeText := `🎉 Welcome to In-House Bot!

I help creative entrepreneurs turn their Instagram profiles into professional product catalogs.

Simply send me your Instagram profile URL and I'll create a beautiful catalog of your products automatically!

Type "start" to begin or send me your Instagram URL directly.`

	return w.SendTextMessage(to, welcomeText)
}

// SendInstagramURLRequest asks user for their Instagram URL
func (w *WhatsAppBot) SendInstagramURLRequest(to string) error {
	message := `📸 Please send me your Instagram profile URL

For example:
• https://instagram.com/yourbusiness
• https://www.instagram.com/yourbusiness

I'll analyze your posts and create a product catalog for you! ✨`

	return w.SendTextMessage(to, message)
}

// SendProcessingMessage notifies user that scraping is in progress
func (w *WhatsAppBot) SendProcessingMessage(to, instagramURL string) error {
	message := fmt.Sprintf(`🔄 Processing your Instagram profile...

📍 Profile: %s

I'm analyzing your posts and extracting product information. This may take a few moments.

I'll send you the catalog once it's ready! ⏰`, instagramURL)

	return w.SendTextMessage(to, message)
}

// SendCatalogComplete notifies user that catalog is ready
func (w *WhatsAppBot) SendCatalogComplete(to string, productCount int, businessName string) error {
	message := fmt.Sprintf(`✅ Your product catalog is ready!

🏪 Business: %s
📦 Products found: %d

Your Instagram posts have been converted into a professional product catalog. You can now use this for WhatsApp Business or e-commerce!

Would you like me to process another Instagram account? Just send me another URL! 🚀`, businessName, productCount)

	return w.SendTextMessage(to, message)
}

// SendTemplateMessage sends a template message
func (w *WhatsAppBot) SendTemplateMessage(message interface{}) error {
	return w.sendMessage(message)
}

// SendErrorMessage sends an error message to user
func (w *WhatsAppBot) SendErrorMessage(to, errorType string) error {
	var message string
	
	switch errorType {
	case "invalid_url":
		message = `❌ Invalid Instagram URL

Please send a valid Instagram profile URL like:
• https://instagram.com/yourbusiness
• https://www.instagram.com/yourbusiness

Try again! 📸`
	case "scraping_failed":
		message = `❌ Could not access Instagram profile

This might be because:
• The profile is private
• The URL is incorrect
• The profile doesn't exist

Please check the URL and try again! 🔄`
	case "no_products":
		message = `📭 No products found

I couldn't find any product posts on this Instagram profile. Make sure:
• The profile has posts with products
• Posts include product descriptions
• The profile is public

Try with a different profile! 📸`
	default:
		message = `❌ Something went wrong

Please try again or contact support if the issue persists.

Send "start" to begin again! 🔄`
	}

	return w.SendTextMessage(to, message)
}

// sendMessage sends a message using WhatsApp Business API
func (w *WhatsAppBot) sendMessage(message interface{}) error {
	url := fmt.Sprintf("%s/%s/messages", w.baseURL, w.phoneNumberID)

	jsonData, err := json.Marshal(message)
	if err != nil {
		return err
	}

	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return err
	}

	req.Header.Set("Authorization", "Bearer "+w.token)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		logrus.WithFields(logrus.Fields{
			"status_code": resp.StatusCode,
			"url":         url,
		}).Error("Failed to send WhatsApp message")
		return fmt.Errorf("failed to send message, status: %d", resp.StatusCode)
	}

	logrus.Debug("WhatsApp message sent successfully")
	return nil
}