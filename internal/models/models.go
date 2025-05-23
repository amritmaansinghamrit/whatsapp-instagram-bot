package models

import (
	"time"

	"go.mongodb.org/mongo-driver/bson/primitive"
)

// User represents a WhatsApp user interacting with the bot
type User struct {
	ID          primitive.ObjectID `bson:"_id,omitempty" json:"id"`
	PhoneNumber string             `bson:"phone_number" json:"phone_number"`
	Name        string             `bson:"name" json:"name"`
	State       ConversationState  `bson:"state" json:"state"`
	CreatedAt   time.Time          `bson:"created_at" json:"created_at"`
	UpdatedAt   time.Time          `bson:"updated_at" json:"updated_at"`
}

// ConversationState represents the current state of conversation with a user
type ConversationState struct {
	Step            string `bson:"step" json:"step"`
	InstagramURL    string `bson:"instagram_url,omitempty" json:"instagram_url,omitempty"`
	CatalogID       string `bson:"catalog_id,omitempty" json:"catalog_id,omitempty"`
	WaitingForURL   bool   `bson:"waiting_for_url" json:"waiting_for_url"`
}

// Product represents a scraped Instagram product
type Product struct {
	ID          primitive.ObjectID `bson:"_id,omitempty" json:"id"`
	UserID      primitive.ObjectID `bson:"user_id" json:"user_id"`
	CatalogID   string             `bson:"catalog_id" json:"catalog_id"`
	Name        string             `bson:"name" json:"name"`
	Description string             `bson:"description" json:"description"`
	Price       string             `bson:"price,omitempty" json:"price,omitempty"`
	ImageURL    string             `bson:"image_url" json:"image_url"`
	PostURL     string             `bson:"post_url" json:"post_url"`
	CreatedAt   time.Time          `bson:"created_at" json:"created_at"`
}

// InstagramPost represents a scraped Instagram post
type InstagramPost struct {
	PostURL     string   `json:"post_url"`
	Caption     string   `json:"caption"`
	Images      []string `json:"images"`
	Likes       int      `json:"likes"`
	Comments    int      `json:"comments"`
	Hashtags    []string `json:"hashtags"`
	PostDate    string   `json:"post_date"`
}

// InstagramProfile represents a scraped Instagram profile
type InstagramProfile struct {
	Username     string          `json:"username"`
	FullName     string          `json:"full_name"`
	Bio          string          `json:"bio"`
	Followers    int             `json:"followers"`
	Following    int             `json:"following"`
	PostsCount   int             `json:"posts_count"`
	ProfileImage string          `json:"profile_image"`
	RecentPosts  []InstagramPost `json:"recent_posts"`
}

// WhatsAppMessage represents incoming WhatsApp message structure for v22.0
type WhatsAppMessage struct {
	Object string `json:"object"`
	Entry  []struct {
		ID      string `json:"id"`
		Changes []struct {
			Value struct {
				MessagingProduct string `json:"messaging_product"`
				Metadata         struct {
					DisplayPhoneNumber string `json:"display_phone_number"`
					PhoneNumberID      string `json:"phone_number_id"`
				} `json:"metadata"`
				Contacts []struct {
					Profile struct {
						Name string `json:"name"`
					} `json:"profile"`
					WAID string `json:"wa_id"`
				} `json:"contacts,omitempty"`
				Messages []struct {
					From      string `json:"from"`
					ID        string `json:"id"`
					Timestamp string `json:"timestamp"`
					Text      *struct {
						Body string `json:"body"`
					} `json:"text,omitempty"`
					Image     *struct {
						Caption  string `json:"caption,omitempty"`
						MimeType string `json:"mime_type"`
						SHA256   string `json:"sha256"`
						ID       string `json:"id"`
					} `json:"image,omitempty"`
					Audio     *struct {
						ID       string `json:"id"`
						MimeType string `json:"mime_type"`
					} `json:"audio,omitempty"`
					Video     *struct {
						ID       string `json:"id"`
						MimeType string `json:"mime_type"`
					} `json:"video,omitempty"`
					Document  *struct {
						ID       string `json:"id"`
						MimeType string `json:"mime_type"`
						SHA256   string `json:"sha256"`
						Caption  string `json:"caption,omitempty"`
						Filename string `json:"filename,omitempty"`
					} `json:"document,omitempty"`
					Location  *struct {
						Latitude  float64 `json:"latitude"`
						Longitude float64 `json:"longitude"`
						Name      string  `json:"name,omitempty"`
						Address   string  `json:"address,omitempty"`
					} `json:"location,omitempty"`
					Context   *struct {
						From string `json:"from"`
						ID   string `json:"id"`
					} `json:"context,omitempty"`
					Type      string `json:"type"`
				} `json:"messages,omitempty"`
				Statuses []struct {
					ID           string `json:"id"`
					Status       string `json:"status"`
					Timestamp    string `json:"timestamp"`
					RecipientID  string `json:"recipient_id"`
					Conversation *struct {
						ID               string `json:"id"`
						ExpirationTimestamp string `json:"expiration_timestamp,omitempty"`
						Origin           *struct {
							Type string `json:"type"`
						} `json:"origin,omitempty"`
					} `json:"conversation,omitempty"`
					Pricing *struct {
						Billable     bool   `json:"billable"`
						PricingModel string `json:"pricing_model"`
						Category     string `json:"category"`
					} `json:"pricing,omitempty"`
				} `json:"statuses,omitempty"`
				Errors []struct {
					Code  int    `json:"code"`
					Title string `json:"title"`
					Message string `json:"message,omitempty"`
					ErrorData *struct {
						Details string `json:"details"`
					} `json:"error_data,omitempty"`
				} `json:"errors,omitempty"`
			} `json:"value"`
			Field string `json:"field"`
		} `json:"changes"`
	} `json:"entry"`
}

// ProductCatalog represents a collection of products for a user
type ProductCatalog struct {
	ID             primitive.ObjectID `bson:"_id,omitempty" json:"id"`
	UserID         primitive.ObjectID `bson:"user_id" json:"user_id"`
	InstagramURL   string             `bson:"instagram_url" json:"instagram_url"`
	BusinessName   string             `bson:"business_name" json:"business_name"`
	ProductCount   int                `bson:"product_count" json:"product_count"`
	Status         string             `bson:"status" json:"status"` // "processing", "completed", "failed"
	CreatedAt      time.Time          `bson:"created_at" json:"created_at"`
	CompletedAt    *time.Time         `bson:"completed_at,omitempty" json:"completed_at,omitempty"`
}