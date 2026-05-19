import { http, HttpResponse } from 'msw'
import { plantsFixture, diseasesFixture, analysisFixture, statusFixture } from './data'

export const handlers = [
  http.get('http://localhost:8000/plants', () => HttpResponse.json(plantsFixture)),
  http.get('http://localhost:8000/diseases', () => HttpResponse.json(diseasesFixture)),
  http.post('http://localhost:8000/analyses', () =>
    HttpResponse.json({ analysis_id: 'test-id-1' }, { status: 201 }),
  ),
  http.get('http://localhost:8000/analyses/:id', () => HttpResponse.json(analysisFixture)),
  http.get('http://localhost:8000/analyses/:id/status', () => HttpResponse.json(statusFixture)),
  http.post(
    'http://localhost:8000/analyses/:id/approve',
    () => new HttpResponse(null, { status: 200 }),
  ),
  http.post(
    'http://localhost:8000/analyses/:id/reject',
    () => new HttpResponse(null, { status: 200 }),
  ),
  http.delete(
    'http://localhost:8000/analyses/:id',
    () => new HttpResponse(null, { status: 204 }),
  ),
  http.get('http://localhost:8000/analyses/:id/export/:stage', () =>
    new HttpResponse('col1,col2\nval1,val2', {
      headers: { 'Content-Type': 'text/csv' },
    }),
  ),
]
