#!/usr/bin/gjs -m
// Native presentation only; the existing loopback server owns identity, audio and tools.
import Gtk from 'gi://Gtk?version=3.0';
import Gdk from 'gi://Gdk?version=3.0';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GLibUnix from 'gi://GLibUnix';
import WebKit from 'gi://WebKit2?version=4.1';
import Cairo from 'cairo';
import {inputMask} from './input-mask.mjs';
import {desktopLayout} from './layout.mjs';
import {stopPlan, walkPlan, walkRoom} from './wander.mjs';

const url = GLib.getenv('SIRO_DESKTOP_URL') || 'http://127.0.0.1:8000/desktop';
const parsed = GLib.Uri.parse(url, GLib.UriFlags.NONE);
if (parsed.get_scheme() !== 'http' || !['127.0.0.1', 'localhost'].includes(parsed.get_host()) || parsed.get_path() !== '/desktop' || parsed.get_userinfo() || parsed.get_query())
    throw new Error('Desktop requires the exact loopback /desktop URL without credentials/query');
const origin = `http://${parsed.get_host()}:${parsed.get_port() > 0 ? parsed.get_port() : 80}`;
const reportDirectory = GLib.getenv('SIRO_DESKTOP_REPORT_DIR');
const app = new Gtk.Application({application_id: 'org.siro.Companion', flags: Gio.ApplicationFlags.FLAGS_NONE});
let window, web, center, pendingSnapshot = false, timer = 0, ready = false, lastChat = false;
let samples = 0, lastRegion = 0, scale = 1, layoutTimer = 0, controlsHeight = 132;
let walk = null; // the walk in progress: the window travels while the renderer plays the steps
const state = {protocol: 1, toolkit: 'GTK3/WebKitGTK4.1', backend: GLib.getenv('GDK_BACKEND') || 'default', sandbox: false, ready: false, alpha: false, input_regions: 0};
const hostFile = Gio.File.new_for_uri(import.meta.url);
state.host_source_sha256 = GLib.compute_checksum_for_data(GLib.ChecksumType.SHA256, hostFile.load_contents(null)[1]);
function saveState() {
    if (!reportDirectory) return;
    GLib.mkdir_with_parents(reportDirectory, 448);
    GLib.file_set_contents(GLib.build_filenamev([reportDirectory, 'native-state.json']), JSON.stringify(state, null, 2));
}
function permitted(uri) {
    try { const p = GLib.Uri.parse(uri, GLib.UriFlags.NONE); return p.get_scheme() === 'http' && p.get_host() === parsed.get_host() && (p.get_port() > 0 ? p.get_port() : 80) === (parsed.get_port() > 0 ? parsed.get_port() : 80); }
    catch (_) { return false; }
}
function restrict(view) {
    view.connect('decide-policy', (_view, decision, type) => {
        if (type === WebKit.PolicyDecisionType.NAVIGATION_ACTION || type === WebKit.PolicyDecisionType.NEW_WINDOW_ACTION) {
            if (!permitted(decision.get_request().get_uri()) || type === WebKit.PolicyDecisionType.NEW_WINDOW_ACTION) { decision.ignore(); return true; }
        }
        return false;
    });
    view.connect('permission-request', (_view, request) => {
        const audioOnly = request instanceof WebKit.UserMediaPermissionRequest &&
            request.is_for_audio_device && !request.is_for_video_device;
        if (!audioOnly || !permitted(view.get_uri() || '')) { request.deny(); return true; }
        const dialog = new Gtk.MessageDialog({transient_for: window, modal: true,
            message_type: Gtk.MessageType.QUESTION, buttons: Gtk.ButtonsType.NONE,
            text: '允許這次使用麥克風嗎？', secondary_text: '只在你按開始說話後錄音；辨識使用目前設定的語音服務。'});
        dialog.add_button('取消', Gtk.ResponseType.CANCEL);
        dialog.add_button('允許這次', Gtk.ResponseType.ACCEPT);
        dialog.connect('response', (_dialog, response) => {
            if (response === Gtk.ResponseType.ACCEPT && permitted(view.get_uri() || '')) request.allow();
            else request.deny();
            dialog.destroy();
        });
        dialog.show_all(); return true;
    });
    view.connect('create', () => null);
}
function evaluate(script) {
    if (!web) return;
    web.evaluate_javascript(script, -1, null, null, null, (_view, result) => {
        try { web.evaluate_javascript_finish(result); } catch (_) { /* closed/reloading view */ }
    });
}
function queueShape() {
    if (layoutTimer) GLib.source_remove(layoutTimer);
    layoutTimer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 160, () => {
        layoutTimer = 0; updateShape(); return GLib.SOURCE_REMOVE;
    });
}
function workArea() {
    const display = Gdk.Display.get_default();
    const monitor = window.get_window() ? display.get_monitor_at_window(window.get_window()) : display.get_primary_monitor();
    return (monitor || display.get_monitor(0))?.get_workarea() ?? null;
}
// ---- Walking: the renderer asks to walk (speed, wanted distance, ramp and turning lead-in);
// the window then travels on the same speed curve as her steps, inside the work area. Anything
// that takes the window over (a drag, the chat, a new layout, hiding, a monitor change) halts it.
function walkReport(update) {
    state.walk = update; saveState();
    evaluate(`window.siroDesktopView?.walkUpdate(${JSON.stringify(update)})`);
}
function startWalk(message) {
    haltWalk('replaced');
    const area = workArea(), layout = state.layout;
    if (lastChat || !area || !layout) return walkReport({id: message.id, state: 'refused', reason: lastChat ? 'chat' : 'layout'});
    const [x, y] = window.get_position();
    const room = walkRoom(x, layout.petX, layout.petWidth, area, message.direction, message.distance);
    const plan = walkPlan(room.distance, message.speed, message.ramp, message.cycle ?? 0);
    if (!plan) return walkReport({id: message.id, state: 'refused', reason: 'room'});
    const now = GLib.get_monotonic_time() / 1e6;
    walk = {id: message.id, direction: room.direction, startX: x, y, plan, began: now + message.delay, stop: null};
    walk.timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 16, stepWalk);
    walkReport({id: walk.id, state: 'started', direction: walk.direction, distance: plan.distance, ramp: plan.ramp, cruise: plan.cruise, delay: message.delay});
}
function stepWalk() {
    if (!walk || !window) return GLib.SOURCE_REMOVE;
    const now = GLib.get_monotonic_time() / 1e6;
    let offset, done;
    if (walk.stop) {
        const s = now - walk.stop.since;
        offset = walk.stop.base + walk.stop.plan.at(s); done = s >= walk.plan.ramp;
    } else {
        const t = now - walk.began;
        offset = walk.plan.at(t); done = t >= walk.plan.duration;
    }
    const area = workArea(), layout = state.layout;
    let next = walk.startX + walk.direction * offset;
    if (area && layout) next = Math.max(area.x - layout.petX, Math.min(next, area.x + area.width - layout.petX - layout.petWidth));
    window.move(Math.round(next), walk.y);
    if (!done) return GLib.SOURCE_CONTINUE;
    walk.timer = 0; finishWalk('arrived');
    return GLib.SOURCE_REMOVE;
}
function stopWalk(id) {
    if (!walk || walk.id !== id || walk.stop) return;
    const now = GLib.get_monotonic_time() / 1e6, t = now - walk.began;
    if (t <= 0) return haltWalk('cancelled');
    const plan = stopPlan(walk.plan, t);
    walk.stop = {since: now, base: walk.plan.at(t), plan};
    walkReport({id, state: 'stopping', remaining: plan.remaining});
}
function finishWalk(reason) {
    if (!walk) return;
    const id = walk.id;
    if (walk.timer) GLib.source_remove(walk.timer);
    walk = null;
    walkReport({id, state: 'ended', reason});
    queueShape();
}
function haltWalk(reason) { if (walk) finishWalk(reason); }
function applyLayout() {
    if (!window || !web) return;
    haltWalk('layout');
    const area = workArea();
    if (!area) return;
    const previous = state.layout, [x, y] = window.get_position();
    const roleX = x + (previous?.petX || 0), roleBottom = y + (previous?.petHeight || 640);
    const layout = desktopLayout(scale, lastChat, Math.min(4096, area.width), Math.min(4096, area.height), controlsHeight);
    // Keep the role anchored when the panel fits to its left near a screen edge.
    if (lastChat && layout.chatY === 8 && roleX + layout.width > area.x + area.width && roleX - layout.chatWidth - 12 >= area.x) {
        layout.paneX = layout.chatWidth + 12; layout.petX += layout.paneX; layout.chatX = 0;
    }
    window.resize(layout.width, layout.height);
    window.move(Math.max(area.x, Math.min(roleX - layout.petX, area.x + area.width - layout.width)),
        Math.max(area.y, Math.min(roleBottom - layout.petHeight, area.y + area.height - layout.height)));
    state.layout = layout; state.scale = layout.scale; state.chat_open = lastChat;
    evaluate(`window.siroDesktopView?.setLayout(${JSON.stringify(layout)})`);
    saveState(); queueShape();
}
function openCenter() {
    if (!center) {
        center = new Gtk.ApplicationWindow({application: app, title: 'SIRO · 控制台', default_width: 1080, default_height: 760});
        const view = new WebKit.WebView({web_context: web.get_context()});
        restrict(view); center.add(view);
        view.load_uri(`${origin}/?view=control`);
        center.connect('delete-event', () => { center.hide(); return true; });
    }
    center.show_all(); center.present();
}
function updateShape() {
    if (!web || !window || pendingSnapshot || !window.get_visible() || web.is_loading) return GLib.SOURCE_CONTINUE;
    pendingSnapshot = true;
    web.get_snapshot(WebKit.SnapshotRegion.VISIBLE, WebKit.SnapshotOptions.TRANSPARENT_BACKGROUND, null, (_view, result) => {
        pendingSnapshot = false;
        if (!window) return;
        try {
            const surface = web.get_snapshot_finish(result);
            const image = Gdk.pixbuf_get_from_surface(surface, 0, 0, surface.getWidth(), surface.getHeight());
            if (!image) throw new Error('Desktop snapshot pixels are unavailable');
            const pixels = image.get_pixels(), channels = image.get_n_channels(), stride = image.get_rowstride();
            const width = image.get_width(), height = image.get_height();
            const region = new Cairo.Region();
            const {rectangles, occupied} = inputMask(pixels, width, height, stride, channels);
            for (const r of rectangles) region.unionRectangle(r);
            // Leave a rescue control area while the page is still loading.
            if (occupied === 0) region.unionRectangle({x: 0, y: 0, width: width, height: 48});
            window.get_window()?.input_shape_combine_region(region, 0, 0);
            lastRegion = region.numRectangles(); samples++;
            state.input_regions = lastRegion; state.occupied_fraction = occupied / (width * height);
            state.alpha = image.get_has_alpha() && occupied < width * height * .95;
            state.snapshots = samples; state.width = width; state.height = height; state.position = window.get_position(); state.chat_open = lastChat;
            saveState();
        } catch (error) { state.snapshot_error = String(error); saveState(); }
    });
    return GLib.SOURCE_CONTINUE;
}
function activate() {
    if (window) { window.deiconify(); window.show_all(); return; }
    const context = WebKit.WebContext.new_ephemeral();
    context.set_sandbox_enabled(true);
    state.sandbox = context.get_sandbox_enabled();
    if (!state.sandbox) throw new Error('WebKit sandbox must remain enabled');
    const manager = new WebKit.UserContentManager();
    const css = 'html,body{background:transparent!important;}';
    manager.add_style_sheet(new WebKit.UserStyleSheet(css, WebKit.UserContentInjectedFrames.ALL_FRAMES, WebKit.UserStyleLevel.USER, null, null));
    manager.register_script_message_handler('siroDesktop');
    manager.connect('script-message-received::siroDesktop', (_manager, result) => {
        if (!web || !permitted(web.get_uri() || '')) return;
        let message;
        try { message = JSON.parse(result.get_js_value().to_string()); } catch (_) { return; }
        if (!message || typeof message.type !== 'string') return;
        if (message.type === 'desktop.quit') app.quit();
        else if (message.type === 'desktop.hide') { haltWalk('hidden'); window.iconify(); }
        else if (message.type === 'desktop.walk' && typeof message.id === 'string' && message.id.length <= 40 &&
            [-1, 0, 1].includes(message.direction) && [message.distance, message.speed, message.ramp, message.delay].every(Number.isFinite) &&
            message.distance > 0 && message.distance <= 4096 && message.speed >= 10 && message.speed <= 2000 &&
            message.ramp >= 0.2 && message.ramp <= 5 && message.delay >= 0 && message.delay <= 5 &&
            (message.cycle === undefined || (Number.isFinite(message.cycle) && message.cycle >= 0 && message.cycle <= 5))) startWalk(message);
        else if (message.type === 'desktop.walk.stop' && typeof message.id === 'string') stopWalk(message.id);
        else if (message.type === 'desktop.console') openCenter();
        else if (message.type === 'desktop.chat' && typeof message.open === 'boolean') {
            lastChat = message.open; window.set_accept_focus(lastChat);
            applyLayout();
            if (lastChat) window.present();
        } else if (message.type === 'desktop.scale' && Number.isInteger(message.step) && [-1, 0, 1].includes(message.step)) {
            scale = message.step === 0 ? 1 : Math.max(.6, Math.min(1.5, Math.round((scale + message.step * .1) * 10) / 10));
            applyLayout();
        } else if (message.type === 'desktop.controls' && Number.isInteger(message.height) && message.height >= 64 && message.height <= 320 && message.height !== controlsHeight) {
            controlsHeight = message.height; applyLayout();
        } else if (message.type === 'desktop.move' && message.button === 1 && Number.isFinite(message.screenX) && Number.isFinite(message.screenY)) {
            const display = Gdk.Display.get_default();
            let insideMonitor = false;
            for (let index = 0; index < display.get_n_monitors(); index++) {
                const area = display.get_monitor(index).get_geometry();
                if (message.screenX >= area.x && message.screenX <= area.x + area.width && message.screenY >= area.y && message.screenY <= area.y + area.height) insideMonitor = true;
            }
            haltWalk('dragged');
            if (insideMonitor) window.begin_move_drag(1, Math.round(message.screenX), Math.round(message.screenY), Gdk.CURRENT_TIME);
        } else if (message.type === 'desktop.ready') { ready = true; state.ready = true; applyLayout(); }
    });
    window = new Gtk.ApplicationWindow({application: app, title: `SIRO 桌寵 · ${GLib.getenv('GDK_BACKEND') === 'x11' ? 'XWayland/X11 相容' : '原生顯示'}`, default_width: 360, default_height: 640, decorated: false, resizable: true});
    window.set_app_paintable(true);
    const rgba = window.get_screen().get_rgba_visual();
    if (!rgba) throw new Error('RGBA compositing visual is unavailable');
    if (!window.get_screen().is_composited()) throw new Error('Desktop compositor is unavailable');
    window.set_icon_from_file(Gio.File.new_for_uri(import.meta.url).get_parent().get_child('siro.svg').get_path());
    window.set_visual(rgba); window.set_keep_above(true); window.set_accept_focus(false); window.set_focus_on_map(false);
    const provider = new Gtk.CssProvider();
    provider.load_from_data('window { background-color: transparent; }');
    window.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION);
    const policies = new WebKit.WebsitePolicies({autoplay: WebKit.AutoplayPolicy.ALLOW});
    web = new WebKit.WebView({web_context: context, user_content_manager: manager, website_policies: policies});
    web.set_size_request(1, 1);
    const transparent = new Gdk.RGBA(); transparent.parse('rgba(0,0,0,0)'); web.set_background_color(transparent);
    const settings = web.get_settings(); settings.set_enable_write_console_messages_to_stdout(Boolean(reportDirectory)); settings.set_enable_webgl(true); settings.set_enable_developer_extras(false); settings.set_media_playback_requires_user_gesture(false);
    restrict(web); window.add(web);
    web.connect('load-changed', (_view, event) => { if (event === WebKit.LoadEvent.FINISHED) applyLayout(); });
    web.connect('size-allocate', queueShape);
    web.connect('web-process-terminated', () => { state.ready = false; saveState(); });
    web.connect('load-failed', () => { state.ready = false; state.load_failed = true; saveState(); return false; });
    window.connect('delete-event', () => { app.quit(); return true; });
    // Minimised, hidden by a lock screen or withdrawn: stop walking where she is.
    window.connect('window-state-event', (_window, event) => {
        const gone = Gdk.WindowState.ICONIFIED | Gdk.WindowState.WITHDRAWN;
        if (event.new_window_state & gone) haltWalk('hidden');
        return false;
    });
    window.connect('unmap', () => haltWalk('hidden'));
    window.show_all();
    const display = Gdk.Display.get_default(), monitor = display.get_primary_monitor() || display.get_monitor(0);
    if (monitor) { const area = monitor.get_workarea(); window.move(area.x + area.width - 390, area.y + area.height - 670); }
    window.get_screen().connect('monitors-changed', () => {
        if (!window) return;
        const d = Gdk.Display.get_default(), m = d.get_monitor_at_window(window.get_window()) || d.get_primary_monitor() || d.get_monitor(0);
        if (!m) return;
        applyLayout();
    });
    web.load_uri(url);
    timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 3000, updateShape);
    saveState();
}
app.connect('activate', activate);
app.connect('shutdown', () => {
    haltWalk('closed');
    if (timer) GLib.source_remove(timer);
    if (layoutTimer) GLib.source_remove(layoutTimer);
    state.closed = true; saveState(); center?.destroy(); window?.destroy(); window = null; web = null;
});
GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, 15, () => { app.quit(); return GLib.SOURCE_REMOVE; });
GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, 2, () => { app.quit(); return GLib.SOURCE_REMOVE; });
app.run([]);
