import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import VideoPanel from './components/VideoPanel.jsx';
import Controls from './components/Controls.jsx';
import {
  downloadSnapshot,
  getCameraSettings,
  getPanTiltState,
  pantiltAbsolute,
  pantiltHome,
  pantiltRelative,
  patchCameraSettings,
} from './lib/api.js';

const DEBOUNCE_MS = 200;

function useToast() {
  const [toast, setToast] = useState(null);
  const timeoutRef = useRef();

  const show = useCallback((message, tone = 'info') => {
    clearTimeout(timeoutRef.current);
    setToast({ message, tone });
    timeoutRef.current = setTimeout(() => setToast(null), 2500);
  }, []);

  const dismiss = useCallback(() => {
    clearTimeout(timeoutRef.current);
    setToast(null);
  }, []);

  useEffect(() => () => clearTimeout(timeoutRef.current), []);

  return { toast, show, dismiss };
}

function useDebouncedCallback(callback, delay) {
  const timeoutRef = useRef();
  const savedCallback = useRef(callback);

  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  return useCallback((...args) => {
    clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => savedCallback.current(...args), delay);
  }, [delay]);
}

export default function App() {
  const [settings, setSettings] = useState(null);
  const [ptz, setPtz] = useState(null);
  const pendingPatch = useRef({});
  const lastKnownSettings = useRef(null);
  const initialSettings = useRef(null);
  const { toast, show: showToast, dismiss } = useToast();

  useEffect(() => {
    let active = true;
    getCameraSettings()
      .then((data) => {
        if (!active) return;
        setSettings(data);
        lastKnownSettings.current = data;
        initialSettings.current = data;
      })
      .catch((err) => showToast(err.message || 'Failed to load camera settings', 'error'));

    getPanTiltState()
      .then((data) => {
        if (!active) return;
        setPtz(data);
      })
      .catch((err) => showToast(err.message || 'Failed to load pan/tilt state', 'error'));

    return () => {
      active = false;
    };
  }, [showToast]);

  const debouncedSave = useDebouncedCallback(async () => {
    const payload = pendingPatch.current;
    pendingPatch.current = {};
    if (!Object.keys(payload).length) return;

    const snapshotBefore = lastKnownSettings.current;
    try {
      const updated = await patchCameraSettings(payload);
      setSettings(updated);
      lastKnownSettings.current = updated;
    } catch (error) {
      console.error(error);
      setSettings(snapshotBefore);
      showToast(error.message || 'Failed to update settings', 'error');
    }
  }, DEBOUNCE_MS);

  const handleSettingsChange = useCallback((partial) => {
    pendingPatch.current = { ...pendingPatch.current, ...partial };
    setSettings((prev) => (prev ? { ...prev, ...partial } : prev));
    debouncedSave();
  }, [debouncedSave]);

  const handleResetSettings = useCallback(async () => {
    if (!initialSettings.current) return;
    try {
      const updated = await patchCameraSettings(initialSettings.current);
      setSettings(updated);
      lastKnownSettings.current = updated;
      pendingPatch.current = {};
      showToast('Settings reset to defaults', 'success');
    } catch (error) {
      showToast(error.message || 'Failed to reset settings', 'error');
    }
  }, [showToast]);

  const handleSnapshot = useCallback(async () => {
    try {
      await downloadSnapshot();
      showToast('Photo saved');
    } catch (error) {
      showToast(error.message || 'Snapshot failed', 'error');
    }
  }, [showToast]);

  const applyRelative = useCallback(async (delta) => {
    try {
      const updated = await pantiltRelative(delta);
      setPtz(updated);
    } catch (error) {
      showToast(error.message || 'PTZ update failed', 'error');
    }
  }, [showToast]);

  const applyAbsolute = useCallback(async (next) => {
    try {
      const updated = await pantiltAbsolute(next);
      setPtz(updated);
    } catch (error) {
      showToast(error.message || 'PTZ update failed', 'error');
    }
  }, [showToast]);

  const handleHome = useCallback(async () => {
    try {
      const updated = await pantiltHome();
      setPtz(updated);
    } catch (error) {
      showToast(error.message || 'Failed to home PTZ', 'error');
    }
  }, [showToast]);

  useEffect(() => {
    const listener = (event) => {
      if (!ptz) return;
      if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) {
        event.preventDefault();
        const delta = { dpan_deg: 0, dtilt_deg: 0 };
        if (event.key === 'ArrowUp') delta.dtilt_deg = 5;
        if (event.key === 'ArrowDown') delta.dtilt_deg = -5;
        if (event.key === 'ArrowLeft') delta.dpan_deg = -5;
        if (event.key === 'ArrowRight') delta.dpan_deg = 5;
        applyRelative(delta);
      }
      if (event.key.toLowerCase() === 'r') {
        handleResetSettings();
      }
      if (event.code === 'Space') {
        handleSnapshot();
      }
    };
    window.addEventListener('keydown', listener);
    return () => window.removeEventListener('keydown', listener);
  }, [ptz, applyRelative, handleResetSettings, handleSnapshot]);

  const manualBadge = useMemo(() => (settings?.exposure_mode === 'manual' ? 'Manual Exposure' : null), [settings]);

  return (
    <div className="app-root">
      <header className="app-header">
        <div>
          <h1 className="app-title">xEye Camera Control</h1>
          <p className="app-subtitle">Raspberry Pi 5 • OV5647 • MJPEG</p>
        </div>
      </header>
      <main className="app-main">
        <VideoPanel
          badge={manualBadge}
          onRelativeMove={applyRelative}
          onHome={handleHome}
          ptz={ptz}
        />
        <Controls
          settings={settings}
          ptz={ptz}
          onSettingsChange={handleSettingsChange}
          onResetSettings={handleResetSettings}
          onSnapshot={handleSnapshot}
          onAbsoluteMove={applyAbsolute}
          onRelativeMove={applyRelative}
          onHome={handleHome}
        />
      </main>
      {toast && (
        <div role="status" className={`toast toast-${toast.tone}`}>
          <button className="toast-close" onClick={dismiss} aria-label="Dismiss toast">
            ×
          </button>
          <span>{toast.message}</span>
        </div>
      )}
    </div>
  );
}
