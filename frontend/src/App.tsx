import L from 'leaflet';
import {
  AlertTriangle,
  Bike,
  Clock3,
  FileJson,
  Gauge,
  Layers,
  Lightbulb,
  ListChecks,
  MapPinned,
  RadioTower,
  RotateCcw,
  Route as RouteIcon,
  Satellite,
  Thermometer,
  Upload
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { MapContainer, Marker, Polyline, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet';
import { fetchRides, resetDemoRides, uploadRide } from './api';
import { average, formatLabel, formatTime, getDistanceKm, getRideMinutes, isAnomaly } from './metrics';
import type { LayerState, Ride, RideEvent } from './types';

const defaultLayers: LayerState = {
  temperature: true,
  light: true,
  labels: true,
  anomalies: true
};

const labelPalette = [
  '#2563eb',
  '#0f766e',
  '#7c3aed',
  '#b45309',
  '#0369a1',
  '#4d7c0f',
  '#be123c'
];

function colorFromString(value: string): string {
  const total = [...value].reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return labelPalette[total % labelPalette.length];
}

function temperatureColor(value: number): string {
  if (value >= 24) {
    return '#dc2626';
  }

  if (value >= 22.5) {
    return '#ea580c';
  }

  if (value >= 21) {
    return '#d97706';
  }

  return '#0891b2';
}

function lightColor(value: number): string {
  if (value >= 750) {
    return '#f59e0b';
  }

  if (value >= 550) {
    return '#84cc16';
  }

  if (value >= 350) {
    return '#06b6d4';
  }

  return '#475569';
}

function markerColor(event: RideEvent, layers: LayerState): string {
  if (layers.anomalies && isAnomaly(event)) {
    return '#dc2626';
  }

  if (layers.labels) {
    return colorFromString(event.aiLabel);
  }

  if (layers.temperature) {
    return temperatureColor(event.temperature);
  }

  if (layers.light) {
    return lightColor(event.light);
  }

  return '#2563eb';
}

function visibleForLayers(event: RideEvent, layers: LayerState): boolean {
  if (layers.temperature || layers.light || layers.labels) {
    return true;
  }

  return layers.anomalies && isAnomaly(event);
}

function getTimelinePosition(event: RideEvent, ride: Ride): number {
  const started = Date.parse(ride.startedAt);
  const ended = Date.parse(ride.endedAt);
  const eventTime = Date.parse(event.timestamp);

  if (!Number.isFinite(started) || !Number.isFinite(ended) || !Number.isFinite(eventTime) || ended <= started) {
    return 0;
  }

  return Math.min(100, Math.max(0, ((eventTime - started) / (ended - started)) * 100));
}

function createEventIcon(color: string, selected: boolean): L.DivIcon {
  return L.divIcon({
    className: 'event-marker',
    html: `<span class="${selected ? 'event-marker-dot selected' : 'event-marker-dot'}" style="background:${color}"></span>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
    popupAnchor: [0, -12]
  });
}

function MapBounds({ ride }: { ride: Ride }) {
  const map = useMap();

  useEffect(() => {
    if (ride.route.length < 2) {
      return;
    }

    const bounds = L.latLngBounds(ride.route.map((point) => [point.lat, point.lon]));
    map.fitBounds(bounds, { padding: [34, 34] });
  }, [map, ride]);

  return null;
}

function EventTimeline({
  ride,
  events,
  layers,
  selectedEventId,
  onSelectEvent
}: {
  ride: Ride;
  events: RideEvent[];
  layers: LayerState;
  selectedEventId: string | null;
  onSelectEvent: (eventId: string) => void;
}) {
  return (
    <section className="event-timeline" aria-label="Ride event timeline">
      <div className="timeline-header">
        <div>
          <span>Ride timeline</span>
          <h2>Events by time</h2>
        </div>
        <strong>{events.length} events</strong>
      </div>
      <div className="timeline-track" role="list">
        <span className="timeline-line" aria-hidden="true" />
        {events.map((event) => {
          const visible = visibleForLayers(event, layers);
          const selected = selectedEventId === event.id;

          return (
            <button
              key={event.id}
              className={`timeline-event${selected ? ' selected' : ''}${visible ? '' : ' muted'}`}
              style={{ '--event-color': markerColor(event, layers), left: `${getTimelinePosition(event, ride)}%` } as React.CSSProperties}
              type="button"
              title={`${formatTime(event.timestamp)} - ${formatLabel(event.aiLabel)}`}
              aria-label={`Select ${formatLabel(event.aiLabel)} at ${formatTime(event.timestamp)}`}
              onClick={() => onSelectEvent(event.id)}
            />
          );
        })}
      </div>
      <div className="timeline-times">
        <span>{formatTime(ride.startedAt)}</span>
        <span>{formatTime(ride.endedAt)}</span>
      </div>
    </section>
  );
}

function EventList({
  events,
  layers,
  selectedEventId,
  onSelectEvent
}: {
  events: RideEvent[];
  layers: LayerState;
  selectedEventId: string | null;
  onSelectEvent: (eventId: string) => void;
}) {
  return (
    <section className="event-list-panel">
      <div className="section-heading">
        <div>
          <span>Review queue</span>
          <h2>Ride events</h2>
        </div>
        <ListChecks size={22} />
      </div>
      <div className="event-list" role="list">
        {events.map((event) => {
          const visible = visibleForLayers(event, layers);
          const selected = selectedEventId === event.id;

          return (
            <button
              key={event.id}
              className={`event-row${selected ? ' selected' : ''}${visible ? '' : ' muted'}`}
              type="button"
              onClick={() => onSelectEvent(event.id)}
            >
              <span className="event-row-marker" style={{ '--event-color': markerColor(event, layers) } as React.CSSProperties} />
              <span className="event-row-main">
                <span className="event-row-meta">
                  <strong>{formatTime(event.timestamp)}</strong>
                  <em className={isAnomaly(event) ? 'event-type anomaly' : 'event-type'}>{event.eventType}</em>
                </span>
                <span className="event-row-label">{formatLabel(event.aiLabel)}</span>
                <span className="event-row-stats">
                  <span>{event.temperature.toFixed(1)} C</span>
                  <span>{Math.round(event.light)} lx</span>
                  <span>{Math.round(event.confidence * 100)}%</span>
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
  detail
}: {
  icon: typeof Bike;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <article className="metric-card">
      <div className="metric-icon" aria-hidden="true">
        <Icon size={19} />
      </div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{detail}</small>
      </div>
    </article>
  );
}

function LayerToggle({
  id,
  checked,
  label,
  accent,
  onChange
}: {
  id: keyof LayerState;
  checked: boolean;
  label: string;
  accent: string;
  onChange: (layer: keyof LayerState) => void;
}) {
  return (
    <label className="layer-toggle" style={{ '--layer-accent': accent } as React.CSSProperties}>
      <input type="checkbox" checked={checked} onChange={() => onChange(id)} />
      <span className="toggle-swatch" aria-hidden="true" />
      <span>{label}</span>
    </label>
  );
}

function Legend({ layers }: { layers: LayerState }) {
  return (
    <div className="legend">
      <div className="legend-title">
        <Layers size={16} />
        Legend
      </div>
      {layers.temperature ? (
        <div className="legend-row">
          <span className="legend-gradient temperature" />
          <span>Temperature: cool to heat</span>
        </div>
      ) : null}
      {layers.light ? (
        <div className="legend-row">
          <span className="legend-gradient light" />
          <span>Light: low to high exposure</span>
        </div>
      ) : null}
      {layers.labels ? (
        <div className="legend-row">
          <span className="legend-dot blue" />
          <span>AI label clusters</span>
        </div>
      ) : null}
      {layers.anomalies ? (
        <div className="legend-row">
          <span className="legend-dot red" />
          <span>Anomaly events</span>
        </div>
      ) : null}
    </div>
  );
}

function EventDetails({ event }: { event: RideEvent | null }) {
  if (!event) {
    return (
      <section className="details empty-state">
        <MapPinned size={22} />
        <h2>Event details</h2>
        <p>Select a map marker to inspect the sensor packet and local AI output.</p>
      </section>
    );
  }

  return (
    <section className="details">
      <div className="section-heading">
        <div>
          <span>Selected event</span>
          <h2>{formatLabel(event.aiLabel)}</h2>
        </div>
        <strong className={isAnomaly(event) ? 'status-pill anomaly' : 'status-pill'}>{event.eventType}</strong>
      </div>

      <dl className="detail-grid">
        <div>
          <dt>Time</dt>
          <dd>{formatTime(event.timestamp)}</dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd>{Math.round(event.confidence * 100)}%</dd>
        </div>
        <div>
          <dt>Temperature</dt>
          <dd>{event.temperature.toFixed(1)} C</dd>
        </div>
        <div>
          <dt>Light</dt>
          <dd>{Math.round(event.light)} lx</dd>
        </div>
        <div>
          <dt>Humidity</dt>
          <dd>{event.humidity === undefined ? 'n/a' : `${Math.round(event.humidity)}%`}</dd>
        </div>
        <div>
          <dt>Coordinates</dt>
          <dd>
            {event.lat.toFixed(5)}, {event.lon.toFixed(5)}
          </dd>
        </div>
      </dl>
    </section>
  );
}

function UploadPanel({
  onReset,
  onUploaded
}: {
  onReset: () => Promise<void>;
  onUploaded: (ride: Ride) => void;
}) {
  const [draft, setDraft] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [isResetting, setIsResetting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  async function handleUpload() {
    setMessage(null);
    setIsUploading(true);

    try {
      const parsed = JSON.parse(draft);
      const ride = await uploadRide(parsed);
      onUploaded(ride);
      setMessage(`Uploaded ${ride.id}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Upload failed');
    } finally {
      setIsUploading(false);
    }
  }

  async function handleFile(file: File | null) {
    if (!file) {
      return;
    }

    setDraft(await file.text());
    setMessage(`Loaded ${file.name}`);
  }

  async function handleReset() {
    setMessage(null);
    setIsResetting(true);

    try {
      await onReset();
      setDraft('');
      setMessage('Demo data reset to the seeded ride');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Reset failed');
    } finally {
      setIsResetting(false);
    }
  }

  return (
    <section className="upload-panel">
      <div className="section-heading">
        <div>
          <span>Ride upload</span>
          <h2>JSON ingest</h2>
        </div>
        <FileJson size={22} />
      </div>
      <label className="file-input">
        <input type="file" accept="application/json,.json" onChange={(event) => handleFile(event.target.files?.[0] ?? null)} />
        <Upload size={16} />
        Select JSON
      </label>
      <textarea
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        placeholder='{"id":"ride-id","bikeId":"bicing-edge-node-14", ...}'
        spellCheck={false}
      />
      <button className="primary-button" type="button" onClick={handleUpload} disabled={isUploading || draft.trim().length === 0}>
        {isUploading ? 'Uploading...' : 'Upload ride'}
      </button>
      <button className="secondary-button" type="button" onClick={handleReset} disabled={isResetting}>
        <RotateCcw size={16} />
        {isResetting ? 'Resetting...' : 'Reset demo data'}
      </button>
      {message ? <p className="upload-message">{message}</p> : null}
    </section>
  );
}

function App() {
  const [rides, setRides] = useState<Ride[]>([]);
  const [selectedRideId, setSelectedRideId] = useState('');
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [layers, setLayers] = useState<LayerState>(defaultLayers);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    fetchRides()
      .then((nextRides) => {
        if (!isMounted) {
          return;
        }

        setRides(nextRides);
        setSelectedRideId(nextRides[0]?.id ?? '');
        setSelectedEventId(nextRides[0]?.events[0]?.id ?? null);
        setError(null);
      })
      .catch((requestError) => {
        if (isMounted) {
          setError(requestError instanceof Error ? requestError.message : 'Unable to fetch rides');
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const ride = rides.find((candidate) => candidate.id === selectedRideId) ?? rides[0] ?? null;

  const selectedEvent = useMemo(() => {
    if (!ride) {
      return null;
    }

    return ride.events.find((event) => event.id === selectedEventId) ?? ride.events[0] ?? null;
  }, [ride, selectedEventId]);

  const visibleEvents = useMemo(() => {
    if (!ride) {
      return [];
    }

    return ride.events.filter((event) => visibleForLayers(event, layers));
  }, [layers, ride]);

  const chronologicalEvents = useMemo(() => {
    if (!ride) {
      return [];
    }

    return [...ride.events].sort((first, second) => Date.parse(first.timestamp) - Date.parse(second.timestamp));
  }, [ride]);

  const metrics = useMemo(() => {
    if (!ride) {
      return null;
    }

    return {
      distanceKm: getDistanceKm(ride.route),
      durationMinutes: getRideMinutes(ride),
      averageTemperature: average(ride.events.map((event) => event.temperature)),
      averageLight: average(ride.events.map((event) => event.light)),
      anomalies: ride.events.filter(isAnomaly).length
    };
  }, [ride]);

  function toggleLayer(layer: keyof LayerState) {
    setLayers((current) => ({
      ...current,
      [layer]: !current[layer]
    }));
  }

  function handleRideUploaded(uploadedRide: Ride) {
    setRides((current) => {
      const withoutUploaded = current.filter((candidate) => candidate.id !== uploadedRide.id);
      return [uploadedRide, ...withoutUploaded];
    });
    setSelectedRideId(uploadedRide.id);
    setSelectedEventId(uploadedRide.events[0]?.id ?? null);
  }

  async function handleDemoReset() {
    const resetRides = await resetDemoRides();
    setRides(resetRides);
    setSelectedRideId(resetRides[0]?.id ?? '');
    setSelectedEventId(resetRides[0]?.events[0]?.id ?? null);
  }

  function handleRideChange(rideId: string) {
    const nextRide = rides.find((candidate) => candidate.id === rideId);
    setSelectedRideId(rideId);
    setSelectedEventId(nextRide?.events[0]?.id ?? null);
  }

  if (isLoading) {
    return (
      <main className="app-shell loading-state">
        <Satellite size={26} />
        <p>Loading Barcelona sensing data...</p>
      </main>
    );
  }

  if (error || !ride || !metrics) {
    return (
      <main className="app-shell loading-state">
        <AlertTriangle size={28} />
        <p>{error ?? 'No ride data available'}</p>
      </main>
    );
  }

  const routePositions = ride.route.map((point) => [point.lat, point.lon] as [number, number]);

  return (
    <main className="app-shell">
      <header className="top-bar">
        <div>
          <span className="eyebrow">Barcelona agencies</span>
          <h1>Bike Sensing Platform</h1>
        </div>
        <div className="ride-selector">
          <label htmlFor="ride-select">Ride</label>
          <select id="ride-select" value={ride.id} onChange={(event) => handleRideChange(event.target.value)}>
            {rides.map((candidate) => (
              <option key={candidate.id} value={candidate.id}>
                {candidate.id}
              </option>
            ))}
          </select>
        </div>
      </header>

      <section className="story-strip">
        <div>
          <Bike size={18} />
          Arduino UNO Q
        </div>
        <div>
          <Satellite size={18} />
          Phone GPS + Bluetooth
        </div>
        <div>
          <Gauge size={18} />
          Edge AI event stream
        </div>
        <div>
          <Upload size={18} />
          Post-ride upload
        </div>
      </section>

      <section className="metrics-grid" aria-label="Ride summary">
        <MetricCard icon={Clock3} label="Duration" value={`${metrics.durationMinutes} min`} detail={ride.bikeId} />
        <MetricCard icon={RouteIcon} label="Distance" value={`${metrics.distanceKm.toFixed(2)} km`} detail={`${ride.route.length} GPS points`} />
        <MetricCard icon={MapPinned} label="Events" value={`${ride.events.length}`} detail={`${visibleEvents.length} visible`} />
        <MetricCard icon={Thermometer} label="Temperature" value={`${metrics.averageTemperature.toFixed(1)} C`} detail="event average" />
        <MetricCard icon={Lightbulb} label="Light" value={`${Math.round(metrics.averageLight)} lx`} detail="event average" />
        <MetricCard icon={AlertTriangle} label="Anomalies" value={`${metrics.anomalies}`} detail="flagged by AI/type" />
        <MetricCard icon={RadioTower} label="Sensor cadence" value="0.33333 Hz" detail="1 sample / 3 sec" />
      </section>

      <section className="dashboard-grid">
        <div className="map-panel">
          <div className="map-toolbar">
            <div className="layer-list" aria-label="Map layers">
              <LayerToggle id="temperature" label="Temperature" accent="#ea580c" checked={layers.temperature} onChange={toggleLayer} />
              <LayerToggle id="light" label="Light" accent="#f59e0b" checked={layers.light} onChange={toggleLayer} />
              <LayerToggle id="labels" label="AI labels" accent="#2563eb" checked={layers.labels} onChange={toggleLayer} />
              <LayerToggle id="anomalies" label="Anomalies" accent="#dc2626" checked={layers.anomalies} onChange={toggleLayer} />
            </div>
          </div>

          <div className="map-stage">
            <MapContainer center={[41.395, 2.172]} zoom={14} scrollWheelZoom className="ride-map">
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <MapBounds ride={ride} />
              <Polyline positions={routePositions} pathOptions={{ color: '#111827', weight: 5, opacity: 0.78 }} />
              <Polyline positions={routePositions} pathOptions={{ color: '#22c55e', weight: 2, opacity: 0.95 }} />
              {visibleEvents.map((event) => {
                const color = markerColor(event, layers);
                const selected = selectedEvent?.id === event.id;

                return (
                  <Marker
                    key={event.id}
                    position={[event.lat, event.lon]}
                    icon={createEventIcon(color, selected)}
                    eventHandlers={{
                      click: () => setSelectedEventId(event.id)
                    }}
                  >
                    <Tooltip direction="top" offset={[0, -10]}>
                      {formatLabel(event.aiLabel)}
                    </Tooltip>
                    <Popup>
                      <strong>{formatLabel(event.aiLabel)}</strong>
                      <br />
                      {event.temperature.toFixed(1)} C · {Math.round(event.light)} lx
                    </Popup>
                  </Marker>
                );
              })}
            </MapContainer>
            <Legend layers={layers} />
          </div>
          <EventTimeline
            ride={ride}
            events={chronologicalEvents}
            layers={layers}
            selectedEventId={selectedEvent?.id ?? null}
            onSelectEvent={setSelectedEventId}
          />
        </div>

        <aside className="side-panel">
          <section className="ride-card">
            <div className="section-heading">
              <div>
                <span>Current ride</span>
                <h2>{ride.id}</h2>
              </div>
              <Bike size={22} />
            </div>
            <p>{ride.agencyNotes}</p>
            <div className="ride-times">
              <span>{formatTime(ride.startedAt)}</span>
              <span>{formatTime(ride.endedAt)}</span>
            </div>
          </section>
          <EventDetails event={selectedEvent} />
          <EventList events={chronologicalEvents} layers={layers} selectedEventId={selectedEvent?.id ?? null} onSelectEvent={setSelectedEventId} />
          <UploadPanel onReset={handleDemoReset} onUploaded={handleRideUploaded} />
        </aside>
      </section>
    </main>
  );
}

export default App;
