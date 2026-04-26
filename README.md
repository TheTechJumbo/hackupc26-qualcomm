# EcoDragon

EcoDragon is a HackUPC dashboard for Barcelona city agencies. The app visualizes bike-mounted trash scan records from Supabase, with environmental readings from Modulino sensors and phone-provided GPS coordinates.

The UI does not run inference, compute `toxicity_level`, upload rides, or write records. It only reads `city_scans` rows and supports generated fake test data for demos.

## Stack

- React
- Vite
- TypeScript
- Leaflet and React Leaflet
- Supabase JS client

## Data Model

Supabase table: `city_scans`

Fields used by the UI:

- `id`
- `latitude`
- `longitude`
- `temperature`
- `humidity`
- `trash_detected`
- `toxicity_level`
- `device_timestamp`

Toxicity level is displayed exactly as stored: `High` or `Medium`.

## Install

```bash
npm install
```

## Environment

Create `frontend/.env.local`:

```bash
VITE_SUPABASE_URL=https://gvpyllkegojlktizqlfi.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

The anon key is intentionally read through `import.meta.env` and is not hardcoded.

## Run

```bash
npm run dev:frontend
```

Open the Vite URL, usually `http://localhost:5173`.

## Data Modes

- `Fake Test Data`: default mode. Generates realistic Barcelona scan records in the browser so the demo works immediately.
- `Real Data`: fetches from Supabase table `city_scans` on mode switch and when `Refresh` is clicked.

There is no realtime subscription.

## Validation

```bash
npm run build --workspace frontend
```

Manual checks:

- Fake mode renders immediately
- Real mode attempts a Supabase fetch using `frontend/.env.local`
- Toggle switches between real and fake modes
- Refresh fetches real data or regenerates fake data
- Map markers open popups and update the details panel
- Table row selection updates the selected marker and details panel
- Summary cards update from the filtered dataset
- Filters apply to trash status, toxicity level, timestamp, temperature, and humidity

## Key Files

- `frontend/src/App.tsx`: dashboard components and UI state
- `frontend/src/api.ts`: Supabase client and `city_scans` fetch
- `frontend/src/fakeData.ts`: frontend-only fake Barcelona records
- `frontend/src/types.ts`: shared TypeScript types
- `frontend/src/styles.css`: dashboard and map styling

## Limitations

- Read-only frontend only
- No backend, auth, database migrations, upload flow, or ML inference
- Real Data mode requires a valid Supabase anon key in `frontend/.env.local`
