#!/bin/bash
# LocalStack initialization - create S3 bucket and SQS queue for local dev

set -e

echo "Initializing LocalStack resources..."

awslocal s3 mb s3://thumbnailai-dev
awslocal s3api put-bucket-cors --bucket thumbnailai-dev --cors-configuration '{
  "CORSRules": [{
    "AllowedOrigins": ["*"],
    "AllowedMethods": ["GET", "PUT", "POST"],
    "AllowedHeaders": ["*"]
  }]
}'

awslocal sqs create-queue --queue-name thumbnailai-dev --attributes '{
  "VisibilityTimeout": "900",
  "MessageRetentionPeriod": "86400"
}'

# Dead letter queue
awslocal sqs create-queue --queue-name thumbnailai-dev-dlq

echo "LocalStack initialization complete."
