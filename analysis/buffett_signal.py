"""
Buffett etiketleme + tez bozulma uyarıları + açıklanabilir karar.

Çıktı "AL/SAT" değil; aşağıdaki etiketlerden biri:
- HARIKA_IS_UCUZ        ("Harika İş - Adil/Ucuz Fiyat")
- HARIKA_IS_PAHALI      ("Harika İş - Pahalı - Bekle")
- IYI_IS_UCUZ           ("İyi İş - Ucuz")
- GECER                 ("Geçer - Dikkat")
- PAS_GEC               ("Pas Geç")
- YETERSIZ_VERI         ("Yetersiz Veri - Değerlendirilemez")

Tez Bozulma Uyarıları:
- ROE son yılda 5y ortalamanın yarısı altına düştü
- Borç/Özsermaye 1 yılda 2x oldu
- Net kâr son yıl negatif (zarar)
- FCF son yıl negatif

Açıklanabilirlik:
- classification_reason: Tek cümlelik etiket gerekçesi
- classification_factors: Karara giden bireysel kuralların pass/fail kayıtları
- horizon_guidance: Kısa / orta / uzun vade için ayrı tutma önerisi
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from analysis.buffett_score import BuffettScoreBreakdown
from analysis.intrinsic_value import IntrinsicValueResult
from fundamentals.downloader import FundamentalsBundle


# ── Etiket sabitleri ────────────────────────────────────────────────────────


LABELS = {
    "HARIKA_IS_UCUZ":   ("Harika İş - Adil/Ucuz Fiyat", "emerald"),
    "HARIKA_IS_PAHALI": ("Harika İş - Pahalı - Bekle",  "amber"),
    "IYI_IS_UCUZ":      ("İyi İş - Ucuz",                "lime"),
    "GECER":            ("Geçer - Dikkat",               "slate"),
    "PAS_GEC":          ("Pas Geç",                      "rose"),
    "YETERSIZ_VERI":    ("Yetersiz Veri - Değerlendirilemez", "sky"),
}


# Kısa/orta/uzun vade pozitiflik etiketleri (UI renklendirmesi için)
HORIZON_VERDICT_COLORS = {
    "GUCLU_AL":   "emerald",
    "AL":         "lime",
    "BIRIKTIR":   "teal",
    "TUT":        "sky",
    "IZLE":       "slate",
    "BEKLE":      "amber",
    "KACIN":      "rose",
    "DEGERLENDIRILEMEZ": "zinc",
}


@dataclass
class HorizonVerdict:
    """Tek bir vade (kısa/orta/uzun) için karar + açıklama."""
    verdict: str            # GUCLU_AL / AL / BIRIKTIR / TUT / IZLE / BEKLE / KACIN / DEGERLENDIRILEMEZ
    label: str              # Türkçe okunur etiket
    color: str              # UI rengi
    reason: str             # Tek cümlelik açıklama
    factors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "label": self.label,
            "color": self.color,
            "reason": self.reason,
            "factors": list(self.factors),
        }


@dataclass
class HorizonGuidance:
    """Kısa / orta / uzun vade için bütünsel öneri seti."""
    short: HorizonVerdict
    medium: HorizonVerdict
    long: HorizonVerdict
    overall: str = ""       # En etkili vadenin tek satırlık özeti

    def as_dict(self) -> dict:
        return {
            "short": self.short.as_dict(),
            "medium": self.medium.as_dict(),
            "long": self.long.as_dict(),
            "overall": self.overall,
        }


@dataclass
class BuffettSignal:
    symbol: str
    label_key: str
    label: str
    color: str
    total_score: float
    margin_of_safety: Optional[float]
    holding_recommendation: str
    warnings: list[str] = field(default_factory=list)
    classification_reason: str = ""
    classification_factors: list[dict] = field(default_factory=list)
    horizon_guidance: Optional[HorizonGuidance] = None

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "label_key": self.label_key,
            "label": self.label,
            "color": self.color,
            "total_score": round(self.total_score, 2),
            "margin_of_safety": (
                round(self.margin_of_safety, 4) if self.margin_of_safety is not None else None
            ),
            "holding_recommendation": self.holding_recommendation,
            "warnings": list(self.warnings),
            "classification_reason": self.classification_reason,
            "classification_factors": list(self.classification_factors),
            "horizon_guidance": (
                self.horizon_guidance.as_dict() if self.horizon_guidance else None
            ),
        }


# ── Etiket kararı + açıklama ────────────────────────────────────────────────


def _factor(rule: str, status: str, detail: str) -> dict:
    """Karar gerekçesi için yapılandırılmış kayıt."""
    return {"rule": rule, "status": status, "detail": detail}


def _classify_with_reason(
    score: BuffettScoreBreakdown,
    intrinsic: IntrinsicValueResult,
) -> tuple[str, str, list[dict]]:
    """Skor + intrinsic'ten etiket key + tek cümle gerekçe + faktör listesi üretir."""
    factors: list[dict] = []
    mos = intrinsic.margin_of_safety

    factors.append(_factor(
        "Veri Kalitesi",
        "OK" if score.data_quality_pct >= 50 else "FAIL",
        f"Mevcut puanlanabilir veri: %{score.data_quality_pct:.0f} "
        f"(eşik %50)",
    ))
    factors.append(_factor(
        "Asgari Veri",
        "OK" if score.has_minimum_data else "FAIL",
        "Net kâr ve özsermaye verisi mevcut" if score.has_minimum_data
        else "Net kâr veya özsermaye verisi eksik",
    ))

    # Veri kalitesi yetersiz
    if score.data_quality_pct < 50 or not score.has_minimum_data:
        reason = (
            f"Veri kalitesi yetersiz (%{score.data_quality_pct:.0f}) - "
            "Buffett skoru güvenilir biçimde hesaplanamadı"
        )
        return "YETERSIZ_VERI", reason, factors

    total = score.total_score
    factors.append(_factor(
        "Toplam Skor",
        "OK" if total >= 60 else "FAIL",
        f"{total:.0f}/100 (60 = Geçer eşiği, 75 = Harika eşiği)",
    ))

    has_mos = mos is not None and mos >= 0.30
    if mos is None:
        mos_status = "NA"
        mos_text = (
            "Güvenlik marjı hesaplanamadı"
            + (f" — {intrinsic.reason}" if intrinsic.reason else "")
        )
    elif has_mos:
        mos_status = "OK"
        mos_text = f"Güvenlik marjı %{mos*100:.1f} (≥%30)"
    else:
        mos_status = "FAIL"
        mos_text = f"Güvenlik marjı %{mos*100:.1f} (<%30)"
    factors.append(_factor("Güvenlik Marjı (MoS)", mos_status, mos_text))

    if total >= 75 and has_mos:
        reason = (
            f"Skor {total:.0f}/100 ≥ 75 ve güvenlik marjı %{mos*100:.0f} ≥ %30 → "
            "harika iş, indirimli fiyat"
        )
        return "HARIKA_IS_UCUZ", reason, factors

    if total >= 75:
        if mos is None:
            mos_part = "ancak güvenlik marjı hesaplanamadı"
        else:
            mos_part = f"ancak güvenlik marjı %{mos*100:.0f} (<%30)"
        reason = f"Skor {total:.0f}/100 ≥ 75 → harika iş, {mos_part}; pahalı"
        return "HARIKA_IS_PAHALI", reason, factors

    if 60 <= total < 75 and has_mos:
        reason = (
            f"Skor {total:.0f}/100 (60-75 bandı) ve güvenlik marjı %{mos*100:.0f} ≥ %30 → "
            "iyi iş, indirimli fiyat"
        )
        return "IYI_IS_UCUZ", reason, factors

    if 60 <= total < 75:
        if mos is None:
            mos_part = "güvenlik marjı hesaplanamadı"
        else:
            mos_part = f"güvenlik marjı %{mos*100:.0f} (<%30)"
        reason = f"Skor {total:.0f}/100 (60-75 bandı) ama {mos_part} → geçer ama dikkat"
        return "GECER", reason, factors

    reason = (
        f"Skor {total:.0f}/100 < 60 → Buffett kalite eşiklerini karşılamıyor; "
        "iş kalitesi, mali sağlık veya değerleme yetersiz"
    )
    return "PAS_GEC", reason, factors


