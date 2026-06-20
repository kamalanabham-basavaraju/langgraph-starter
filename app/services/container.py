from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings, settings
from app.integrations.enterpro import EnterProClient
from app.integrations.groq import GroqIncidentAnalyzer
from app.integrations.parcel import ParcelClient


@dataclass
class WorkflowServices:
    parcel: ParcelClient
    groq: GroqIncidentAnalyzer
    enterpro: EnterProClient
    settings: Settings


def build_services(config: Settings = settings) -> WorkflowServices:
    return WorkflowServices(
        parcel=ParcelClient(
            config.parcel_base_url,
            config.parcel_search_path,
            config.parcel_api_key,
            config.external_request_timeout,
        ),
        groq=GroqIncidentAnalyzer(config.groq_api_key, config.groq_model),
        enterpro=EnterProClient(
            config.enterpro_url, config.enterpro_api_key, config.external_request_timeout
        ),
        settings=config,
    )
