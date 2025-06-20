# Temperature Monitor

AWS serverless app to track temperature from Nest sensors and store in DynamoDB.

## Local Development

1. Copy `.env.example` to `.env` and fill in your Nest API credentials
2. Install Docker (for local DynamoDB)
3. Run `./run_local.sh` to test locally
4. Use `./test_nest_api.py` to verify Nest API connection

## AWS Deployment

1. Install AWS SAM CLI
2. Get Nest API credentials from Google Cloud Console
3. Update `parameters.json` with your credentials
4. Run `./deploy.sh`

## Architecture

- **Lambda**: Polls Nest API every 15 minutes
- **DynamoDB**: Stores readings 
- **EventBridge**: Triggers Lambda on schedule

## Cost

Designed to stay within AWS free tier limits.