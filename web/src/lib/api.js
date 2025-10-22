export const API_BASE = '/api';

const JSON_HEADERS = { 'Content-Type': 'application/json' };

async function handleJsonResponse(res) {
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || res.statusText);
  }
  return res.json();
}

export async function getCameraSettings() {
  const res = await fetch(`${API_BASE}/camera/settings`);
  return handleJsonResponse(res);
}

let patchTimer;
let pendingPatch = {};
const patchWaiters = [];
let flushChain = Promise.resolve();

async function sendCameraPatch(payload) {
  if (!Object.keys(payload).length) {
    return getCameraSettings();
  }
  const res = await fetch(`${API_BASE}/camera/settings`, {
    method: 'PATCH',
    headers: JSON_HEADERS,
    body: JSON.stringify(payload),
  });
  return handleJsonResponse(res);
}

async function flushPendingPatch() {
  const payload = pendingPatch;
  pendingPatch = {};
  const listeners = patchWaiters.splice(0, patchWaiters.length);
  if (!listeners.length) {
    return;
  }

  try {
    const updated = await sendCameraPatch(payload);
    listeners.forEach(({ resolve }) => resolve(updated));
  } catch (error) {
    listeners.forEach(({ reject }) => reject(error));
  }
}

function schedulePatchFlush(immediate = false) {
  const trigger = () => {
    flushChain = flushChain.then(() => flushPendingPatch()).catch(() => undefined);
  };

  if (immediate) {
    if (patchTimer) {
      clearTimeout(patchTimer);
      patchTimer = undefined;
    }
    trigger();
    return;
  }

  if (patchTimer) {
    clearTimeout(patchTimer);
  }
  patchTimer = setTimeout(() => {
    patchTimer = undefined;
    trigger();
  }, 200);
}

export function patchCameraSettings(partial, options = {}) {
  const { debounce = true } = options;
  Object.assign(pendingPatch, partial);

  return new Promise((resolve, reject) => {
    patchWaiters.push({ resolve, reject });
    schedulePatchFlush(!debounce);
  });
}

export async function getPanTiltState() {
  const res = await fetch(`${API_BASE}/pantilt`);
  return handleJsonResponse(res);
}

export async function pantiltAbsolute(payload) {
  const res = await fetch(`${API_BASE}/pantilt/absolute`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(payload),
  });
  return handleJsonResponse(res);
}

export async function pantiltRelative(payload) {
  const res = await fetch(`${API_BASE}/pantilt/relative`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(payload),
  });
  return handleJsonResponse(res);
}

export async function ptzNudge(panDeg, tiltDeg) {
  const res = await fetch(`${API_BASE}/ptz/relative`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ pan_deg: panDeg, tilt_deg: tiltDeg }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || res.statusText);
  }
  return res.json().catch(() => ({}));
}

export async function pantiltHome() {
  const res = await fetch(`${API_BASE}/pantilt/home`, { method: 'POST' });
  return handleJsonResponse(res);
}

export async function takeSnapshot() {
  const res = await fetch(`${API_BASE}/snapshot.jpg`);
  if (!res.ok) {
    throw new Error('Failed to capture snapshot');
  }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const ts = new Date().toISOString().replace(/[:.]/g, '').slice(0, 15);
  const link = document.createElement('a');
  link.href = url;
  link.download = `photo_${ts}.jpg`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}
