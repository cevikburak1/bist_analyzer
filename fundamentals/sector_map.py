"""
Sembol -> sektör sınıflandırması.

V1: Buffett skorlamasının sektör-bazlı dallanması için yalnızca kaba bir sınıf
döndürür (BANKA, GYO, SIGORTA, HOLDING, SANAYI, DIGER). Bu sınıflara göre bazı
metrikler kapatılır veya farklı eşik kullanılır.

Strateji:
1) Önce elle bakım haritasına bak (`KNOWN_SECTORS`).
2) Bulunamazsa yfinance `Ticker.info["sector"]/["industry"]` üzerinden tahmin et.
3) Yine bulunamazsa "DIGER" döndür.

Manuel haritayı zamanla genişletmek mümkün; V1 için en yaygın BIST hisselerini
kapsayacak şekilde tutuyoruz.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SectorClass:
    """Sektör sınıfı. `kind` skorlama tarafından kullanılır."""
    kind: str            # BANKA / GYO / SIGORTA / HOLDING / SANAYI / DIGER
    label: str           # gösterim için Türkçe etiket
    source: str = "manual"


_BANKA = SectorClass("BANKA", "Banka", "manual")
_GYO = SectorClass("GYO", "Gayrimenkul Yatırım Ortaklığı", "manual")
_SIGORTA = SectorClass("SIGORTA", "Sigorta", "manual")
_HOLDING = SectorClass("HOLDING", "Holding", "manual")
_SANAYI = SectorClass("SANAYI", "Sanayi / Üretim", "manual")
_DIGER = SectorClass("DIGER", "Diğer", "manual")


KNOWN_SECTORS: dict[str, SectorClass] = {
    # Bankalar
    "AKBNK": _BANKA, "GARAN": _BANKA, "ISCTR": _BANKA, "YKBNK": _BANKA,
    "HALKB": _BANKA, "VAKBN": _BANKA, "TSKB": _BANKA, "ALBRK": _BANKA,
    "QNBFB": _BANKA, "SKBNK": _BANKA, "ICBCT": _BANKA, "DENIZ": _BANKA,
    # Sigortalar
    "AKGRT": _SIGORTA, "ANSGR": _SIGORTA, "RAYSG": _SIGORTA,
    "TURSG": _SIGORTA, "AGESA": _SIGORTA, "ANHYT": _SIGORTA,
    # Holdingler
    "KCHOL": _HOLDING, "SAHOL": _HOLDING, "DOHOL": _HOLDING,
    "TKFEN": _HOLDING, "ALARK": _HOLDING, "GSDHO": _HOLDING,
    "SISE": _HOLDING, "ENKAI": _HOLDING, "EREGL": _SANAYI,
    # GYO'lar
    "ISGYO": _GYO, "EKGYO": _GYO, "OZGYO": _GYO, "DZGYO": _GYO,
    "AKGYO": _GYO, "TRGYO": _GYO, "EGEGY": _GYO, "OZRDN": _GYO,
    "MRGYO": _GYO, "AVGYO": _GYO, "PEGYO": _GYO, "PSGYO": _GYO,
    "RYGYO": _GYO, "SRVGY": _GYO, "VKGYO": _GYO, "KRGYO": _GYO,
}


def _classify_from_yf_info(info: Optional[dict]) -> SectorClass:
    """yfinance info sözlüğünden sektör tahmin et."""
    if not info:
        return _DIGER

    sector = (info.get("sector") or "").lower()
    industry = (info.get("industry") or "").lower()

    blob = f"{sector} {industry}"

    if "bank" in blob:
        return SectorClass(_BANKA.kind, _BANKA.label, source="yfinance")
    if "insurance" in blob:
        return SectorClass(_SIGORTA.kind, _SIGORTA.label, source="yfinance")
    if "real estate" in blob or "reit" in blob:
        return SectorClass(_GYO.kind, _GYO.label, source="yfinance")
    if "holding" in blob or "conglomerate" in blob:
        return SectorClass(_HOLDING.kind, _HOLDING.label, source="yfinance")
    if any(k in blob for k in ("manufactur", "industri", "chemical", "steel", "auto")):
        return SectorClass(_SANAYI.kind, _SANAYI.label, source="yfinance")

    return SectorClass(_DIGER.kind, _DIGER.label, source="yfinance")


def classify_sector(symbol: str, yf_info: Optional[dict] = None) -> SectorClass:
    """Sembol için sektör sınıfı döndürür.

    Önce elle haritaya, sonra yfinance bilgisine, en sonda DIGER'e düşer.
    """
    sym = symbol.upper().replace(".IS", "")
    if sym in KNOWN_SECTORS:
        return KNOWN_SECTORS[sym]
    return _classify_from_yf_info(yf_info)
