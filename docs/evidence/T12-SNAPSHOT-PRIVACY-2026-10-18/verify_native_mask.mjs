import Gtk from 'gi://Gtk?version=3.0';
import Gdk from 'gi://Gdk?version=3.0';
import GdkPixbuf from 'gi://GdkPixbuf?version=2.0';
import GLib from 'gi://GLib';
import WebKit from 'gi://WebKit2?version=4.1';
import Cairo from 'cairo';
import {inputMask} from '../../../desktop/input-mask.mjs';

// Only this verifier writes a known synthetic PNG for old/new parity.
// No product service, database, microphone, user window or remote URL is used.
Gtk.init(null);
const directory = GLib.dir_make_tmp('siro-synthetic-mask-XXXXXX');
const scratch = GLib.build_filenamev([directory, 'synthetic.png']);
const loop = new GLib.MainLoop(null, false);
const context = WebKit.WebContext.new_ephemeral();
context.set_sandbox_enabled(true);
if (!context.get_sandbox_enabled()) throw Error('sandbox disabled');
const view = new WebKit.WebView({web_context: context});
const window = new Gtk.OffscreenWindow();
window.set_default_size(96, 72); window.add(view);
const transparent = new Gdk.RGBA(); transparent.parse('rgba(0,0,0,0)');
view.set_background_color(transparent);
let failure = null, completed = false;
const source = new TextDecoder().decode(GLib.file_get_contents(
    GLib.build_filenamev([GLib.get_current_dir(), 'desktop/host.js']))[1]);
const implementation = source.slice(source.indexOf('function updateShape()'), source.indexOf('\nfunction activate()'));
view.connect('load-changed', (_view, event) => {
    if (event !== WebKit.LoadEvent.FINISHED) return;
    view.get_snapshot(WebKit.SnapshotRegion.VISIBLE, WebKit.SnapshotOptions.TRANSPARENT_BACKGROUND, null, (_v, result) => {
        try {
            const surface = view.get_snapshot_finish(result);
            surface.writeToPNG(scratch);
            const before = GdkPixbuf.Pixbuf.new_from_file(scratch);
            const after = Gdk.pixbuf_get_from_surface(surface, 0, 0, surface.getWidth(), surface.getHeight());
            const describe = image => ({width:image.get_width(),height:image.get_height(),channels:image.get_n_channels(),
                mask:inputMask(image.get_pixels(),image.get_width(),image.get_height(),image.get_rowstride(),image.get_n_channels())});
            const baseline = describe(before), current = describe(after);
            if (JSON.stringify(baseline) !== JSON.stringify(current)) throw Error('input geometry differs');
            GLib.unlink(scratch);
            const invoke = new Function('web','window','GLib','Gdk','Cairo','WebKit','inputMask', `
                let pendingSnapshot=false,lastChat=true,samples=0,lastRegion=0;
                const state={}; const saveState=()=>{};
                ${implementation}
                updateShape(); return state;
            `);
            // A synchronous adapter hands the actual WebKit-produced Cairo surface
            // to the exact production function; GTK and GDK remain real.
            const sampled = invoke({is_loading:false,
                get_snapshot:(_r,_o,_c,callback)=>callback(view,result),
                get_snapshot_finish:()=>surface}, {get_visible:()=>true,get_position:()=>[0,0],
                get_window:()=>({input_shape_combine_region:()=>{}})},
                GLib, Gdk, Cairo, WebKit, inputMask);
            if (sampled.snapshot_error || !sampled.alpha || sampled.snapshots !== 1) throw Error(JSON.stringify(sampled));
            if (GLib.file_test(scratch, GLib.FileTest.EXISTS)) throw Error('production recreated PNG');
            print(JSON.stringify({status:'PASS',sandbox:true,actual_webkit_surface:true,
                original_png_vs_memory_mask_equal:true,production_updateShape_executed:true,
                no_production_png:true,width:current.width,height:current.height,
                input_regions:current.mask.rectangles.length,occupied:current.mask.occupied}));
            completed = true;
        } catch (error) { failure = String(error); }
        loop.quit();
    });
});
window.show_all();
view.load_html('<html><body style="margin:0;background:transparent"><div style="position:absolute;left:5px;top:7px;width:17px;height:21px;background:#345678"></div></body></html>', 'about:blank');
const timeout = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 10000, () => {failure='snapshot timed out';loop.quit();return GLib.SOURCE_REMOVE;});
try { loop.run(); } finally {
    if (completed || failure !== 'snapshot timed out') GLib.source_remove(timeout);
    window.destroy(); GLib.unlink(scratch); GLib.rmdir(directory);
}
if (failure || !completed) throw Error(failure || 'not completed');
