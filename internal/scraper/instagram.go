package scraper

import (
	"fmt"
	"net/url"
	"regexp"
	"strings"
	"time"

	"github.com/gocolly/colly/v2"
	"github.com/gocolly/colly/v2/debug"
	"github.com/sirupsen/logrus"
	"go.mongodb.org/mongo-driver/bson/primitive"
	
	"whatsapp-instagram-bot/internal/models"
)

type InstagramScraper struct {
	collector *colly.Collector
}

func NewInstagramScraper() *InstagramScraper {
	c := colly.NewCollector(
		colly.Debugger(&debug.LogDebugger{}),
		colly.UserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"),
	)

	// Rate limiting
	c.Limit(&colly.LimitRule{
		DomainGlob:  "*instagram.*",
		Parallelism: 1,
		Delay:       2 * time.Second,
	})

	// Error handling
	c.OnError(func(r *colly.Response, err error) {
		logrus.WithError(err).WithField("url", r.Request.URL).Error("Scraping error")
	})

	return &InstagramScraper{
		collector: c,
	}
}

// ValidateInstagramURL checks if the provided URL is a valid Instagram profile URL
func (s *InstagramScraper) ValidateInstagramURL(rawURL string) (string, error) {
	// Clean and parse URL
	if !strings.HasPrefix(rawURL, "http") {
		rawURL = "https://" + rawURL
	}

	u, err := url.Parse(rawURL)
	if err != nil {
		return "", fmt.Errorf("invalid URL format")
	}

	// Check if it's Instagram
	if !strings.Contains(u.Host, "instagram.com") {
		return "", fmt.Errorf("not an Instagram URL")
	}

	// Extract username from path
	pathParts := strings.Split(strings.Trim(u.Path, "/"), "/")
	if len(pathParts) == 0 || pathParts[0] == "" {
		return "", fmt.Errorf("no username found in URL")
	}

	username := pathParts[0]
	// Validate username format
	usernameRegex := regexp.MustCompile(`^[a-zA-Z0-9._]+$`)
	if !usernameRegex.MatchString(username) {
		return "", fmt.Errorf("invalid Instagram username format")
	}

	return fmt.Sprintf("https://www.instagram.com/%s/", username), nil
}

// ScrapeProfile scrapes an Instagram profile and extracts product information
func (s *InstagramScraper) ScrapeProfile(instagramURL string) (*models.InstagramProfile, error) {
	profile := &models.InstagramProfile{}
	var posts []models.InstagramPost

	// Create a new collector for this request
	c := s.collector.Clone()

	// Extract profile information
	c.OnHTML("script[type='application/ld+json']", func(e *colly.HTMLElement) {
		// This would contain structured data about the profile
		logrus.Debug("Found structured data script")
	})

	// Extract profile metadata from meta tags
	c.OnHTML("meta[property='og:title']", func(e *colly.HTMLElement) {
		profile.FullName = e.Attr("content")
	})

	c.OnHTML("meta[name='description']", func(e *colly.HTMLElement) {
		content := e.Attr("content")
		profile.Bio = content
	})

	// Extract posts data (this is a simplified approach)
	// In a real implementation, you'd need to handle Instagram's JavaScript rendering
	c.OnHTML("script", func(e *colly.HTMLElement) {
		scriptContent := e.Text
		if strings.Contains(scriptContent, "window._sharedData") {
			// Extract JSON data from _sharedData
			// This is where you'd parse the Instagram data structure
			logrus.Debug("Found Instagram shared data")
		}
	})

	// Visit the profile
	err := c.Visit(instagramURL)
	if err != nil {
		return nil, fmt.Errorf("failed to visit Instagram profile: %w", err)
	}

	// Extract username from URL
	u, _ := url.Parse(instagramURL)
	pathParts := strings.Split(strings.Trim(u.Path, "/"), "/")
	if len(pathParts) > 0 {
		profile.Username = pathParts[0]
	}

	// Simulate finding products (in real implementation, this would extract from actual posts)
	posts = s.extractProductsFromPosts(instagramURL)
	profile.RecentPosts = posts

	if profile.FullName == "" {
		profile.FullName = profile.Username
	}

	logrus.WithFields(logrus.Fields{
		"username": profile.Username,
		"posts":    len(profile.RecentPosts),
	}).Info("Instagram profile scraped")

	return profile, nil
}

