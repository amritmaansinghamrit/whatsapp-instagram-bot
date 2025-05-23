package database

import (
	"context"
	"time"

	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
	"github.com/sirupsen/logrus"
)

var client *mongo.Client
var db *mongo.Database

// Connect establishes connection to MongoDB
func Connect(mongoURI, databaseName string) (*mongo.Database, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	clientOptions := options.Client().ApplyURI(mongoURI)
	
	var err error
	client, err = mongo.Connect(ctx, clientOptions)
	if err != nil {
		return nil, err
	}

	// Ping the database
	err = client.Ping(ctx, nil)
	if err != nil {
		return nil, err
	}

	db = client.Database(databaseName)
	logrus.WithField("database", databaseName).Info("Connected to MongoDB")

	return db, nil
}

// Disconnect closes the MongoDB connection
func Disconnect() {
	if client != nil {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		
		if err := client.Disconnect(ctx); err != nil {
			logrus.WithError(err).Error("Error disconnecting from MongoDB")
		} else {
			logrus.Info("Disconnected from MongoDB")
		}
	}
}

// GetDatabase returns the database instance
func GetDatabase() *mongo.Database {
	return db
}

// GetCollection returns a collection from the database
func GetCollection(collectionName string) *mongo.Collection {
	return db.Collection(collectionName)
}