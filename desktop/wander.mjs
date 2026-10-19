/** Desktop walking: how far the window may travel and where it is at each moment of a walk.
 *
 * The renderer plays walk_start, the walk loop and walk_stop; the window travels in step with
 * them so the planted foot doesn't skate. walk_start grows the stride over one ramp with the
 * in-out curve below (4u³, then 1 - (2 - 2u)³ / 2) and walk_stop is its mirror, so the window's
 * speed follows the same curve: the ramps each cover half a ramp at full speed.
 */

const MARGIN = 8; // pixels kept between the pet pane and the edge of the work area

export function ease(u) {
    const x = Math.min(1, Math.max(0, u));
    return x < 0.5 ? 4 * x ** 3 : 1 - (2 - 2 * x) ** 3 / 2;
}

/** Distance covered over a ramp at full speed 1, from its start to fraction u (0..1). */
export function rampDistance(u) {
    const x = Math.min(1, Math.max(0, u));
    if (x < 0.5) return x ** 4;
    return 0.0625 + (x - 0.5) + ((2 - 2 * x) ** 4 - 1) / 16;
}

/** A walk of `distance` pixels at `speed` px/s with ramps of `ramp` seconds, or null when the
 * room is shorter than the two ramps need. Times in seconds, positions in pixels from the start. */
export function walkPlan(distance, speed, ramp) {
    if (![distance, speed, ramp].every(Number.isFinite) || distance <= 0 || speed <= 0 || ramp <= 0) return null;
    const cruise = distance / speed - ramp;
    if (cruise < 0) return null;
    const duration = 2 * ramp + cruise;
    const at = t => {
        if (t <= 0) return 0;
        if (t < ramp) return speed * ramp * rampDistance(t / ramp);
        if (t < ramp + cruise) return speed * (ramp / 2 + t - ramp);
        if (t < duration) {
            const u = (t - ramp - cruise) / ramp;
            return speed * (ramp / 2 + cruise + ramp * (u - rampDistance(u)));
        }
        return distance;
    };
    return {distance, speed, ramp, cruise, duration, at};
}

/** Cut a walk short from time `t`: settle over one ramp from the speed it has then. Returns the
 * distance still to go and the plan for it (a ramp-down only). */
export function stopPlan(plan, t) {
    const time = Math.min(Math.max(0, t), plan.duration);
    let fraction = 1; // of full speed at `time`
    if (time < plan.ramp) fraction = ease(time / plan.ramp);
    else if (time >= plan.ramp + plan.cruise) fraction = 1 - ease((time - plan.ramp - plan.cruise) / plan.ramp);
    const speed = plan.speed * fraction;
    const remaining = Math.min(plan.distance - plan.at(time), speed * plan.ramp / 2);
    return {remaining, at: s => Math.min(remaining, speed * plan.ramp * (Math.min(1, Math.max(0, s / plan.ramp)) - rampDistance(s / plan.ramp)))};
}

/** How far the pet pane can walk in `direction` (-1 left, 1 right; 0 picks the roomier side)
 * without leaving the work area, capped at `wanted`. */
export function walkRoom(windowX, petX, petWidth, area, direction, wanted) {
    const left = windowX + petX - (area.x + MARGIN);
    const right = area.x + area.width - MARGIN - (windowX + petX + petWidth);
    const side = direction === 0 ? (right >= left ? 1 : -1) : Math.sign(direction);
    const room = Math.max(0, side > 0 ? right : left);
    return {direction: side, distance: Math.max(0, Math.min(wanted, room))};
}
