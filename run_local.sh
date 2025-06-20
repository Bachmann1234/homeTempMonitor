#!/bin/bash

set -e

echo "Starting local temperature monitor..."

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo "Please edit .env with your Nest API credentials"
    exit 1
fi

# Start DynamoDB local in background
echo "Starting local DynamoDB..."
docker-compose up -d dynamodb-local

# Wait for DynamoDB to be ready
echo "Waiting for DynamoDB to be ready..."
sleep 5

# Install dependencies if needed
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment and installing dependencies..."
source venv/bin/activate
pip install -r requirements.txt

# Run the local version
echo "Running temperature monitor locally..."
cd src
python local_lambda.py

echo "Done! Check the output above for results."