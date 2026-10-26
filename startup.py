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


class ApplicationLaunch:
    def __init__(self, arguments):
        self.arguments = arguments
        self.process = None
        self.attempts = 0

    def start(self, retry=False):
        if self.attempts and not retry:
            return self.process
        if self.attempts >= 2:
            return self.process
        if not Path(APP).is_file() or not os.access(APP, os.X_OK):
            raise RuntimeError(f'找不到可运行的 ChatGPT 桌面程序：{APP}')
        CACHE.mkdir(parents=True, exist_ok=True)
        with (CACHE / 'app-launch.log').open('a') as output:
            self.process = subprocess.Popen([APP, *self.arguments], start_new_session=True,
                                            stdin=subprocess.DEVNULL, stdout=output,
                                            stderr=subprocess.STDOUT)
        self.attempts += 1
        log('app_launch_requested', pid=self.process.pid, attempt=self.attempts, executable=APP)
        return self.process


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


def play(preview, reason, application, bounds=None):
    lock = acquire_lock('player.lock')
    # Launch the client before initializing any video component. A missing or
    # broken player must never prevent a click from opening the application.
    if not preview:
        application.start()
    if lock is None:
        log('duplicate_animation_skipped', reason=reason)
        return 0

    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('Gdk', '3.0')
    gi.require_version('Gst', '1.0')
    from gi.repository import Gdk, GLib, Gst, Gtk
    Gtk.Window.set_auto_startup_notification(False)
    if not Gtk.init_check()[0]:
        raise RuntimeError('无法连接 Linux 图形桌面')
    Gst.init(None)

    wnck_screen = None
    if 'x11' in type(Gdk.Display.get_default()).__name__.lower():
        try:
            gi.require_version('Wnck', '3.0')
            from gi.repository import Wnck
            Wnck.set_client_type(Wnck.ClientType.PAGER)
            wnck_screen = Wnck.Screen.get_default()
        except (ImportError, ValueError):
            pass

    def app_window():
        if wnck_screen:
            wnck_screen.force_update()
            pids = app_processes()
            windows = [w for w in wnck_screen.get_windows_stacked() if w.get_pid() in pids]
            active = wnck_screen.get_active_window()
            if active in windows:
                return active
            if windows:
                normal = [w for w in windows if w.get_window_type() == Wnck.WindowType.NORMAL]
                return (normal or windows)[-1]
        return None

    def app_geometry():
        if bounds is not None:
            return bounds
        target = app_window()
        if target:
            return list(target.get_geometry())
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

    def activation_timestamp():
        if wnck_screen:
            try:
                gi.require_version('GdkX11', '3.0')
                from gi.repository import GdkX11
                return GdkX11.x11_get_server_time(Gdk.get_default_root_window())
            except (ImportError, ValueError, TypeError) as error:
                log('activation_timestamp_fallback', error=str(error))
        return Gtk.get_current_event_time()

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
            self.finished = False
            self.handoff_enabled = not preview or reason == 'process'
            self.handoff_status = 'pending' if self.handoff_enabled else 'preview'
            self.handoff_window = None
            self.recovery_requested = False
            self.last_activation = 0
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
                       'app_launch_attempts': application.attempts,
                       'app_handoff': self.handoff_status,
                       'app_window': self.handoff_window,
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
            self.phase = phase
            self.snapshot(phase)
            log('animation_finished', phase=phase, frames=self.frames, draws=self.draws,
                visible=self.had_visible_video, geometry=self.geometry)
            self.pipeline.set_state(Gst.State.NULL)
            self.window.hide()
            if self.handoff_enabled:
                self.handoff_started = time.monotonic()
                GLib.timeout_add(120, self.handoff)
            else:
                self.complete()
            return True

        def handoff(self):
            if wnck_screen is None:
                try:
                    application.start(retry=bool(application.attempts))
                except Exception as error:
                    log('app_activation_error', error=str(error))
                self.handoff_status = 'activation_requested_unverified'
                self.complete()
                return False
            elapsed = time.monotonic() - self.handoff_started
            target = app_window()
            if target:
                current_workspace = wnck_screen.get_active_workspace()
                self.handoff_window = {
                    'xid': target.get_xid(), 'pid': target.get_pid(),
                    'active': target.is_active(), 'minimized': target.is_minimized(),
                    'visible_on_workspace': bool(current_workspace and target.is_visible_on_workspace(current_workspace)),
                    'geometry': list(target.get_geometry()),
                }
                if (self.handoff_window['active'] and not self.handoff_window['minimized']
                        and self.handoff_window['visible_on_workspace']):
                    self.handoff_status = 'active'
                    log('app_handoff_confirmed', **self.handoff_window)
                    self.complete()
                    return False
                if time.monotonic() - self.last_activation > 0.75:
                    timestamp = activation_timestamp()
                    workspace = target.get_workspace()
                    if workspace and workspace != current_workspace:
                        workspace.activate(timestamp)
                    target.unminimize(timestamp)
                    target.activate_transient(timestamp)
                    log('app_activation_requested', xid=target.get_xid(), timestamp=timestamp,
                        minimized=target.is_minimized())
                    self.last_activation = time.monotonic()
            elif elapsed > 1.5 and not self.recovery_requested:
                self.recovery_requested = True
                try:
                    application.start(retry=bool(application.attempts))
                except Exception as error:
                    log('app_recovery_error', error=str(error))
            if elapsed >= 8:
                self.handoff_status = 'failed'
                log('app_handoff_failed', window=self.handoff_window,
                    launcher_exit=application.process.poll() if application.process else None)
                try:
                    subprocess.Popen(['notify-send', '-u', 'critical', 'ChatGPT 启动失败',
                                      f'未找到可进入的 ChatGPT 窗口。详细错误：{CACHE / "app-launch.log"}'])
                except OSError:
                    pass
                self.complete()
                return False
            self.snapshot(self.phase)
            return True

        def complete(self):
            self.snapshot(self.phase)
            self.window.destroy()
            Gtk.main_quit()

    splash = Splash()
    Gtk.main()
    if splash.handoff_enabled:
        return 0 if splash.handoff_status in ('active', 'activation_requested_unverified') else 1
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
    application = ApplicationLaunch(forwarded)
    try:
        if options.watch:
            return watch(options.process_executable)
        return play(options.preview, options.reason, application, options.bounds)
    except Exception as error:
        log('startup_error', error=str(error))
        print(f'Dragon Codex Boot: {error}', file=sys.stderr)
        if not options.preview and not options.watch:
            try:
                application.start()
            except Exception as launch_error:
                log('app_launch_failed', error=str(launch_error))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
