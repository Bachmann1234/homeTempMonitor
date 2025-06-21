import json
import os
import time
from datetime import datetime, timedelta
from decimal import Decimal
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
        
        current_time = datetime.utcnow()
        timestamp = int(current_time.timestamp())
        date_str = current_time.strftime('%Y-%m-%d')
        
        for device in devices:
            reading = nest_client.get_sensor_data(device['name'])
            if reading:
                device_short_id = device['name'].split('/')[-1]  # Get just the device ID part
                
                # Try to get a human-readable name from multiple sources
                device_name = nest_client.get_device_display_name(device)
                
                reading_data = {
                    'date': date_str,
                    'timestamp_device': f"{timestamp}#{device_short_id}",
                    'device_id': device['name'],
                    'device_name': device_name,
                    'timestamp': timestamp,
                    'readable_time': current_time.isoformat()
                }
                reading_data.update(reading)
                sensor_readings.append(reading_data)
        
        # Get outdoor weather data
        outdoor_weather = weather_client.get_weather_data()
        if outdoor_weather:
            outdoor_reading = {
                'date': date_str,
                'timestamp_device': f"{timestamp}#outdoor_weather",
                'device_id': 'outdoor_weather',
                'device_name': 'Boston, MA (OpenWeather)',
                'timestamp': timestamp,
                'readable_time': current_time.isoformat()
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
    
    def get_device_display_name(self, device):
        """Extract the best human-readable name for a device"""
        # Try multiple sources for device name
        
        # 1. Check displayName
        if device.get('displayName'):
            return device['displayName']
        
        # 2. Check traits.Info.customName
        traits = device.get('traits', {})
        info_trait = traits.get('sdm.devices.traits.Info', {})
        if info_trait.get('customName'):
            return info_trait['customName']
        
        # 3. Check parentRelations for room name
        parent_relations = device.get('parentRelations', [])
        for relation in parent_relations:
            if relation.get('displayName'):
                return f"Thermostat ({relation['displayName']})"
        
        # 4. Use device type + short ID as fallback
        device_type = device.get('type', '').replace('sdm.devices.types.', '')
        short_id = device['name'].split('/')[-1][-8:]  # Last 8 chars of ID
        return f"{device_type} {short_id}"


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
                # Convert floats to Decimal for DynamoDB
                converted_reading = self._convert_floats_to_decimal(reading)
                batch.put_item(Item=converted_reading)
    
    def _convert_floats_to_decimal(self, obj):
        """Recursively convert floats to Decimal for DynamoDB compatibility"""
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {k: self._convert_floats_to_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_floats_to_decimal(item) for item in obj]
        else:
            return obj
    
    def get_readings_by_date(self, date_str):
        """Get all readings for a specific date"""
        response = self.table.query(
            KeyConditionExpression='#date = :date',
            ExpressionAttributeNames={'#date': 'date'},
            ExpressionAttributeValues={':date': date_str},
            ScanIndexForward=True
        )
        return response['Items']
    
    def get_readings_date_range(self, start_date, end_date):
        """Get readings across multiple dates (for charting)"""
        all_readings = []
        current_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        
        while current_date <= end_date_obj:
            date_str = current_date.strftime('%Y-%m-%d')
            readings = self.get_readings_by_date(date_str)
            all_readings.extend(readings)
            current_date += timedelta(days=1)
            
        return sorted(all_readings, key=lambda x: x['timestamp'])