import json
import os
import time
from datetime import datetime, timedelta
import boto3
import requests


def lambda_handler(event, context):
    try:
        nest_client = NestClient(
            client_id=os.environ['NEST_CLIENT_ID'],
            client_secret=os.environ['NEST_CLIENT_SECRET'],
            refresh_token=os.environ['NEST_REFRESH_TOKEN']
        )
        
        dynamodb_client = DynamoDBClient(os.environ['DYNAMODB_TABLE'])
        
        devices = nest_client.get_devices()
        temperature_readings = []
        
        for device in devices:
            reading = nest_client.get_temperature(device['name'])
            if reading:
                temperature_readings.append({
                    'device_id': device['name'],
                    'device_name': device.get('displayName', device['name']),
                    'temperature_celsius': reading,
                    'timestamp': int(time.time()),
                    'readable_time': datetime.utcnow().isoformat()
                })
        
        if temperature_readings:
            dynamodb_client.save_readings(temperature_readings)
            print(f"Saved {len(temperature_readings)} temperature readings")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully processed {len(temperature_readings)} readings',
                'readings': temperature_readings
            })
        }
        
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


class NestClient:
    def __init__(self, client_id, client_secret, refresh_token):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.access_token = None
        self.base_url = "https://smartdevicemanagement.googleapis.com/v1"
        
    def get_access_token(self):
        if self.access_token:
            return self.access_token
            
        token_url = "https://www.googleapis.com/oauth2/v4/token"
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token,
            'grant_type': 'refresh_token'
        }
        
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        self.access_token = token_data['access_token']
        return self.access_token
    
    def get_devices(self):
        headers = {
            'Authorization': f'Bearer {self.get_access_token()}',
            'Content-Type': 'application/json'
        }
        
        project_id = os.environ.get('NEST_PROJECT_ID')
        if not project_id:
            raise ValueError("NEST_PROJECT_ID environment variable is required")
            
        url = f"{self.base_url}/enterprises/{project_id}/devices"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        return data.get('devices', [])
    
    def get_temperature(self, device_name):
        headers = {
            'Authorization': f'Bearer {self.get_access_token()}',
            'Content-Type': 'application/json'
        }
        
        url = f"{self.base_url}/{device_name}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        device_data = response.json()
        traits = device_data.get('traits', {})
        
        temperature_trait = traits.get('sdm.devices.traits.Temperature', {})
        if temperature_trait:
            return temperature_trait.get('ambientTemperatureCelsius')
            
        return None


class DynamoDBClient:
    def __init__(self, table_name):
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
    
    def save_readings(self, readings):
        ttl_days = 365
        ttl_timestamp = int((datetime.utcnow() + timedelta(days=ttl_days)).timestamp())
        
        with self.table.batch_writer() as batch:
            for reading in readings:
                reading['ttl'] = ttl_timestamp
                batch.put_item(Item=reading)
    
    def get_recent_readings(self, device_id, hours=24):
        since_timestamp = int((datetime.utcnow() - timedelta(hours=hours)).timestamp())
        
        response = self.table.query(
            KeyConditionExpression='device_id = :device_id AND #ts >= :since_ts',
            ExpressionAttributeNames={'#ts': 'timestamp'},
            ExpressionAttributeValues={
                ':device_id': device_id,
                ':since_ts': since_timestamp
            },
            ScanIndexForward=False
        )
        
        return response['Items']