package main

import (
	"log"
	"os"

	"github.com/joho/godotenv"
	"whatsapp-instagram-bot/internal/bot"
)

func main() {
	// Load environment variables
	if err := godotenv.Load(); err != nil {
		log.Println("No .env file found, using system environment variables")
	}

	// Get config from environment
	token := os.Getenv("WHATSAPP_TOKEN")
	phoneNumberID := os.Getenv("PHONE_NUMBER_ID")

	if token == "" || phoneNumberID == "" {
		log.Fatal("Missing WHATSAPP_TOKEN or PHONE_NUMBER_ID")
	}

	// Create bot
	whatsappBot := bot.NewWhatsAppBot(token, phoneNumberID)

	// Send proactive welcome message
	targetPhone := "919557705317"
	
	log.Printf("Sending message to: %s", targetPhone)
	log.Printf("Using token: %s...", token[:20])
	log.Printf("Using phone number ID: %s", phoneNumberID)
	
	// Send hello_world template message (approved template)
	templateMsg := struct {
		MessagingProduct string `json:"messaging_product"`
		To               string `json:"to"`
		Type             string `json:"type"`
		Template         struct {
			Name     string `json:"name"`
			Language struct {
				Code string `json:"code"`
			} `json:"language"`
		} `json:"template"`
	}{
		MessagingProduct: "whatsapp",
		To:               targetPhone,
		Type:             "template",
	}
	templateMsg.Template.Name = "hello_world"
	templateMsg.Template.Language.Code = "en_US"

	err := whatsappBot.SendTemplateMessage(templateMsg)
	if err != nil {
		log.Fatalf("Failed to send message: %v", err)
	}

	log.Println("Proactive message sent successfully to +91 9557705317!")
}