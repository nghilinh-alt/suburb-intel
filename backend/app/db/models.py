from sqlalchemy import Column, Text, Integer, Float, DateTime, JSON, ForeignKeyConstraint, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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
