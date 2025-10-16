const JSON_HEADERS = { 'Content-Type': 'application/json' };

async function handleJsonResponse(res) {
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || res.statusText);
  }
  return res.json();
}

export async function getCameraSettings() {
  const res = await fetch('/api/camera/settings');
  return handleJsonResponse(res);
}

export async function patchCameraSettings(partial) {
  const res = await fetch('/api/camera/settings', {
    method: 'PATCH',
    headers: JSON_HEADERS,
    body: JSON.stringify(partial),
  });
  return handleJsonResponse(res);
}

export async function getPanTiltState() {
  const res = await fetch('/api/pantilt');
  return handleJsonResponse(res);
}

export async function pantiltAbsolute(payload) {
  const res = await fetch('/api/pantilt/absolute', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(payload),
  });
  return handleJsonResponse(res);
}

export async function pantiltRelative(payload) {
  const res = await fetch('/api/pantilt/relative', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(payload),
  });
  return handleJsonResponse(res);
}

export async function pantiltHome() {
  const res = await fetch('/api/pantilt/home', { method: 'POST' });
  return handleJsonResponse(res);
}

export async function downloadSnapshot() {
  const res = await fetch('/api/snapshot.jpg');
  if (!res.ok) {
    throw new Error('Failed to capture snapshot');
  }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const timestamp = new Date().toISOString().replace(/[-:]/g, '').split('.')[0];
  const link = document.createElement('a');
  link.href = url;
  link.download = `photo_${timestamp}.jpg`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}
