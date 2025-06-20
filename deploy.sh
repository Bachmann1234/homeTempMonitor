#!/bin/bash

# Deploy script for temperature monitoring app
set -e

echo "Deploying temperature monitoring app..."

# Check if parameters file exists
if [ ! -f "parameters.json" ]; then
    echo "Creating parameters template..."
    cat > parameters.json << EOF
{
    "NestClientId": "your-nest-client-id",
    "NestClientSecret": "your-nest-client-secret", 
    "NestRefreshToken": "your-nest-refresh-token"
}
EOF
    echo "Please edit parameters.json with your Nest API credentials"
    exit 1
fi

# Build and deploy
sam build
sam deploy --guided --parameter-overrides file://parameters.json

echo "Deployment complete!"