def _holding_recommendation(label_key: str) -> str:
    """Buffett zihniyetinde tutma süresi önerisi."""
    return {
        "HARIKA_IS_UCUZ":   "Önerilen Tutma: 5-10+ yıl (yüksek inanç)",
        "HARIKA_IS_PAHALI": "Şirket harika; daha düşük fiyatı bekle",
        "IYI_IS_UCUZ":      "Önerilen Tutma: 3-5+ yıl",
        "GECER":            "Daha iyi fırsat çıkana kadar gözlem",
        "PAS_GEC":          "Bu şirkete yatırım önerilmez",
        "YETERSIZ_VERI":    "Manuel inceleme gerek",
    }[label_key]


# ── Vade bazlı öneri (kısa / orta / uzun) ───────────────────────────────────


def _verdict(verdict: str, label: str, reason: str, factors: list[str]) -> HorizonVerdict:
    return HorizonVerdict(
        verdict=verdict,
        label=label,
        color=HORIZON_VERDICT_COLORS.get(verdict, "slate"),
        reason=reason,
        factors=factors,
    )


def _build_horizon_guidance(
    label_key: str,
    score: BuffettScoreBreakdown,
    intrinsic: IntrinsicValueResult,
    warnings: list[str],
) -> HorizonGuidance:
    """Buffett çıktısını kısa/orta/uzun vade kararına dönüştürür.

    Buffett doğası gereği uzun vadelidir: kısa vadede "BEKLE/IZLE" baskındır,
    asıl ağırlık uzun vade kararındadır.
    """
    mos = intrinsic.margin_of_safety
    total = score.total_score
    has_warnings = len(warnings) > 0

    mos_text = f"%{mos*100:.0f}" if mos is not None else "hesaplanamadı"
    warn_text = f"{len(warnings)} tez-bozulma uyarısı" if has_warnings else "tez-bozulma uyarısı yok"

    base_factors = [
        f"Toplam skor {total:.0f}/100",
        f"Güvenlik marjı {mos_text}",
        f"Veri kalitesi %{score.data_quality_pct:.0f}",
        warn_text,
    ]

    if label_key == "YETERSIZ_VERI":
        verd = _verdict(
            "DEGERLENDIRILEMEZ",
            "Değerlendirilemez",
            "Temel veri yetersiz - Buffett çerçevesinde karar verilemez",
            base_factors,
        )
        return HorizonGuidance(
            short=verd, medium=verd, long=verd,
            overall="Temel veri yetersiz; manuel inceleme şart.",
        )

    # ── KISA VADE (1-3 ay) ──────────────────────────────────────────────
    # Buffett analizi kısa vadeli fiyat hareketini öngörmez. Bu yüzden
    # kararlar daima "izle/bekle" odaklıdır; sadece tehlikede aktif KAÇIN deriz.
    if has_warnings:
        short = _verdict(
            "BEKLE",
            "Kısa Vade: Tetikte Bekle",
            "Tez bozulma uyarıları var - kısa vadede yeni pozisyon tehlikeli",
            base_factors,
        )
    elif label_key == "PAS_GEC":
        short = _verdict(
            "KACIN",
            "Kısa Vade: Yeni Pozisyon Açma",
            "Şirket Buffett kalite eşiklerini karşılamıyor; kısa vadede de cazip değil",
            base_factors,
        )
    elif label_key in ("HARIKA_IS_UCUZ", "IYI_IS_UCUZ"):
        short = _verdict(
            "IZLE",
            "Kısa Vade: İzle / Kademe Başlat",
            "Temelde ucuz; kısa vadeli giriş için teknik tetik bekle (kademeli)",
            base_factors,
        )
    elif label_key == "HARIKA_IS_PAHALI":
        short = _verdict(
            "BEKLE",
            "Kısa Vade: Geri Çekilme Bekle",
            "İyi iş ama pahalı; kısa vadede MoS oluşması için bekle",
            base_factors,
        )
    else:  # GECER
        short = _verdict(
            "IZLE",
            "Kısa Vade: Gözlemde Tut",
            "Skor sınırda; kısa vadeli yeni pozisyon için aceleci olma",
            base_factors,
        )

    # ── ORTA VADE (6-18 ay) ────────────────────────────────────────────
    if has_warnings and label_key in ("PAS_GEC", "GECER"):
        medium = _verdict(
            "KACIN",
            "Orta Vade: Pozisyon Hafiflet",
            "Düşük skor ve aktif tez bozulma uyarıları orta vadede risk",
            base_factors,
        )
    elif label_key == "PAS_GEC":
        medium = _verdict(
            "KACIN",
            "Orta Vade: Tutma",
            "Buffett çerçevesinde orta vadede de yatırım için yeterli kalite yok",
            base_factors,
        )
    elif label_key == "HARIKA_IS_UCUZ":
        medium = _verdict(
            "AL",
            "Orta Vade: Kademeli Topla",
            "Kalite + indirimli fiyat orta vadede güçlü pozisyon kurmaya elverişli",
            base_factors,
        )
    elif label_key == "IYI_IS_UCUZ":
        medium = _verdict(
            "BIRIKTIR",
            "Orta Vade: Biriktir",
            "İyi temeller + ucuz fiyat - orta vadede kademeli birikim mantıklı",
            base_factors,
        )
    elif label_key == "HARIKA_IS_PAHALI":
        medium = _verdict(
            "TUT",
            "Orta Vade: Mevcudu Tut, Yeni Alma",
            "Kalite yüksek ama orta vadede MoS yetersiz; yeni giriş için bekle",
            base_factors,
        )
    else:  # GECER
        medium = _verdict(
            "IZLE",
            "Orta Vade: Sınırda - İzle",
            "Skor 60-75 bandında ve MoS yetersiz; daha iyi fırsatları gözle",
            base_factors,
        )

    # ── UZUN VADE (3+ yıl, çekirdek Buffett perspektifi) ────────────────
    if label_key == "HARIKA_IS_UCUZ":
        long = _verdict(
            "GUCLU_AL",
            "Uzun Vade: Çekirdek Pozisyon (5-10+ yıl)",
            "Harika iş + indirimli fiyat - klasik Buffett çekirdek alımı",
            base_factors,
        )
    elif label_key == "HARIKA_IS_PAHALI":
        long = _verdict(
            "TUT",
            "Uzun Vade: Mevcudu Tut, Geri Çekilmede Ekle",
            "Kalite uzun vadede çekici; fiyat normalleşince ekle",
            base_factors,
        )
    elif label_key == "IYI_IS_UCUZ":
        long = _verdict(
            "AL",
            "Uzun Vade: Tut (3-5+ yıl)",
            "Kalite biraz daha düşük olsa da indirimli fiyat uzun vadeyi destekler",
            base_factors,
        )
    elif label_key == "GECER":
        long = _verdict(
            "IZLE",
            "Uzun Vade: Koşullu - Daha İyi Fırsat Bekle",
            "Skor sınırda; uzun vadeli kalite eşiği tam karşılanmıyor",
            base_factors,
        )
    else:  # PAS_GEC
        long = _verdict(
            "KACIN",
            "Uzun Vade: Portföye Alma",
            "Buffett kalite eşiğini karşılamıyor - uzun vadede de elenmeli",
            base_factors,
        )

    overall = (
        f"Uzun vade vurgusu: {long.label}. "
        f"Orta vade: {medium.label}. "
        f"Kısa vade: {short.label}."
    )
    return HorizonGuidance(short=short, medium=medium, long=long, overall=overall)


