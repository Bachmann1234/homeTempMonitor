#!/bin/bash

# Deploy script for temperature monitoring app
set -e

echo "Deploying temperature monitoring app..."

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "Please create .env file with your API credentials"
    echo "Copy .env.example to .env and fill in the values"
    exit 1
fi

# Build and deploy
sam build

# Read parameters from .env and convert to SAM format
PARAMS=$(python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()

# Map .env variables to CloudFormation parameter names
param_mapping = {
    'NEST_CLIENT_ID': 'NestClientId',
    'NEST_CLIENT_SECRET': 'NestClientSecret', 
    'NEST_REFRESH_TOKEN': 'NestRefreshToken',
    'NEST_PROJECT_ID': 'NestProjectId',
    'OPENWEATHER_API_KEY': 'OpenWeatherApiKey',
    'WEATHER_LAT': 'WeatherLat',
    'WEATHER_LON': 'WeatherLon'
}

params = []
for env_var, cf_param in param_mapping.items():
    value = os.getenv(env_var)
    if value:
        params.append(f'{cf_param}={value}')

print(' '.join(params))
")

sam deploy --guided --parameter-overrides $PARAMS

echo "Deployment complete!"