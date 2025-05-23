package config

import (
	"os"
)

type Config struct {
	WhatsAppToken    string
	PhoneNumberID    string
	VerifyToken      string
	MongoURI         string
	DatabaseName     string
	Port             string
	WebhookEndpoint  string
	UserAgent        string
}

func Load() *Config {
	return &Config{
		WhatsAppToken:   getEnv("WHATSAPP_TOKEN", ""),
		PhoneNumberID:   getEnv("WHATSAPP_PHONE_NUMBER_ID", ""),
		VerifyToken:     getEnv("VERIFY_TOKEN", ""),
		MongoURI:        getEnv("MONGODB_URI", "mongodb://localhost:27017"),
		DatabaseName:    getEnv("MONGODB_DATABASE", "whatsapp_bot"),
		Port:            getEnv("PORT", "8080"),
		WebhookEndpoint: getEnv("WEBHOOK_ENDPOINT", "/webhook"),
		UserAgent:       getEnv("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}