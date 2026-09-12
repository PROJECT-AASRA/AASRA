"""
SQLAlchemy ORM Models for Project AASRA
Defines relational schemas for Households, Relocation Centers (Shelters),
and Cached Hazard Assessments using SQLite (disaster.db).
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    func
)
from sqlalchemy.orm import relationship

from app.database import Base


class HouseholdModel(Base):
    """
    SQLAlchemy model representing a surveyed or ingested household.
    Stores demographic data, vulnerability metrics, and computed hazard/risk scores.
    """
    __tablename__ = "households"

    # Primary identification
    household_id = Column(String, primary_key=True, index=True)
    state = Column(String, nullable=False, index=True)
    district = Column(String, nullable=False, index=True)
    village = Column(String, nullable=False, index=True)

    # Geospatial coordinates
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # Demographics
    population = Column(Integer, nullable=False, default=1)
    children = Column(Integer, nullable=False, default=0)
    elderly = Column(Integer, nullable=False, default=0)
    disabled = Column(Integer, nullable=False, default=0)
    low_income = Column(Boolean, nullable=False, default=False)

    # Disaster and hazard exposure
    hazard_exposure = Column(Float, nullable=True, default=0.0)
    previous_disaster_exposure = Column(Float, nullable=False, default=0.0)

    # Evaluated Vulnerability and Risk scores
    vulnerability_score = Column(Float, nullable=True)
    vulnerability_level = Column(String, nullable=True)
    priority_level = Column(String, nullable=True)
    risk_score = Column(Float, nullable=True)
    risk_level = Column(String, nullable=True)

    # Cached geospatial attributes
    in_historical_flood_zone = Column(Boolean, nullable=True, default=False)
    distance_to_nearest_river_km = Column(Float, nullable=True)
    distance_to_nearest_hospital_km = Column(Float, nullable=True)
    nearest_hospital = Column(String, nullable=True)
    flood_exposure = Column(Float, nullable=True)
    river_exposure = Column(Float, nullable=True)
    landslide_exposure = Column(Float, nullable=True)
    rainfall_exposure = Column(Float, nullable=True)
    hazard_tier = Column(String, nullable=True)
    elevation_meters = Column(Float, nullable=True)
    slope_degrees = Column(Float, nullable=True)

    # Metadata timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    assessments = relationship(
        "HazardAssessmentModel",
        back_populates="household",
        cascade="all, delete-orphan"
    )

    def to_dict(self):
        """Converts the ORM object into a dictionary matching HouseholdResponse."""
        return {
            "household_id": self.household_id,
            "state": self.state,
            "district": self.district,
            "village": self.village,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "population": self.population,
            "children": self.children,
            "elderly": self.elderly,
            "disabled": self.disabled,
            "low_income": self.low_income,
            "hazard_exposure": self.hazard_exposure,
            "previous_disaster_exposure": bool(self.previous_disaster_exposure) if self.previous_disaster_exposure in (0.0, 1.0) else self.previous_disaster_exposure,
            "vulnerability_score": self.vulnerability_score,
            "vulnerability_level": self.vulnerability_level,
            "priority_level": self.priority_level,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "in_historical_flood_zone": self.in_historical_flood_zone,
            "distance_to_nearest_river_km": self.distance_to_nearest_river_km,
            "distance_to_nearest_hospital_km": self.distance_to_nearest_hospital_km,
            "nearest_hospital": self.nearest_hospital,
            "flood_exposure": self.flood_exposure,
            "river_exposure": self.river_exposure,
            "landslide_exposure": self.landslide_exposure,
            "rainfall_exposure": self.rainfall_exposure,
            "hazard_tier": self.hazard_tier,
            "elevation_meters": self.elevation_meters,
            "slope_degrees": self.slope_degrees,
        }


class RelocationCenterModel(Base):
    """
    SQLAlchemy model representing an emergency shelter or relocation facility.
    Stores operational capacity, accessibility flags, and essential relief resources.
    """
    __tablename__ = "relocation_centers"

    # Primary identification
    center_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    state = Column(String, nullable=False, index=True)
    district = Column(String, nullable=False, index=True)
    village = Column(String, nullable=False, index=True)

    # Geospatial coordinates
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # Capacity management
    total_capacity = Column(Integer, nullable=False)
    current_occupancy = Column(Integer, nullable=False, default=0)

    # Amenities and accessibility
    medical_support = Column(Boolean, nullable=False, default=True)
    food_available = Column(Boolean, nullable=False, default=True)
    water_available = Column(Boolean, nullable=False, default=True)
    sanitation_available = Column(Boolean, nullable=False, default=True)
    accessible_for_disabled = Column(Boolean, nullable=False, default=True)
    active = Column(Boolean, nullable=False, default=True)

    # Metadata timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        """Converts the ORM object into a dictionary matching RelocationCenterResponse."""
        available = max(0, self.total_capacity - self.current_occupancy) if self.active else 0
        return {
            "center_id": self.center_id,
            "name": self.name,
            "state": self.state,
            "district": self.district,
            "village": self.village,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "total_capacity": self.total_capacity,
            "current_occupancy": self.current_occupancy,
            "available_capacity": available,
            "medical_support": self.medical_support,
            "food_available": self.food_available,
            "water_available": self.water_available,
            "sanitation_available": self.sanitation_available,
            "accessible_for_disabled": self.accessible_for_disabled,
            "active": self.active,
        }


class HazardAssessmentModel(Base):
    """
    SQLAlchemy model storing cached hazard evaluation and decision assessments.
    Prevents redundant heavy geospatial computations for frequently assessed locations.
    """
    __tablename__ = "hazard_assessments"

    assessment_id = Column(String, primary_key=True, index=True)
    household_id = Column(String, ForeignKey("households.household_id", ondelete="SET NULL"), nullable=True, index=True)

    state = Column(String, nullable=False, index=True)
    district = Column(String, nullable=False, index=True)
    village = Column(String, nullable=True)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # Environmental indicators
    elevation_meters = Column(Float, nullable=True)
    slope_degrees = Column(Float, nullable=True)
    landslide_exposure = Column(Float, nullable=True)
    flood_exposure = Column(Float, nullable=True)
    river_exposure = Column(Float, nullable=True)
    rainfall_exposure = Column(Float, nullable=True)
    distance_to_nearest_river_km = Column(Float, nullable=True)
    distance_to_nearest_hospital_km = Column(Float, nullable=True)
    nearest_hospital_name = Column(String, nullable=True)

    # Composite scores
    composite_hazard_exposure = Column(Float, nullable=False)
    hazard_tier = Column(String, nullable=True)
    vulnerability_score = Column(Float, nullable=True)
    vulnerability_level = Column(String, nullable=True)
    risk_score = Column(Float, nullable=True)
    risk_level = Column(String, nullable=True)
    priority_level = Column(String, nullable=True)

    # Relocation assignment
    recommended_shelter_id = Column(String, nullable=True)
    recommended_shelter_name = Column(String, nullable=True)
    shelter_distance_km = Column(Float, nullable=True)

    assessed_at = Column(DateTime, server_default=func.now())

    # Relationship to household
    household = relationship("HouseholdModel", back_populates="assessments")

    def to_dict(self):
        """Converts assessment ORM record into dictionary format."""
        return {
            "assessment_id": self.assessment_id,
            "household_id": self.household_id,
            "state": self.state,
            "district": self.district,
            "village": self.village,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "elevation_meters": self.elevation_meters,
            "slope_degrees": self.slope_degrees,
            "landslide_exposure": self.landslide_exposure,
            "flood_exposure": self.flood_exposure,
            "river_exposure": self.river_exposure,
            "rainfall_exposure": self.rainfall_exposure,
            "distance_to_nearest_river_km": self.distance_to_nearest_river_km,
            "distance_to_nearest_hospital_km": self.distance_to_nearest_hospital_km,
            "nearest_hospital_name": self.nearest_hospital_name,
            "composite_hazard_exposure": self.composite_hazard_exposure,
            "hazard_tier": self.hazard_tier,
            "vulnerability_score": self.vulnerability_score,
            "vulnerability_level": self.vulnerability_level,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "priority_level": self.priority_level,
            "recommended_shelter_id": self.recommended_shelter_id,
            "recommended_shelter_name": self.recommended_shelter_name,
            "shelter_distance_km": self.shelter_distance_km,
            "assessed_at": self.assessed_at.isoformat() if self.assessed_at else None,
        }
