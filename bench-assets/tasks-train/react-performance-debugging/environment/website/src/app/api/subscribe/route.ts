// src/app/api/subscribe/route.ts
import { NextRequest, NextResponse } from 'next/server';
import {
  fetchReaderFromService,
  fetchPreferencesFromService,
  fetchReaderDigestFromService,
} from '@/services/api-client';

export const dynamic = 'force-dynamic';

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));

  const [reader, preferences] = await Promise.all([
    fetchReaderFromService(),
    fetchPreferencesFromService(),
  ]);

  const digest = await fetchReaderDigestFromService(reader.id);

  return NextResponse.json({
    success: true,
    reader: { id: reader.id, name: reader.name },
    digest,
    preferences: { timezone: preferences.timezone },
  });
}
