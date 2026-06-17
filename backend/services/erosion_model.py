import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from ..models.orm import SensorData, WallSegment, ErosionSimulation
from ..models.schemas import ErosionPredictionResponse


class WindErosionSimulator:
    def __init__(self):
        self.AIR_DENSITY = 1.225
        self.SAND_DENSITY = 2650.0
        self.GRAVITY = 9.81
        self.VON_KARMAN = 0.4
        self.ROUGHNESS_LENGTH = 0.001
        self.SAND_DIAMETER = 0.0002
        self.PARTICLE_SHAPE_FACTOR = 0.8
        self.HARDNESS_CORRECTION = 0.001
        self.MOISTURE_CORRECTION = 0.05

    def calculate_threshold_friction_velocity(
        self,
        particle_diameter: float,
        air_density: float = None,
        sand_density: float = None,
        gravity: float = None
    ) -> float:
        air_density = air_density or self.AIR_DENSITY
        sand_density = sand_density or self.SAND_DENSITY
        gravity = gravity or self.GRAVITY
        
        shields_parameter = 0.03
        u_star_t = np.sqrt(
            shields_parameter * 
            ((sand_density - air_density) / air_density) * 
            gravity * particle_diameter
        )
        return u_star_t

    def calculate_friction_velocity(
        self,
        wind_speed: float,
        height: float = 2.0
    ) -> float:
        u_star = (wind_speed * self.VON_KARMAN) / np.log(height / self.ROUGHNESS_LENGTH)
        return u_star

    def calculate_sand_transport_rate(
        self,
        u_star: float,
        u_star_t: float,
        wind_direction: float
    ) -> float:
        if u_star <= u_star_t:
            return 0.0
        
        alpha = 2.0
        q = alpha * self.AIR_DENSITY / self.GRAVITY * u_star**3 * (1 - (u_star_t / u_star)**2)
        return max(0.0, q)

    def calculate_wind_energy(
        self,
        wind_speed: float,
        duration_hours: float = 1.0
    ) -> float:
        kinetic_energy_per_unit_volume = 0.5 * self.AIR_DENSITY * wind_speed**2
        energy = kinetic_energy_per_unit_volume * wind_speed * duration_hours * 3600
        return energy

    def calculate_particle_impact_energy(
        self,
        wind_speed: float,
        particle_mass: float = None
    ) -> float:
        if particle_mass is None:
            particle_mass = (4/3) * np.pi * (self.SAND_DIAMETER/2)**3 * self.SAND_DENSITY
        
        impact_velocity = wind_speed * 0.8
        impact_energy = 0.5 * particle_mass * impact_velocity**2
        return impact_energy

    def calculate_erosion_rate_from_impact(
        self,
        impact_energy: float,
        surface_hardness: float,
        soil_moisture: float,
        impact_count: float
    ) -> float:
        hardness_factor = np.exp(-self.HARDNESS_CORRECTION * surface_hardness)
        moisture_factor = np.exp(-self.MOISTURE_CORRECTION * soil_moisture)
        
        erosion_per_impact = (
            impact_energy * 
            self.PARTICLE_SHAPE_FACTOR * 
            hardness_factor * 
            moisture_factor / 
            (surface_hardness * 1e6)
        )
        
        total_erosion = erosion_per_impact * impact_count
        return total_erosion

    def simulate_two_phase_flow(
        self,
        wind_speed: float,
        wind_direction: float,
        surface_hardness: float,
        soil_moisture: float,
        duration_hours: float = 1.0,
        grid_resolution: int = 10
    ) -> Dict[str, Any]:
        u_star = self.calculate_friction_velocity(wind_speed)
        u_star_t = self.calculate_threshold_friction_velocity(self.SAND_DIAMETER)
        sand_transport = self.calculate_sand_transport_rate(u_star, u_star_t, wind_direction)
        wind_energy = self.calculate_wind_energy(wind_speed, duration_hours)
        impact_energy = self.calculate_particle_impact_energy(wind_speed)
        
        particle_concentration = sand_transport / max(wind_speed, 0.1)
        area = 1.0
        particle_count = (
            particle_concentration * 
            area * 
            wind_speed * 
            duration_hours * 
            3600 / 
            ((4/3) * np.pi * (self.SAND_DIAMETER/2)**3 * self.SAND_DENSITY)
        )
        
        erosion_depth = self.calculate_erosion_rate_from_impact(
            impact_energy, surface_hardness, soil_moisture, particle_count
        )
        
        wind_direction_rad = np.radians(wind_direction)
        velocity_x = wind_speed * np.sin(wind_direction_rad)
        velocity_y = wind_speed * np.cos(wind_direction_rad)
        velocity_z = wind_speed * 0.1
        
        grid = np.zeros((grid_resolution, grid_resolution))
        for i in range(grid_resolution):
            for j in range(grid_resolution):
                distance_factor = 1.0 - np.sqrt((i - grid_resolution/2)**2 + (j - grid_resolution/2)**2) / (grid_resolution/2)
                distance_factor = max(0.1, distance_factor)
                angle_effect = np.abs(np.cos(np.radians(wind_direction) - np.arctan2(i - grid_resolution/2, j - grid_resolution/2)))
                grid[i, j] = erosion_depth * distance_factor * (0.5 + 0.5 * angle_effect)
        
        return {
            "friction_velocity": u_star,
            "threshold_velocity": u_star_t,
            "sand_transport_rate": sand_transport,
            "wind_energy": wind_energy,
            "particle_impact_energy": impact_energy,
            "particle_impact_count": particle_count,
            "erosion_depth_mm": erosion_depth * 1000,
            "velocity_components": {
                "x": velocity_x,
                "y": velocity_y,
                "z": velocity_z
            },
            "erosion_grid": grid.tolist(),
            "particle_concentration": particle_concentration
        }

    def calculate_long_term_erosion_rate(
        self,
        wind_speeds: np.ndarray,
        wind_directions: np.ndarray,
        surface_hardness: np.ndarray,
        soil_moisture: np.ndarray,
        time_interval_hours: float = 1.0
    ) -> Dict[str, Any]:
        n = len(wind_speeds)
        total_erosion = 0.0
        total_wind_energy = 0.0
        total_particle_count = 0.0
        erosion_events = []
        
        for i in range(n):
            result = self.simulate_two_phase_flow(
                wind_speeds[i],
                wind_directions[i],
                surface_hardness[i],
                soil_moisture[i],
                time_interval_hours
            )
            total_erosion += result["erosion_depth_mm"]
            total_wind_energy += result["wind_energy"]
            total_particle_count += result["particle_impact_count"]
            
            erosion_events.append({
                "time_index": i,
                "wind_speed": wind_speeds[i],
                "erosion_depth": result["erosion_depth_mm"],
                "wind_energy": result["wind_energy"]
            })
        
        total_hours = n * time_interval_hours
        erosion_rate_mm_per_year = (total_erosion / total_hours) * 365 * 24
        
        critical_zones = []
        for event in sorted(erosion_events, key=lambda x: x["erosion_depth"], reverse=True)[:10]:
            if event["erosion_depth"] > np.mean([e["erosion_depth"] for e in erosion_events]) * 1.5:
                critical_zones.append(event)
        
        return {
            "total_erosion_mm": total_erosion,
            "erosion_rate_mm_per_year": erosion_rate_mm_per_year,
            "max_erosion_depth_mm": max([e["erosion_depth"] for e in erosion_events]),
            "avg_erosion_depth_mm": np.mean([e["erosion_depth"] for e in erosion_events]),
            "total_wind_energy": total_wind_energy,
            "total_particle_count": total_particle_count,
            "critical_zones": critical_zones,
            "erosion_events": erosion_events
        }

    def predict_future_erosion(
        self,
        historical_wind_speeds: np.ndarray,
        historical_wind_directions: np.ndarray,
        historical_hardness: np.ndarray,
        historical_moisture: np.ndarray,
        prediction_years: float = 5.0,
        climate_change_factor: float = 1.1
    ) -> Dict[str, Any]:
        current_result = self.calculate_long_term_erosion_rate(
            historical_wind_speeds,
            historical_wind_directions,
            historical_hardness,
            historical_moisture
        )
        
        future_wind_speeds = historical_wind_speeds * climate_change_factor
        future_hardness = historical_hardness * (1 - 0.01 * prediction_years)
        future_moisture = historical_moisture * (1 - 0.02 * prediction_years)
        
        future_result = self.calculate_long_term_erosion_rate(
            future_wind_speeds,
            historical_wind_directions,
            future_hardness,
            future_moisture
        )
        
        predicted_total_erosion = future_result["erosion_rate_mm_per_year"] * prediction_years
        cumulative_erosion = current_result["total_erosion_mm"] + predicted_total_erosion
        
        return {
            "current_erosion_rate": current_result["erosion_rate_mm_per_year"],
            "predicted_erosion_rate": future_result["erosion_rate_mm_per_year"],
            "predicted_max_depth": cumulative_erosion,
            "prediction_years": prediction_years,
            "climate_change_factor": climate_change_factor,
            "future_critical_zones": future_result["critical_zones"]
        }

    async def get_segment_erosion_prediction(
        self,
        db: AsyncSession,
        segment_id: int,
        prediction_years: float = 5.0,
        wind_speed_avg: Optional[float] = None,
        wind_direction_avg: Optional[float] = None,
        include_critical_zones: bool = True
    ) -> ErosionPredictionResponse:
        segment = await db.get(WallSegment, segment_id)
        if not segment:
            raise ValueError(f"Segment {segment_id} not found")
        
        end_time = datetime.now()
        start_time = end_time - timedelta(days=30)
        
        stmt = (
            select(SensorData)
            .where(
                SensorData.segment_id == segment_id,
                SensorData.time >= start_time,
                SensorData.time <= end_time
            )
            .order_by(SensorData.time)
        )
        result = await db.execute(stmt)
        sensor_data = result.scalars().all()
        
        if len(sensor_data) < 24:
            stmt = select(SensorData).where(SensorData.segment_id == segment_id).order_by(SensorData.time.desc()).limit(720)
            result = await db.execute(stmt)
            sensor_data = list(reversed(result.scalars().all()))
        
        if not sensor_data:
            return ErosionPredictionResponse(
                segment_id=segment_id,
                segment_name=segment.name,
                current_erosion_rate=0.0,
                predicted_erosion_rate=0.0,
                predicted_max_depth=0.0,
                prediction_years=prediction_years,
                risk_level="未知",
                critical_zones=[],
                recommendation="数据不足，无法进行准确预测"
            )
        
        wind_speeds = np.array([d.wind_speed for d in sensor_data])
        wind_directions = np.array([d.wind_direction for d in sensor_data])
        surface_hardness = np.array([d.surface_hardness for d in sensor_data])
        soil_moisture = np.array([d.soil_moisture for d in sensor_data])
        
        if wind_speed_avg is not None:
            wind_speeds = np.full_like(wind_speeds, wind_speed_avg)
        if wind_direction_avg is not None:
            wind_directions = np.full_like(wind_directions, wind_direction_avg)
        
        prediction = self.predict_future_erosion(
            wind_speeds,
            wind_directions,
            surface_hardness,
            soil_moisture,
            prediction_years
        )
        
        risk_level = "低"
        if prediction["predicted_erosion_rate"] > 0.5:
            risk_level = "高"
        elif prediction["predicted_erosion_rate"] > 0.2:
            risk_level = "中"
        
        recommendation = self._generate_recommendation(
            prediction["predicted_erosion_rate"],
            segment.original_compaction or 0.8
        )
        
        simulation_record = ErosionSimulation(
            segment_id=segment_id,
            simulation_time=datetime.now(),
            prediction_period_days=int(prediction_years * 365),
            erosion_rate=prediction["predicted_erosion_rate"],
            max_erosion_depth=prediction["predicted_max_depth"],
            critical_zones=prediction["future_critical_zones"],
            wind_energy=prediction.get("current_erosion_rate", 0),
            particle_impact_count=0,
            model_parameters={
                "climate_change_factor": prediction["climate_change_factor"],
                "data_points": len(sensor_data)
            }
        )
        db.add(simulation_record)
        
        return ErosionPredictionResponse(
            segment_id=segment_id,
            segment_name=segment.name,
            current_erosion_rate=prediction["current_erosion_rate"],
            predicted_erosion_rate=prediction["predicted_erosion_rate"],
            predicted_max_depth=prediction["predicted_max_depth"],
            prediction_years=prediction_years,
            risk_level=risk_level,
            critical_zones=prediction["future_critical_zones"] if include_critical_zones else [],
            recommendation=recommendation
        )

    def _generate_recommendation(self, erosion_rate: float, compaction: float) -> str:
        if erosion_rate > 0.5:
            if compaction < 0.85:
                return "强烈建议立即采用硅酸乙酯进行深度渗透加固，配合糯米灰浆表面封护"
            else:
                return "高风险！建议优先采用改性硅酸乙酯加固，定期监测风蚀发展"
        elif erosion_rate > 0.2:
            return "中等风险，建议制定加固方案，可考虑复合加固剂处理"
        else:
            return "风险较低，建议继续监测，必要时进行预防性加固"

    def generate_wind_field(
        self,
        wind_speed: float,
        wind_direction: float,
        grid_size: Tuple[int, int, int] = (10, 5, 5),
        bounds: Tuple[float, float, float, float, float, float] = (0, 10, 0, 5, 0, 3)
    ) -> List[Dict[str, Any]]:
        x_min, x_max, y_min, y_max, z_min, z_max = bounds
        nx, ny, nz = grid_size
        
        x_coords = np.linspace(x_min, x_max, nx)
        y_coords = np.linspace(y_min, y_max, ny)
        z_coords = np.linspace(z_min, z_max, nz)
        
        wind_direction_rad = np.radians(wind_direction)
        base_vx = wind_speed * np.sin(wind_direction_rad)
        base_vy = wind_speed * np.cos(wind_direction_rad)
        
        field_data = []
        current_time = datetime.now()
        
        for i, x in enumerate(x_coords):
            for j, y in enumerate(y_coords):
                for k, z in enumerate(z_coords):
                    height_factor = np.log(z + self.ROUGHNESS_LENGTH) / np.log(2.0 + self.ROUGHNESS_LENGTH)
                    height_factor = max(0.1, min(1.5, height_factor))
                    
                    turbulence = np.random.normal(0, 0.1)
                    vx = base_vx * height_factor * (1 + turbulence)
                    vy = base_vy * height_factor * (1 + turbulence)
                    vz = wind_speed * 0.05 * (1 + np.random.normal(0, 0.2))
                    
                    speed = np.sqrt(vx**2 + vy**2 + vz**2)
                    direction = np.degrees(np.arctan2(vx, vy)) % 360
                    
                    field_data.append({
                        "time": current_time,
                        "grid_x": i,
                        "grid_y": j,
                        "grid_z": k,
                        "position_x": x,
                        "position_y": y,
                        "position_z": z,
                        "velocity_x": vx,
                        "velocity_y": vy,
                        "velocity_z": vz,
                        "wind_speed": speed,
                        "wind_direction": direction,
                        "turbulence_intensity": abs(turbulence),
                        "particle_concentration": speed * 0.01 if speed > 5 else 0
                    })
        
        return field_data


erosion_simulator = WindErosionSimulator()
