import type { CityScanRecord, ToxicityLevel } from './types';

const barcelonaHotspots = [
  { name: 'eixample', latitude: 41.3912, longitude: 2.1649 },
  { name: 'gracia', latitude: 41.4024, longitude: 2.1587 },
  { name: 'sant-antoni', latitude: 41.3777, longitude: 2.1617 },
  { name: 'raval', latitude: 41.3816, longitude: 2.1701 },
  { name: 'barceloneta', latitude: 41.3801, longitude: 2.1899 },
  { name: 'poblenou', latitude: 41.4007, longitude: 2.2037 },
  { name: 'sants', latitude: 41.3765, longitude: 2.1372 },
  { name: 'les-corts', latitude: 41.3869, longitude: 2.1327 }
];

function randomBetween(min: number, max: number): number {
  return min + Math.random() * (max - min);
}

function jitter(value: number, spread: number): number {
  return value + randomBetween(-spread, spread);
}

function round(value: number, decimals = 1): number {
  const factor = 10 ** decimals;
  return Math.round(value * factor) / factor;
}

function createTimestamp(index: number, count: number): string {
  const now = Date.now();
  const rideWindowMinutes = 240;
  const position = (count - index) / count;
  const minutesAgo = position * rideWindowMinutes + randomBetween(0, 4);

  return new Date(now - minutesAgo * 60_000).toISOString();
}

export function generateFakeCityScans(count = 56): CityScanRecord[] {
  const records: CityScanRecord[] = Array.from({ length: count }, (_, index) => {
    const hotspot = barcelonaHotspots[index % barcelonaHotspots.length];
    const trashDetected = Math.random() > 0.33;
    const toxicityLevel: ToxicityLevel = trashDetected
      ? Math.random() > 0.52
        ? 'High'
        : 'Medium'
      : Math.random() > 0.9
        ? 'High'
        : 'Medium';
    const warmer = toxicityLevel === 'High' ? randomBetween(1.1, 3.4) : randomBetween(-0.4, 1.5);
    const humidityShift = toxicityLevel === 'High' ? randomBetween(-4, 8) : randomBetween(-7, 5);

    return {
      id: `fake-${hotspot.name}-${String(index + 1).padStart(2, '0')}`,
      latitude: round(jitter(hotspot.latitude, 0.0058), 6),
      longitude: round(jitter(hotspot.longitude, 0.0062), 6),
      temperature: round(randomBetween(20.4, 27.6) + warmer),
      humidity: round(randomBetween(46, 71) + humidityShift),
      trash_detected: trashDetected,
      toxicity_level: toxicityLevel,
      device_timestamp: createTimestamp(index, count)
    };
  });

  return records.sort((first, second) => Date.parse(second.device_timestamp) - Date.parse(first.device_timestamp));
}
