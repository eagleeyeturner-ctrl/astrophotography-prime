#!/usr/bin/env python3
"""
Astrophotography Macro - Clean, modular design for lunar and celestial tracking
"""

import time
import math
import datetime as dt
from dataclasses import dataclass
from typing import Dict, List, Tuple
from enum import Enum


# ===================== ENUMS =====================
class SkyCondition(Enum):
    CLEAR = "clear"
    ATMOSPHERIC = "atmospheric"
    LOW_HORIZON = "low_horizon"
    DEEP_SKY = "deep_sky"


class CelestialObject(Enum):
    MOON = "moon"
    PLANET = "planet"
    SATELLITE = "satellite"
    DEEP_SKY_OBJECT = "dso"


# ===================== DATA CLASSES =====================
@dataclass
class Position:
    azimuth: float
    elevation: float

    @property
    def is_visible(self) -> bool:
        return self.elevation > 0


@dataclass
class CameraConfig:
    iso: int
    f_stop: float
    shutter: float
    focal_length: int
    focus: str = "infinity"

    def __str__(self) -> str:
        return f"ISO {self.iso} • f/{self.f_stop} • {self.shutter}s • {self.focal_length}mm"


@dataclass
class CelestialData:
    position: Position
    phase: float  # 0-1
    distance_km: float
    angular_size_arcmin: float
    magnitude: float

    @property
    def condition(self) -> SkyCondition:
        if self.position.elevation < 15:
            return SkyCondition.LOW_HORIZON
        elif self.position.elevation < 30:
            return SkyCondition.ATMOSPHERIC
        return SkyCondition.CLEAR


