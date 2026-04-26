export type RoutePoint = {
  lat: number;
  lon: number;
  timestamp: string;
};

export type RideEvent = {
  id: string;
  lat: number;
  lon: number;
  timestamp: string;
  light: number;
  temperature: number;
  humidity?: number;
  aiLabel: string;
  confidence: number;
  eventType: string;
};

export type Ride = {
  id: string;
  bikeId: string;
  startedAt: string;
  endedAt: string;
  agencyNotes?: string;
  route: RoutePoint[];
  events: RideEvent[];
};

export type LayerState = {
  temperature: boolean;
  light: boolean;
  labels: boolean;
  anomalies: boolean;
};
