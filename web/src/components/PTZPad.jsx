import { useCallback } from 'react';
import { ptzNudge } from '../lib/api.js';

export default function PTZPad({ step = 1 }) {
  const nudge = useCallback(async (panDeg, tiltDeg) => {
    try {
      await ptzNudge(panDeg, tiltDeg);
    } catch (error) {
      console.debug('PTZ nudge failed', error);
    }
  }, []);

  const stepValue = typeof step === 'number' && !Number.isNaN(step) ? step : 1;
  const up = useCallback(() => nudge(0, stepValue), [nudge, stepValue]);
  const down = useCallback(() => nudge(0, -stepValue), [nudge, stepValue]);
  const left = useCallback(() => nudge(-stepValue, 0), [nudge, stepValue]);
  const right = useCallback(() => nudge(stepValue, 0), [nudge, stepValue]);

  return (
    <div className="ptz-pad">
      <div className="ptz-row center">
        <button type="button" className="ghost-button" onClick={up}>
          ▲ Up
        </button>
      </div>
      <div className="ptz-row space">
        <button type="button" className="ghost-button" onClick={left}>
          ◀ Left
        </button>
        <button type="button" className="ghost-button" onClick={right}>
          Right ▶
        </button>
      </div>
      <div className="ptz-row center">
        <button type="button" className="ghost-button" onClick={down}>
          ▼ Down
        </button>
      </div>
    </div>
  );
}
