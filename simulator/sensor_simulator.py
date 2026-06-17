#!/usr/bin/env python3
"""
夯土墙传感器模拟器 - 模拟4G DTU数据上报
模拟8段墙体每小时上报风蚀深度、土体含水量、表面硬度、风速风向数据
"""

import asyncio
import httpx
import json
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("SensorSimulator")


class WallSegmentSimulator:
    def __init__(
        self,
        segment_id: int,
        segment_name: str,
        base_erosion_rate: float = 0.1,
        base_hardness: float = 2.5,
        base_moisture: float = 5.0
    ):
        self.segment_id = segment_id
        self.segment_name = segment_name
        self.base_erosion_rate = base_erosion_rate
        self.base_hardness = base_hardness
        self.base_moisture = base_moisture
        self.current_erosion_depth = 0.0
        self.hourly_count = 0
        
        self.erosion_trend = random.uniform(0.8, 1.2)
        self.hardness_decay = random.uniform(0.995, 0.999)
        self.moisture_variation = random.uniform(0.8, 1.2)
    
    def generate_wind_data(self) -> tuple:
        season_factor = 1.0
        month = datetime.now().month
        if month in [3, 4, 5]:
            season_factor = 1.3
        elif month in [6, 7, 8]:
            season_factor = 0.8
        elif month in [12, 1, 2]:
            season_factor = 1.1
        
        diurnal_factor = 1.0
        hour = datetime.now().hour
        if 10 <= hour <= 16:
            diurnal_factor = 1.2
        elif 22 <= hour or hour <= 5:
            diurnal_factor = 0.6
        
        base_wind_speed = random.uniform(2.0, 8.0) * season_factor * diurnal_factor
        gust_factor = random.choice([1.0, 1.0, 1.0, 1.5, 2.0])
        wind_speed = base_wind_speed * gust_factor
        
        wind_direction = random.uniform(0, 360)
        if random.random() < 0.7:
            dominant_directions = [0, 45, 90, 180, 225, 270]
            wind_direction = random.choice(dominant_directions) + random.uniform(-15, 15)
        
        return max(0.5, wind_speed), wind_direction % 360
    
    def generate_erosion_depth(self, wind_speed: float) -> float:
        wind_factor = wind_speed ** 2 / 25.0
        hourly_erosion = self.base_erosion_rate * wind_factor * self.erosion_trend / 8760.0
        hourly_erosion *= random.uniform(0.8, 1.2)
        
        self.current_erosion_depth += hourly_erosion
        return max(0.001, self.current_erosion_depth)
    
    def generate_soil_moisture(self) -> float:
        month = datetime.now().month
        if month in [7, 8, 9]:
            base_moisture = self.base_moisture * 1.5
        elif month in [12, 1, 2]:
            base_moisture = self.base_moisture * 0.7
        else:
            base_moisture = self.base_moisture
        
        moisture = base_moisture * self.moisture_variation * random.uniform(0.9, 1.1)
        return max(0.5, min(20.0, moisture))
    
    def generate_surface_hardness(self) -> float:
        self.base_hardness *= self.hardness_decay
        hardness = self.base_hardness * random.uniform(0.95, 1.05)
        return max(0.5, min(5.0, hardness))
    
    def generate_sensor_data(self) -> Dict[str, Any]:
        self.hourly_count += 1
        
        wind_speed, wind_direction = self.generate_wind_data()
        erosion_depth = self.generate_erosion_depth(wind_speed)
        soil_moisture = self.generate_soil_moisture()
        surface_hardness = self.generate_surface_hardness()
        
        temperature = random.uniform(10.0, 30.0)
        humidity = random.uniform(30.0, 80.0)
        dtu_signal = random.uniform(-85.0, -55.0)
        
        return {
            "time": datetime.now().isoformat(),
            "segment_id": self.segment_id,
            "sensor_id": f"DTU-{self.segment_id:02d}-{datetime.now().strftime('%Y%m%d%H')}",
            "wind_erosion_depth": round(erosion_depth, 4),
            "soil_moisture": round(soil_moisture, 2),
            "surface_hardness": round(surface_hardness, 3),
            "wind_speed": round(wind_speed, 2),
            "wind_direction": round(wind_direction, 1),
            "temperature": round(temperature, 1),
            "humidity": round(humidity, 1),
            "dtu_signal_strength": round(dtu_signal, 1)
        }
    
    def generate_crack_data(self) -> Dict[str, Any]:
        if random.random() > 0.1:
            return None
        
        crack_width = random.uniform(0.1, 5.0)
        extension_rate = crack_width / random.uniform(10.0, 100.0)
        
        return {
            "time": datetime.now().isoformat(),
            "segment_id": self.segment_id,
            "crack_id": f"CRK-{self.segment_id:02d}-{random.randint(1, 10):02d}",
            "crack_width": round(crack_width, 2),
            "crack_length": round(random.uniform(0.5, 5.0), 2),
            "crack_depth": round(random.uniform(0.1, 0.8), 2),
            "extension_rate": round(extension_rate, 4),
            "location_x": round(random.uniform(0, 1), 3),
            "location_y": round(random.uniform(0, 1), 3)
        }


