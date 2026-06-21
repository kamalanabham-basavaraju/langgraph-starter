from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings, settings
from app.integrations.enterpro import EnterProClient
from app.integrations.groq import GroqIncidentAnalyzer
from app.integrations.parcle import ParcleClient


@dataclass
class WorkflowServices:
    parcle: ParcleClient
    groq: GroqIncidentAnalyzer
    enterpro: EnterProClient
    settings: Settings


def build_services(config: Settings = settings) -> WorkflowServices:
    return WorkflowServices(
        parcle=ParcleClient(
            config.parcle_api_key,
            config.parcle_user_id,
        ),
        groq=GroqIncidentAnalyzer(config.groq_api_key, config.groq_model),
        enterpro=EnterProClient(
            config.enterpro_url,
            config.enterpro_api_key,
            config.enterpro_command,
            config.enterpro_workspace_id,
            config.external_request_timeout,
        ),
        settings=config,
    )
