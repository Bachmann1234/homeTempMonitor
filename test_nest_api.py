#!/usr/bin/env python3

import os
from dotenv import load_dotenv
from src.lambda_function import NestClient, OpenWeatherClient

load_dotenv()

def test_all_sensors():
    print("Testing all sensor connections...")
    
    # Test Nest
    print("\n=== Nest Thermostats ===")
    nest_client = NestClient(
        client_id=os.environ['NEST_CLIENT_ID'],
        client_secret=os.environ['NEST_CLIENT_SECRET'],
        refresh_token=os.environ['NEST_REFRESH_TOKEN']
    )
    
    nest_success = True
    try:
        print("Getting access token...")
        token = nest_client.get_access_token()
        print(f"✓ Access token obtained: {token[:20]}...")
        
        print("Fetching devices...")
        devices = nest_client.get_devices()
        print(f"✓ Found {len(devices)} devices")
        
        for device in devices:
            device_name = nest_client.get_device_display_name(device)
            print(f"  - Device: {device_name}")
            print(f"    ID: {device['name']}")
            
            # Show additional device info for debugging
            traits = device.get('traits', {})
            info_trait = traits.get('sdm.devices.traits.Info', {})
            print(f"    Custom Name: {info_trait.get('customName', 'None')}")
            print(f"    Display Name: {device.get('displayName', 'None')}")
            
            parent_relations = device.get('parentRelations', [])
            if parent_relations:
                for relation in parent_relations:
                    print(f"    Room: {relation.get('displayName', 'None')}")
            
            sensor_data = nest_client.get_sensor_data(device['name'])
            if sensor_data:
                if 'temperature_celsius' in sensor_data:
                    temp = sensor_data['temperature_celsius']
                    print(f"    Temperature: {temp}°C ({temp * 9/5 + 32:.1f}°F)")
                if 'humidity_percent' in sensor_data:
                    humidity = sensor_data['humidity_percent']
                    print(f"    Humidity: {humidity}%")
            else:
                print("    No sensor data available")
            print()
        
    except Exception as e:
        print(f"✗ Nest Error: {e}")
        nest_success = False
    
    # Test OpenWeather
    print("\n=== OpenWeather (Medford, MA) ===")
    weather_success = True
    try:
        weather_client = OpenWeatherClient(os.environ['OPENWEATHER_API_KEY'])
        weather_data = weather_client.get_weather_data()
        
        if weather_data:
            print("✓ Weather data retrieved")
            print(f"  Temperature: {weather_data['temperature_celsius']}°C ({weather_data['temperature_celsius'] * 9/5 + 32:.1f}°F)")
            print(f"  Feels like: {weather_data['feels_like_celsius']}°C ({weather_data['feels_like_celsius'] * 9/5 + 32:.1f}°F)")
            print(f"  Humidity: {weather_data['humidity_percent']}%")
            print(f"  Pressure: {weather_data['pressure_hpa']} hPa")
            print(f"  UV Index: {weather_data['uv_index']}")
            print(f"  Wind Speed: {weather_data['wind_speed_ms']} m/s")
            print(f"  Conditions: {weather_data['weather_description']}")
        else:
            print("✗ No weather data received")
            weather_success = False
            
    except Exception as e:
        print(f"✗ Weather Error: {e}")
        weather_success = False
    
    return nest_success and weather_success

if __name__ == "__main__":
    if not os.path.exists('.env'):
        print("Please create .env file with your API credentials")
        print("Copy .env.example to .env and fill in the values")
        exit(1)
    
    success = test_all_sensors()
    exit(0 if success else 1)