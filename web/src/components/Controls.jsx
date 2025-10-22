import { useEffect, useMemo, useState } from 'react';

const EXPOSURE_MIN = 100;
const EXPOSURE_MAX = 1_000_000;

function toExposureSlider(value) {
  const min = Math.log10(EXPOSURE_MIN);
  const max = Math.log10(EXPOSURE_MAX);
  const safe = Math.min(Math.max(value, EXPOSURE_MIN), EXPOSURE_MAX);
  return ((Math.log10(safe) - min) / (max - min)) * 100;
}

function fromExposureSlider(value) {
  const min = Math.log10(EXPOSURE_MIN);
  const max = Math.log10(EXPOSURE_MAX);
  const exp = min + (value / 100) * (max - min);
  return Math.round(10 ** exp);
}

export default function Controls({
  settings,
  ptz,
  onSettingsChange,
  onResetSettings,
  onSnapshot,
  onAbsoluteMove,
  onRelativeMove,
  onHome,
}) {
  const [pan, setPan] = useState(0);
  const [tilt, setTilt] = useState(0);

  useEffect(() => {
    if (ptz) {
      setPan(ptz.pan_deg);
      setTilt(ptz.tilt_deg);
    }
  }, [ptz]);

  const exposureSlider = useMemo(() => (settings ? toExposureSlider(settings.exposure_time_us || EXPOSURE_MIN) : 0), [settings]);

  if (!settings) {
    return (
      <aside className="card">
        <p>Loading camera controls…</p>
      </aside>
    );
  }

  const isoGain = Number(settings.iso_gain ?? 1);
  const brightness = Number(settings.brightness ?? 0);
  const contrast = Number(settings.contrast ?? 1);
  const saturation = Number(settings.saturation ?? 1);
  const sharpness = Number(settings.sharpness ?? 1);
  const lowLight = Boolean(settings.low_light);
  const zoom = Number(settings.zoom ?? 1);

  const handleExposureSlider = (event) => {
    onSettingsChange({ exposure_time_us: fromExposureSlider(Number(event.target.value)) });
  };

  const handleIso = (event) => {
    onSettingsChange({ iso_gain: Number(event.target.value) });
  };

  const handleAwbEnable = (event) => {
    onSettingsChange({ awb_enable: event.target.checked });
  };

  const handleAwbMode = (event) => {
    onSettingsChange({ awb_mode: event.target.value });
  };

  const handleLowLight = (event) => {
    onSettingsChange({ low_light: event.target.checked });
  };

  const handleRange = (key) => (event) => {
    onSettingsChange({ [key]: Number(event.target.value) });
  };

  const handleZoom = (event) => {
    onSettingsChange({ zoom: Number(event.target.value) });
  };

  const handleAbsoluteSubmit = (event) => {
    event.preventDefault();
    onAbsoluteMove?.({ pan_deg: pan, tilt_deg: tilt });
  };

  return (
    <aside className="card">
      <div className="controls-grid">
        <section className="control-group" aria-label="Camera settings">
          <h2>Camera</h2>
          <div className="control-row">
            <label htmlFor="exposure-auto">Exposure mode</label>
            <div className="button-row">
              <button
                type="button"
                className={`ghost-button${settings.exposure_mode === 'auto' ? ' active' : ''}`}
                id="exposure-auto"
                onClick={() => onSettingsChange({ exposure_mode: 'auto' })}
              >
                Auto
              </button>
              <button
                type="button"
                className={`ghost-button${settings.exposure_mode === 'manual' ? ' active' : ''}`}
                onClick={() => onSettingsChange({ exposure_mode: 'manual' })}
              >
                Manual
              </button>
            </div>
          </div>
          {settings.exposure_mode === 'manual' && (
            <>
              <div className="control-row">
                <label htmlFor="exposure-time">Exposure time ({settings.exposure_time_us} µs)</label>
                <input
                  id="exposure-time"
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  value={exposureSlider}
                  onChange={handleExposureSlider}
                />
              </div>
              <div className="control-row">
                <label htmlFor="iso-gain">ISO / Gain ({isoGain.toFixed(1)}×)</label>
                <input
                  id="iso-gain"
                  type="range"
                  min="1"
                  max="8"
                  step="0.1"
                  value={isoGain}
                  onChange={handleIso}
                />
              </div>
            </>
          )}
          <div className="control-row">
            <label htmlFor="awb-enable">
              <input
                id="awb-enable"
                type="checkbox"
                checked={settings.awb_enable}
                onChange={handleAwbEnable}
              />{' '}
              Auto white balance
            </label>
            <select
              aria-label="White balance mode"
              value={settings.awb_mode}
              onChange={handleAwbMode}
              disabled={!settings.awb_enable}
            >
              <option value="auto">Auto</option>
              <option value="incandescent">Incandescent</option>
              <option value="fluorescent">Fluorescent</option>
              <option value="daylight">Daylight</option>
              <option value="cloudy">Cloudy</option>
            </select>
          </div>
          <div className="control-row">
            <label htmlFor="low-light" title="Available in auto exposure mode">
              <input
                id="low-light"
                type="checkbox"
                checked={lowLight}
                disabled={settings.exposure_mode !== 'auto'}
                onChange={handleLowLight}
              />{' '}
              Low light mode
            </label>
          </div>
          <div className="control-row">
            <label htmlFor="brightness">Brightness ({brightness.toFixed(2)})</label>
            <input
              id="brightness"
              type="range"
              min="-1"
              max="1"
              step="0.05"
              value={brightness}
              onChange={handleRange('brightness')}
            />
          </div>
          <div className="control-row">
            <label htmlFor="contrast">Contrast ({contrast.toFixed(2)})</label>
            <input
              id="contrast"
              type="range"
              min="0"
              max="2"
              step="0.05"
              value={contrast}
              onChange={handleRange('contrast')}
            />
          </div>
          <div className="control-row">
            <label htmlFor="saturation">Saturation ({saturation.toFixed(2)})</label>
            <input
              id="saturation"
              type="range"
              min="0"
              max="2"
              step="0.05"
              value={saturation}
              onChange={handleRange('saturation')}
            />
          </div>
          <div className="control-row">
            <label htmlFor="sharpness">Sharpness ({sharpness.toFixed(2)})</label>
            <input
              id="sharpness"
              type="range"
              min="0"
              max="2"
              step="0.05"
              value={sharpness}
              onChange={handleRange('sharpness')}
            />
          </div>
          <div className="control-row">
            <label htmlFor="zoom">Zoom ({zoom.toFixed(1)}×)</label>
            <input
              id="zoom"
              type="range"
              min="1"
              max="4"
              step="0.1"
              value={zoom}
              onChange={handleZoom}
            />
          </div>
        </section>

        <section className="control-group" aria-label="Pan tilt controls">
          <h2>Pan &amp; Tilt</h2>
          <form className="control-row" onSubmit={handleAbsoluteSubmit}>
            <label htmlFor="pan-angle">Pan angle (°)</label>
            <input
              id="pan-angle"
              type="number"
              value={pan}
              step="1"
              min={ptz?.limits.pan[0] ?? -90}
              max={ptz?.limits.pan[1] ?? 90}
              onChange={(event) => setPan(Number(event.target.value))}
            />
            <label htmlFor="tilt-angle">Tilt angle (°)</label>
            <input
              id="tilt-angle"
              type="number"
              value={tilt}
              step="1"
              min={ptz?.limits.tilt[0] ?? -70}
              max={ptz?.limits.tilt[1] ?? 70}
              onChange={(event) => setTilt(Number(event.target.value))}
            />
            <div className="button-row">
              <button type="submit" className="primary-button">
                Move
              </button>
              <button type="button" className="ghost-button" onClick={() => onHome?.()}>
                Home
              </button>
            </div>
          </form>
          <div className="button-row">
            <button type="button" className="ghost-button" onClick={() => onRelativeMove?.({ dpan_deg: -5, dtilt_deg: 0 })}>
              ◀ Left
            </button>
            <button type="button" className="ghost-button" onClick={() => onRelativeMove?.({ dpan_deg: 5, dtilt_deg: 0 })}>
              Right ▶
            </button>
            <button type="button" className="ghost-button" onClick={() => onRelativeMove?.({ dpan_deg: 0, dtilt_deg: 5 })}>
              ▲ Up
            </button>
            <button type="button" className="ghost-button" onClick={() => onRelativeMove?.({ dpan_deg: 0, dtilt_deg: -5 })}>
              Down ▼
            </button>
          </div>
        </section>

        <section className="control-group" aria-label="Actions">
          <h2>Actions</h2>
          <div className="button-row">
            <button type="button" className="primary-button" onClick={onSnapshot}>
              Take photo
            </button>
            <button type="button" className="ghost-button" onClick={onResetSettings}>
              Reset settings
            </button>
          </div>
        </section>
      </div>
    </aside>
  );
}
