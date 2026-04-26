export type ToxicityLevel = 'High' | 'Medium';

export type DataMode = 'real' | 'fake';

export type TrashStatusFilter = 'all' | 'detected' | 'clear';

export type ToxicityLevelFilter = 'all' | ToxicityLevel;

export type CityScanRecord = {
  id: string;
  latitude: number;
  longitude: number;
  temperature: number;
  humidity: number;
  trash_detected: boolean;
  toxicity_level: ToxicityLevel;
  device_timestamp: string;
};

export type ScanFilters = {
  trashStatus: TrashStatusFilter;
  toxicityLevel: ToxicityLevelFilter;
  startTimestamp: string;
  endTimestamp: string;
  minTemperature: string;
  maxTemperature: string;
  minHumidity: string;
  maxHumidity: string;
};

export type SummaryMetric = {
  label: string;
  value: string;
  detail: string;
};
