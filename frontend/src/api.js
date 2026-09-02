const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function request(path, options = {}) {
  const res = await fetch(`${API}${path}`, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function uploadCSVs(files) {
  const form = new FormData();
  form.append('works_recommended', files.works_recommended);
  form.append('works_sanctioned', files.works_sanctioned);
  form.append('works_completed', files.works_completed);
  form.append('expenditure', files.expenditure);
  return request('/api/upload', { method: 'POST', body: form });
}

export async function getWorks({ mp = '', state = '', fraud_type = '', min_risk = 0, page = 1, page_size = 50 } = {}) {
  const params = new URLSearchParams();
  if (mp) params.set('mp', mp);
  if (state) params.set('state', state);
  if (fraud_type) params.set('fraud_type', fraud_type);
  if (min_risk > 0) params.set('min_risk', min_risk);
  params.set('page', page);
  params.set('page_size', page_size);
  return request(`/api/works?${params}`);
}

export async function getWorkDetail(workId) {
  return request(`/api/works/${encodeURIComponent(workId)}`);
}

export async function getOffenders(top = 20) {
  return request(`/api/offenders?top=${top}`);
}

export async function getMPs() {
  return request('/api/mps');
}

export async function getSimilar(desc, k = 5) {
  return request('/api/similar', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ desc, k }),
  });
}

export async function getHealth() {
  return request('/health');
}
