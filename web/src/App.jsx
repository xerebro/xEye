import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import VideoPanel from './components/VideoPanel.jsx';
import Controls from './components/Controls.jsx';
import {
  getCameraSettings,
  getPanTiltState,
  pantiltAbsolute,
  pantiltHome,
  pantiltRelative,
  patchCameraSettings,
  takeSnapshot,
} from './lib/api.js';

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

export default function App() {
  const [settings, setSettings] = useState(null);
  const [ptz, setPtz] = useState(null);
  const lastKnownSettings = useRef(null);
  const initialSettings = useRef(null);
  const { toast, show: showToast, dismiss } = useToast();

  useEffect(() => {
    let active = true;
    getCameraSettings()
      .then((data) => {
        if (!active) return;
        const snapshot = { ...data };
        setSettings(snapshot);
        lastKnownSettings.current = snapshot;
        initialSettings.current = { ...snapshot };
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

  useEffect(() => {
    let cancelled = false;
    const poll = () => {
      getPanTiltState()
        .then((data) => {
          if (!cancelled) {
            setPtz(data);
          }
        })
        .catch((error) => {
          if (!cancelled) {
            console.debug('PTZ poll failed', error);
          }
        });
    };
    poll();
    const id = setInterval(poll, 1000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const handleSettingsChange = useCallback((partial) => {
    const snapshotBefore = lastKnownSettings.current ? { ...lastKnownSettings.current } : null;
    setSettings((prev) => (prev ? { ...prev, ...partial } : prev));
    patchCameraSettings(partial)
      .then((updated) => {
        const snapshot = { ...updated };
        setSettings(snapshot);
        lastKnownSettings.current = snapshot;
      })
      .catch((error) => {
        console.error(error);
        if (snapshotBefore) {
          setSettings(snapshotBefore);
          lastKnownSettings.current = snapshotBefore;
        }
        showToast(error.message || 'Failed to update settings', 'error');
      });
  }, [showToast]);

  const handleResetSettings = useCallback(async () => {
    if (!initialSettings.current) return;
    const snapshotBefore = lastKnownSettings.current ? { ...lastKnownSettings.current } : null;
    try {
      const updated = await patchCameraSettings(initialSettings.current, { debounce: false });
      const snapshot = { ...updated };
      setSettings(snapshot);
      lastKnownSettings.current = snapshot;
      initialSettings.current = { ...snapshot };
      showToast('Settings reset to defaults', 'success');
    } catch (error) {
      if (snapshotBefore) {
        setSettings(snapshotBefore);
        lastKnownSettings.current = snapshotBefore;
      }
      showToast(error.message || 'Failed to reset settings', 'error');
    }
  }, [showToast]);

  const handleSnapshot = useCallback(async () => {
    try {
      await takeSnapshot();
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
