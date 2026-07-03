from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class Bucket(BaseModel):
    label: str
    count: int


class OverviewResponse(BaseModel):
    total: int
    outbound: int
    inbound: int
    delivered: int
    failed: int
    delivery_rate: float
    by_channel: List[Bucket]
    by_direction: List[Bucket]


class ChannelBreakdown(BaseModel):
    channel: str
    total: int
    outbound: int
    inbound: int
    delivered: int
    failed: int
    opened: int
    clicked: int
    read: int
    delivery_rate: float
    open_rate: float
    avg_talk_time: int


class AgentPerformance(BaseModel):
    agent_id: str
    agent_name: str
    total: int
    outbound: int
    inbound: int
    calls: int
    failed: int
    avg_talk_time: int
    avg_response_seconds: int
    by_channel: List[Bucket]


class ResponseTime(BaseModel):
    avg_response_seconds: int
    median_response_seconds: int
    sample_size: int


class TalkTime(BaseModel):
    avg_talk_seconds: int
    total_talk_seconds: int
    calls_with_duration: int


class MissedResponse(BaseModel):
    missed_calls: int
    failed_messages: int
    total_missed: int
    by_channel: List[Bucket]


class ConversionResponse(BaseModel):
    leads_contacted: int
    converted: int
    conversion_rate: float
    revenue: float


class EngagementItem(BaseModel):
    entity_type: str
    entity_id: str
    name: str
    interactions: int
    inbound: int
    outbound: int
    channels: List[str]
    last_at: datetime


class HeatmapPeak(BaseModel):
    weekday: int
    hour: int
    count: int


class HeatmapResponse(BaseModel):
    grid: List[List[int]]
    peak: HeatmapPeak
    total: int
