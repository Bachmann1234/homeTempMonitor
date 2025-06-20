#!/usr/bin/env python3

import os
from dotenv import load_dotenv
from src.lambda_function import NestClient

load_dotenv()

def test_nest_connection():
    print("Testing Nest API connection...")
    
    client = NestClient(
        client_id=os.environ['NEST_CLIENT_ID'],
        client_secret=os.environ['NEST_CLIENT_SECRET'],
        refresh_token=os.environ['NEST_REFRESH_TOKEN']
    )
    
    try:
        print("Getting access token...")
        token = client.get_access_token()
        print(f"✓ Access token obtained: {token[:20]}...")
        
        print("Fetching devices...")
        devices = client.get_devices()
        print(f"✓ Found {len(devices)} devices")
        
        for device in devices:
            print(f"  - Device: {device.get('displayName', device['name'])}")
            print(f"    ID: {device['name']}")
            
            sensor_data = client.get_sensor_data(device['name'])
            if sensor_data:
                if 'temperature_celsius' in sensor_data:
                    temp = sensor_data['temperature_celsius']
                    print(f"    Temperature: {temp}°C ({temp * 9/5 + 32:.1f}°F)")
                if 'humidity_percent' in sensor_data:
                    humidity = sensor_data['humidity_percent']
                    print(f"    Humidity: {humidity}%")
            else:
                print("    No sensor data available")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

if __name__ == "__main__":
    if not os.path.exists('.env'):
        print("Please create .env file with your Nest API credentials")
        print("Copy .env.example to .env and fill in the values")
        exit(1)
    
    success = test_nest_connection()
    exit(0 if success else 1)