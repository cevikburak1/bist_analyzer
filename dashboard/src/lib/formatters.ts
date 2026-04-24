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

export function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "-";
  }

  return new Date(value).toLocaleString("tr-TR", {
    dateStyle: "short",
    timeStyle: "short",
  });
}
