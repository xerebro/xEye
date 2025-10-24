import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import VideoPanel from './components/VideoPanel.jsx';
import Controls from './components/Controls.jsx';
import PTZControls from './components/PTZControls.jsx';
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
  const [monitoring, setMonitoring] = useState(false);
  const monitoringRef = useRef(false);

  useEffect(() => {
    monitoringRef.current = monitoring;
    return () => {
      monitoringRef.current = false;
    };
  }, [monitoring]);

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
    const optimistic = { ...partial };
    if (Object.prototype.hasOwnProperty.call(partial, 'wb_preset')) {
      const preset = partial.wb_preset;
      if (preset != null) {
        optimistic.awb_mode = preset;
        if (preset === 'low_light') {
          optimistic.low_light = true;
          optimistic.awb_enable = true;
        } else {
          optimistic.low_light = false;
        }
      }
      delete optimistic.wb_preset;
    }
    setSettings((prev) => (prev ? { ...prev, ...optimistic } : prev));
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
    setMonitoring(false);
    try {
      const updated = await pantiltHome();
      setPtz(updated);
    } catch (error) {
      showToast(error.message || 'Failed to home PTZ', 'error');
    }
  }, [showToast]);

  useEffect(() => {
    if (!ptz) {
      setMonitoring(false);
    }
  }, [ptz]);

  const panMin = ptz?.limits?.pan?.[0] ?? -90;
  const panMax = ptz?.limits?.pan?.[1] ?? 90;
  const tiltMin = ptz?.limits?.tilt?.[0] ?? -70;
  const tiltMax = ptz?.limits?.tilt?.[1] ?? 70;
  const hasPtz = Boolean(ptz);

  useEffect(() => {
    if (!monitoring || !hasPtz) {
      return undefined;
    }

    let cancelled = false;
    const panLimits = [panMin, panMax];
    const tiltLimits = [tiltMin, tiltMax];

    const clamp = (value, [min, max]) => Math.max(min, Math.min(max, value));
    const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

    const panLeft = clamp(-60, panLimits);
    const panRight = clamp(60, panLimits);
    const tiltTop = clamp(30, tiltLimits);
    const tiltBottom = clamp(-30, tiltLimits);

    const hasPanRange = Math.abs(panRight - panLeft) > 0.01;
    const hasTiltRange = Math.abs(tiltTop - tiltBottom) > 0.01;

    const PAN_STEP = 2;
    const TILT_STEP = 2;
    const PAN_DELAY = 250;
    const TILT_DELAY = 600;

    const safeApply = async (pan, tilt) => {
      if (cancelled || !monitoringRef.current) {
        return;
      }
      try {
        await applyAbsolute({ pan_deg: pan, tilt_deg: tilt });
      } catch (error) {
        console.error(error);
      }
    };

    const cycle = async () => {
      let currentPan = panLeft;
      let currentTilt = tiltTop;
      let panDirection = 1;
      let tiltDirection = -1;

      await safeApply(currentPan, currentTilt);
      await wait(800);

      while (!cancelled && monitoringRef.current) {
        if (hasPanRange) {
          const targetPan = panDirection === 1 ? panRight : panLeft;
          while (
            !cancelled &&
            monitoringRef.current &&
            ((panDirection === 1 && currentPan < targetPan) ||
              (panDirection === -1 && currentPan > targetPan))
          ) {
            currentPan += panDirection * PAN_STEP;
            if (panDirection === 1) {
              currentPan = Math.min(currentPan, targetPan);
            } else {
              currentPan = Math.max(currentPan, targetPan);
            }
            currentPan = clamp(currentPan, panLimits);
            await safeApply(currentPan, currentTilt);
            await wait(PAN_DELAY);
          }
        } else {
          await wait(PAN_DELAY);
        }

        if (cancelled || !monitoringRef.current) {
          break;
        }

        if (hasTiltRange) {
          if (tiltDirection === -1 && currentTilt <= tiltBottom) {
            tiltDirection = 1;
          } else if (tiltDirection === 1 && currentTilt >= tiltTop) {
            tiltDirection = -1;
          }

          let nextTilt = currentTilt + tiltDirection * TILT_STEP;
          if (tiltDirection === -1 && nextTilt < tiltBottom) {
            nextTilt = tiltBottom;
          }
          if (tiltDirection === 1 && nextTilt > tiltTop) {
            nextTilt = tiltTop;
          }

          if (nextTilt !== currentTilt) {
            currentTilt = clamp(nextTilt, tiltLimits);
            await safeApply(currentPan, currentTilt);
            await wait(TILT_DELAY);
          } else {
            await wait(TILT_DELAY);
          }
        } else {
          await wait(TILT_DELAY);
        }

        panDirection *= -1;
      }
    };

    cycle();

    return () => {
      cancelled = true;
    };
  }, [monitoring, hasPtz, panMin, panMax, tiltMin, tiltMax, applyAbsolute]);

  const handleToggleMonitoring = useCallback(() => {
    if (!ptz) {
      showToast('Pan/tilt state not ready yet', 'info');
      return;
    }
    setMonitoring((active) => !active);
  }, [ptz, showToast]);

  const handleZoomUpdate = useCallback((nextZoom) => {
    handleSettingsChange({ zoom: Number(nextZoom) });
  }, [handleSettingsChange]);

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
        <PTZControls
          step={5}
          onRelativeMove={ptz ? applyRelative : undefined}
          zoom={Number(settings?.zoom ?? 1)}
          onZoomChange={settings ? handleZoomUpdate : undefined}
          isMonitoring={monitoring}
          onToggleMonitoring={ptz ? handleToggleMonitoring : undefined}
        />
        <Controls
          settings={settings}
          ptz={ptz}
          onSettingsChange={handleSettingsChange}
          onResetSettings={handleResetSettings}
          onSnapshot={handleSnapshot}
          onAbsoluteMove={applyAbsolute}
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
