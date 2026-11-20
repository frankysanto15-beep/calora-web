// Lógica pura de la mascota (sin DOM) para poder probarla con node.
export const DECAY_PER_HOUR = 2;   // de 100 a 0 en ~2 días sin taps
export const TAP_GAIN = 0.4;
export const DAILY_GOAL = 50;      // taps al día para sumar racha

const DAY = 864e5;
const day = t => new Date(t).toLocaleDateString('en-CA'); // AAAA-MM-DD hora local

export const fresh = now => ({ weight: 60, updated: now, streak: 0, lastDay: null, todayTaps: 0, today: day(now) });

export function tick(s, now) {
  const weight = Math.max(0, s.weight - (now - s.updated) / 36e5 * DECAY_PER_HOUR);
  const d = day(now);
  const todayTaps = d === s.today ? s.todayTaps : 0;
  const alive = s.lastDay === d || s.lastDay === day(now - DAY);
  return { ...s, weight, updated: now, today: d, todayTaps, streak: alive ? s.streak : 0 };
}

export function tap(s, now, n = 1) {
  s = tick(s, now);
  const todayTaps = s.todayTaps + n;
  let { streak, lastDay } = s;
  if (todayTaps >= DAILY_GOAL && lastDay !== s.today) {
    streak = lastDay === day(now - DAY) ? streak + 1 : 1;
    lastDay = s.today;
  }
  return { ...s, weight: Math.min(100, s.weight + TAP_GAIN * n), todayTaps, streak, lastDay };
}

// Al conectarse, los dos teléfonos se quedan con lo mejor de cada uno.
export function merge(a, b, now) {
  a = tick(a, now); b = tick(b, now);
  return { ...a, weight: Math.max(a.weight, b.weight), streak: Math.max(a.streak, b.streak),
    todayTaps: Math.max(a.todayTaps, b.todayTaps), lastDay: [a.lastDay, b.lastDay].sort().pop() ?? null };
}

export const mood = w => w >= 70 ? '¡Gordito y feliz!' : w >= 40 ? 'Contento' : w >= 15 ? 'Tiene hambre…' : 'Muy flaquito 😢';
