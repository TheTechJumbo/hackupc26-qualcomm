import cors from 'cors';
import express, { type NextFunction, type Request, type Response } from 'express';
import { randomUUID } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { Ride, RideEvent, RoutePoint } from './types.js';

const app = express();
const port = Number(process.env.PORT ?? 4000);

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const repoRoot = resolve(__dirname, '..', '..');
const sampleRidePath = resolve(repoRoot, 'sample-data', 'barcelona-ride.json');
const dataDir = resolve(repoRoot, 'backend', 'data');
const storePath = resolve(dataDir, 'rides.json');
const defaultAllowedOrigins = ['http://localhost:5173', 'http://127.0.0.1:5173'];
const allowedOrigins = (process.env.CORS_ORIGINS ?? defaultAllowedOrigins.join(','))
  .split(',')
  .map((origin) => origin.trim())
  .filter(Boolean);

app.use(
  cors({
    origin(origin, callback) {
      if (!origin || allowedOrigins.includes(origin)) {
        callback(null, true);
        return;
      }

      callback(null, false);
    }
  })
);
app.use(express.json({ limit: '2mb' }));

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function isTimestamp(value: unknown): value is string {
  return typeof value === 'string' && !Number.isNaN(Date.parse(value));
}

function stringValue(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim().length > 0 ? value.trim() : undefined;
}

function validateRoutePoint(point: unknown, index: number): RoutePoint | string {
  if (!isRecord(point)) {
    return `route[${index}] must be an object`;
  }

  if (!isFiniteNumber(point.lat) || !isFiniteNumber(point.lon)) {
    return `route[${index}] requires numeric lat and lon`;
  }

  if (!isTimestamp(point.timestamp)) {
    return `route[${index}] requires an ISO timestamp`;
  }

  return {
    lat: point.lat,
    lon: point.lon,
    timestamp: point.timestamp
  };
}

function validateEvent(event: unknown, index: number, rideId: string): RideEvent | string {
  if (!isRecord(event)) {
    return `events[${index}] must be an object`;
  }

  const aiLabel = stringValue(event.aiLabel);
  const eventType = stringValue(event.eventType);
  const id = stringValue(event.id) ?? `${rideId}-event-${index + 1}`;

  if (!isFiniteNumber(event.lat) || !isFiniteNumber(event.lon)) {
    return `events[${index}] requires numeric lat and lon`;
  }

  if (!isTimestamp(event.timestamp)) {
    return `events[${index}] requires an ISO timestamp`;
  }

  if (!isFiniteNumber(event.light)) {
    return `events[${index}] requires numeric light`;
  }

  if (!isFiniteNumber(event.temperature)) {
    return `events[${index}] requires numeric temperature`;
  }

  if (event.humidity !== undefined && !isFiniteNumber(event.humidity)) {
    return `events[${index}] humidity must be numeric when provided`;
  }

  if (!aiLabel) {
    return `events[${index}] requires aiLabel`;
  }

  if (!isFiniteNumber(event.confidence) || event.confidence < 0 || event.confidence > 1) {
    return `events[${index}] requires confidence from 0 to 1`;
  }

  if (!eventType) {
    return `events[${index}] requires eventType`;
  }

  return {
    id,
    lat: event.lat,
    lon: event.lon,
    timestamp: event.timestamp,
    light: event.light,
    temperature: event.temperature,
    humidity: event.humidity,
    aiLabel,
    confidence: event.confidence,
    eventType
  };
}

function validateRide(payload: unknown): { ride: Ride; errors: [] } | { ride: null; errors: string[] } {
  const errors: string[] = [];

  if (!isRecord(payload)) {
    return { ride: null, errors: ['ride payload must be an object'] };
  }

  const id = stringValue(payload.id) ?? `ride-${randomUUID()}`;
  const bikeId = stringValue(payload.bikeId);
  const agencyNotes = stringValue(payload.agencyNotes);

  if (!bikeId) {
    errors.push('bikeId is required');
  }

  if (!isTimestamp(payload.startedAt)) {
    errors.push('startedAt must be an ISO timestamp');
  }

  if (!isTimestamp(payload.endedAt)) {
    errors.push('endedAt must be an ISO timestamp');
  }

  if (isTimestamp(payload.startedAt) && isTimestamp(payload.endedAt)) {
    if (Date.parse(payload.startedAt) >= Date.parse(payload.endedAt)) {
      errors.push('endedAt must be after startedAt');
    }
  }

  if (!Array.isArray(payload.route) || payload.route.length < 2) {
    errors.push('route must contain at least two points');
  }

  if (!Array.isArray(payload.events) || payload.events.length < 1) {
    errors.push('events must contain at least one event');
  }

  const route: RoutePoint[] = [];
  if (Array.isArray(payload.route)) {
    payload.route.forEach((point, index) => {
      const result = validateRoutePoint(point, index);
      if (typeof result === 'string') {
        errors.push(result);
      } else {
        route.push(result);
      }
    });
  }

  const events: RideEvent[] = [];
  if (Array.isArray(payload.events)) {
    payload.events.forEach((event, index) => {
      const result = validateEvent(event, index, id);
      if (typeof result === 'string') {
        errors.push(result);
      } else {
        events.push(result);
      }
    });
  }

  if (errors.length > 0 || !bikeId || !isTimestamp(payload.startedAt) || !isTimestamp(payload.endedAt)) {
    return { ride: null, errors };
  }

  return {
    ride: {
      id,
      bikeId,
      startedAt: payload.startedAt,
      endedAt: payload.endedAt,
      agencyNotes,
      route,
      events
    },
    errors: []
  };
}

