package main

import (
	"fmt"
	"log"

	"github.com/gin-gonic/gin"
)

func main() {
	router := gin.Default()
	
	// Simple webhook handler with explicit logging
	router.POST("/webhook", func(c *gin.Context) {
		fmt.Println("🚀 WEBHOOK RECEIVED!")
		log.Println("Webhook POST request received")
		
		// Log request body
		body, _ := c.GetRawData()
		fmt.Printf("Request body: %s\n", string(body))
		
		c.JSON(200, gin.H{"status": "received"})
	})
	
	router.GET("/webhook", func(c *gin.Context) {
		verifyToken := c.Query("hub.verify_token")
		challenge := c.Query("hub.challenge")
		mode := c.Query("hub.mode")
		
		fmt.Printf("Webhook verification: mode=%s, token=%s, challenge=%s\n", mode, verifyToken, challenge)
		
		if mode == "subscribe" && verifyToken == "myverifytoken123" {
			fmt.Println("✅ Webhook verified!")
			c.String(200, challenge)
		} else {
			fmt.Println("❌ Webhook verification failed")
			c.Status(403)
		}
	})
	
	router.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "healthy"})
	})
	
	port := "8080"
	fmt.Printf("🔥 Debug server starting on port %s\n", port)
	router.Run(":" + port)
}