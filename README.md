# Barcelona Bike Sensing Platform

HackUPC MVP web stack for a bike-mounted urban sensing system in Barcelona. Public bikes act as mobile Edge AI + sensor nodes: Arduino UNO Q reads local sensors, the phone adds GPS and stores events during the ride, then uploads ride JSON after the ride ends.

## Stack

- Frontend: React + Vite + TypeScript + Leaflet
- Backend: Node + Express + TypeScript
- Storage: local JSON file at `backend/data/rides.json`
- Sample ride: `sample-data/barcelona-ride.json`

For this MVP, the Arduino/phone pipeline samples sensor readings at `0.33333 Hz`, meaning one GPS-aligned reading every 3 seconds during a ride before post-ride upload.

## Controlled Live Demo

This project is still intentionally built without auth or a database for a controlled HackUPC demo with one trusted bike/operator, a local laptop backend, and demo-only GPS traces. Real hardware does not automatically require production infrastructure when the upload path is local, the operator is trusted, and the ride data can be reset after the presentation.

Minimum safeguards included:

- Backend storage is local JSON and can be reset to the seeded sample ride.
- CORS defaults to `http://localhost:5173` and `http://127.0.0.1:5173`.
- Set `CORS_ORIGINS` if the frontend must be opened from another local origin during the demo.
- Uploaded rides are validated before being written.
- Payload size is capped at `2mb`.

Move to authenticated durable storage when this becomes a multi-bike field pilot, involves untrusted networks, or keeps GPS traces as agency records.

## Setup

```bash
npm install
```

Run the backend:

```bash
npm run dev:backend
```

Run the frontend in a second terminal:

```bash
npm run dev:frontend
```

Open the Vite URL, usually `http://localhost:5173`. The frontend expects the API at `http://localhost:4000` by default. To override it:

```bash
VITE_API_BASE_URL=http://localhost:4000 npm run dev:frontend
```

## API

```bash
curl http://localhost:4000/api/health
curl http://localhost:4000/api/demo/status
curl http://localhost:4000/api/rides
curl http://localhost:4000/api/rides/ride-barcelona-eixample-001
curl -X POST http://localhost:4000/api/rides \
  -H "Content-Type: application/json" \
  --data-binary @sample-data/barcelona-ride.json
curl -X POST http://localhost:4000/api/demo/reset
```

## Ride JSON

Events support:

- `lat`
- `lon`
- `timestamp`
- `light`
- `temperature`
- optional `humidity`
- `aiLabel`
- `confidence`
- `eventType`

The sample ride includes temperature, light, AI labels, mobility events, microclimate events, and anomalies so the dashboard is not trash-only.

## Validation

```bash
npm run typecheck
npm run build
```

Manual checks:

- Backend returns `GET /api/health`
- Backend returns controlled-demo guidance from `GET /api/demo/status`
- Backend returns seeded rides from `GET /api/rides`
- Frontend map renders the Barcelona route polyline
- Event markers appear and update the details panel
- Event timeline and review queue select the same event as the map markers
- Layer toggles change marker visibility/styling
- Uploading the sample JSON through the UI or API succeeds
- Resetting demo data restores the seeded ride
