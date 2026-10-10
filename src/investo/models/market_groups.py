"""Fixed observation groups for the flat public radar; no provider-controlled labels."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from investo.models.sector import SectorTicker


class AdditionalAssetTicker(StrEnum):
    SMH = "SMH"
    XSW = "XSW"
    MAGS = "MAGS"
    AAPL = "AAPL"
    DELL = "DELL"
    HPQ = "HPQ"
    HPE = "HPE"
    CSCO = "CSCO"
    ANET = "ANET"
    NTAP = "NTAP"
    GLW = "GLW"


ADDITIONAL_REQUEST_TICKERS: Final = tuple(AdditionalAssetTicker)
HARDWARE_MEMBERS: Final = tuple(AdditionalAssetTicker)[3:]
FUND_GROUP_ASSETS: Final = tuple(AdditionalAssetTicker)[:3]
PublicAssetTicker = SectorTicker | AdditionalAssetTicker


class MarketGroupId(StrEnum):
    XLC = "XLC"
    XLY = "XLY"
    XLP = "XLP"
    XLE = "XLE"
    XLF = "XLF"
    XLV = "XLV"
    XLI = "XLI"
    XLB = "XLB"
    XLRE = "XLRE"
    XLU = "XLU"
    SEMICONDUCTORS = "semiconductors"
    SOFTWARE_SERVICES = "software-services"
    HARDWARE = "hardware"
    BIG_TECH = "big-tech"


class GroupKind(StrEnum):
    INDUSTRY = "industry"
    THEME = "theme"
    REPRESENTATIVE = "representative_basket"


class GroupCategory(StrEnum):
    TECHNOLOGY = "technology"
    CONSUMER = "consumer"
    FINANCIAL = "financial"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class MarketGroupDefinition:
    group_id: MarketGroupId
    name: str
    category: GroupCategory
    kind: GroupKind
    members: tuple[PublicAssetTicker, ...]
    scope: str


def _sector_definition(
    ticker: SectorTicker, name: str, category: GroupCategory = GroupCategory.OTHER
) -> MarketGroupDefinition:
    return MarketGroupDefinition(
        MarketGroupId(ticker.value),
        name,
        category,
        GroupKind.INDUSTRY,
        (ticker,),
        "S&P 500 섹터 ETF 프록시",
    )


GROUP_DEFINITIONS: Final = (
    _sector_definition(SectorTicker.XLC, "커뮤니케이션 서비스"),
    _sector_definition(SectorTicker.XLY, "경기소비재", GroupCategory.CONSUMER),
    _sector_definition(SectorTicker.XLP, "필수소비재", GroupCategory.CONSUMER),
    _sector_definition(SectorTicker.XLE, "에너지"),
    _sector_definition(SectorTicker.XLF, "금융", GroupCategory.FINANCIAL),
    _sector_definition(SectorTicker.XLV, "헬스케어"),
    _sector_definition(SectorTicker.XLI, "산업재"),
    _sector_definition(SectorTicker.XLB, "소재"),
    _sector_definition(SectorTicker.XLRE, "부동산", GroupCategory.FINANCIAL),
    _sector_definition(SectorTicker.XLU, "유틸리티"),
    MarketGroupDefinition(
        MarketGroupId.SEMICONDUCTORS,
        "반도체·장비",
        GroupCategory.TECHNOLOGY,
        GroupKind.INDUSTRY,
        (AdditionalAssetTicker.SMH,),
        "미국 상장 반도체·장비 ETF · 해외 기업 포함",
    ),
    MarketGroupDefinition(
        MarketGroupId.SOFTWARE_SERVICES,
        "소프트웨어·IT서비스",
        GroupCategory.TECHNOLOGY,
        GroupKind.INDUSTRY,
        (AdditionalAssetTicker.XSW,),
        "미국 전 규모 소프트웨어·서비스 ETF · 일부 인접 업종 포함",
    ),
    MarketGroupDefinition(
        MarketGroupId.HARDWARE,
        "하드웨어·장비",
        GroupCategory.TECHNOLOGY,
        GroupKind.REPRESENTATIVE,
        HARDWARE_MEMBERS,
        "대표 8종목 · 일별 동일비중 가격지수",
    ),
    MarketGroupDefinition(
        MarketGroupId.BIG_TECH,
        "빅테크(M7)",
        GroupCategory.TECHNOLOGY,
        GroupKind.THEME,
        (AdditionalAssetTicker.MAGS,),
        "M7 동일비중 노출 ETF · 다른 그룹과 종목 중복",
    ),
)
MARKET_GROUP_IDS: Final = tuple(definition.group_id for definition in GROUP_DEFINITIONS)
GROUP_BY_ID: Final = {definition.group_id: definition for definition in GROUP_DEFINITIONS}


def expected_asset_type(ticker: PublicAssetTicker) -> str:
    return "EQUITY" if ticker in HARDWARE_MEMBERS else "ETF"
