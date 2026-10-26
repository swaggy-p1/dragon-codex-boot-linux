#!/usr/bin/python3
"""A sized GTK/GStreamer splash and a per-user ChatGPT launch watcher."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
CACHE = Path(os.environ.get('XDG_CACHE_HOME', str(Path.home() / '.cache'))) / 'dragon-codex-boot'
APP = os.environ.get('DRAGON_APP_EXECUTABLE', '/usr/bin/chatgpt')
PROCESS = os.environ.get('DRAGON_APP_PROCESS', '/usr/lib/chatgpt/ChatGPT')


def write_json(name, value):
    CACHE.mkdir(parents=True, exist_ok=True)
    temporary = CACHE / (name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(CACHE / name)


def log(event, **fields):
    CACHE.mkdir(parents=True, exist_ok=True)
    with (CACHE / 'startup.log').open('a') as stream:
        stream.write(json.dumps({'time': time.time(), 'event': event, **fields}, ensure_ascii=False) + '\n')


def acquire_lock(name):
    CACHE.mkdir(parents=True, exist_ok=True)
    lock = (CACHE / name).open('a+')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock
    except BlockingIOError:
        lock.close()
        return None


def app_processes(executable=PROCESS):
    found = set()
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            argv = path.read_bytes().split(b'\0')
            if os.fsdecode(argv[0]) != executable:
                continue
            if any(arg.startswith(b'--type=') for arg in argv):
                continue
            found.add(int(path.parent.name))
        except (OSError, ValueError):
            continue
    return found


def launch_app(arguments):
    if not Path(APP).is_file():
        raise RuntimeError(f'找不到 ChatGPT 桌面程序：{APP}')
    process = subprocess.Popen([APP, *arguments], start_new_session=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log('app_launch_requested', pid=process.pid)


def watch(executable):
    identity = hashlib.sha256(executable.encode()).hexdigest()[:12]
    lock = acquire_lock(f'watcher-{identity}.lock')
    if lock is None:
        return 0
    previous = app_processes(executable)
    log('watcher_ready', existing_pids=sorted(previous), executable=executable)
    while True:
        current = app_processes(executable)
        added = current - previous
        if added:
            log('app_start_detected', pids=sorted(added), executable=executable)
            subprocess.Popen([sys.executable, str(ROOT / 'startup.py'), '--preview', '--reason=process'],
                             start_new_session=True)
        previous = current
        time.sleep(0.35)


def play(preview, reason, arguments, bounds=None):
    lock = acquire_lock('player.lock')
    if lock is None:
        log('duplicate_animation_skipped', reason=reason)
        if not preview:
            launch_app(arguments)
        return 0

    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('Gdk', '3.0')
    gi.require_version('Gst', '1.0')
    from gi.repository import Gdk, GLib, Gst, Gtk
    if not Gtk.init_check()[0]:
        raise RuntimeError('无法连接 Linux 图形桌面')
    Gst.init(None)

    wnck_screen = None
    if 'x11' in type(Gdk.Display.get_default()).__name__.lower():
        try:
            gi.require_version('Wnck', '3.0')
            from gi.repository import Wnck
            wnck_screen = Wnck.Screen.get_default()
        except (ImportError, ValueError):
            pass

    def app_geometry():
        if bounds is not None:
            return bounds
        if wnck_screen:
            wnck_screen.force_update()
            pids = app_processes()
            windows = [w for w in wnck_screen.get_windows() if w.get_pid() in pids]
            active = wnck_screen.get_active_window()
            if active in windows:
                return list(active.get_geometry())
            if windows:
                return list(windows[-1].get_geometry())
        try:
            data = json.loads((Path.home() / '.codex/.codex-global-state.json').read_text())
            saved_bounds = data.get('electron-main-window-bounds') or data.get('.electron-main-window-bounds')
            if saved_bounds:
                return [int(saved_bounds[k]) for k in ('x', 'y', 'width', 'height')]
        except (OSError, ValueError, KeyError, TypeError):
            pass
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        area = monitor.get_workarea()
        width = min(1280, int(area.width * 0.85))
        height = min(820, int(area.height * 0.85))
        return [area.x + (area.width-width)//2, area.y + (area.height-height)//2, width, height]

    def fit_geometry(bounds):
        x, y, width, height = bounds
        display = Gdk.Display.get_default()
        monitor = display.get_monitor_at_point(x + width//2, y + height//2)
        area = monitor.get_workarea()
        width = min(max(320, width), area.width)
        height = min(max(180, height), area.height)
        return [max(area.x, min(x, area.x+area.width-width)),
                max(area.y, min(y, area.y+area.height-height)), width, height]

    class Splash:
        def __init__(self):
            self.frames = 0
            self.draws = 0
            self.had_visible_video = False
            self.launched = preview
            self.finished = False
            self.geometry = None
            self.started = time.monotonic()
            self.window = Gtk.Window(title='ChatGPT · Dragon startup')
            self.window.set_wmclass('dragon-codex-startup', 'DragonCodexBoot')
            self.window.set_decorated(False)
            # GTK otherwise locks the sink to the source video's natural size.
            # A borderless resizable window can follow the application's bounds.
            self.window.set_resizable(True)
            self.window.set_keep_above(True)
            self.window.set_skip_taskbar_hint(True)
            self.window.set_skip_pager_hint(True)
            self.window.set_type_hint(Gdk.WindowTypeHint.SPLASHSCREEN)
            self.window.connect('delete-event', lambda *_: self.finish('closed'))
            self.window.connect('key-press-event', self.key)

            self.sink = Gst.ElementFactory.make('gtksink', 'embedded-video')
            if self.sink is None:
                raise RuntimeError('缺少 gtksink，请安装 gstreamer1.0-gtk3')
            self.sink.set_property('force-aspect-ratio', True)
            self.widget = self.sink.get_property('widget')
            self.widget.set_size_request(1, 1)
            self.widget.set_hexpand(True)
            self.widget.set_vexpand(True)
            self.widget.connect_after('draw', self.drawn)
            self.window.add(self.widget)
            style = Gtk.CssProvider()
            style.load_from_data(b'window, widget { background-color: #000; }')
            self.window.get_style_context().add_provider(style, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self.pipeline = Gst.ElementFactory.make('playbin', 'startup-video')
            self.pipeline.set_property('uri', (ROOT / 'startup.mp4').as_uri())
            self.pipeline.set_property('video-sink', self.sink)
            self.sink.get_static_pad('sink').add_probe(Gst.PadProbeType.BUFFER, self.buffer)
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect('message::eos', lambda *_: self.finish('eos'))
            bus.connect('message::error', self.error)
            self.follow_window()
            self.window.show_all()
            self.window.present()
            self.pipeline.set_state(Gst.State.PLAYING)
            self.snapshot('starting')
            GLib.timeout_add(250, self.follow_window)
            GLib.timeout_add(500, self.progress)
            GLib.timeout_add_seconds(4, self.ensure_launched)
            GLib.timeout_add_seconds(24, lambda: self.finish('timeout'))

        def buffer(self, _pad, _info):
            self.frames += 1
            return Gst.PadProbeReturn.OK

        def drawn(self, _widget, _context):
            if self.frames and self.widget.get_mapped():
                self.draws += 1
                if not self.had_visible_video:
                    self.had_visible_video = True
                    self.snapshot('visible_video')
                    log('visible_video', reason=reason, geometry=self.geometry)
                    GLib.idle_add(self.ensure_launched)
            return False

        def ensure_launched(self):
            if not self.launched:
                self.launched = True
                launch_app(arguments)
            return False

        def follow_window(self):
            if self.finished:
                return False
            geometry = fit_geometry(app_geometry())
            if geometry != self.geometry or list(self.window.get_size()) != geometry[2:]:
                self.geometry = geometry
                self.window.move(*geometry[:2])
                self.window.set_default_size(*geometry[2:])
                self.window.resize(*geometry[2:])
            return True

        def snapshot(self, phase):
            allocation = self.widget.get_allocation()
            write_json('status.json', {'phase': phase, 'reason': reason, 'time': time.time(),
                       'pid': os.getpid(), 'geometry': self.geometry,
                       'window_size': list(self.window.get_size()),
                       'window_position': list(self.window.get_position()),
                       'video_allocation': [allocation.width, allocation.height],
                       'mapped': self.widget.get_mapped(), 'frames_received': self.frames,
                       'video_draws': self.draws, 'had_visible_video': self.had_visible_video,
                       'fit': 'contain', 'source_aspect_ratio': '16:9',
                       'elapsed_seconds': round(time.monotonic()-self.started, 2)})

        def progress(self):
            if self.finished:
                return False
            self.snapshot('playing' if self.had_visible_video else 'starting')
            return True

        def key(self, _window, event):
            if event.keyval == Gdk.KEY_Escape:
                self.finish('escape')
            return False

        def error(self, _bus, message):
            error, debug = message.parse_error()
            log('playback_error', error=str(error), debug=debug)
            self.finish('error')

        def finish(self, phase):
            if self.finished:
                return True
            self.finished = True
            self.ensure_launched()
            self.snapshot(phase)
            log('animation_finished', phase=phase, frames=self.frames, draws=self.draws,
                visible=self.had_visible_video, geometry=self.geometry)
            self.pipeline.set_state(Gst.State.NULL)
            self.window.destroy()
            Gtk.main_quit()
            return True

    splash = Splash()
    Gtk.main()
    return 0 if splash.had_visible_video else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--reason', default='desktop')
    parser.add_argument('--process-executable', default=PROCESS)
    parser.add_argument('--bounds', nargs=4, type=int, metavar=('X', 'Y', 'WIDTH', 'HEIGHT'))
    parser.add_argument('app_args', nargs=argparse.REMAINDER)
    options = parser.parse_args()
    forwarded = options.app_args
    if forwarded[:1] == ['--']:
        forwarded = forwarded[1:]
    try:
        if options.watch:
            return watch(options.process_executable)
        return play(options.preview, options.reason, forwarded, options.bounds)
    except Exception as error:
        log('startup_error', error=str(error))
        print(f'Dragon Codex Boot: {error}', file=sys.stderr)
        if not options.preview and not options.watch:
            launch_app(forwarded)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
