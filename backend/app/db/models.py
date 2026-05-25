from sqlalchemy import Column, Text, Integer, Float, DateTime, JSON, ForeignKeyConstraint, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import datetime


class Base(DeclarativeBase):
    pass


class SA2Region(Base):
    __tablename__ = "sa2_regions"
    
    sa2_code = Column(Text, primary_key=True)
    sa2_name = Column(Text, nullable=False)
    state = Column(Text, nullable=False)


class ABSCEntensMetrics(Base):
    __tablename__ = "abs_census_metrics"
    
    sa2_code = Column(Text, ForeignKey("sa2_regions.sa2_code"), nullable=False, primary_key=True)
    year = Column(Integer, nullable=False, primary_key=True)
    population = Column(Integer, nullable=True)
    median_income = Column(Integer, nullable=True)
    median_age = Column(Float, nullable=True)
    renters_pct = Column(Float, nullable=True)
    owners_pct = Column(Float, nullable=True)
    industry_profile = Column(JSON, nullable=True)


class InfrastructureProject(Base):
    __tablename__ = "infrastructure_projects"
    
    project_id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    type = Column(Text, nullable=False)
    value_aud = Column(Integer, nullable=True)
    status = Column(Text, nullable=False)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)


class SA2ProjectLink(Base):
    __tablename__ = "sa2_project_link"
    
    sa2_code = Column(Text, ForeignKey("sa2_regions.sa2_code"), nullable=False, primary_key=True)
    project_id = Column(Text, ForeignKey("infrastructure_projects.project_id"), nullable=False, primary_key=True)
    impact_score = Column(Float, nullable=True)


class SuburbScore(Base):
    __tablename__ = "suburb_scores"
    
    sa2_code = Column(Text, primary_key=True)
    investment_score = Column(Float, nullable=True)
    demographic_score = Column(Float, nullable=True)
    economic_score = Column(Float, nullable=True)
    housing_pressure_score = Column(Float, nullable=True)
    resilience_score = Column(Float, nullable=True)
    gov_investment_score = Column(Float, nullable=True)
    risk_flags = Column(JSON, nullable=True)
    updated_at = Column(DateTime, nullable=True)


class AmenityData(Base):
    """Store OpenStreetMap Overpass API amenity counts for suburb intelligence."""
    
    __tablename__ = "osm_amenities"
    
    suburb_id = Column(Text, primary_key=True, comment="Suburb identifier (name or code)")
    amenity_type = Column(Text, nullable=False, comment="Type of amenity: cafe, gym, hospital, etc.")
    
    count_500m = Column(Integer, nullable=False, default=0, comment="Count within 500m radius")
    count_1km = Column(Integer, nullable=False, default=0, comment="Count within 1km radius")
    count_2km = Column(Integer, nullable=False, default=0, comment="Count within 2km radius")
    
    amenity_density_score = Column(
        Float, 
        nullable=True, 
        comment="Normalized score from amenity counts"
    )
    
    overpass_response = Column(JSON, nullable=True, comment="Full Overpass API response JSON")
    
    last_fetched = Column(DateTime, nullable=False, default=lambda: datetime.utcnow())
    data_source = Column(Text, nullable=False, default="overpass_api")
    fetched_by = Column(Text, nullable=True)
