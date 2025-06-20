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
        
        weather_client = OpenWeatherClient(os.environ['OPENWEATHER_API_KEY'])
        dynamodb_client = DynamoDBClient(os.environ['DYNAMODB_TABLE'])
        
        devices = nest_client.get_devices()
        sensor_readings = []
        
        for device in devices:
            reading = nest_client.get_sensor_data(device['name'])
            if reading:
                reading_data = {
                    'device_id': device['name'],
                    'device_name': device.get('displayName', device['name']),
                    'timestamp': int(time.time()),
                    'readable_time': datetime.utcnow().isoformat()
                }
                reading_data.update(reading)
                sensor_readings.append(reading_data)
        
        # Get outdoor weather data
        outdoor_weather = weather_client.get_weather_data()
        if outdoor_weather:
            outdoor_reading = {
                'device_id': 'outdoor_medford_ma',
                'device_name': 'Medford, MA (OpenWeather)',
                'timestamp': int(time.time()),
                'readable_time': datetime.utcnow().isoformat()
            }
            outdoor_reading.update(outdoor_weather)
            sensor_readings.append(outdoor_reading)
        
        if sensor_readings:
            dynamodb_client.save_readings(sensor_readings)
            print(f"Saved {len(sensor_readings)} sensor readings")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully processed {len(sensor_readings)} readings',
                'readings': sensor_readings
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
    
    def get_sensor_data(self, device_name):
        headers = {
            'Authorization': f'Bearer {self.get_access_token()}',
            'Content-Type': 'application/json'
        }
        
        url = f"{self.base_url}/{device_name}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        device_data = response.json()
        traits = device_data.get('traits', {})
        
        data = {}
        
        # Get temperature
        temperature_trait = traits.get('sdm.devices.traits.Temperature', {})
        if temperature_trait:
            data['temperature_celsius'] = temperature_trait.get('ambientTemperatureCelsius')
            
        # Get humidity
        humidity_trait = traits.get('sdm.devices.traits.Humidity', {})
        if humidity_trait:
            data['humidity_percent'] = humidity_trait.get('ambientHumidityPercent')
            
        return data


class OpenWeatherClient:
    def __init__(self, api_key, lat=None, lon=None):
        self.api_key = api_key
        self.base_url = "https://api.openweathermap.org/data/3.0"
        # Use environment variables or defaults to Boston, MA
        self.lat = lat or os.environ.get('WEATHER_LAT', 42.3601)
        self.lon = lon or os.environ.get('WEATHER_LON', -71.0589)
    
    def get_weather_data(self):
        url = f"{self.base_url}/onecall"
        params = {
            'lat': self.lat,
            'lon': self.lon,
            'appid': self.api_key,
            'units': 'metric',
            'exclude': 'minutely,hourly,daily,alerts'  # Only get current weather
        }

        print(url)
        print(params)
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        current = data['current']
        
        return {
            'temperature_celsius': current['temp'],
            'humidity_percent': current['humidity'],
            'weather_description': current['weather'][0]['description'],
            'feels_like_celsius': current['feels_like'],
            'pressure_hpa': current['pressure'],
            'uv_index': current.get('uvi', 0),
            'wind_speed_ms': current.get('wind_speed', 0)
        }


class DynamoDBClient:
    def __init__(self, table_name):
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
    
    def save_readings(self, readings):
        with self.table.batch_writer() as batch:
            for reading in readings:
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