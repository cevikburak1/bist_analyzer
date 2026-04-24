export function formatPrice(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }

  if (Math.abs(value) >= 1000) {
    return new Intl.NumberFormat("tr-TR", {
      maximumFractionDigits: 0,
    }).format(value);
  }

  return new Intl.NumberFormat("tr-TR", {
    minimumFractionDigits: value >= 10 ? 2 : 3,
    maximumFractionDigits: value >= 10 ? 2 : 3,
  }).format(value);
}

export function formatCompactNumber(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }

  return new Intl.NumberFormat("tr-TR", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

export function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }

  return `%${value.toFixed(2)}`;
}

/**
 * Oranı (0-1 ölçekli) yüzde olarak biçimlendirir.
 * |ratio| > 5 (yani %500'den büyük) durumunda gösterimi "Anomali" diye işaretler.
 * Bu sayede DCF/MoS hesaplamasında oluşabilecek -28191.3% gibi yanıltıcı
 * değerler kullanıcıya saçma bir sayı yerine anlamlı bir uyarı olarak görünür.
 */
export function formatRatioPercent(
  value: number | null | undefined,
  options: { anomalyThreshold?: number; fractionDigits?: number } = {}
) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  const threshold = options.anomalyThreshold ?? 5;
  const digits = options.fractionDigits ?? 1;

  if (Math.abs(value) > threshold) {
    return "Anomali";
  }
  return `${(value * 100).toFixed(digits)}%`;
}

/**
 * Oran (0-1) için kısa gösterim ile birlikte anomali ipucu döndürür.
 */
export function describeRatioPercent(value: number | null | undefined): {
  label: string;
  isAnomaly: boolean;
} {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return { label: "-", isAnomaly: false };
  }
  if (Math.abs(value) > 5) {
    return { label: "Veri Anomalisi", isAnomaly: true };
  }
  return { label: `${(value * 100).toFixed(1)}%`, isAnomaly: false };
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "-";
  }

  return new Date(value).toLocaleString("tr-TR", {
    dateStyle: "short",
    timeStyle: "short",
  });
}
