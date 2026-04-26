import type { Ride } from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:4000';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers
    },
    ...options
  });

  const data = (await response.json()) as T & { error?: string; details?: string[] };

  if (!response.ok) {
    const details = data.details?.length ? `: ${data.details.join(', ')}` : '';
    throw new Error(`${data.error ?? 'Request failed'}${details}`);
  }

  return data;
}

export async function fetchRides(): Promise<Ride[]> {
  const data = await request<{ rides: Ride[] }>('/api/rides');
  return data.rides;
}

export async function uploadRide(ride: unknown): Promise<Ride> {
  const data = await request<{ ride: Ride }>('/api/rides', {
    method: 'POST',
    body: JSON.stringify(ride)
  });

  return data.ride;
}

export async function resetDemoRides(): Promise<Ride[]> {
  const data = await request<{ rides: Ride[] }>('/api/demo/reset', {
    method: 'POST'
  });

  return data.rides;
}