// extractProductsFromPosts simulates extracting product information from posts
// In a real implementation, this would parse actual Instagram post data
func (s *InstagramScraper) extractProductsFromPosts(profileURL string) []models.InstagramPost {
	// This is a mock implementation
	// In reality, you'd need to:
	// 1. Extract post URLs from the profile
	// 2. Visit each post to get detailed information
	// 3. Use AI/ML to identify products in images and captions
	// 4. Extract pricing information from captions

	mockPosts := []models.InstagramPost{
		{
			PostURL:  profileURL + "p/mock_post_1/",
			Caption:  "Beautiful handmade bag 🛍️ Perfect for everyday use! Available now for ₹1,299 #handmade #bags #fashion",
			Images:   []string{"https://example.com/image1.jpg"},
			Likes:    45,
			Comments: 12,
			Hashtags: []string{"handmade", "bags", "fashion"},
			PostDate: time.Now().AddDate(0, 0, -5).Format("2006-01-02"),
		},
		{
			PostURL:  profileURL + "p/mock_post_2/",
			Caption:  "Fresh celebration cake 🎂 Custom designs available! Order now for ₹899 #cakes #celebration #custom",
			Images:   []string{"https://example.com/image2.jpg"},
			Likes:    78,
			Comments: 23,
			Hashtags: []string{"cakes", "celebration", "custom"},
			PostDate: time.Now().AddDate(0, 0, -3).Format("2006-01-02"),
		},
		{
			PostURL:  profileURL + "p/mock_post_3/",
			Caption:  "Cozy crochet scarf 🧣 Keep warm in style! Available in multiple colors for ₹799 #crochet #scarf #winter",
			Images:   []string{"https://example.com/image3.jpg"},
			Likes:    32,
			Comments: 8,
			Hashtags: []string{"crochet", "scarf", "winter"},
			PostDate: time.Now().AddDate(0, 0, -1).Format("2006-01-02"),
		},
	}

	return mockPosts
}

// ExtractProducts converts Instagram posts to product models
func (s *InstagramScraper) ExtractProducts(profile *models.InstagramProfile, userID, catalogID string) []models.Product {
	var products []models.Product

	for _, post := range profile.RecentPosts {
		product := s.postToProduct(post, userID, catalogID)
		if product != nil {
			products = append(products, *product)
		}
	}

	return products
}

// postToProduct converts an Instagram post to a product
func (s *InstagramScraper) postToProduct(post models.InstagramPost, userID, catalogID string) *models.Product {
	// Convert userID string to ObjectID
	userObjectID, err := primitive.ObjectIDFromHex(userID)
	if err != nil {
		logrus.WithError(err).Error("Invalid user ID format")
		return nil
	}
	// Extract product name from caption (first line or before emoji)
	name := s.extractProductName(post.Caption)
	if name == "" {
		return nil // Skip posts without identifiable products
	}

	// Extract price from caption
	price := s.extractPrice(post.Caption)

	// Get main image
	imageURL := ""
	if len(post.Images) > 0 {
		imageURL = post.Images[0]
	}

	product := &models.Product{
		UserID:      userObjectID,
		CatalogID:   catalogID,
		Name:        name,
		Description: post.Caption,
		Price:       price,
		ImageURL:    imageURL,
		PostURL:     post.PostURL,
		CreatedAt:   time.Now(),
	}

	return product
}

// extractProductName extracts product name from Instagram caption
func (s *InstagramScraper) extractProductName(caption string) string {
	// Split by newlines and take first non-empty line
	lines := strings.Split(caption, "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line != "" {
			// Remove emojis and extract first part
			words := strings.Fields(line)
			if len(words) >= 2 {
				// Take first 2-4 words as product name
				name := strings.Join(words[:min(4, len(words))], " ")
				// Remove common social media symbols
				name = regexp.MustCompile(`[🎉🛍️🎂🧣❤️✨📸🔥💫⭐]`).ReplaceAllString(name, "")
				return strings.TrimSpace(name)
			}
		}
	}
	return ""
}

// extractPrice extracts price from Instagram caption
func (s *InstagramScraper) extractPrice(caption string) string {
	// Look for price patterns like ₹1299, $25, Rs.500, etc.
	priceRegex := regexp.MustCompile(`(?i)(?:₹|rs\.?|inr|price|cost)\s*(\d+(?:,\d+)*(?:\.\d+)?)`)
	matches := priceRegex.FindStringSubmatch(caption)
	if len(matches) > 1 {
		return "₹" + matches[1]
	}

	// Look for standalone number patterns that might be prices
	numberRegex := regexp.MustCompile(`₹\s*(\d+(?:,\d+)*(?:\.\d+)?)`)
	matches = numberRegex.FindStringSubmatch(caption)
	if len(matches) > 1 {
		return "₹" + matches[1]
	}

	return ""
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}