# ===================== CALCULATORS =====================
class AstronomyCalculator:
    """Handles astronomical calculations with proper formulas"""

    @staticmethod
    def julian_day(timestamp: dt.datetime) -> float:
        """Convert datetime to Julian Day Number"""
        a = (14 - timestamp.month) // 12
        y = timestamp.year + 4800 - a
        m = timestamp.month + 12 * a - 3

        jdn = (timestamp.day + (153 * m + 2) // 5 + 365 * y +
               y // 4 - y // 100 + y // 400 - 32045)

        fraction = ((timestamp.hour - 12) / 24 +
                    timestamp.minute / 1440 +
                    timestamp.second / 86400)

        return jdn + fraction

    @staticmethod
    def lunar_position(jd: float, lat: float, lon: float) -> Tuple[float, float]:
        """Calculate lunar position (simplified but accurate enough)"""
        d = jd - 2451545.0
        L = math.radians((218.316 + 13.176396 * d) % 360)
        M = math.radians((134.963 + 13.064993 * d) % 360)
        M_sun = math.radians((357.528 + 0.985600 * d) % 360)

        lon_ecl = L + math.radians(6.289 * math.sin(M) -
                                   1.274 * math.sin(M - 2 * M_sun) +
                                   0.658 * math.sin(2 * M_sun))

        lat_ecl = math.radians(5.128 * math.sin(math.radians(93.272 + 13.229350 * d)))

        azimuth = (math.degrees(lon_ecl) + 180) % 360
        elevation = max(-90, min(90, math.degrees(lat_ecl) + 30))
        return azimuth, elevation

    @staticmethod
    def lunar_phase(jd: float) -> float:
        """Calculate lunar phase (0 = new moon, 1 = full moon)"""
        d = jd - 2451545.0
        L = math.radians((218.316 + 13.176396 * d) % 360)
        S = math.radians((280.466 + 0.985647 * d) % 360)
        phase_angle = L - S
        return (1 + math.cos(phase_angle)) / 2


class CameraPresets:
    """Optimized camera settings for different conditions"""

    PRESETS = {
        SkyCondition.CLEAR: CameraConfig(200, 8.0, 1/125, 300),
        SkyCondition.ATMOSPHERIC: CameraConfig(400, 5.6, 1/200, 250),
        SkyCondition.LOW_HORIZON: CameraConfig(800, 4.0, 1/160, 400),
        SkyCondition.DEEP_SKY: CameraConfig(1600, 2.8, 30, 50)
    }

    @classmethod
    def get_config(cls, condition: SkyCondition) -> CameraConfig:
        return cls.PRESETS[condition]

    @classmethod
    def adjust_for_phase(cls, config: CameraConfig, phase: float) -> CameraConfig:
        """Adjust camera settings based on moon phase brightness"""
        brightness_factor = 0.3 + (0.7 * phase)
        if brightness_factor < 0.5:
            new_iso = min(3200, int(config.iso * 2))
            new_f_stop = max(2.8, config.f_stop - 1)
        else:
            new_iso = config.iso
            new_f_stop = config.f_stop
        return CameraConfig(new_iso, new_f_stop, config.shutter, config.focal_length)


class ExposureCalculator:
    """Handles exposure compensation calculations"""

    @staticmethod
    def atmospheric_compensation(elevation: float) -> float:
        if elevation < 10:
            return 2.0
        elif elevation < 20:
            return 1.0
        elif elevation < 30:
            return 0.5
        return 0.0

    @staticmethod
    def phase_compensation(phase: float) -> float:
        return -2.5 * phase + 1.5

    @classmethod
    def total_compensation(cls, celestial_data: CelestialData) -> float:
        return cls.atmospheric_compensation(celestial_data.position.elevation) + \
               cls.phase_compensation(celestial_data.phase)


# ===================== SESSION DATA =====================
@dataclass
class ShootingPlan:
    timestamp: dt.datetime
    celestial_data: CelestialData
    camera_config: CameraConfig
    exposure_comp: float

    def to_dict(self) -> Dict:
        return {
            "time": self.timestamp.strftime('%H:%M:%S'),
            "azimuth": round(self.celestial_data.position.azimuth, 1),
            "elevation": round(self.celestial_data.position.elevation, 1),
            "phase": round(self.celestial_data.phase, 2),
            "iso": self.camera_config.iso,
            "f_stop": self.camera_config.f_stop,
            "shutter": self.camera_config.shutter,
            "focal_length": self.camera_config.focal_length,
            "exposure_comp": round(self.exposure_comp, 1)
        }


class TimelapseCalculator:
    """Calculate optimal timelapse parameters"""

    @staticmethod
    def calculate_interval(duration_hours: float, target_fps: int = 24,
                           final_duration_seconds: int = 30) -> Dict:
        total_seconds = duration_hours * 3600
        target_frames = target_fps * final_duration_seconds
        interval_seconds = total_seconds / target_frames
        storage_gb = (target_frames * 25) / 1024
        battery_hours = duration_hours * 0.75

        return {
            "interval_seconds": round(interval_seconds, 1),
            "total_frames": target_frames,
            "storage_gb": round(storage_gb, 1),
            "battery_hours": round(battery_hours, 1),
            "playback_fps": target_fps
        }


class AstroSession:
    """Main class for managing astrophotography sessions"""

    def __init__(self, latitude: float, longitude: float):
        self.lat = latitude
        self.lon = longitude
        self.calc = AstronomyCalculator()

    def get_lunar_data(self, timestamp: dt.datetime) -> CelestialData:
        jd = self.calc.julian_day(timestamp)
        azimuth, elevation = self.calc.lunar_position(jd, self.lat, self.lon)
        phase = self.calc.lunar_phase(jd)
        distance = 384400
        angular_size = 31.1
        magnitude = -12.7 * phase - 2.5
        return CelestialData(Position(azimuth, elevation), phase, distance, angular_size, magnitude)

    def create_shooting_plan(self, timestamp: dt.datetime) -> ShootingPlan:
        lunar_data = self.get_lunar_data(timestamp)
        base_config = CameraPresets.get_config(lunar_data.condition)
        adjusted_config = CameraPresets.adjust_for_phase(base_config, lunar_data.phase)
        exposure_comp = ExposureCalculator.total_compensation(lunar_data)
        return ShootingPlan(timestamp, lunar_data, adjusted_config, exposure_comp)

    def generate_sequence(self, duration_minutes: int, interval_minutes: int = 5) -> List[ShootingPlan]:
        sequence = []
        start_time = dt.datetime.now()
        for i in range(0, duration_minutes, interval_minutes):
            timestamp = start_time + dt.timedelta(minutes=i)
            sequence.append(self.create_shooting_plan(timestamp))
        return sequence

    def export_session_data(self, duration_minutes: int) -> Dict:
        sequence = self.generate_sequence(duration_minutes)
        timelapse = TimelapseCalculator.calculate_interval(duration_minutes / 60)
        return {
            "session": {
                "start_time": dt.datetime.now().isoformat(),
                "duration_minutes": duration_minutes,
                "location": {"lat": self.lat, "lon": self.lon}
            },
            "shooting_sequence": [plan.to_dict() for plan in sequence],
            "timelapse_settings": timelapse,
            "summary": {
                "total_positions": len(sequence),
                "elevation_range": f"{min(p.celestial_data.position.elevation for p in sequence):.1f}° - {max(p.celestial_data.position.elevation for p in sequence):.1f}°",
                "optimal_shots": len([p for p in sequence if p.celestial_data.position.elevation > 30])
            }
        }


# ===================== DEMO =====================
def demo():
    print("🌙 Astrophotography Session Planner")
    print("=" * 40)

    session = AstroSession(40.7128, -74.0060)
    now = dt.datetime.now()
    lunar_data = session.get_lunar_data(now)

    print("\nCurrent Conditions:")
    print(f"  Position: {lunar_data.position.azimuth:.1f}° az, {lunar_data.position.elevation:.1f}° el")
    print(f"  Phase: {lunar_data.phase:.1%}")
    print(f"  Condition: {lunar_data.condition.value}")

    plan = session.create_shooting_plan(now)
    print("\nRecommended Settings:")
    print(f"  {plan.camera_config}")
    print(f"  Exposure Compensation: {plan.exposure_comp:+.1f} EV")

    sequence = session.generate_sequence(120, 15)
    print("\n2-Hour Tracking Sequence:")
    print(f"  {len(sequence)} shooting positions")
    print(f"  Elevation range: {min(p.celestial_data.position.elevation for p in sequence):.1f}° to {max(p.celestial_data.position.elevation for p in sequence):.1f}°")

    timelapse = TimelapseCalculator.calculate_interval(2.0)
    print("\nTimelapse Settings:")
    print(f"  Interval: {timelapse['interval_seconds']}s")
    print(f"  Storage: {timelapse['storage_gb']}GB")
    print(f"  Battery: {timelapse['battery_hours']}h")


if __name__ == "__main__":
    demo()