import type { Ride, RideEvent, RoutePoint } from './types';

const kilometersPerRadian = 6371;

function toRadians(value: number): number {
  return (value * Math.PI) / 180;
}

function distanceBetween(start: RoutePoint, end: RoutePoint): number {
  const lat1 = toRadians(start.lat);
  const lat2 = toRadians(end.lat);
  const deltaLat = toRadians(end.lat - start.lat);
  const deltaLon = toRadians(end.lon - start.lon);

  const a =
    Math.sin(deltaLat / 2) * Math.sin(deltaLat / 2) +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLon / 2) * Math.sin(deltaLon / 2);

  return kilometersPerRadian * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

export function getDistanceKm(route: RoutePoint[]): number {
  return route.reduce((total, point, index) => {
    if (index === 0) {
      return total;
    }

    return total + distanceBetween(route[index - 1], point);
  }, 0);
}

export function getRideMinutes(ride: Ride): number {
  const started = Date.parse(ride.startedAt);
  const ended = Date.parse(ride.endedAt);

  return Math.max(0, Math.round((ended - started) / 60000));
}

export function average(values: number[]): number {
  if (values.length === 0) {
    return 0;
  }

  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

export function isAnomaly(event: RideEvent): boolean {
  const type = event.eventType.toLowerCase();
  const label = event.aiLabel.toLowerCase();

  return type.includes('anomaly') || label.includes('anomaly');
}

export function formatLabel(value: string): string {
  return value
    .split(/[_-]/)
    .filter(Boolean)
    .map((part) => `${part[0].toUpperCase()}${part.slice(1)}`)
    .join(' ');
}

export function formatTime(timestamp: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  }).format(new Date(timestamp));
}
