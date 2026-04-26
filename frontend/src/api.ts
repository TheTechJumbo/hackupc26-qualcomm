import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import type { CityScanRecord, ToxicityLevel } from './types';

type CityScanRow = {
  id: string | number;
  latitude: number | string | null;
  longitude: number | string | null;
  temperature: number | string | null;
  humidity: number | string | null;
  trash_detected: boolean | null;
  toxicity_level: string | null;
  device_timestamp: string | null;
};

let supabaseClient: SupabaseClient | null = null;

function getSupabaseClient(): SupabaseClient {
  const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;
  const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

  if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error('Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY. Add them to frontend/.env.local.');
  }

  if (!supabaseClient) {
    supabaseClient = createClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        persistSession: false,
        autoRefreshToken: false
      }
    });
  }

  return supabaseClient;
}

function isToxicityLevel(value: unknown): value is ToxicityLevel {
  return value === 'High' || value === 'Medium';
}

function toNumber(value: number | string | null, field: string): number {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    throw new Error(`Supabase returned an invalid ${field} value.`);
  }

  return numericValue;
}

function normalizeCityScan(row: CityScanRow): CityScanRecord {
  if (!row.device_timestamp) {
    throw new Error('Supabase returned a row without device_timestamp.');
  }

  return {
    id: String(row.id),
    latitude: toNumber(row.latitude, 'latitude'),
    longitude: toNumber(row.longitude, 'longitude'),
    temperature: toNumber(row.temperature, 'temperature'),
    humidity: toNumber(row.humidity, 'humidity'),
    trash_detected: Boolean(row.trash_detected),
    toxicity_level: isToxicityLevel(row.toxicity_level) ? row.toxicity_level : 'Medium',
    device_timestamp: row.device_timestamp
  };
}

export async function fetchCityScans(): Promise<CityScanRecord[]> {
  const supabase = getSupabaseClient();
  const { data, error } = await supabase
    .from('city_scans')
    .select('id, latitude, longitude, temperature, humidity, trash_detected, toxicity_level, device_timestamp')
    .order('device_timestamp', { ascending: false });

  if (error) {
    throw new Error(error.message);
  }

  return ((data ?? []) as CityScanRow[]).map(normalizeCityScan);
}