# ── Tez bozulma uyarıları ───────────────────────────────────────────────────


def _detect_warnings(
    bundle: FundamentalsBundle,
    score: BuffettScoreBreakdown,
) -> list[str]:
    warnings: list[str] = []

    income = bundle.income_annual
    balance = bundle.balance_annual

    roes: list[float] = []
    for inc, bal in zip(income[-5:], balance[-5:]):
        ni = inc.get("net_income")
        eq = bal.get("total_equity")
        if ni is not None and eq is not None and eq != 0:
            roes.append(ni / eq)
    if len(roes) >= 3:
        avg = sum(roes[:-1]) / len(roes[:-1])
        last = roes[-1]
        if avg > 0 and last < avg * 0.5:
            warnings.append(
                f"ROE son yılda %{last*100:.1f}, önceki ortalama %{avg*100:.1f} (sert düşüş)"
            )

    if len(balance) >= 2:
        prev_bal = balance[-2]
        last_bal = balance[-1]
        prev_de = (
            (prev_bal.get("total_debt") or 0) / prev_bal["total_equity"]
            if prev_bal.get("total_equity") else None
        )
        last_de = (
            (last_bal.get("total_debt") or 0) / last_bal["total_equity"]
            if last_bal.get("total_equity") else None
        )
        if prev_de is not None and last_de is not None and prev_de > 0 and last_de >= prev_de * 2:
            warnings.append(
                f"Borç/Özsermaye 1 yılda {prev_de:.2f} -> {last_de:.2f} (2 katından fazla arttı)"
            )

    if income:
        last_ni = income[-1].get("net_income")
        if last_ni is not None and last_ni < 0:
            warnings.append("Şirket son yıl zarar açıkladı")

    cf = bundle.cashflow_annual
    if cf:
        last_fcf = cf[-1].get("free_cash_flow")
        if last_fcf is not None and last_fcf < 0:
            warnings.append("Son yıl serbest nakit akışı negatif")

    if 50 <= score.data_quality_pct < 70:
        warnings.append(
            f"Veri kalitesi sınırlı (%{score.data_quality_pct:.0f}); skoru ihtiyatlı yorumla"
        )

    return warnings


# ── Public ───────────────────────────────────────────────────────────────────


def build_buffett_signal(
    bundle: FundamentalsBundle,
    score: BuffettScoreBreakdown,
    intrinsic: IntrinsicValueResult,
) -> BuffettSignal:
    label_key, classification_reason, factors = _classify_with_reason(score, intrinsic)
    label, color = LABELS[label_key]
    warnings = _detect_warnings(bundle, score)
    horizon = _build_horizon_guidance(label_key, score, intrinsic, warnings)

    return BuffettSignal(
        symbol=bundle.symbol,
        label_key=label_key,
        label=label,
        color=color,
        total_score=score.total_score,
        margin_of_safety=intrinsic.margin_of_safety,
        holding_recommendation=_holding_recommendation(label_key),
        warnings=warnings,
        classification_reason=classification_reason,
        classification_factors=factors,
        horizon_guidance=horizon,
    )
