from __future__ import annotations

import httpx

from app.adapters.ashby import AshbyAdapter
from app.adapters.base import ATSAdapter
from app.adapters.greenhouse import GreenhouseAdapter
from app.adapters.lever import LeverAdapter
from app.adapters.personio import PersonioAdapter
from app.adapters.recruitee import RecruiteeAdapter
from app.adapters.smartrecruiters import SmartRecruitersAdapter
from app.adapters.teamtailor import TeamtailorAdapter
from app.adapters.workable import WorkableAdapter
from app.config import Settings
from app.models.enums import ATSProvider
from app.services.ats_request_manager import ATSRequestManager

_ADAPTERS: dict[str, type[ATSAdapter]] = {
    ATSProvider.GREENHOUSE.value: GreenhouseAdapter,
    ATSProvider.LEVER.value: LeverAdapter,
    ATSProvider.ASHBY.value: AshbyAdapter,
    ATSProvider.SMARTRECRUITERS.value: SmartRecruitersAdapter,
    ATSProvider.RECRUITEE.value: RecruiteeAdapter,
    ATSProvider.WORKABLE.value: WorkableAdapter,
    ATSProvider.PERSONIO.value: PersonioAdapter,
    ATSProvider.TEAMTAILOR.value: TeamtailorAdapter,
}


def build_adapter(
    provider: str,
    client: httpx.AsyncClient,
    settings: Settings,
    request_manager: ATSRequestManager | None = None,
) -> ATSAdapter:
    try:
        adapter_class = _ADAPTERS[provider]
    except KeyError as exc:
        raise ValueError(f"Unsupported ATS provider: {provider}") from exc
    return adapter_class(client, settings, request_manager)
