#!/usr/bin/env python3

import argparse
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from dotenv import load_dotenv
from src.lambda_function import DynamoDBClient
import boto3
import pytz

load_dotenv()

def setup_aws():
    """Setup AWS configuration for local or cloud DynamoDB"""
    if os.getenv('LOCAL_DYNAMODB') == 'true':
        os.environ['AWS_ACCESS_KEY_ID'] = 'fake'
        os.environ['AWS_SECRET_ACCESS_KEY'] = 'fake'
        os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
        
        boto3.setup_default_session(
            aws_access_key_id='fake',
            aws_secret_access_key='fake',
            region_name='us-east-1'
        )
        
        original_resource = boto3.resource
        def local_dynamodb_resource(service_name, **kwargs):
            if service_name == 'dynamodb':
                kwargs['endpoint_url'] = 'http://localhost:8000'
            return original_resource(service_name, **kwargs)
        
        boto3.resource = local_dynamodb_resource

def convert_decimal_to_float(obj):
    """Convert Decimal objects to float for pandas"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: convert_decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimal_to_float(item) for item in obj]
    else:
        return obj

def fetch_data(start_date, end_date, local_tz=None):
    """Fetch temperature data from DynamoDB with timezone support"""
    setup_aws()
    
    table_name = os.environ['DYNAMODB_TABLE']
    client = DynamoDBClient(table_name)
    
    print(f"Fetching data from {start_date} to {end_date} (UTC dates)...")
    
    # Get readings for the date range
    readings = client.get_readings_date_range(start_date, end_date)
    
    if not readings:
        print("No data found for the specified date range")
        return pd.DataFrame()
    
    # Convert Decimal objects to float
    readings = [convert_decimal_to_float(reading) for reading in readings]
    
    print(f"Found {len(readings)} readings")
    
    # Convert to DataFrame
    df = pd.DataFrame(readings)
    
    # Convert timestamp to datetime in UTC first, then to local timezone if specified
    df['datetime_utc'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
    
    if local_tz:
        df['datetime'] = df['datetime_utc'].dt.tz_convert(local_tz)
        df['local_date'] = df['datetime'].dt.date
    else:
        df['datetime'] = df['datetime_utc']
        df['local_date'] = df['datetime'].dt.date
    
    return df

def create_charts(df, save_path=None):
    """Create temperature and humidity charts"""
    if df.empty:
        print("No data to chart")
        return
    
    # Set up the plot style
    plt.style.use('default')
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    fig.suptitle('Temperature and Humidity Over Time', fontsize=16, fontweight='bold')
    
    # Get unique devices
    devices = df['device_name'].unique()
    colors = plt.cm.tab10(range(len(devices)))
    
    # Temperature chart (convert to Fahrenheit)
    for i, device in enumerate(devices):
        device_data = df[df['device_name'] == device]
        if 'temperature_celsius' in device_data.columns and device_data['temperature_celsius'].notna().any():
            # Convert Celsius to Fahrenheit
            temp_fahrenheit = device_data['temperature_celsius'] * 9/5 + 32
            ax1.plot(device_data['datetime'], temp_fahrenheit, 
                    label=device, color=colors[i], linewidth=2, marker='o', markersize=3)
    
    ax1.set_title('Temperature (°F)', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Temperature (°F)', fontsize=12)
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # Format x-axis for temperature
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax1.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
    
    # Humidity chart
    for i, device in enumerate(devices):
        device_data = df[df['device_name'] == device]
        if 'humidity_percent' in device_data.columns and device_data['humidity_percent'].notna().any():
            ax2.plot(device_data['datetime'], device_data['humidity_percent'], 
                    label=device, color=colors[i], linewidth=2, marker='o', markersize=3)
    
    ax2.set_title('Humidity (%)', fontsize=14, fontweight='bold')
    ax2.set_ylabel('Humidity (%)', fontsize=12)
    ax2.set_xlabel('Time', fontsize=12)
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    # Format x-axis for humidity
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
    
    # Adjust layout
    plt.tight_layout()
    
    # Save or show
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Chart saved to {save_path}")
    else:
        plt.show()

def print_summary(df):
    """Print data summary"""
    if df.empty:
        return
    
    print("\n=== Data Summary ===")
    print(f"Time range: {df['datetime'].min()} to {df['datetime'].max()}")
    print(f"Total readings: {len(df)}")
    
    print("\nDevices found:")
    for device in df['device_name'].unique():
        device_data = df[df['device_name'] == device]
        count = len(device_data)
        
        if 'temperature_celsius' in device_data.columns and device_data['temperature_celsius'].notna().any():
            temp_avg_c = device_data['temperature_celsius'].mean()
            temp_avg_f = temp_avg_c * 9/5 + 32
            temp_min_f = device_data['temperature_celsius'].min() * 9/5 + 32
            temp_max_f = device_data['temperature_celsius'].max() * 9/5 + 32
            temp_range = f"{temp_min_f:.1f}-{temp_max_f:.1f}"
            print(f"  - {device}: {count} readings, avg temp {temp_avg_f:.1f}°F (range: {temp_range}°F)")
        else:
            print(f"  - {device}: {count} readings (no temperature data)")

def calculate_utc_date_range(local_date_str, local_tz_str):
    """Calculate UTC date range needed to get all data for a local timezone day"""
    # Parse the local date
    local_date = datetime.strptime(local_date_str, '%Y-%m-%d').date()
    
    # Get timezone object
    local_tz = pytz.timezone(local_tz_str)
    
    # Create start and end of day in local timezone
    local_start = local_tz.localize(datetime.combine(local_date, datetime.min.time()))
    local_end = local_tz.localize(datetime.combine(local_date, datetime.max.time()))
    
    # Convert to UTC
    utc_start = local_start.astimezone(pytz.UTC)
    utc_end = local_end.astimezone(pytz.UTC)
    
    # Get the date strings we need to query
    utc_start_date = utc_start.date().strftime('%Y-%m-%d')
    utc_end_date = utc_end.date().strftime('%Y-%m-%d')
    
    return utc_start_date, utc_end_date, utc_start, utc_end

def filter_data_by_local_date(df, target_local_date, local_tz_str):
    """Filter dataframe to only include data from the target local date"""
    if df.empty:
        return df
    
    target_date = datetime.strptime(target_local_date, '%Y-%m-%d').date()
    return df[df['local_date'] == target_date]

def main():
    parser = argparse.ArgumentParser(description='Chart temperature and humidity data')
    parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD), defaults to today in local timezone')
    parser.add_argument('--end', type=str, help='End date (YYYY-MM-DD), defaults to start date')
    parser.add_argument('--timezone', type=str, default='America/New_York', help='Local timezone (default: America/New_York for EST/EDT)')
    parser.add_argument('--save', type=str, help='Save chart to file instead of displaying')
    parser.add_argument('--summary', action='store_true', help='Show data summary')
    parser.add_argument('--utc', action='store_true', help='Use UTC dates instead of local timezone')
    
    args = parser.parse_args()
    
    local_tz_str = args.timezone
    local_tz = pytz.timezone(local_tz_str)
    
    if args.utc:
        # Legacy UTC mode
        if args.start:
            start_date = args.start
        else:
            start_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        if args.end:
            end_date = args.end
        else:
            end_date = start_date
        
        print(f"Charting data from {start_date} to {end_date} (UTC mode)")
        df = fetch_data(start_date, end_date)
    else:
        # New timezone-aware mode
        if args.start:
            local_start_date = args.start
        else:
            # Get today in local timezone
            local_now = datetime.now(local_tz)
            local_start_date = local_now.strftime('%Y-%m-%d')
        
        if args.end:
            local_end_date = args.end
        else:
            local_end_date = local_start_date
        
        print(f"Charting data for {local_start_date} to {local_end_date} in {local_tz_str}")
        
        # Calculate UTC date range needed
        utc_start_date, utc_end_date, utc_start_dt, utc_end_dt = calculate_utc_date_range(local_start_date, local_tz_str)
        
        if local_start_date != local_end_date:
            # Handle date ranges
            _, end_utc_end_date, _, _ = calculate_utc_date_range(local_end_date, local_tz_str)
            utc_end_date = end_utc_end_date
        
        print(f"Querying UTC dates {utc_start_date} to {utc_end_date} to get local data")
        
        # Fetch data with timezone info
        df = fetch_data(utc_start_date, utc_end_date, local_tz_str)
        
        # Filter to only include data from the requested local date(s)
        if not df.empty:
            if local_start_date == local_end_date:
                df = filter_data_by_local_date(df, local_start_date, local_tz_str)
            else:
                # Handle date ranges
                start_date_obj = datetime.strptime(local_start_date, '%Y-%m-%d').date()
                end_date_obj = datetime.strptime(local_end_date, '%Y-%m-%d').date()
                df = df[(df['local_date'] >= start_date_obj) & (df['local_date'] <= end_date_obj)]
    
    if args.summary:
        print_summary(df)
    
    if not df.empty:
        create_charts(df, args.save)
    else:
        print("No data available for charting")

if __name__ == "__main__":
    main()