class DTUSimulator:
    def __init__(
        self,
        api_base_url: str = "http://localhost:8000",
        interval_seconds: int = 3600,
        num_segments: int = 8,
        generate_historical: bool = True,
        historical_days: int = 30
    ):
        self.api_base_url = api_base_url
        self.interval_seconds = interval_seconds
        self.num_segments = num_segments
        self.generate_historical = generate_historical
        self.historical_days = historical_days
        
        self.segments: List[WallSegmentSimulator] = []
        self._init_segments()
    
    def _init_segments(self):
        segment_params = [
            (1, "西墙北段", 0.08, 2.8, 4.5),
            (2, "西墙南段", 0.15, 2.2, 5.0),
            (3, "北墙西段", 0.12, 2.5, 4.8),
            (4, "北墙东段", 0.06, 3.0, 4.2),
            (5, "东墙北段", 0.10, 2.3, 5.5),
            (6, "东墙南段", 0.18, 2.0, 6.0),
            (7, "南墙西段", 0.09, 2.6, 4.6),
            (8, "南墙东段", 0.14, 2.1, 5.2),
        ]
        
        for seg_id, name, erosion_rate, hardness, moisture in segment_params[:self.num_segments]:
            self.segments.append(WallSegmentSimulator(
                segment_id=seg_id,
                segment_name=name,
                base_erosion_rate=erosion_rate,
                base_hardness=hardness,
                base_moisture=moisture
            ))
    
    async def send_data(self, endpoint: str, data: Dict[str, Any]) -> bool:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.api_base_url}{endpoint}",
                    json=data,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code in [200, 201]:
                    logger.debug(f"Data sent successfully to {endpoint}")
                    return True
                else:
                    logger.error(f"Failed to send data: HTTP {response.status_code} - {response.text}")
                    return False
        except Exception as e:
            logger.error(f"Error sending data: {e}")
            return False
    
    async def send_batch_data(self, data_list: List[Dict[str, Any]]) -> bool:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.api_base_url}/api/sensor-data/batch",
                    json=data_list,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code in [200, 201]:
                    result = response.json()
                    logger.info(f"Batch data sent: {result.get('count', len(data_list))} records")
                    return True
                else:
                    logger.error(f"Failed to send batch data: HTTP {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"Error sending batch data: {e}")
            return False
    
    async def generate_historical_data(self):
        if not self.generate_historical:
            return
        
        logger.info(f"Generating {self.historical_days} days of historical data...")
        
        total_hours = self.historical_days * 24
        batch_size = 100
        
        for day in range(self.historical_days):
            day_data = []
            base_time = datetime.now() - timedelta(days=self.historical_days - day)
            
            for hour in range(24):
                current_time = base_time + timedelta(hours=hour)
                
                for segment in self.segments:
                    data = segment.generate_sensor_data()
                    data["time"] = current_time.isoformat()
                    day_data.append(data)
                    
                    if len(day_data) >= batch_size:
                        await self.send_batch_data(day_data)
                        day_data = []
            
            if day_data:
                await self.send_batch_data(day_data)
            
            logger.info(f"Generated historical data for day {day + 1}/{self.historical_days}")
            await asyncio.sleep(0.5)
        
        logger.info("Historical data generation complete")
    
    async def run_once(self):
        logger.info("Generating sensor data for all segments...")
        
        sensor_data_batch = []
        crack_data_list = []
        
        for segment in self.segments:
            data = segment.generate_sensor_data()
            sensor_data_batch.append(data)
            
            crack_data = segment.generate_crack_data()
            if crack_data:
                crack_data_list.append(crack_data)
            
            logger.info(
                f"[{segment.segment_name}] "
                f"风蚀: {data['wind_erosion_depth']:.4f}mm, "
                f"风速: {data['wind_speed']:.1f}m/s, "
                f"硬度: {data['surface_hardness']:.2f}MPa, "
                f"含水量: {data['soil_moisture']:.1f}%"
            )
        
        if sensor_data_batch:
            success = await self.send_batch_data(sensor_data_batch)
            if success:
                logger.info(f"Successfully reported {len(sensor_data_batch)} sensor records")
        
        for crack_data in crack_data_list:
            success = await self.send_data("/api/wind-field/crack", crack_data)
            if success:
                logger.info(f"Crack data reported: {crack_data['crack_id']}")
        
        return sensor_data_batch
    
    async def run_continuous(self):
        logger.info("Starting continuous sensor simulation...")
        logger.info(f"Reporting interval: {self.interval_seconds} seconds")
        logger.info(f"Number of segments: {self.num_segments}")
        
        if self.generate_historical:
            await self.generate_historical_data()
        
        while True:
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"Error in simulation cycle: {e}")
            
            logger.info(f"Waiting {self.interval_seconds} seconds for next report...")
            await asyncio.sleep(self.interval_seconds)


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="夯土墙4G DTU传感器模拟器")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="后端API地址"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="上报间隔（秒），默认3600秒（1小时）"
    )
    parser.add_argument(
        "--segments",
        type=int,
        default=8,
        help="模拟墙体段数"
    )
    parser.add_argument(
        "--no-historical",
        action="store_true",
        help="不生成历史数据"
    )
    parser.add_argument(
        "--historical-days",
        type=int,
        default=30,
        help="生成历史数据的天数"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="只运行一次，不循环"
    )
    
    args = parser.parse_args()
    
    simulator = DTUSimulator(
        api_base_url=args.api_url,
        interval_seconds=args.interval,
        num_segments=args.segments,
        generate_historical=not args.no_historical,
        historical_days=args.historical_days
    )
    
    if args.once:
        await simulator.run_once()
    else:
        await simulator.run_continuous()


if __name__ == "__main__":
    asyncio.run(main())