async function readSeedRide(): Promise<Ride> {
  const raw = await readFile(sampleRidePath, 'utf8');
  const validation = validateRide(JSON.parse(raw));

  if (!validation.ride) {
    throw new Error(`Sample ride is invalid: ${validation.errors.join(', ')}`);
  }

  return validation.ride;
}

async function ensureStore(): Promise<void> {
  await mkdir(dataDir, { recursive: true });

  try {
    await readFile(storePath, 'utf8');
  } catch {
    const seedRide = await readSeedRide();
    await writeFile(storePath, `${JSON.stringify([seedRide], null, 2)}\n`);
  }
}

async function readRides(): Promise<Ride[]> {
  await ensureStore();
  const raw = await readFile(storePath, 'utf8');
  const parsed = JSON.parse(raw);

  if (!Array.isArray(parsed)) {
    throw new Error('Ride store is corrupted');
  }

  return parsed.map((ride) => {
    const validation = validateRide(ride);
    if (!validation.ride) {
      throw new Error(`Ride store contains invalid data: ${validation.errors.join(', ')}`);
    }
    return validation.ride;
  });
}

async function writeRides(rides: Ride[]): Promise<void> {
  await mkdir(dataDir, { recursive: true });
  await writeFile(storePath, `${JSON.stringify(rides, null, 2)}\n`);
}

async function resetRideStore(): Promise<Ride[]> {
  const seedRide = await readSeedRide();
  await writeRides([seedRide]);
  return [seedRide];
}

function asyncHandler(
  handler: (request: Request, response: Response, next: NextFunction) => Promise<void>
) {
  return (request: Request, response: Response, next: NextFunction) => {
    handler(request, response, next).catch(next);
  };
}

app.get('/api/health', (_request, response) => {
  response.json({
    status: 'ok',
    service: 'barcelona-bike-sensing-backend'
  });
});

app.get('/api/demo/status', (_request, response) => {
  response.json({
    mode: 'controlled-demo',
    auth: 'none',
    storage: 'local-json',
    corsOrigins: allowedOrigins,
    resetAvailable: true,
    guidance:
      'No auth or database is used because this MVP is intended for one trusted local demo operator. Move to authenticated durable storage for a multi-bike field pilot.'
  });
});

app.get(
  '/api/rides',
  asyncHandler(async (_request, response) => {
    const rides = await readRides();
    response.json({ rides });
  })
);

app.get(
  '/api/rides/:id',
  asyncHandler(async (request, response) => {
    const rides = await readRides();
    const ride = rides.find((candidate) => candidate.id === request.params.id);

    if (!ride) {
      response.status(404).json({ error: 'Ride not found' });
      return;
    }

    response.json({ ride });
  })
);

app.post(
  '/api/rides',
  asyncHandler(async (request, response) => {
    const validation = validateRide(request.body);

    if (!validation.ride) {
      response.status(400).json({
        error: 'Invalid ride payload',
        details: validation.errors
      });
      return;
    }

    const rides = await readRides();
    const existingIndex = rides.findIndex((ride) => ride.id === validation.ride.id);
    const nextRides =
      existingIndex >= 0
        ? rides.map((ride, index) => (index === existingIndex ? validation.ride : ride))
        : [validation.ride, ...rides];

    await writeRides(nextRides);

    response.status(existingIndex >= 0 ? 200 : 201).json({ ride: validation.ride });
  })
);

app.post(
  '/api/demo/reset',
  asyncHandler(async (_request, response) => {
    const rides = await resetRideStore();
    response.json({ rides });
  })
);

app.use((error: unknown, _request: Request, response: Response, _next: NextFunction) => {
  const message = error instanceof Error ? error.message : 'Unknown server error';
  response.status(500).json({ error: message });
});

app.listen(port, () => {
  console.log(`Barcelona Bike Sensing API listening on http://localhost:${port}`);
});
