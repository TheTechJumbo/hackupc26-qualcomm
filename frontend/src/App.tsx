import L from 'leaflet';
import {
  AlertCircle,
  CheckCircle2,
  Database,
  Droplets,
  Filter,
  Flame,
  LocateFixed,
  MapPinned,
  RefreshCw,
  Table2,
  Thermometer,
  Trash2,
  XCircle
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { type KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react';
import { MapContainer, Marker, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet';
import { fetchCityScans } from './api';
import { generateFakeCityScans } from './fakeData';
import type {
  CityScanRecord,
  DataMode,
  ScanFilters,
  SummaryMetric,
  ToxicityLevel,
  ToxicityLevelFilter,
  TrashStatusFilter
} from './types';

const barcelonaCenter: [number, number] = [41.3874, 2.1686];

const defaultFilters: ScanFilters = {
  trashStatus: 'all',
  toxicityLevel: 'all',
  startTimestamp: '',
  endTimestamp: '',
  minTemperature: '',
  maxTemperature: '',
  minHumidity: '',
  maxHumidity: ''
};

function formatTimestamp(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat('en-GB', {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(date);
}

function formatShortTime(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    minute: '2-digit'
  }).format(date);
}

function average(values: number[]): number {
  if (values.length === 0) {
    return 0;
  }

  return values.reduce((total, value) => total + value, 0) / values.length;
}

function markerColor(record: CityScanRecord): string {
  return record.toxicity_level === 'High' ? '#dc2626' : '#eab308';
}

function createMarkerIcon(record: CityScanRecord, selected: boolean): L.DivIcon {
  const classes = ['scan-marker-dot', record.toxicity_level.toLowerCase()];

  if (selected) {
    classes.push('selected');
  }

  return L.divIcon({
    className: 'scan-marker',
    html: `<span class="${classes.join(' ')}" style="background:${markerColor(record)}"></span>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
    popupAnchor: [0, -13]
  });
}

function filterRecords(records: CityScanRecord[], filters: ScanFilters): CityScanRecord[] {
  const start = filters.startTimestamp ? Date.parse(filters.startTimestamp) : null;
  const end = filters.endTimestamp ? Date.parse(filters.endTimestamp) : null;
  const minTemperature = filters.minTemperature === '' ? null : Number(filters.minTemperature);
  const maxTemperature = filters.maxTemperature === '' ? null : Number(filters.maxTemperature);
  const minHumidity = filters.minHumidity === '' ? null : Number(filters.minHumidity);
  const maxHumidity = filters.maxHumidity === '' ? null : Number(filters.maxHumidity);

  return records.filter((record) => {
    const timestamp = Date.parse(record.device_timestamp);

    if (filters.trashStatus === 'detected' && !record.trash_detected) {
      return false;
    }

    if (filters.trashStatus === 'clear' && record.trash_detected) {
      return false;
    }

    if (filters.toxicityLevel !== 'all' && record.toxicity_level !== filters.toxicityLevel) {
      return false;
    }

    if (start !== null && timestamp < start) {
      return false;
    }

    if (end !== null && timestamp > end) {
      return false;
    }

    if (minTemperature !== null && Number.isFinite(minTemperature) && record.temperature < minTemperature) {
      return false;
    }

    if (maxTemperature !== null && Number.isFinite(maxTemperature) && record.temperature > maxTemperature) {
      return false;
    }

    if (minHumidity !== null && Number.isFinite(minHumidity) && record.humidity < minHumidity) {
      return false;
    }

    if (maxHumidity !== null && Number.isFinite(maxHumidity) && record.humidity > maxHumidity) {
      return false;
    }

    return true;
  });
}

function getSummaryMetrics(records: CityScanRecord[]): SummaryMetric[] {
  const detected = records.filter((record) => record.trash_detected).length;
  const high = records.filter((record) => record.toxicity_level === 'High').length;
  const medium = records.filter((record) => record.toxicity_level === 'Medium').length;
  const averageTemperature = average(records.map((record) => record.temperature));
  const averageHumidity = average(records.map((record) => record.humidity));

  return [
    { label: 'Total records', value: String(records.length), detail: 'visible scan points' },
    { label: 'Trash detected', value: String(detected), detail: `${records.length - detected} clear scans` },
    { label: 'High toxicity', value: String(high), detail: 'red intervention queue' },
    { label: 'Medium toxicity', value: String(medium), detail: 'yellow review queue' },
    {
      label: 'Avg temperature',
      value: records.length ? `${averageTemperature.toFixed(1)} C` : '0.0 C',
      detail: 'Modulino reading'
    },
    {
      label: 'Avg humidity',
      value: records.length ? `${averageHumidity.toFixed(0)}%` : '0%',
      detail: 'Modulino reading'
    }
  ];
}

function ModeToggle({
  mode,
  onModeChange
}: {
  mode: DataMode;
  onModeChange: (mode: DataMode) => void;
}) {
  return (
    <div className="mode-toggle" aria-label="Data source">
      <button className={mode === 'real' ? 'active' : ''} type="button" onClick={() => onModeChange('real')}>
        Real Data
      </button>
      <button className={mode === 'fake' ? 'active' : ''} type="button" onClick={() => onModeChange('fake')}>
        Fake Test Data
      </button>
    </div>
  );
}

function TopBar({
  mode,
  isLoading,
  lastUpdated,
  onModeChange,
  onRefresh
}: {
  mode: DataMode;
  isLoading: boolean;
  lastUpdated: Date | null;
  onModeChange: (mode: DataMode) => void;
  onRefresh: () => void;
}) {
  return (
    <header className="top-bar">
      <div className="brand-block">
        <span className="eyebrow">Barcelona city agencies</span>
        <h1>EcoDragon</h1>
        <p>Trash detection records with bike-mounted environmental context.</p>
      </div>
      <div className="top-actions">
        <ModeToggle mode={mode} onModeChange={onModeChange} />
        <button className="refresh-button" type="button" onClick={onRefresh} disabled={isLoading}>
          <RefreshCw size={16} />
          {mode === 'fake' ? 'Regenerate' : 'Refresh'}
        </button>
        <span className="updated-at">{lastUpdated ? `Updated ${formatShortTime(lastUpdated.toISOString())}` : 'Not loaded'}</span>
      </div>
    </header>
  );
}

function SummaryCards({ records }: { records: CityScanRecord[] }) {
  const metrics = getSummaryMetrics(records);
  const icons: LucideIcon[] = [Database, Trash2, Flame, AlertCircle, Thermometer, Droplets];

  return (
    <section className="summary-grid" aria-label="Scan summary">
      {metrics.map((metric, index) => {
        const Icon = icons[index];

        return (
          <article className="summary-card" key={metric.label}>
            <div className="summary-icon" aria-hidden="true">
              <Icon size={18} />
            </div>
            <div>
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              <small>{metric.detail}</small>
            </div>
          </article>
        );
      })}
    </section>
  );
}

function FiltersPanel({
  filters,
  onChange,
  onReset
}: {
  filters: ScanFilters;
  onChange: (filters: Partial<ScanFilters>) => void;
  onReset: () => void;
}) {
  return (
    <section className="panel filters-panel">
      <div className="section-heading">
        <div>
          <span>Controls</span>
          <h2>Filters</h2>
        </div>
        <Filter size={20} />
      </div>

      <div className="filter-grid">
        <label>
          <span>Trash detected</span>
          <select
            value={filters.trashStatus}
            onChange={(event) => onChange({ trashStatus: event.currentTarget.value as TrashStatusFilter })}
          >
            <option value="all">All scans</option>
            <option value="detected">Detected</option>
            <option value="clear">Not detected</option>
          </select>
        </label>

        <label>
          <span>Toxicity level</span>
          <select
            value={filters.toxicityLevel}
            onChange={(event) => onChange({ toxicityLevel: event.currentTarget.value as ToxicityLevelFilter })}
          >
            <option value="all">All toxicity levels</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
          </select>
        </label>

        <label>
          <span>From timestamp</span>
          <input
            type="datetime-local"
            value={filters.startTimestamp}
            onChange={(event) => onChange({ startTimestamp: event.currentTarget.value })}
          />
        </label>

        <label>
          <span>To timestamp</span>
          <input
            type="datetime-local"
            value={filters.endTimestamp}
            onChange={(event) => onChange({ endTimestamp: event.currentTarget.value })}
          />
        </label>

        <div className="range-row">
          <label>
            <span>Min temp</span>
            <input
              type="number"
              inputMode="decimal"
              step="0.1"
              value={filters.minTemperature}
              onChange={(event) => onChange({ minTemperature: event.currentTarget.value })}
              placeholder="C"
            />
          </label>
          <label>
            <span>Max temp</span>
            <input
              type="number"
              inputMode="decimal"
              step="0.1"
              value={filters.maxTemperature}
              onChange={(event) => onChange({ maxTemperature: event.currentTarget.value })}
              placeholder="C"
            />
          </label>
        </div>

        <div className="range-row">
          <label>
            <span>Min humidity</span>
            <input
              type="number"
              inputMode="decimal"
              step="1"
              value={filters.minHumidity}
              onChange={(event) => onChange({ minHumidity: event.currentTarget.value })}
              placeholder="%"
            />
          </label>
          <label>
            <span>Max humidity</span>
            <input
              type="number"
              inputMode="decimal"
              step="1"
              value={filters.maxHumidity}
              onChange={(event) => onChange({ maxHumidity: event.currentTarget.value })}
              placeholder="%"
            />
          </label>
        </div>
      </div>

      <button className="secondary-button" type="button" onClick={onReset}>
        Reset filters
      </button>
    </section>
  );
}

function MapBounds({ records }: { records: CityScanRecord[] }) {
  const map = useMap();

  useEffect(() => {
    if (records.length === 0) {
      map.setView(barcelonaCenter, 13);
      return;
    }

    if (records.length === 1) {
      map.setView([records[0].latitude, records[0].longitude], 15);
      return;
    }

    const bounds = L.latLngBounds(records.map((record) => [record.latitude, record.longitude]));
    map.fitBounds(bounds, { padding: [32, 32], maxZoom: 15 });
  }, [map, records]);

  return null;
}

function SelectedRecordFocus({ record }: { record: CityScanRecord | null }) {
  const map = useMap();

  useEffect(() => {
    if (!record) {
      return;
    }

    map.setView([record.latitude, record.longitude], Math.max(map.getZoom(), 15));
  }, [map, record]);

  return null;
}

function ToxicityLevelBadge({ toxicityLevel }: { toxicityLevel: ToxicityLevel }) {
  return <span className={`toxicity-badge ${toxicityLevel.toLowerCase()}`}>{toxicityLevel}</span>;
}

function DetectionBadge({ detected }: { detected: boolean }) {
  return (
    <span className={`detection-badge ${detected ? 'detected' : 'clear'}`}>
      {detected ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
      {detected ? 'Detected' : 'Clear'}
    </span>
  );
}

function ScanMarker({
  record,
  selected,
  openPopup,
  onSelect
}: {
  record: CityScanRecord;
  selected: boolean;
  openPopup: boolean;
  onSelect: (recordId: string) => void;
}) {
  const markerRef = useRef<L.Marker | null>(null);

  useEffect(() => {
    if (openPopup) {
      markerRef.current?.openPopup();
    }
  }, [openPopup]);

  return (
    <Marker
      ref={markerRef}
      position={[record.latitude, record.longitude]}
      icon={createMarkerIcon(record, selected)}
      eventHandlers={{
        click: () => onSelect(record.id)
      }}
    >
      <Tooltip direction="top" offset={[0, -12]}>
        {record.toxicity_level} toxicity level
      </Tooltip>
      <Popup>
        <div className="marker-popup">
          <strong>{record.id}</strong>
          <span>{formatTimestamp(record.device_timestamp)}</span>
          <span>{record.toxicity_level} toxicity trash</span>
          <span>
            {record.temperature.toFixed(1)} C / {record.humidity.toFixed(0)}%
          </span>
        </div>
      </Popup>
    </Marker>
  );
}

function MapLegend() {
  return (
    <div className="legend">
      <div className="legend-title">Legend</div>
      <div className="legend-row">
        <span className="legend-dot high" />
        High toxicity
      </div>
      <div className="legend-row">
        <span className="legend-dot medium" />
        Medium toxicity
      </div>
    </div>
  );
}

function TrashMap({
  records,
  selectedRecord,
  focusedRecord,
  onSelectRecord
}: {
  records: CityScanRecord[];
  selectedRecord: CityScanRecord | null;
  focusedRecord: CityScanRecord | null;
  onSelectRecord: (recordId: string) => void;
}) {
  const markerRecords = records.filter((record) => record.trash_detected);

  return (
    <section className="map-panel">
      <div className="section-heading map-heading">
        <div>
          <span>Map view</span>
          <h2>Barcelona scan points</h2>
        </div>
        <MapPinned size={20} />
      </div>
      <div className="map-stage">
        <MapContainer center={barcelonaCenter} zoom={13} scrollWheelZoom className="scan-map">
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <MapBounds records={markerRecords} />
          <SelectedRecordFocus record={focusedRecord} />
          {markerRecords.map((record) => (
            <ScanMarker
              key={record.id}
              record={record}
              selected={selectedRecord?.id === record.id}
              openPopup={focusedRecord?.id === record.id}
              onSelect={onSelectRecord}
            />
          ))}
        </MapContainer>
        <MapLegend />
      </div>
    </section>
  );
}

function DetailsPanel({ record }: { record: CityScanRecord | null }) {
  if (!record) {
    return (
      <section className="panel details-panel empty-panel">
        <LocateFixed size={22} />
        <h2>No scan selected</h2>
      </section>
    );
  }

  return (
    <section className="panel details-panel">
      <div className="section-heading">
        <div>
          <span>Selected scan</span>
          <h2>{record.id}</h2>
        </div>
        <DetectionBadge detected={record.trash_detected} />
      </div>

      <dl className="detail-grid">
        <div>
          <dt>Latitude</dt>
          <dd>{record.latitude.toFixed(6)}</dd>
        </div>
        <div>
          <dt>Longitude</dt>
          <dd>{record.longitude.toFixed(6)}</dd>
        </div>
        <div>
          <dt>Temperature</dt>
          <dd>{record.temperature.toFixed(1)} C</dd>
        </div>
        <div>
          <dt>Humidity</dt>
          <dd>{record.humidity.toFixed(0)}%</dd>
        </div>
        <div>
          <dt>Trash detected</dt>
          <dd>{record.trash_detected ? 'true' : 'false'}</dd>
        </div>
        <div>
          <dt>Toxicity level</dt>
          <dd>
            <ToxicityLevelBadge toxicityLevel={record.toxicity_level} />
          </dd>
        </div>
        <div className="full-width">
          <dt>Device timestamp</dt>
          <dd>{formatTimestamp(record.device_timestamp)}</dd>
        </div>
      </dl>
    </section>
  );
}

function RecordsTable({
  records,
  selectedRecordId,
  onSelectRecord
}: {
  records: CityScanRecord[];
  selectedRecordId: string | null;
  onSelectRecord: (recordId: string) => void;
}) {
  function handleKeyDown(event: KeyboardEvent<HTMLTableRowElement>, recordId: string) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onSelectRecord(recordId);
    }
  }

  return (
    <section className="table-panel">
      <div className="section-heading">
        <div>
          <span>Table view</span>
          <h2>Records</h2>
        </div>
        <Table2 size={20} />
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Timestamp</th>
              <th>Trash</th>
              <th>Toxicity</th>
              <th>Temp</th>
              <th>Humidity</th>
              <th>Latitude</th>
              <th>Longitude</th>
            </tr>
          </thead>
          <tbody>
            {records.length === 0 ? (
              <tr>
                <td colSpan={8} className="empty-table-cell">
                  No records match the current filters.
                </td>
              </tr>
            ) : (
              records.map((record) => (
                <tr
                  key={record.id}
                  className={`${selectedRecordId === record.id ? 'selected' : ''} ${record.trash_detected ? 'has-trash' : ''} ${
                    record.toxicity_level === 'High' ? 'high-toxicity' : ''
                  }`}
                  tabIndex={0}
                  onClick={() => onSelectRecord(record.id)}
                  onKeyDown={(event) => handleKeyDown(event, record.id)}
                >
                  <td>{record.id}</td>
                  <td>{formatTimestamp(record.device_timestamp)}</td>
                  <td>
                    <DetectionBadge detected={record.trash_detected} />
                  </td>
                  <td>
                    <ToxicityLevelBadge toxicityLevel={record.toxicity_level} />
                  </td>
                  <td>{record.temperature.toFixed(1)} C</td>
                  <td>{record.humidity.toFixed(0)}%</td>
                  <td>{record.latitude.toFixed(5)}</td>
                  <td>{record.longitude.toFixed(5)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function App() {
  const [mode, setMode] = useState<DataMode>('fake');
  const [records, setRecords] = useState<CityScanRecord[]>([]);
  const [selectedRecordId, setSelectedRecordId] = useState<string | null>(null);
  const [focusedRecordId, setFocusedRecordId] = useState<string | null>(null);
  const [filters, setFilters] = useState<ScanFilters>(defaultFilters);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  async function loadRecords(nextMode: DataMode) {
    setIsLoading(true);
    setError(null);

    try {
      const nextRecords = nextMode === 'fake' ? generateFakeCityScans() : await fetchCityScans();

      setRecords(nextRecords);
      setSelectedRecordId(nextRecords[0]?.id ?? null);
      setFocusedRecordId(null);
      setLastUpdated(new Date());
    } catch (requestError) {
      setRecords([]);
      setSelectedRecordId(null);
      setFocusedRecordId(null);
      setError(requestError instanceof Error ? requestError.message : 'Unable to load scan records.');
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadRecords(mode);
  }, [mode]);

  const filteredRecords = useMemo(() => filterRecords(records, filters), [records, filters]);

  useEffect(() => {
    if (filteredRecords.length === 0 && selectedRecordId !== null) {
      setSelectedRecordId(null);
      return;
    }

    if (filteredRecords.length > 0 && !filteredRecords.some((record) => record.id === selectedRecordId)) {
      setSelectedRecordId(filteredRecords[0].id);
    }
  }, [filteredRecords, selectedRecordId]);

  const selectedRecord = filteredRecords.find((record) => record.id === selectedRecordId) ?? null;
  const focusedRecord = filteredRecords.find((record) => record.id === focusedRecordId) ?? null;

  function handleFilterChange(nextFilters: Partial<ScanFilters>) {
    setFilters((current) => ({
      ...current,
      ...nextFilters
    }));
  }

  function handleSelectRecord(recordId: string) {
    setSelectedRecordId(recordId);
    setFocusedRecordId(recordId);
  }

  return (
    <main className="app-shell">
      <TopBar
        mode={mode}
        isLoading={isLoading}
        lastUpdated={lastUpdated}
        onModeChange={setMode}
        onRefresh={() => void loadRecords(mode)}
      />

      {error ? (
        <section className="state-banner error-state">
          <AlertCircle size={18} />
          <span>{error}</span>
        </section>
      ) : null}

      {isLoading ? (
        <section className="state-banner loading-state">
          <RefreshCw size={18} />
          <span>{mode === 'fake' ? 'Generating fake test data...' : 'Fetching Supabase city_scans records...'}</span>
        </section>
      ) : null}

      {!isLoading && !error && records.length === 0 ? (
        <section className="state-banner empty-state">
          <Database size={18} />
          <span>No records returned.</span>
        </section>
      ) : null}

      <SummaryCards records={filteredRecords} />

      <section className="dashboard-grid">
        <aside className="left-rail">
          <FiltersPanel filters={filters} onChange={handleFilterChange} onReset={() => setFilters(defaultFilters)} />
          <DetailsPanel record={selectedRecord} />
        </aside>

        <div className="workspace">
          <TrashMap
            records={filteredRecords}
            selectedRecord={selectedRecord}
            focusedRecord={focusedRecord}
            onSelectRecord={handleSelectRecord}
          />
          <RecordsTable records={filteredRecords} selectedRecordId={selectedRecordId} onSelectRecord={handleSelectRecord} />
        </div>
      </section>
    </main>
  );
}

export default App;
