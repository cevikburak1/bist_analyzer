const ISTANBUL_TZ = "Europe/Istanbul";
const MARKET_OPEN_MINUTES = 10 * 60;
const MARKET_CLOSE_MINUTES = 18 * 60 + 10;

function getIstanbulNow() {
  const formatter = new Intl.DateTimeFormat("en-GB", {
    timeZone: ISTANBUL_TZ,
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  const parts = formatter.formatToParts(new Date());
  const weekday = parts.find((part) => part.type === "weekday")?.value ?? "Mon";
  const hour = Number(parts.find((part) => part.type === "hour")?.value ?? 0);
  const minute = Number(parts.find((part) => part.type === "minute")?.value ?? 0);

  return { weekday, totalMinutes: hour * 60 + minute };
}

export function isMarketOpen() {
  const { weekday, totalMinutes } = getIstanbulNow();
  const isWeekday = !["Sat", "Sun"].includes(weekday);
  return isWeekday && totalMinutes >= MARKET_OPEN_MINUTES && totalMinutes <= MARKET_CLOSE_MINUTES;
}

export function isSnapshotStale(generatedAt: string | undefined, refreshIntervalMinutes: number) {
  if (!generatedAt) {
    return true;
  }

  const generatedTime = new Date(generatedAt).getTime();
  const maxAge = refreshIntervalMinutes * 60 * 1000;
  return Date.now() - generatedTime >= maxAge;
}
