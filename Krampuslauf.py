"""Krampuslauf — official Classic Client + Razor Enhanced.

Windows-only native .NET Windows Forms UI via Python.NET. No Tkinter.
No account names/passwords are requested, read, or stored by this app.
Beta: automation must be validated against the actual official CC menu layout.
"""
import os
import uuid
import json
import queue
import threading
import time
from datetime import datetime
from activity_history import ActivityHistory
from shard_policy import SHARD_GROUP_OPTIONS, normalize_shards, run_shards, supported_shards
from ui_assets import artwork_bounds
from ui_layout import HEADER_HEIGHT, DONATION_URL
from ui_layout import NAVIGATION, LAYOUTS, FONT_PT, VERSION, PROJECT_URL, tab_widths
from ui_assets import artwork_path, windows_text
from ui_guidance import explain_error, ActionNeeded
from escape_hotkey import EscapeHotkey, escape_action

UI_HOST = None

import pyautogui as pg
import native_mouse

from pythonnet import load
load("netfx")
import clr
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")
from System import Decimal, Convert
from System.Drawing import (Bitmap, Color, Font, FontStyle, Point, Size, SizeF, Region, Icon, GraphicsUnit,
                            ContentAlignment, Pen, Rectangle)
from System.Drawing.Drawing2D import GraphicsPath
from System.Windows.Forms import (
    Application, AnchorStyles, AutoScaleMode, BorderStyle, Button, CheckBox, RadioButton, CheckedListBox,
    ComboBox, ComboBoxStyle,
    DialogResult, DockStyle, FlatStyle, Form, FormBorderStyle,
    FormStartPosition, FormWindowState, Label, ListBox,
    MessageBox, MessageBoxButtons, MessageBoxIcon, NumericUpDown,
    Panel, PictureBox, PictureBoxSizeMode, ProgressBar, ScrollBars,
    FlowLayoutPanel, FlowDirection, Padding, TextBox, Timer, Cursors, TextRenderer
)

from bridge_protocol import BridgeSession, BridgeCancelled
from setup_checklist import SETUP_STEPS, checklist_from, setup_missing
from razor_paths import find_razor_roots
from profile_isolation import (IsolationError, session_status,
                               normalize_root, prepare as prepare_re_profiles,
                               restore as restore_re_profiles)
from shard_identity import shard_from_title
from cycler_engine import (
    APP_DIR, CONFIG_FILE, DEFAULTS, GameWorker, Cancelled,
    atomic_json, load_json, test_config, pin_window, selected_window,
    game_windows, focus_game, point_screen, game_area, KNOWN_SHARDS, occupied_slots_for
)
from app_paths import migrate_app_data
if __name__ == '__main__':
    # Move an older data folder before settings are read. Imports do not do this,
    # so tests never touch a real data directory.
    migrate_app_data()
from menu_layout import POINTS as BUILT_IN_POINTS, POINT_LABELS, merged_points, valid_point
import appearance
from seeder_engine import MergedWorker
from seeder_rules import account_token
from seed_recovery import pending_seed_candidates, confirm_pending_not_created
from shard_scanner import ShardScanner, MAP_FILE
from shard_map import load_map, map_status, timezone_key

# Resolve the Windows *app* theme on startup, not the taskbar theme.
# Explicit settings are applied after restarting, so all WinForms controls
# are constructed from a consistent palette.
from ui_theme import palette_for, resolve_theme, set_windows_dark_caption
THEME_PREFERENCE = str(load_json(CONFIG_FILE, {}).get('appearance_theme', 'system'))
ACTIVE_THEME = resolve_theme(THEME_PREFERENCE)
_palette = palette_for(ACTIVE_THEME)
BG, PANEL, CARD, INK, MUTED, ACCENT, GREEN, RED, NOTE, WARNING = (
    Color.FromArgb(*_palette[key]) for key in
    ('bg', 'panel', 'card', 'ink', 'muted', 'accent', 'green', 'red', 'note', 'warning')
)


def apply_caption_on_show(sender, _args):
    """Style only Krampuslauf's own title bars, not Classic Client or Razor."""
    set_windows_dark_caption(sender.Handle, ACTIVE_THEME == 'dark')


class BorderlessTabHost(Panel):
    """A real borderless WinForms tab layout, without a native TabControl.

    TabControl.DrawMode=OwnerDrawFixed paints only headers; Windows still paints
    the native white content frame. This uses normal Panels for the tab strip
    and content, so neither header nor body can acquire native TabControl chrome.
    Main tabs and focused subtabs use the same keyboard-accessible control.
    """

    def __init__(self):
        super().__init__()
        self.BackColor = BG
        self.ForeColor = INK
        self.BorderStyle = getattr(BorderStyle, "None")
        self._entries = []
        self._selected = None
        self._plain_font = Font('Segoe UI', 9.5, FontStyle.Regular)
        self._active_font = Font('Segoe UI', 9.5, FontStyle.Bold)

        # Add the fill panel before the top-docked strip, so normal WinForms
        # docking allocates the remaining client space to the content panel.
        self.content_panel = Panel()
        self.content_panel.Dock = DockStyle.Fill
        self.content_panel.BackColor = PANEL
        self.content_panel.ForeColor = INK
        self.content_panel.BorderStyle = getattr(BorderStyle, "None")
        self.Controls.Add(self.content_panel)

        self.header = FlowLayoutPanel()
        self.header.Dock = DockStyle.Top
        self.header.Height = 36
        self.header.BackColor = BG
        self.header.ForeColor = INK
        self.header.BorderStyle = getattr(BorderStyle, "None")
        self.header.FlowDirection = FlowDirection.LeftToRight
        self.header.WrapContents = False
        self.header.AutoScroll = False
        self.header.Padding = Padding(0)
        self.header.SizeChanged += self.fit_tabs
        self.Controls.Add(self.header)

    def add_page(self, title, page):
        """Register a plain Panel as a page and a flat keyboard-accessible tab."""
        page.Dock = DockStyle.Fill
        page.BorderStyle = getattr(BorderStyle, "None")
        page.BackColor, page.ForeColor = PANEL, INK
        page.Visible = False
        self.content_panel.Controls.Add(page)

        nav = Button()
        nav.Text = str(title)
        nav.Font = self._plain_font
        nav.Width = max(62, int(TextRenderer.MeasureText(str(title), self._active_font).Width) + 18)
        nav.Height = 32
        nav.Margin = Padding(0, 1, 3, 0)
        nav.Padding = Padding(2, 0, 2, 0)
        nav.FlatStyle = FlatStyle.Flat
        nav.FlatAppearance.BorderSize = 0
        nav.FlatAppearance.MouseOverBackColor = CARD
        nav.FlatAppearance.MouseDownBackColor = PANEL
        nav.UseVisualStyleBackColor = False
        nav.BackColor = BG
        nav.ForeColor = INK
        nav.TabStop = True
        nav.Click += protected_ui(lambda sender, args, target=page: self.select_page(target))
        self.header.Controls.Add(nav)
        self._entries.append((page, nav))
        self.fit_tabs()
        if self._selected is None:
            self.select_page(page)
        return page

    def fit_tabs(self, sender=None, args=None):
        widths = tab_widths(int(self.header.ClientSize.Width), len(self._entries))
        self.header.SuspendLayout()
        try:
            for i, ((page, nav), width) in enumerate(zip(self._entries, widths)):
                nav.Margin = Padding(0, 1, 3 if i < len(widths)-1 else 0, 0)
                nav.Width = width
        finally:
            self.header.ResumeLayout()

    def select_page(self, page):
        if not any(candidate.Equals(page) for candidate, _ in self._entries):
            raise ValueError('Unknown Krampuslauf tab page.')
        self._selected = page
        for candidate, nav in self._entries:
            active = candidate.Equals(page)
            candidate.Visible = active
            nav.BackColor = PANEL if active else BG
            nav.ForeColor = ACCENT if active else INK
            nav.Font = self._active_font if active else self._plain_font
        page.BringToFront()
        host = self.FindForm()
        if host is not None and hasattr(host, 'health_status'):
            host.refresh_health_status()


def window_message(text, title="Krampuslauf", error=False):
    if error:
        if UI_HOST is not None:
            return UI_HOST.report_ui_error(text)
        issue = explain_error(text)
        return MessageBox.Show(issue.message, issue.title, MessageBoxButtons.OK, MessageBoxIcon.Warning)
    return MessageBox.Show(str(text), title, MessageBoxButtons.OK, MessageBoxIcon.Information)


def net_integer(value):
    """Convert .NET NumericUpDown.Decimal to a Python int for JSON and settings.

    Python.NET 3.2.x does not implement int(System.Decimal) on all runtimes.
    System.Convert.ToInt32 performs the managed Decimal -> Int32 conversion.
    str(...) then bridges safely whether Python.NET returns int or Int32.
    """
    return int(str(Convert.ToInt32(value)))


def protected_ui(callback):
    """Prevent .NET event callbacks from showing an unhandled JIT crash dialog."""
    def invoke(sender, args):
        try:
            return callback(sender, args)
        except Exception as exc:
            window_message(exc, error=True)
    return invoke


def label(parent, text, x, y, w=250, h=25, bold=False, size=10.5, color=None, tone=None):
    ctl = Label()
    ctl.Text = text
    # Notices stay smaller than body text and headings, without stacked +2pt boosts.
    size = max(9.5, float(size))
    if tone in ('note', 'warning'):
        color = WARNING if tone == 'warning' else NOTE
        bold, size = True, FONT_PT[tone]
    ctl.ForeColor = color or INK
    ctl.BackColor = parent.BackColor
    ctl.Location, ctl.Size = Point(x, y), Size(w, h)
    ctl.Font = Font("Segoe UI", float(size), FontStyle.Bold if bold else FontStyle.Regular)
    ctl.AutoEllipsis = True
    ctl.UseMnemonic = False
    parent.Controls.Add(ctl)
    return ctl


def round_button(sender, _args):
    """Use a native button region so keyboard/focus behavior remains standard."""
    width, height = int(sender.Width), int(sender.Height)
    if width < 2 or height < 2:
        return
    diameter = min(12 * max(1, int(getattr(sender, 'DeviceDpi', 96))) // 96, width - 1, height - 1)
    path = GraphicsPath()
    try:
        for x, y, start in ((0, 0, 180), (width-diameter-1, 0, 270),
                            (width-diameter-1, height-diameter-1, 0), (0, height-diameter-1, 90)):
            path.AddArc(int(x), int(y), int(diameter), int(diameter), float(start), 90.0)
        path.CloseFigure()
        previous = sender.Region
        sender.Region = Region(path)
        if previous is not None:
            previous.Dispose()
    finally:
        path.Dispose()


def button(parent, text, x, y, w, h, action, highlight=False, start_green=False):
    ctl = Button()
    ctl.Text = text
    ctl.Location, ctl.Size = Point(x, y), Size(w, h)
    # Darker button fills keep white call-to-action text readable. The brighter
    # GREEN / ACCENT palette values are reserved for readable status labels.
    ctl.BackColor = (Color.FromArgb(33, 117, 77) if start_green else
                     Color.FromArgb(40, 103, 164) if highlight else CARD)
    ctl.ForeColor = Color.White if start_green or highlight else INK
    ctl.FlatStyle = FlatStyle.Flat
    ctl.FlatAppearance.BorderSize = 0
    ctl.Font = Font("Segoe UI", FONT_PT["button"], FontStyle.Bold)
    ctl.UseVisualStyleBackColor = False
    ctl.UseMnemonic = False
    ctl.FlatAppearance.MouseOverBackColor = (Color.FromArgb(44, 132, 88) if start_green else
                                              Color.FromArgb(48, 116, 180) if highlight else PANEL)
    ctl.Cursor = Cursors.Hand
    ctl.AccessibleName = str(text)
    ctl.SizeChanged += round_button
    round_button(ctl, None)
    ctl.Click += protected_ui(action)
    parent.Controls.Add(ctl)
    return ctl


def entry(parent, x, y, w, default="", multiline=False):
    ctl = TextBox()
    ctl.Location = Point(x, y)
    ctl.Size = Size(w, 27 if not multiline else 230)
    ctl.BackColor, ctl.ForeColor = CARD, INK
    ctl.BorderStyle = BorderStyle.FixedSingle
    ctl.Text = windows_text(default) if multiline else str(default)
    ctl.Font = Font("Segoe UI", FONT_PT["body"])
    if multiline:
        ctl.Multiline, ctl.ScrollBars = True, ScrollBars.Vertical
        ctl.Font = Font("Consolas", FONT_PT["mono"])
    parent.Controls.Add(ctl)
    return ctl


def combo(parent, x, y, w):
    ctl = ComboBox()
    ctl.Location, ctl.Size = Point(x, y), Size(w, 27)
    ctl.DropDownStyle = ComboBoxStyle.DropDownList
    ctl.BackColor, ctl.ForeColor = CARD, INK
    ctl.Font = Font("Segoe UI", FONT_PT["body"])
    parent.Controls.Add(ctl)
    return ctl


class ActivityWindow(Form):
    """Small independent run window; does not create another automation session."""
    def __init__(self, parent):
        super().__init__()
        self.Text = "Krampuslauf | Activity"
        self.Icon = parent.Icon
        self.StartPosition = FormStartPosition.CenterScreen
        self.ClientSize = Size(570, 334)
        self.MinimumSize = Size(490, 294)
        self.BackColor, self.ForeColor = BG, INK
        self.Shown += apply_caption_on_show
        self.FormBorderStyle = FormBorderStyle.Sizable
        self.status = label(self, "Ready", 12, 8, 545, 38, True, 9)
        self.status.Anchor = AnchorStyles.Left | AnchorStyles.Top | AnchorStyles.Right
        self.log = entry(self, 12, 49, 545, "", multiline=True)
        self.log.ReadOnly = True
        self.log.Size = Size(545, 175)
        self.log.Anchor = (AnchorStyles.Left | AnchorStyles.Top |
                           AnchorStyles.Bottom | AnchorStyles.Right)
        # A run is started exclusively from Gift Cycler or Character Seeder.
        self.pause_button = button(self, "PAUSE", 12, 233, 110, 34, parent.toggle_pause)
        self.stop_button = button(self, "STOP", 134, 233, 110, 34, parent.request_stop)
        self.restore_button = button(self, "SHOW MAIN WINDOW", 256, 233, 300, 34,
                                     lambda a,b: parent.restore_full_window())
        for ctl in (self.pause_button, self.stop_button, self.restore_button):
            ctl.Anchor = AnchorStyles.Left | AnchorStyles.Bottom
        self.progress = ProgressBar()
        self.progress.Minimum, self.progress.Maximum = 0, 100
        self.progress.Location, self.progress.Size = Point(12, 276), Size(544, 18)
        self.progress.Anchor = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Bottom
        self.Controls.Add(self.progress)
        self.escape_hint = label(self, "ESC: PAUSE · ESC AGAIN: STOP · Click Resume to continue", 12, 302, 545, 20, size=9)
        self.escape_hint.Anchor = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Bottom


class MainWindow(Form):
    def __init__(self):
        super().__init__()
        APP_DIR.mkdir(parents=True, exist_ok=True)
        self.history_store = ActivityHistory(APP_DIR / "activity_history.log")
        global UI_HOST
        UI_HOST = self
        self.owned_images = []
        self.pending_issue = None
        self.escape_hotkey = None
        saved = load_json(CONFIG_FILE, {})
        if saved.get('points') and CONFIG_FILE.exists():
            # Older window-relative calibration; keep a private copy once.
            backup = CONFIG_FILE.with_name('settings.before-built-in-layout.json')
            if not backup.exists():
                from shutil import copy2
                copy2(str(CONFIG_FILE), str(backup))
        self.cfg = {**DEFAULTS, **saved}
        # Menu positions are built in (640 x 480 game area); optional recorded
        # overrides from Setup > Game Client > Click points replace individual points.
        self.cfg['point_overrides'] = {k: v for k, v in dict(self.cfg.get('point_overrides') or {}).items()
                                       if valid_point(v)}
        self.cfg['points'] = merged_points(self.cfg['point_overrides'])
        self.cfg['appearance'] = appearance.settings(self.cfg)
        for legacy in ('gump_cleanup_mode',):
            self.cfg.pop(legacy, None)
        if not self.cfg.get('gift_cycle_id'):
            self.cfg['gift_cycle_id'] = uuid.uuid4().hex[:16]
        # Shard list has nine fixed visible rows in Classic Client.
        self.cfg['visible_rows'] = 9
        self.cfg['post_logout_seconds'] = max(3, int(self.cfg.get('post_logout_seconds', 7)))
        self.cfg['auto_detect_slots'] = True
        self.cfg['account_cap'] = int(self.cfg.get('account_cap', 7))
        self.cfg['name_format_version'] = 'shard_letter_spaced_v1'
        for legacy in ('seed_name_input_verified', 'seed_fantasy_tested_style'):
            self.cfg.pop(legacy, None)  # The name-typing test was retired.
        self.cfg.get('manual_test_passes', {}).pop('name_typing', None)
        # An older release stored the checklist under another key, and a still
        # older one used a dedicated profile. Those old boxes do not count.
        self.cfg['setup_checklist'] = checklist_from(self.cfg)
        self.cfg.pop('monkey_setup', None)
        if 'profile' in self.cfg['setup_checklist'] and 'default_profile' not in self.cfg['setup_checklist']:
            self.cfg['setup_checklist'] = {}
        cached_map=load_map(MAP_FILE,self.cfg)
        if cached_map is not None:
            self.cfg['shards']=list(cached_map['shards'])
            self.cfg['verified_order']=True
        normalize_shards(self.cfg)
        # An old release persisted the client title, potentially including the
        # account name. Erase it on startup; the HWND is selected each run.
        self.cfg["window_title"] = ""
        atomic_json(CONFIG_FILE, {k: v for k, v in self.cfg.items() if k != 'points'})
        self.screen_recognized = False
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.worker = None
        self.game_worker = None
        self.events = queue.Queue()
        self.window_by_label = {}
        self.active_profile_key = None
        self.account_radios = {}
        self.setup_checks = {}
        self.test_buttons = {}
        self.app_checks = {}
        self.skin_palettes = {}
        self.color_palettes = {}
        self.app_style_key = None
        self.record_key = None
        self.record_timer = None
        self.Text = "Krampuslauf " + VERSION
        self.StartPosition = FormStartPosition.CenterScreen
        # 720 x 890 outer window at 100% Windows scaling; scale as a unit at high DPI.
        self.AutoScaleDimensions = SizeF(96.0, 96.0)
        self.AutoScaleMode = AutoScaleMode.Dpi
        self.Size = Size(720, 890)
        self.MinimumSize = Size(720, 890)
        self.FormBorderStyle = FormBorderStyle.Sizable
        self.MaximizeBox = True
        self.BackColor, self.ForeColor = BG, INK
        self.Shown += apply_caption_on_show
        self.Font = Font("Segoe UI", FONT_PT["body"])
        self.build_ui()
        self.initialize_accounts()
        self.load_windows()
        self.refresh_exclusions()
        self.refresh_test_shards()
        try:
            prior_state = session_status(APP_DIR)
            if prior_state['active']:
                self.log_line('PROFILE ISOLATION: ' + prior_state['status'] +
                              '. Remember to restore original links after closing RE and Classic Client.')
        except Exception as exc:
            self.log_line('PROFILE RECOVERY WARNING: ' + str(exc))
        self.ui_timer = Timer()
        self.ui_timer.Interval = 125
        self.ui_timer.Tick += protected_ui(self.drain_events)
        self.ui_timer.Start()
        self.FormClosing += protected_ui(self.before_close)
        self.activity_window = ActivityWindow(self)
        self.activity_window.FormClosing += protected_ui(self.activity_close)
        # These aliases keep existing worker/status plumbing intact, but the
        # controls now live exclusively in the compact Activity window.
        self.pause_btn = self.activity_window.pause_button
        self.stop_btn = self.activity_window.stop_button
        self.progress = self.activity_window.progress
        self.stop_btn.Enabled = False
        self.pause_btn.Enabled = False
        self.compact_running = False
        self.active_compact_run = False

    def build_ui(self):
        """Every settings page fits without page scrolling."""
        self.brand_panel = Panel()
        self.brand_panel.Location = Point(14, 4)
        self.brand_panel.Size = Size(self.ClientSize.Width - 28, HEADER_HEIGHT)
        self.brand_panel.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right
        self.brand_panel.BackColor = self.BackColor
        self.Controls.Add(self.brand_panel)
        self.brand_title = self.add_title_banner(self.brand_panel)
        self.brand_panel.Resize += protected_ui(self.layout_branding)
        self.layout_branding()
        self.app_icon = None
        icon_path = artwork_path('Krampuslauf.ico')
        if icon_path:
            try:
                source_icon = Icon(str(icon_path))
                try:
                    self.app_icon = source_icon.Clone()
                finally:
                    source_icon.Dispose()
                self.Icon = self.app_icon
            except Exception as exc:
                self.log_line('Application icon could not be loaded: ' + str(exc))
        self.FormClosed += self.dispose_artwork
        self.tabs = BorderlessTabHost()
        self.tabs.Location = Point(14, HEADER_HEIGHT + 8)
        self.tabs.Size = Size(self.ClientSize.Width - 28, self.ClientSize.Height - HEADER_HEIGHT - 22)
        self.tabs.Anchor = (AnchorStyles.Top | AnchorStyles.Bottom |
                            AnchorStyles.Left | AnchorStyles.Right)
        self.Controls.Add(self.tabs)
        self.pages, self.page_paths = {}, {}
        for title, children in NAVIGATION:
            root = Panel()
            root.AutoScroll = False
            self.tabs.add_page(title, root)
            subhost = None
            if len(children) > 1:
                subhost = BorderlessTabHost()
                subhost.Dock = DockStyle.Fill
                root.Controls.Add(subhost)
            for caption, key in children:
                page = Panel()
                page.BackColor, page.ForeColor = PANEL, INK
                page.Dock = DockStyle.Fill
                page.AutoScroll = False
                if subhost is None:
                    root.Controls.Add(page)
                else:
                    subhost.add_page(caption, page)
                self.pages[key] = page
                self.page_paths[key] = (root, subhost, page)
        self.setup_tab = self.pages['setup']
        self.calibration = self.pages['client']
        self.shards_tab = self.pages['shards']
        self.home = self.pages['gift']
        self.seeder_tab = self.pages['seeder']
        self.settings_tab = self.pages['appearance']
        self.testing_tab = self.pages['diagnostics']
        self.build_setup()
        self.build_calibration()
        self.build_shards()
        self.build_home()
        self.build_seeder()
        self.build_settings()
        self.build_testing()
        # Attach change handlers only after every referenced control exists.
        self.game_pick.SelectedIndexChanged += protected_ui(self.select_window)
        self.point_pick.SelectedIndexChanged += protected_ui(self.update_point_status)
        self.app_style_group.SelectedIndexChanged += protected_ui(self.style_group_changed)
        self.app_palette_pick.SelectedIndexChanged += protected_ui(self.refresh_palette_view)
        for key, box in self.app_checks.items():
            box.CheckedChanged += protected_ui(lambda sender, args, key=key: self.appearance_selection_changed(key))
        self.app_mode.SelectedIndexChanged += protected_ui(self.appearance_mode_changed)
        self.seed_mode_pick.SelectedIndexChanged += protected_ui(self.update_seed_name_mode)
        self.gift_shard_group.SelectedIndexChanged += protected_ui(self.sync_shard_group)
        self.seed_shard_group.SelectedIndexChanged += protected_ui(self.sync_shard_group)
        self.account_field.TextChanged += protected_ui(self.account_label_changed)
        self.account_field.Leave += protected_ui(self.save_account_profile)
        for slot, radio in self.account_radios.items():
            radio.CheckedChanged += protected_ui(lambda sender, args, slot=slot: self.account_radio_changed(slot))
        self.sort_confirm.CheckedChanged += protected_ui(self.confirm_order)
        self.shard_checks.ItemCheck += protected_ui(self.shard_selection_changed)
        self.update_seed_name_mode()
        self.update_test_status()
        self.refresh_health_status()

    def add_title_banner(self, parent):
        """Show the supplied title artwork through a viewport over its visible art.

        The original PNG stays unchanged. Its nearly transparent outer padding
        is outside the viewport, letting the lettering use the header height.
        """
        path = artwork_path('title_banner.png')
        if not path:
            return label(parent, 'KRAMPUSLAUF', 0, 0, 644, HEADER_HEIGHT, True, 28)
        ctl = Panel()
        ctl.Size = Size(644, HEADER_HEIGHT)
        ctl.BackColor = parent.BackColor
        ctl.AccessibleName = 'Krampuslauf title'
        loaded = Bitmap(str(path))
        try:
            title_image = Bitmap(loaded)
        finally:
            loaded.Dispose()
        self.owned_images.append(title_image)
        bounds = artwork_bounds('title_banner.png') or (0, 0, title_image.Width, title_image.Height)
        source = Rectangle(*bounds)
        def paint_title(sender, event):
            # Fill the taller header with the user's complete visible title artwork.
            target = Rectangle(0, 0, sender.Width, sender.Height)
            event.Graphics.DrawImage(title_image, target, source, GraphicsUnit.Pixel)
        ctl.Paint += paint_title
        parent.Controls.Add(ctl)
        return ctl

    def layout_branding(self, sender=None, args=None):
        """Let the title use the full header, including after resizing or DPI scaling."""
        if not hasattr(self, 'brand_title'):
            return
        self.brand_title.Location = Point(10, 0)
        self.brand_title.Size = Size(max(1, self.brand_panel.ClientSize.Width - 20),
                                    self.brand_panel.ClientSize.Height)

    def add_artwork(self, parent, filename, x, y, width, height):
        pic = PictureBox()
        pic.Location, pic.Size = Point(x, y), Size(width, height)
        pic.SizeMode = PictureBoxSizeMode.Zoom
        pic.TabStop = False
        pic.BackColor = parent.BackColor
        parent.Controls.Add(pic)
        path = artwork_path(filename)
        if path:
            try:
                loaded = Bitmap(str(path))
                try:
                    image = Bitmap(loaded)
                finally:
                    loaded.Dispose()
                self.owned_images.append(image)
                pic.Image = image
            except Exception as exc:
                self.log_line('Optional artwork could not be loaded: ' + str(exc))
        return pic

    def dispose_artwork(self, sender, args):
        for image in self.owned_images:
            image.Dispose()
        self.owned_images.clear()
        if self.app_icon is not None:
            self.app_icon.Dispose()
            self.app_icon = None

    def report_ui_error(self, error, navigate=True, log=True):
        issue = explain_error(error)
        if log:
            detail = str(error)
            title = str(getattr(self, 'cfg', {}).get('window_title', ''))
            if title:
                detail = detail.replace(title, '[selected client]')
            self.log_line('ERROR DETAILS: ' + detail)
        if (navigate and hasattr(self, 'page_paths') and issue.page in self.page_paths
                and not self.busy()):
            self.show_page(issue.page)
        owner = (self.activity_window if hasattr(self, 'activity_window') and self.activity_window.Visible else self)
        return MessageBox.Show(owner, issue.message, issue.title,
                               MessageBoxButtons.OK, MessageBoxIcon.Warning)

    def show_page(self, key):
        root, subhost, page = self.page_paths[key]
        self.tabs.select_page(root)
        if subhost is not None:
            subhost.select_page(page)
        if key == 'profiles':
            self.offer_razor_root()
        if key == 'setup':
            self.update_setup_progress()

    def layout_action(self, action):
        if action.startswith('page:'):
            return lambda s, e: self.show_page(action.split(':', 1)[1])
        return getattr(self, action)

    def mount_page(self, key):
        """Bind the measured layout to real WinForms controls and existing handlers."""
        parent = self.pages[key]
        for spec in LAYOUTS[key]:
            kind = spec['kind']
            x, y, w, h = (spec[n] for n in ('x', 'y', 'w', 'h'))
            value = self.cfg.get(spec['config'], spec.get('default', '')) if spec.get('config') else spec.get('default', '')
            data_source = spec.get('source')
            if data_source == 'shards':
                value = '\n'.join(self.cfg['shards'])
            elif data_source == 'slot_rules':
                value = self.format_slot_rules(self.cfg.get('skip_slots', {}))
            if kind == 'text':
                role = spec.get('role', 'body')
                tone = role if role in ('warning', 'note') else None
                color = (Color.FromArgb(183, 255, 73) if role == 'next' else
                         ACCENT if role == 'heading' else MUTED if role == 'muted' else INK)
                ctl = label(parent, spec['text'], x, y, w, h, role in ('heading', 'next'),
                            FONT_PT[role], color, tone)
                if role == 'next':
                    ctl.BackColor = Color.FromArgb(28, 42, 25)
                    ctl.Padding = Padding(8, 0, 4, 0)
                    ctl.TextAlign = ContentAlignment.MiddleLeft
                    ctl.AutoEllipsis = False
            elif kind == 'image':
                ctl = self.add_artwork(parent, spec['asset'], x, y, w, h)
                ctl.AccessibleName = spec.get('text') or spec.get('asset')
                if spec.get('action'):
                    ctl.Cursor = Cursors.Hand
                    ctl.TabStop = True
                    ctl.Click += protected_ui(self.layout_action(spec['action']))
            elif kind == 'button':
                ctl = button(parent, spec['text'], x, y, w, h, self.layout_action(spec['action']),
                             highlight=spec.get('tone') == 'accent', start_green=spec.get('tone') == 'start')
            elif kind in ('entry', 'textarea', 'log'):
                ctl = entry(parent, x, y, w, value, multiline=kind != 'entry')
                if kind != 'entry':
                    ctl.Size = Size(w, h)
                    ctl.WordWrap = True
                    ctl.ScrollBars = ScrollBars.Vertical
                if kind == 'log':
                    ctl.ReadOnly = True
                    ctl.MaxLength = 2147483647
                if spec.get('max_length'):
                    ctl.MaxLength = spec['max_length']
                if spec.get('readonly'):
                    ctl.ReadOnly = True
                    ctl.AccessibleName = 'Discord username'
            elif kind == 'choice':
                ctl = combo(parent, x, y, w)
                choices = spec.get('items', ())
                if data_source == 'click_points':
                    choices = [(caption, key) for key, caption in POINT_LABELS]
                elif data_source == 'style_groups':
                    choices = [(caption, key) for key, caption in appearance.STYLE_LABELS.items()]
                for caption, _value in choices:
                    ctl.Items.Add(caption)
                if choices:
                    values = [v for _, v in choices]
                    ctl.SelectedIndex = values.index(value) if value in values else 0
                ctl.DropDownWidth = w
            elif kind == 'number':
                ctl = NumericUpDown()
                ctl.Location, ctl.Size = Point(x, y), Size(w, h)
                ctl.Minimum = Decimal.Parse(str(spec['low']))
                ctl.Maximum = Decimal.Parse(str(spec['high']))
                ctl.Value = Decimal.Parse(str(min(spec['high'], max(spec['low'], int(value)))))
                ctl.Font = Font('Segoe UI', FONT_PT['body'])
                ctl.BackColor, ctl.ForeColor = CARD, INK
                parent.Controls.Add(ctl)
            elif kind in ('check', 'radio'):
                ctl = RadioButton() if kind == 'radio' else CheckBox()
                ctl.Text = windows_text(spec['text'])
                if kind == 'check' and '\n' in spec['text']:
                    ctl.UseCompatibleTextRendering = True
                ctl.Font = Font('Segoe UI', FONT_PT['body'])
                ctl.Location, ctl.Size = Point(x, y), Size(w, h)
                ctl.BackColor, ctl.ForeColor = PANEL, INK
                if spec.get('ref', '').startswith('setup_checks.'):
                    value = checklist_from(self.cfg).get(spec['ref'].split('.')[1], False)
                ctl.Checked = bool(value)
                if kind == 'radio':
                    ctl.AutoEllipsis = True
                    ctl.UseMnemonic = False
                parent.Controls.Add(ctl)
            elif kind == 'checklist':
                ctl = CheckedListBox()
                ctl.CheckOnClick = True
                ctl.IntegralHeight = False
                ctl.Location, ctl.Size = Point(x, y), Size(w, h)
                ctl.Font = Font('Segoe UI', FONT_PT['body'])
                ctl.BackColor, ctl.ForeColor = CARD, INK
                ctl.BorderStyle = BorderStyle.FixedSingle
                parent.Controls.Add(ctl)
            elif kind == 'palette':
                ctl = self.make_palette(parent, spec)
            elif kind == 'list':
                ctl = ListBox()
                ctl.IntegralHeight = False
                ctl.Location, ctl.Size = Point(x, y), Size(w, h)
                ctl.Font = Font('Segoe UI', FONT_PT['body'])
                ctl.BackColor, ctl.ForeColor = CARD, INK
                ctl.BorderStyle = BorderStyle.FixedSingle
                parent.Controls.Add(ctl)
            elif kind == 'rule':
                ctl = Panel()
                ctl.Location, ctl.Size = Point(x, y), Size(w, h)
                ctl.BackColor = CARD
                parent.Controls.Add(ctl)
            else:
                raise ValueError('Unknown UI control: ' + kind)
            ref = spec.get('ref')
            if ref:
                ctl.Name = ref
                if '.' in ref:
                    collection, name = ref.split('.', 1)
                    getattr(self, collection)[name] = ctl
                else:
                    setattr(self, ref, ctl)
            ctl.AccessibleName = spec.get('ref') or spec['text']

    def make_palette(self, parent, spec):
        """Clickable palette image split into its grid of cells (skin tone, hair or facial hair colour)."""
        collection, name = spec['ref'].split('.', 1)
        if collection == 'skin_palettes':
            target = ('skin', name)
        else:
            race, part = name.split('_', 1)
            target = (appearance.COLOR_FIELDS[part], race)
        ctl = PictureBox()
        ctl.Location, ctl.Size = Point(spec['x'], spec['y']), Size(spec['w'], spec['h'])
        ctl.SizeMode = PictureBoxSizeMode.StretchImage
        ctl.BackColor = parent.BackColor
        ctl.Cursor = Cursors.Hand
        path = artwork_path(spec['asset'])
        if path:
            loaded = Bitmap(str(path))
            try:
                image = Bitmap(loaded)
            finally:
                loaded.Dispose()
            self.owned_images.append(image)
            ctl.Image = image
        ctl.MouseClick += protected_ui(lambda s, e, t=target, c=ctl: self.palette_click(t, c, e))
        ctl.Paint += lambda s, e, t=target: self.palette_paint(t, s, e)
        parent.Controls.Add(ctl)
        return ctl

    @staticmethod
    def palette_grid(target):
        field, race = target
        return appearance.SKIN_GRIDS[race] if field == 'skin' else appearance.COLOR_GRIDS[race]

    def palette_cell_rect(self, target, ctl, cell):
        cols, rows = self.palette_grid(target)
        width, height = int(ctl.Width), int(ctl.Height)
        col, row = cell % cols, cell // cols
        if target[0] == 'skin':
            x0, y0 = col * width // cols, row * height // rows
            x1, y1 = (col + 1) * width // cols, (row + 1) * height // rows
        else:
            left, top, right, bottom = appearance.color_cell_bounds(target[1], cell)
            xs, ys = appearance.COLOR_BOUNDS[target[1]]
            x0, x1 = round(left * width / xs[-1]), round(right * width / xs[-1])
            y0, y1 = round(top * height / ys[-1]), round(bottom * height / ys[-1])
        return Rectangle(x0 + 1, y0 + 1, x1 - x0 - 3, y1 - y0 - 3)

    def palette_click(self, target, ctl, e):
        field, race = target
        cols, rows = self.palette_grid(target)
        if field == 'skin':
            col = min(cols - 1, max(0, int(e.X) * cols // max(1, int(ctl.Width))))
            row = min(rows - 1, max(0, int(e.Y) * rows // max(1, int(ctl.Height))))
        else:
            xs, ys = appearance.COLOR_BOUNDS[race]
            col = sum(int(e.X) * xs[-1] >= edge * int(ctl.Width) for edge in xs[1:-1])
            row = sum(int(e.Y) * ys[-1] >= edge * int(ctl.Height) for edge in ys[1:-1])
        cell = row * cols + col
        cells = list(self.cfg['appearance'][field].get(race, []))
        if cell in cells:
            cells.remove(cell)
        elif self.app_mode.SelectedIndex == 0:
            cells = [cell]  # Fixed mode: one choice per race.
        else:
            cells.append(cell)
        self.cfg['appearance'][field][race] = sorted(cells)
        ctl.Invalidate()
        self.update_skin_status()

    def palette_paint(self, target, ctl, e):
        try:
            field, race = target
            outer, inner = Pen(Color.Black, 3), Pen(Color.Lime, 1)
            try:
                for cell in self.cfg['appearance'][field].get(race, []):
                    rect = self.palette_cell_rect(target, ctl, cell)
                    e.Graphics.DrawRectangle(outer, rect)
                    e.Graphics.DrawRectangle(inner, rect)
            finally:
                outer.Dispose()
                inner.Dispose()
        except Exception:
            pass  # Never raise from a paint callback.

    def palette_view(self):
        """Which palette the viewer shows: 'skin', 'hair' or 'facial'."""
        return ('skin', 'hair', 'facial')[max(0, int(self.app_palette_pick.SelectedIndex))]

    def active_palette(self):
        """(target, control) of the visible palette, or (None, None) when this race has none."""
        view, race = self.palette_view(), getattr(self, 'active_skin_race', 'human')
        if view == 'skin':
            return ('skin', race), self.skin_palettes[race]
        sex = getattr(self, 'active_appearance_sex', 'male')
        if view in appearance.COLOR_ASSETS.get(race, {}) and appearance.style_group(race, sex, view):
            return (appearance.COLOR_FIELDS[view], race), self.color_palettes[race + '_' + view]
        return None, None

    def update_skin_status(self):
        if not hasattr(self, 'skin_status'):
            return
        if self.app_mode.SelectedIndex == appearance.MODES.index('all'):
            self.skin_status.Text = 'Randomize All uses every valid option.'
            return
        target, _ = self.active_palette()
        race = getattr(self, 'active_skin_race', 'human')
        if target is None:
            self.skin_status.Text = ('Elves have no facial hair.' if race == 'elf'
                                     else 'No facial hair or horns for this sex.')
            return
        field, race = target
        cells = self.cfg['appearance'][field].get(race, [])
        noun, none = ('shade', 'No shade selected: random') if field == 'skin' else ('colour', 'No colour selected: game default')
        self.skin_status.Text = '{} {}{} selected'.format(len(cells), noun, '' if len(cells) == 1 else 's') if cells else none

    def refresh_palette_view(self, sender=None, args=None):
        view, race = self.palette_view(), getattr(self, 'active_skin_race', 'human')
        for key, ctl in self.skin_palettes.items():
            ctl.Visible = view == 'skin' and key == race
        _, active = self.active_palette()
        for ctl in self.color_palettes.values():
            ctl.Visible = ctl is active
        self.update_skin_status()

    def show_race_palette(self, race):
        self.active_skin_race = race
        self.refresh_palette_view()

    def appearance_selection_changed(self, key):
        if getattr(self, '_changing_appearance', False):
            return
        group, value = key.split('_', 1)
        checked = self.app_checks[key].Checked
        self._changing_appearance = True
        try:
            if checked and self.app_mode.SelectedIndex == 0:
                for other, box in self.app_checks.items():
                    if other.startswith(group + '_') and other != key:
                        box.Checked = False
        finally:
            self._changing_appearance = False
        selected_races = [r for r in appearance.RACES if self.app_checks['race_' + r].Checked]
        current = getattr(self, 'active_skin_race', 'human')
        race = (value if group == 'race' and checked else
                current if current in selected_races else next(iter(selected_races), 'human'))
        selected_sexes = [s for s in appearance.SEXES if self.app_checks['sex_' + s].Checked]
        current_sex = getattr(self, 'active_appearance_sex', 'male')
        sex = (value if group == 'sex' and checked else current_sex if current_sex in selected_sexes
               else next(iter(selected_sexes), 'male'))
        self.active_appearance_sex = sex
        self.show_race_palette(race)
        target = appearance.style_group(race, sex, 'hair')
        self.app_style_group.SelectedIndex = list(appearance.STYLE_LABELS).index(target)

    def appearance_mode_changed(self, sender=None, args=None):
        if getattr(self, '_loading_account', False):
            return
        if self.app_mode.SelectedIndex != 0:
            self.update_skin_status()
            return
        # Switching back to Fixed retains one selected race, sex and style.
        self._changing_appearance = True
        try:
            for group, values in (('race', appearance.RACES), ('sex', appearance.SEXES)):
                selected = [v for v in values if self.app_checks[group + '_' + v].Checked]
                keep = getattr(self, 'active_skin_race', 'human') if group == 'race' else None
                keep = keep if keep in selected else next(iter(selected), None)
                for value in selected:
                    self.app_checks[group + '_' + value].Checked = value == keep
            self.store_style_items()
            for key, values in self.cfg['appearance']['styles'].items():
                self.cfg['appearance']['styles'][key] = values[:1]
            for field in ('skin', 'hair_color', 'facial_color'):
                for race, values in self.cfg['appearance'][field].items():
                    self.cfg['appearance'][field][race] = values[:1]
        finally:
            self._changing_appearance = False
        self.app_style_key = None
        self.style_group_changed()
        for ctl in list(self.skin_palettes.values()) + list(self.color_palettes.values()):
            ctl.Invalidate()
        race = next((r for r in appearance.RACES if self.app_checks['race_' + r].Checked), 'human')
        self.appearance_selection_changed('race_' + race)

    def clear_skin(self, sender, args):
        """Clear the selection in the palette currently shown (skin tone, hair or facial hair colour)."""
        target, ctl = self.active_palette()
        if target is None:
            return
        field, race = target
        self.cfg['appearance'][field][race] = []
        ctl.Invalidate()
        self.update_skin_status()

    def load_appearance_controls(self):
        look = self.cfg['appearance']
        self.app_enabled.Checked = bool(look['enabled'])
        mode = look['mode'] if look['mode'] in appearance.MODES else 'fixed'
        self.app_mode.SelectedIndex = appearance.MODES.index(mode)
        for sex in appearance.SEXES:
            self.app_checks['sex_' + sex].Checked = sex in look['sex']
        for race in appearance.RACES:
            self.app_checks['race_' + race].Checked = race in look['race']
        self.app_style_key = None
        self.appearance_selection_changed('race_' + next(iter(look['race']), 'human'))
        self.style_group_changed()

    def store_style_items(self):
        if self.app_style_key:
            self.cfg['appearance']['styles'][self.app_style_key] = sorted(
                int(i) for i in self.app_style_items.CheckedIndices)

    def style_group_changed(self, sender=None, args=None):
        self.store_style_items()
        keys = list(appearance.STYLE_LABELS)
        key = keys[max(0, int(self.app_style_group.SelectedIndex))]
        self.app_style_key = key
        chosen = set(self.cfg['appearance']['styles'].get(key, []))
        self.app_style_items.Items.Clear()
        for index, option in enumerate(appearance.STYLE_OPTIONS[key]):
            self.app_style_items.Items.Add(option, index in chosen)

    def read_appearance_controls(self):
        if not hasattr(self, 'app_enabled'):
            return
        look = self.cfg['appearance']
        look['enabled'] = bool(self.app_enabled.Checked)
        look['mode'] = appearance.MODES[max(0, int(self.app_mode.SelectedIndex))]
        look['sex'] = [s for s in appearance.SEXES if self.app_checks['sex_' + s].Checked]
        look['race'] = [r for r in appearance.RACES if self.app_checks['race_' + r].Checked]
        self.store_style_items()

    def save_appearance(self, sender, args):
        self.save_settings()
        issues = appearance.validate(self.cfg)
        missing = [key for key in appearance.required_points(self.cfg) if key not in self.cfg['points']]
        if issues:
            raise ValueError('Appearance needs attention: ' + ' '.join(issues))
        self.log_line('Appearance saved: {}.'.format(
            'customized, ' + self.cfg['appearance']['mode'] if self.cfg['appearance']['enabled'] else 'game default'))
        if missing:
            window_message('Appearance saved.\n\nBefore creating characters, record these click points under '
                           'Setup > Game Client > Click points:\n\n- ' + '\n- '.join(
                               dict(POINT_LABELS).get(k, k) for k in missing))

    def randomize_all_appearance(self, sender, args):
        self.app_enabled.Checked = True
        self.app_mode.SelectedIndex = appearance.MODES.index('all')
        self.save_appearance(sender, args)

    def selected_point(self):
        index = int(self.point_pick.SelectedIndex)
        if not 0 <= index < len(POINT_LABELS):
            raise RuntimeError('Choose a click point first.')
        return POINT_LABELS[index]

    def update_point_status(self, sender=None, args=None):
        if not hasattr(self, 'point_status'):
            return
        key, caption = self.selected_point()
        value = self.cfg['points'].get(key)
        recorded = key in self.cfg.get('point_overrides', {})
        source = ('recorded by you' if recorded else 'built-in' if key in BUILT_IN_POINTS
                  else 'no built-in value: record it before use')
        self.point_status.Text = '{}\r\nCurrent: {} · {}\r\nRecorded points: {}'.format(
            caption, '({}, {})'.format(*value) if value else 'not set', source,
            len(self.cfg.get('point_overrides', {})))
        self.point_status.ForeColor = GREEN if value else WARNING

    def record_point(self, sender, args):
        if self.busy() or self.record_timer is not None:
            return
        self.chosen_window()
        key, caption = self.selected_point()
        if MessageBox.Show('Show the screen with this control in Classic Client:\n\n  {}\n\n'
                           'Click OK, then hover over its centre within 4 seconds.\n'
                           'Do not click anything in the game.'.format(caption),
                           'Record click point', MessageBoxButtons.OKCancel,
                           MessageBoxIcon.Information) != DialogResult.OK:
            return
        self.record_key = key
        self.WindowState = FormWindowState.Minimized
        self.record_timer = Timer()
        self.record_timer.Interval = 4000
        self.record_timer.Tick += protected_ui(self.store_recorded_point)
        self.record_timer.Start()

    def store_recorded_point(self, sender, args):
        self.record_timer.Stop()
        self.record_timer.Dispose()
        self.record_timer = None
        self.WindowState = FormWindowState.Normal
        key, self.record_key = self.record_key, None
        area = game_area(self.cfg['window_title'])
        scale = area.require_scale()
        cx, cy = native_mouse.cursor_position()
        point = [(cx - area.left) / scale, (cy - area.top) / scale]
        if not valid_point(point):
            raise RuntimeError('The pointer was outside the 640x480 game area; nothing was recorded.')
        point = [int(round(point[0])), int(round(point[1]))]
        self.cfg.setdefault('point_overrides', {})[key] = point
        self.cfg['points'] = merged_points(self.cfg['point_overrides'])
        self.save_settings()
        self.update_point_status()
        self.log_line('Recorded click point {}: ({}, {}) in the 640×480 game area.'.format(key, *point))

    def reset_point(self, sender, args):
        if self.busy():
            return
        key, caption = self.selected_point()
        if self.cfg.get('point_overrides', {}).pop(key, None) is None:
            return
        self.cfg['points'] = merged_points(self.cfg['point_overrides'])
        self.save_settings()
        self.update_point_status()
        self.log_line('Click point {} reset to its built-in value.'.format(key))

    def refresh_health_status(self, sender=None, args=None):
        if not hasattr(self, 'health_status') or not hasattr(self, 'test_status_label'):
            return
        state = self.update_isolation_state()
        checks = sum(bool(box.Checked) for box in self.setup_checks.values())
        self.health_status.Text = '\r\n'.join([
            'Version: ' + VERSION,
            'Data folder: %LOCALAPPDATA%\\Krampuslauf',
            'Setup checklist: {}/{} confirmed'.format(checks, len(SETUP_STEPS)),
            'Classic Client: ' + ('Selected for this launch' if self.cfg.get('window_title') else 'Not selected'),
            'Profile isolation: ' + str(state.get('status', 'Unknown')),
            'Click points: built-in 640×480 layout, {} recorded'.format(len(self.cfg.get('point_overrides', {}))),
            'Shard map: ' + map_status(MAP_FILE, self.cfg),
            'Seeder history: ' + (self.account_display_name() if self.active_profile_key else 'Choose an account'),
            'Appearance: ' + (self.cfg['appearance']['mode'].title() if self.cfg['appearance']['enabled']
                              else 'Game default'),
            'Theme: ' + ACTIVE_THEME.title(),
        ])
        self.update_setup_state()

    def open_project_link(self, sender, args):
        # A user click opens exactly the supplied project URL in the default browser.
        import webbrowser
        webbrowser.open(PROJECT_URL)

    def open_donation_link(self, sender=None, args=None):
        import webbrowser
        webbrowser.open(DONATION_URL)


    def open_data_folder(self, sender, args):
        os.startfile(str(APP_DIR))

        # Main window deliberately has no activity log / pause / stop footer.
        # The sole Start controls live on their corresponding mode tabs.

    def build_setup(self):
        self.mount_page('setup')
        self.mount_page('profiles')
        self.offer_razor_root()
        self.update_setup_state()
        self.update_isolation_state()


    def update_setup_state(self):
        self.update_setup_progress()

    def offer_razor_root(self):
        """Fill the only detected Razor folder. A picker can hide behind an elevated window."""
        if not hasattr(self, 're_root_field') or str(self.re_root_field.Text).strip():
            return
        roots = find_razor_roots()
        if len(roots) == 1:
            self.re_root_field.Text = str(roots[0])
            self.cfg['razor_data_root'] = str(roots[0])

    def show_bridge_script(self, sender=None, args=None):
        """Reveal the bridge file in Explorer. Do not launch it with desktop Python."""
        import subprocess
        import sys
        from pathlib import Path
        base = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
        path = base / 'krampuslauf_bridge.py'
        if not path.is_file():
            raise RuntimeError('krampuslauf_bridge.py was not found beside Krampuslauf. Keep the whole application folder together.')
        subprocess.Popen(['explorer', '/select,', str(path)])
        self.log_line('Showing krampuslauf_bridge.py. Add it in Razor Scripting and enable AutoStart at Login.')

    def update_setup_progress(self):
        if not hasattr(self, 'setup_progress'):
            return
        if getattr(self, 'setup_checks', None):
            self.cfg['setup_checklist'] = {key: bool(box.Checked) for key, box in self.setup_checks.items()}
        try:
            state = session_status(APP_DIR)
            isolated = bool(state.get('active') and state.get('states') == ['temporary', 'temporary'])
        except Exception:
            isolated = False
        verified = 'VERIFIED' in map_status(MAP_FILE, self.cfg)
        steps = (
            (not setup_missing(self.cfg), 'Checklist saved', 'Check every box, then Save checklist.'),
            (isolated, 'Profiles isolated', 'Close Razor and the client, then Prepare profiles.'),
            (bool(self.cfg.get('window_title')), 'Game window selected', 'Go: Game, then select the client.'),
            (bool(getattr(self, 'screen_recognized', False)), 'Current screen recognized', 'Go: Game, then Check current screen.'),
            (verified, 'Shard list verified', 'Go: Shards, then Scan / resume.'),
            (bool(self.cfg.get('manual_test_passes', {}).get('bridge')), 'Bridge tested', 'Diagnostics, then RE bridge.'),
        )
        pending = next((hint for ready, _label, hint in steps if not ready), 'Test one shard on Gift Cycler.')
        lines = ['OK   ' + label if ready else 'NO   ' + label for ready, label, _hint in steps]
        lines.append('Next: ' + pending)
        self.setup_progress.Text = '\n'.join(lines)

    def save_setup_checklist(self, sender, args):
        self.cfg['setup_checklist'] = {key: bool(box.Checked) for key, box in self.setup_checks.items()}
        self.cfg.pop('monkey_setup', None)
        self.save_settings()
        missing = setup_missing(self.cfg)
        self.update_setup_progress()
        self.log_line('Setup checklist: {}/{} steps confirmed.'.format(
            len(SETUP_STEPS)-len(missing), len(SETUP_STEPS)))
        if missing:
            window_message('Complete these steps and check their boxes before running:\n\n- ' +
                           '\n- '.join(missing))
        else:
            window_message('Checklist saved.\n\nNEXT: Close Razor and Classic Client, then prepare profiles.')
            self.show_page('profiles')

    def choose_re_root(self, sender, args):
        """Auto-detect common data locations; NEVER block on a Shell folder picker.

        For custom installations, the field accepts a path pasted from Explorer.
        Only folder names are inspected, never the password/shard file contents.
        """
        if self.busy():
            raise RuntimeError('Stop automation before changing the Razor data directory.')
        candidate = str(self.re_root_field.Text).strip()
        if candidate:
            try:
                root = normalize_root(candidate)
                self.cfg['razor_data_root'] = str(root)
                self.re_root_field.Text = str(root)
                self.save_settings()
                self.log_line('Razor data folder validated.')
                return
            except (OSError, IsolationError) as exc:
                self.log_line('Pasted path not valid: {}'.format(exc))
        roots = find_razor_roots()
        if len(roots) == 1:
            self.re_root_field.Text = str(roots[0])
            self.cfg['razor_data_root'] = str(roots[0])
            self.save_settings()
            self.log_line('Razor data folder detected and validated.')
        elif len(roots) > 1:
            # Do not silently choose among multiple RE installations.
            text = '\n'.join(str(r) for r in roots[:8])
            window_message('Multiple Razor data folders found. Copy the correct path into the text box:\n\n' + text)
        else:
            window_message('No standard Razor data folder was found. In File Explorer, open the folder '
                           'that contains both Profiles and Backup, copy its path, and paste it into the box. '
                           'Then click Find / validate folder. There is no Browse button, because that window '
                           'can open behind Krampuslauf. No password files are read.')

    def update_isolation_state(self):
        try:
            status = session_status(APP_DIR)
            text = status['status']
            if status['active']:
                text += ' — {} profiles preserved; {} links temporarily removed'.format(
                    status['profiles'], status['links'])
            self.isolation_status_label.Text = text
            self.isolation_status_label.ForeColor = (GREEN if status['active'] and
                                                      status.get('states') == ['temporary','temporary']
                                                      else MUTED)
            return status
        except Exception as exc:
            # A damaged recovery record must NOT prevent the GUI from starting.
            # Prepare/Restore will still refuse modifications until repaired.
            self.isolation_status_label.Text = 'RECOVERY ERROR: ' + str(exc)
            self.isolation_status_label.ForeColor = RED
            return {'active': False, 'status': 'RECOVERY ERROR: ' + str(exc)}

    def check_isolation_status(self, sender, args):
        status = self.update_isolation_state()
        self.log_line('Razor profile isolation: ' + status['status'])

    def prepare_profile_mode(self, sender, args):
        if self.busy():
            raise RuntimeError('Stop Gift Cycler/Character Seeder first.')
        root = str(self.re_root_field.Text).strip()
        if not root:
            raise RuntimeError('Paste the Razor data folder path or click Find Folder.')
        root = str(normalize_root(root))
        self.re_root_field.Text = root
        self.cfg['razor_data_root'] = root
        self.save_settings()
        if MessageBox.Show('Razor Enhanced AND Classic Client must be CLOSED.\n\n'
                           'Krampuslauf will back up both NewProfiles files, preserve all profile names, '
                           'temporarily unlink characters, and select default.\n\n'
                           'No named profile folder, password or launcher file will be changed.\n\n'
                           'Prepare now?', 'Prepare Krampuslauf', MessageBoxButtons.YesNo,
                           MessageBoxIcon.Warning) != DialogResult.Yes:
            return
        try:
            result = prepare_re_profiles(root, APP_DIR)
        finally:
            self.update_isolation_state()
        self.log_line('Profile isolation prepared: {} names kept, {} old character links cleared.'.format(
            result['profiles'], result['links']))
        window_message('Profiles prepared.\n\nNEXT: Start Razor with the default profile selected, '
                       'then launch the game through Razor. '
                       'Open Game client and select the game window.\n\n'
                       'When finished, close both programs and use Setup > Profiles > Restore original profiles.')

    def restore_profile_mode(self, sender, args):
        if self.busy():
            raise RuntimeError('Stop Gift Cycler/Character Seeder first.')
        state = session_status(APP_DIR)
        if not state['active']:
            window_message('No temporary profile isolation is active.')
            return
        if MessageBox.Show('CLOSE Razor Enhanced AND Classic Client first.\n\n'
                           'Restore original character links from verified recovery backups?\n'
                           'Any new character/profile links made during isolation may be discarded.',
                           'Restore Original Profiles', MessageBoxButtons.YesNo,
                           MessageBoxIcon.Warning) != DialogResult.Yes:
            return
        try:
            result = restore_re_profiles(APP_DIR)
        except IsolationError as exc:
            if 'modified one of the temporary registries' not in str(exc):
                self.update_isolation_state()
                raise
            if MessageBox.Show('Razor Enhanced changed a temporary registry.\n\n'
                               'Restoring will discard those temporary changes but preserve '
                               'the original registry exactly as backed up. Continue?',
                               'Changed Temporary Registry', MessageBoxButtons.YesNo,
                               MessageBoxIcon.Warning) != DialogResult.Yes:
                return
            result = restore_re_profiles(APP_DIR, allow_modified=True)
        self.update_isolation_state()
        self.log_line(result['status'])
        window_message(result['status'] + '\n\nStart Razor Enhanced to confirm your original profile links.')

    def require_setup(self):
        self.cfg['setup_checklist'] = {k: bool(v.Checked) for k, v in self.setup_checks.items()}
        missing = setup_missing(self.cfg)
        if missing:
            self.show_page('setup')
            raise RuntimeError('Finish the setup checklist and check every box before running:\n- ' +
                               '\n- '.join(missing))
        state = session_status(APP_DIR)
        if not state['active'] or state.get('states') != ['temporary', 'temporary']:
            self.show_page('profiles')
            raise RuntimeError('Prepare Krampuslauf on Setup > Profiles first. Close Razor Enhanced and Classic Client, then click Prepare Krampuslauf.')

    def build_home(self):
        self.mount_page('gift')
        self.cycle_status_label.Text = 'Cycle: ' + self.cfg.get('gift_cycle_id', '')[:8]

    def sync_shard_group(self, sender, args):
        selected = sender.SelectedIndex
        for picker in (self.gift_shard_group, self.seed_shard_group):
            if picker.SelectedIndex != selected:
                picker.SelectedIndex = selected

    def new_gift_cycle(self, sender=None, args=None):
        if self.busy():
            raise RuntimeError('Stop the active run before starting a new cycle.')
        if MessageBox.Show('Start a NEW gift cycle? This creates a separate anonymous progress record.\n'
                           'Use it when switching accounts or beginning a new gift event.\n\n'
                           'The previous cycle will remain saved, but this run will start from zero.',
                           'New Gift Cycle', MessageBoxButtons.YesNo,
                           MessageBoxIcon.Question) != DialogResult.Yes:
            return
        self.cfg['gift_cycle_id'] = uuid.uuid4().hex[:16]
        self.cycle_status_label.Text = 'Cycle: '+self.cfg['gift_cycle_id'][:8]
        self.save_settings()
        self.log_line('New anonymous gift cycle created; prior progress preserved.')

    def build_calibration(self):
        self.mount_page('client')
        self.screen_status.Text = 'Select the client, open any game menu, then click Check current screen.'
        self.update_point_status()

    def verify_screen(self, sender, args):
        """Read-only: report game-area size, scaling and the recognized menu."""
        if self.busy():
            return
        self.chosen_window()
        area = game_area(self.cfg['window_title'])
        scale = area.scale
        lines = ['Game area: {}×{} at ({}, {}).'.format(area.width, area.height, area.left, area.top)]
        if scale is None:
            self.screen_recognized = False
            lines.append('Not a 640×480 menu screen (in-world view or unusual scaling). '
                         'Return the client to a game menu and check again.')
            self.screen_status.Text = '\r\n'.join(lines)
            self.screen_status.ForeColor = WARNING
            self.update_setup_progress()
            return
        worker = GameWorker(json.loads(json.dumps(self.cfg)), 'screen_check', 'diagnostic',
                            self.stop_event, self.emit, self.pause_event)
        state = worker.state()
        best = max(worker.marker_scores(), default=(0.0, 'none'))
        lines.append('Display scaling: {:.0%} of the 640×480 menu layout.'.format(scale))
        lines.append('Recognized screen: {}{}'.format(
            state, '' if state != 'unknown' else ' (best match {} at {:.2f})'.format(best[1], best[0])))
        self.screen_recognized = state != 'unknown'
        self.screen_status.Text = '\r\n'.join(lines)
        self.screen_status.ForeColor = GREEN if self.screen_recognized else WARNING
        self.update_setup_progress()
        self.log_line('SCREEN CHECK: area {}x{}, scale {:.2f}, state {}, best {} {:.2f}.'.format(
            area.width, area.height, scale, state, best[1], best[0]))

    def build_testing(self):
        self.mount_page('diagnostics')


    def build_shards(self):
        self.mount_page('shards')
        self.map_status_label.Text = map_status(MAP_FILE, self.cfg)


    def build_seeder(self):
        for key in ('seeder', 'looks'):
            self.mount_page(key)
        self.load_appearance_controls()


    def update_seed_name_mode(self, sender=None, args=None):
        fantasy = bool(self.seed_mode_pick.SelectedIndex == 1)
        self.seed_prefix_field.Enabled = not fantasy
        self.seed_style_pick.Enabled = fantasy
        self.seed_name_hint.Text = ('Matches race and sex.\nMax 16 characters.'
                                    if fantasy else 'Format: Llama CAT b\nMax 16 characters; prefix 1–10 letters.')

    def preview_seed_names(self, sender, args):
        self.save_settings()
        if self.cfg.get('seed_naming_mode') == 'fantasy':
            from fantasy_name_generator import FantasyNameGenerator
            style = self.cfg.get('seed_fantasy_style', 'mixed')
            import appearance
            look = appearance.selection_pools(self.cfg)
            categories = [r + '_' + sex for r in (look['race'] or ['human'])
                          for sex in (look['sex'] or ['male'])] if look['enabled'] else ['human_male']
            generator = FantasyNameGenerator()
            examples = [category.replace('_', ' ').title() + ': ' +
                        generator.generate(style=style, category=category)
                        for category in (categories * 12)[:12]]
            window_message('Fantasy-name mode ({})\n\n{}\n\n'
                           'These are previews only, not reserved.\n'
                           'Naming changes apply to future submissions. '
                           'Already submitted characters keep their names.'.format(
                               style, '\n'.join(examples)), 'Fantasy name preview')
            return
        from seeder_rules import generated_name
        prefix = str(self.seed_prefix_field.Text).strip()
        examples = ('Legends', 'Atlantic', 'Lake Superior')
        names = [generated_name(prefix, '', 0, n, shard=examples[0]) for n in (0, 1)]
        names += [generated_name(prefix, '', 1, 0, shard=examples[1]),
                  generated_name(prefix, '', 2, 0, shard=examples[2])]
        window_message('Legends:       {} / {}\n'
                       'Atlantic:       {}\n'
                       'Lake Superior: {}\n\n'
                       'Prefix + space + 3-letter shard + space + slot letter (a-g).\n'
                       'No account code. Prefix: 1-10 letters; total: max 16.'.format(*names),
                       'Character name preview')

    def initialize_accounts(self):
        from account_profiles import new_catalog, complete_catalog
        self.account_catalog = complete_catalog(load_json(APP_DIR / 'account_catalog.json', new_catalog()))
        slot = self.cfg.get('selected_account_slot', self.account_catalog.get('selected', 'main'))
        if slot not in self.account_catalog['accounts']:
            slot = 'main'
        self.select_account(slot, initial=True)

    def account_display_name(self):
        from account_profiles import display_name
        return display_name(self.account_catalog, self.selected_account_slot)

    def account_radio_changed(self, slot):
        if (getattr(self, '_loading_account', False) or not hasattr(self, 'account_catalog')
                or not self.account_radios[slot].Checked):
            return
        self.select_account(slot)

    def select_account(self, slot, initial=False):
        from account_profiles import ACCOUNT_SETTINGS, display_name
        from uuid import uuid4
        if not initial and self.active_profile_key:
            self.save_settings()
        self._loading_account = True
        self._changing_appearance = True
        try:
            self.selected_account_slot = slot
            self.account_catalog['selected'] = slot
            entry = self.account_catalog['accounts'][slot]
            self.active_profile_key = entry['history_id']
            self.cfg['account_history_id'] = entry['history_id']
            self.cfg['selected_account_slot'] = slot
            saved = load_json(APP_DIR / 'account_profiles.json', {}).get('profiles', {}).get(entry['history_id'], {})
            for key in ACCOUNT_SETTINGS:
                if key in saved:
                    self.cfg[key] = saved[key]
            if not saved:
                self.cfg['excluded'], self.cfg['skip_slots'] = [], {}
            group = saved.get('shard_group', 'all')
            self.gift_shard_group.SelectedIndex = next(
                (index for index, (_, value) in enumerate(SHARD_GROUP_OPTIONS) if value == group), 0)
            if not initial and 'seed_route_delay_seconds' not in saved:
                self.cfg['seed_route_delay_seconds'] = 5
            if 'gift_cycle_id' not in saved:
                self.cfg['gift_cycle_id'] = uuid4().hex[:16]
            from shard_policy import normalize_shards
            normalize_shards(self.cfg)
            self.cfg['appearance'] = appearance.settings(self.cfg)
            self.account_field.Text = str(entry.get('nickname', ''))
            for key, radio in self.account_radios.items():
                radio.Text = display_name(self.account_catalog, key)
                radio.Checked = key == slot
            self.seed_capacity_pick.SelectedIndex = (5,6,7).index(int(self.cfg.get('account_cap',7)))
            self.reserve_slot_checkbox.Checked = bool(self.cfg.get('reserve_transfer_slot',False))
            self.seed_route_delay.Value = Decimal.Parse(str(self.cfg.get('seed_route_delay_seconds', 5)))
            self.seed_prefix_field.Text = self.cfg.get('seed_name_prefix','Llama')
            self.seed_mode_pick.SelectedIndex = 1 if self.cfg.get('seed_naming_mode','fantasy') == 'fantasy' else 0
            self.seed_style_pick.SelectedIndex = ('single','full','mixed').index(self.cfg.get('seed_fantasy_style','mixed'))
            self.seed_profession_pick.SelectedIndex = (appearance.PROFESSIONS+('random',)).index(self.cfg.get('seed_profession','blacksmith'))
            self.create_missing_checkbox.Checked = bool(self.cfg.get('create_missing',False))
            self.gift_wait.Value = Decimal.Parse(str(self.cfg.get('gift_wait',5)))
            self.post_logout.Value = Decimal.Parse(str(self.cfg.get('post_logout_seconds',7)))
            self.online_cooldown.Value = Decimal.Parse(str(self.cfg.get('online_cooldown_seconds',305)))
            if hasattr(self, 'fast_last_shard'):
                self.fast_last_shard.Checked = bool(self.cfg.get('fast_last_shard', False))
            self.slots_field.Text = self.format_slot_rules(self.cfg.get('skip_slots',{}))
            self.cycle_status_label.Text = 'Cycle: ' + str(self.cfg.get('gift_cycle_id',''))[:8]
            self.load_appearance_controls()
            self.refresh_exclusions()
            self.update_seed_name_mode()
        finally:
            self._loading_account = False
            self._changing_appearance = False
        look = self.cfg['appearance']
        self.appearance_selection_changed('race_' + next(iter(look['race']), 'human'))
        self.update_account_summary()
        self.save_settings()

    def update_account_summary(self):
        from cycler_engine import SEED_PROGRESS_FILE
        state = load_json(SEED_PROGRESS_FILE, {})
        profile = state.get('profiles', {}).get(self.active_profile_key, {})
        from shard_policy import is_supported
        finished = sum(r.get('standalone_seed', {}).get('status') == 'complete' for shard, r in profile.items() if is_supported(shard))
        from account_profiles import shard_seed_complete
        from shard_policy import supported_shards
        remaining = [shard for shard in supported_shards(self.cfg['shards']) if shard not in self.cfg.get('excluded', [])
                     and not shard_seed_complete(profile.get(shard, {}),
                         int(self.cfg.get('account_cap',7)))]
        self.account_history_summary.Text = '{}: {} finished shard(s). Next: {}.'.format(
            self.account_display_name(), finished, remaining[0] if remaining else 'all finished')

    def persist_profile_if_active(self):
        if not self.active_profile_key or getattr(self, '_loading_account', False):
            return
        from account_profiles import settings_snapshot
        data = load_json(APP_DIR / 'account_profiles.json', {})
        data.setdefault('profiles', {})[self.active_profile_key] = settings_snapshot(self.cfg)
        atomic_json(APP_DIR / 'account_profiles.json', data)
        atomic_json(APP_DIR / 'account_catalog.json', self.account_catalog)

    def account_label_changed(self, sender=None, args=None):
        if getattr(self, '_loading_account', False) or not hasattr(self, 'account_catalog'):
            return
        from account_profiles import NICKNAME_LIMIT
        self.account_catalog['accounts'][self.selected_account_slot]['nickname'] = str(self.account_field.Text).strip()[:NICKNAME_LIMIT]
        self.account_radios[self.selected_account_slot].Text = self.account_display_name()

    def load_account_profile(self, sender=None, args=None, silent=False):
        self.select_account(self.selected_account_slot, initial=True)

    def save_account_profile(self, sender=None, args=None):
        if not hasattr(self, 'account_catalog') or getattr(self, '_loading_account', False):
            return
        self.account_label_changed()
        self.save_settings()
        self.update_account_summary()

    def require_active_account_profile(self):
        if not self.active_profile_key:
            raise RuntimeError('Choose an account under Character Seeder before starting.')

    def learn_shard_names(self,sender,args):
        if self.busy():return
        try:
            self.save_settings()
            self.apply_verified_map()
            self.chosen_window()
            order=list(self.cfg.get('navigation_shards', self.cfg.get('shards',[])))
            if not self.cfg.get('verified_order') or len(order)<2:
                raise RuntimeError('Confirm or scan the shard order first (Shards page).')
            if MessageBox.Show('Open the SHARD LIST first.\n\n'
                 'The app scrolls the list to the top, then down one row at a time (about 20 seconds), '
                 'saving a small picture of each shard name. Only the mouse wheel is used: '
                 'no shard is clicked and no key is pressed.\n\n'
                 'Pictures are labelled from the shard order you verified. Press Escape to stop.',
                 'Learn shard names',MessageBoxButtons.YesNo,MessageBoxIcon.Question)!=DialogResult.Yes:return
            cfg=json.loads(json.dumps(self.cfg))
            worker=GameWorker(cfg,'learn_shards','learn_shards',self.stop_event,self.emit,self.pause_event)
            self.game_worker=worker
            self.run_job(lambda:worker.learn_shard_names(order))
        except Exception as exc:window_message(exc,error=True)

    def scan_shards(self,sender,args):
        if self.busy():return
        try:
            self.save_settings()
            self.chosen_window()
            partial=load_map(MAP_FILE,self.cfg,require_complete=False)
            prior=list(partial['shards']) if partial and not partial.get('complete') else []
            detail=('Resume at {}/27. YES = resume; NO = scan from row 1; CANCEL = stop.'
                    .format(len(prior)+1)) if prior else 'Start new 27-shard scan? YES = start; CANCEL = stop.'
            response=MessageBox.Show('Open the SHARD LIST with scrollbar at the VERY TOP.\n\n'
                 'All identities are checked against the client window title.\n'
                 'A missing click gets three attempts, and each completed row is saved.\n'
                 'Empty shards that open New Character are supported.\n\n'+detail,
                 'Scan / Resume Shards',MessageBoxButtons.YesNoCancel,
                 MessageBoxIcon.Warning)
            if response==DialogResult.Cancel:return
            if not prior and response!=DialogResult.Yes:return
            resume=bool(prior and response==DialogResult.Yes)
            cfg=json.loads(json.dumps(self.cfg))
            scanner=ShardScanner(cfg,'shard_scan','scan',self.stop_event,self.emit,self.pause_event)
            self.game_worker = scanner
            def job():
                try:
                    names=scanner.scan(27,resume=resume)
                    self.events.put(('scan_map_ready',names))
                finally:
                    self.events.put(('scan_progress_refresh',None))
            self.run_job(job)
        except Exception as exc:window_message(exc,error=True)

    def apply_verified_map(self):
        if not self.cfg.get('use_scanned_map',True):return
        result=load_map(MAP_FILE,self.cfg)
        if result:
            self.cfg['navigation_shards'] = list(result['shards'])
            names=supported_shards(result['shards'])
            if self.cfg['shards']!=names:
                self.cfg['shards']=names
                self.cfg['verified_order']=True
                self.shard_text.Text=windows_text('\n'.join(names))
                self.sort_confirm.Checked=True
                self.refresh_exclusions()
                self.refresh_test_shards()
            self.cfg['verified_order']=True
            self.log_line('Using title-verified shard map for time zone: '+timezone_key())
        elif MAP_FILE.exists():
            raise RuntimeError('A saved shard map exists, but is incomplete or does not match the current time zone / row geometry. Rescan before running.')

    def start_seeder_run(self,sender,args):
        if self.busy():return
        try:
            self.require_setup()
            self.save_settings()
            self.apply_verified_map()
            self.chosen_window()
            issues=test_config(self.cfg)
            if issues:raise ValueError('Setup incomplete: '+'; '.join(issues))
            self.require_active_account_profile()
            targets = run_shards(self.cfg)
            if not targets:
                raise ValueError('No included shards in the selected shard group.')
            self.persist_profile_if_active()
            cfg=json.loads(json.dumps(self.cfg))
            worker=MergedWorker(cfg,self.account_display_name(),'seeder',
                                self.stop_event,self.emit,self.pause_event)
            worker.check_seed_setup()
            if len(game_windows())!=1:raise RuntimeError('Exactly one Classic Client window required.')
            prompt = ('This run will write history to your {} account.\n\n'
                      'Create characters on {} included shard(s), choose Moonglow, '
                      'and log out at the inn. Finished shards will be skipped.\n\nProceed?').format(
                          self.account_display_name(), len(targets))
            if MessageBox.Show(prompt, 'Start Character Seeder', MessageBoxButtons.YesNo,
                               MessageBoxIcon.Question) != DialogResult.Yes:
                return
            self.game_worker=worker
            self.run_job(worker.run_seeder, compact=True)
        except Exception as exc:window_message(exc,error=True)

    def build_settings(self):
        self.mount_page('status')
        self.mount_page('appearance')


    def load_windows(self, sender=None, args=None):
        self.window_by_label.clear()
        current_title = self.cfg.get("window_title", "")
        self.game_pick.Items.Clear()
        selected = -1
        for w, pid in game_windows():
            text = "{}   [PID {}, HWND {:X}]".format(w.title, pid, w._hWnd)
            self.window_by_label[text] = w._hWnd
            idx = self.game_pick.Items.Add(text)
            if w.title == current_title:
                selected = idx
        if selected >= 0:
            self.game_pick.SelectedIndex = selected
        elif self.game_pick.Items.Count == 1:
            self.game_pick.SelectedIndex = 0
        elif self.game_pick.Items.Count == 0:
            self.status.Text = "No official client.exe window found; start Classic Client through Razor Enhanced."

    def select_window(self, sender, args):
        shown = str(self.game_pick.SelectedItem or "")
        if shown in self.window_by_label:
            try:
                self.cfg["window_title"] = pin_window(self.window_by_label[shown])
                self.log_line("Selected official Classic Client window (title not logged or stored).")
                self.save_settings()
            except Exception as exc:
                window_message(exc, error=True)

    def refresh_exclusions(self):
        from shard_policy import supported_shards
        self._loading_shards = True
        try:
            self.shard_checks.Items.Clear()
            excluded = set(self.cfg.get('excluded', []))
            for shard in supported_shards(self.cfg['shards']):
                self.shard_checks.Items.Add(shard, shard not in excluded)
        finally:
            self._loading_shards = False

    def shard_selection_changed(self, sender, args):
        if getattr(self, '_loading_shards', False):
            return
        shard = str(self.shard_checks.Items[int(args.Index)])
        excluded = set(self.cfg.get('excluded', []))
        if str(args.NewValue) == 'Checked':
            excluded.discard(shard)
        else:
            excluded.add(shard)
        self.cfg['excluded'] = [name for name in self.cfg['shards'] if name in excluded]
        self.save_settings()

    def select_all_shards(self, sender=None, args=None):
        self.cfg['excluded'] = []
        self.refresh_exclusions()
        self.save_settings()

    def select_no_shards(self, sender=None, args=None):
        self.cfg['excluded'] = list(self.cfg['shards'])
        self.refresh_exclusions()
        self.save_settings()

    def save_shards(self, sender=None, args=None):
        from shard_policy import supported_shards
        shards = [line.strip() for line in str(self.shard_text.Text).splitlines() if line.strip()]
        if not shards or len(set(s.casefold() for s in shards)) != len(shards):
            window_message("Enter one distinct shard per line.", error=True)
            return
        physical_changed = (shards != supported_shards(shards)
                            and shards != self.cfg.get("navigation_shards", []))
        if supported_shards(shards) != self.cfg["shards"] or physical_changed:
            # A changed filtered order cannot establish the hidden physical row positions.
            self.cfg["navigation_shards"] = shards if len(supported_shards(shards)) != len(shards) else []
            self.cfg["verified_order"] = False
            self.sort_confirm.Checked = False
            self.cfg["excluded"] = [s for s in self.cfg["excluded"] if s in shards]
        self.cfg["shards"] = supported_shards(shards)
        self.shard_text.Text = windows_text("\n".join(self.cfg["shards"]))
        self.refresh_exclusions()
        self.refresh_test_shards()
        self.save_settings()
        self.log_line("Saved {} shards. Verify order in-game before cycling.".format(len(shards)))

    def confirm_order(self, sender, args):
        self.cfg["verified_order"] = bool(self.sort_confirm.Checked)
        self.save_settings()

    @staticmethod
    def format_slot_rules(mapping):
        lines = []
        for shard, slots in sorted(mapping.items()):
            if isinstance(slots, int):
                slots = list(range(1, slots+1))
            lines.append("{}: {}".format(shard, ",".join(str(v) for v in slots)))
        return "\n".join(lines)

    def read_slot_rules(self):
        rules = {}
        if not hasattr(self, "slots_field"):
            return self.cfg.get("skip_slots", {})
        for raw in str(self.slots_field.Text).splitlines():
            if not raw.strip():
                continue
            if ":" not in raw:
                raise ValueError("Slot-skip rule must use 'Shard Name: 1-5' or 'Shard: 1,3,5': " + raw)
            name, text = [x.strip() for x in raw.split(":", 1)]
            matches = [s for s in self.cfg["shards"] if s.casefold() == name.casefold()]
            if len(matches) != 1:
                raise ValueError("Slot rule shard not in the ordered list: " + name)
            try:
                if "-" in text and "," not in text:
                    left, right = [int(x.strip()) for x in text.split("-", 1)]
                    if not 1 <= left <= right <= 7:
                        raise ValueError('Invalid slot range')
                    numbers = list(range(left, right + 1))
                else:
                    numbers = [int(x.strip()) for x in text.split(",")]
            except ValueError:
                raise ActionNeeded('Correct the slot-skip entry',
                                   'Open Automation > Gift Cycler. Enter slots 1–7, for example '
                                   'Atlantic: 1-5 or Origin: 1,3,5. Then click Save slot skips.',
                                   'gift') from None
            if not numbers or any(v < 1 or v > 7 for v in numbers):
                raise ValueError("Slot skips must be from 1 to 7 for " + name)
            rules[matches[0]] = sorted(set(numbers))
        return rules

    def save_slot_rules(self, sender=None, args=None):
        try:
            self.cfg["skip_slots"] = self.read_slot_rules()
            self.save_settings()
            self.persist_profile_if_active()
            self.log_line("Saved optional character-slot skips. Empty rule means all positions attempted.")
        except Exception as exc:
            window_message(exc, error=True)

    def save_settings_click(self, sender, args):
        prior = THEME_PREFERENCE.lower()
        self.save_settings()
        self.persist_profile_if_active()
        self.log_line("Settings saved locally.")
        if str(self.cfg.get('appearance_theme', 'system')).lower() != prior:
            window_message("Appearance saved. Restart Krampuslauf to apply the new theme everywhere.\n"
                           "The active Cycler / Seeder configuration is unchanged.")

    def save_settings(self):
        if hasattr(self, "setup_checks"):
            self.cfg["setup_checklist"] = {k: bool(v.Checked) for k, v in self.setup_checks.items()}
            self.cfg.pop("monkey_setup", None)
        if hasattr(self, "gift_wait"):
            self.cfg["gift_wait"] = net_integer(self.gift_wait.Value)
            self.cfg["visible_rows"] = 9
            self.cfg["row_spacing"] = net_integer(self.row_spacing.Value)
            self.cfg["scroll_reset_clicks"] = net_integer(self.scroll_reset_clicks.Value)
            self.cfg["post_logout_seconds"] = net_integer(self.post_logout.Value)
            self.cfg["online_cooldown_seconds"] = net_integer(self.online_cooldown.Value)
        if hasattr(self, "seed_route_delay"):
            self.cfg["seed_route_delay_seconds"] = net_integer(self.seed_route_delay.Value)
        if hasattr(self, "theme_pick"):
            self.cfg['appearance_theme'] = ('system', 'light', 'dark')[max(0, int(self.theme_pick.SelectedIndex))]
        if hasattr(self, "fast_last_shard"):
            self.cfg["fast_last_shard"] = bool(self.fast_last_shard.Checked)
        if hasattr(self,'create_missing_checkbox'):
            self.cfg['create_missing']=bool(self.create_missing_checkbox.Checked)
        if hasattr(self, 'gift_shard_group'):
            self.cfg['shard_group'] = SHARD_GROUP_OPTIONS[int(self.gift_shard_group.SelectedIndex)][1]
        if hasattr(self, 'seed_capacity_pick'):
            capacity_index = int(self.seed_capacity_pick.SelectedIndex)
            if capacity_index not in (0, 1, 2):
                raise ValueError('Choose the actual account slot capacity: 5, 6 or 7.')
            self.cfg['account_cap'] = (5, 6, 7)[capacity_index]
            self.cfg['reserve_transfer_slot'] = bool(self.reserve_slot_checkbox.Checked)
        if hasattr(self, 'seed_profession_pick'):
            self.cfg['seed_profession'] = (appearance.PROFESSIONS + ('random',))[max(0, int(self.seed_profession_pick.SelectedIndex))]
        if hasattr(self, 'seed_mode_pick'):
            self.cfg['seed_naming_mode'] = ('convention', 'fantasy')[max(0, int(self.seed_mode_pick.SelectedIndex))]
            self.cfg['seed_fantasy_style'] = ('single', 'full', 'mixed')[max(0, int(self.seed_style_pick.SelectedIndex))]
        if hasattr(self,'seed_prefix_field') and self.cfg.get('seed_naming_mode') == 'convention':
            prefix=str(self.seed_prefix_field.Text).strip()
            if not prefix or not prefix.isascii() or not prefix.isalpha() or len(prefix) > 10:
                raise ValueError('Name prefix must consist of 1 to 10 letters (A-Z).')
            self.cfg['seed_name_prefix']=prefix
        if hasattr(self, 're_root_field'):
            self.cfg['razor_data_root'] = str(self.re_root_field.Text).strip()
        self.read_appearance_controls()
        to_disk = {k: v for k, v in self.cfg.items() if k != 'points'}  # Built-in + point_overrides.
        to_disk["window_title"] = ""  # OS title may contain a UO account name.
        atomic_json(CONFIG_FILE, to_disk)
        if hasattr(self, 'account_catalog'):
            self.persist_profile_if_active()

    def chosen_window(self):
        title = self.cfg.get("window_title", "")
        if not title:
            raise RuntimeError("Select the official Classic Client window under Game client.")
        return selected_window(title)

    def update_test_status(self):
        """Green labels reflect previously confirmed diagnostic results, not test clicks."""
        passes = self.cfg.get('manual_test_passes', {})
        for key, ctl in self.test_buttons.items():
            ctl.ForeColor = GREEN if bool(passes.get(key)) else INK
        if hasattr(self, 'test_status_label'):
            count = sum(bool(passes.get(key)) for key in self.test_buttons)
            self.test_status_label.Text = 'Saved successful tests: {}/{}'.format(count, len(self.test_buttons))
            self.test_status_label.ForeColor = GREEN if count == len(self.test_buttons) else MUTED

    def mark_test_pass(self, key):
        # All callbacks from worker threads travel through the WinForms UI queue.
        self.events.put(('test_passed', key))

    def clear_test_results(self, sender, args):
        if self.busy():
            return
        if MessageBox.Show('Clear the green status labels for manual diagnostic tests?\n\n'
                           'This will NOT delete shard scans or Seeder name verification.',
                           'Reset test statuses', MessageBoxButtons.YesNo,
                           MessageBoxIcon.Question) != DialogResult.Yes:
            return
        self.cfg['manual_test_passes'] = {}
        self.update_test_status()
        self.save_settings()

    def show_activity_window(self, hide_main=True):
        """Show current run, not the historic log; only Activity owns run controls."""
        self.compact_running = True
        self.activity_window.status.Text = "Running — monitor activity below"
        self.activity_window.status.ForeColor = INK
        self.activity_window.log.Clear()
        self.activity_window.progress.Value = self.progress.Value
        self.activity_window.pause_button.Text = "PAUSE"
        self.activity_window.pause_button.Enabled = True
        self.activity_window.stop_button.Enabled = True
        self.activity_window.restore_button.Text = "SHOW MAIN WINDOW"
        if hide_main:
            self.Hide()
        self.activity_window.Show()
        self.activity_window.WindowState = FormWindowState.Normal
        self.activity_window.Activate()

    def restore_full_window(self):
        """An active run always keeps Activity accessible for Stop/Pause."""
        if self.busy():
            # Show configuration, but do NOT hide the only run-control window.
            if not self.Visible:
                self.Show()
            self.Activate()
            self.activity_window.BringToFront()
            return
        if self.activity_window.Visible:
            self.activity_window.Hide()
        self.compact_running = False
        self.active_compact_run = False
        if not self.Visible:
            self.Show()
        self.Activate()
        if self.pending_issue:
            destination = self.pending_issue.page
            self.pending_issue = None
            self.show_page(destination)

    def activity_close(self, sender, e):
        # X counts as an acknowledgement after a run has stopped; it cannot
        # close the only active Pause/Stop surface while automation is running.
        e.Cancel = True
        self.restore_full_window()

    def busy(self):
        return self.worker is not None and self.worker.is_alive()

    def log_line(self, text):
        line = "[{}] {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), text)
        # Preserve the full activity/error log on disk independently of the UI.
        try:
            self.history_store.append(line)
        except OSError:
            pass  # A full/read-only disk must never crash the game controller.
        if hasattr(self, "status"):
            self.status.Text = str(text)[:115]
        if hasattr(self, 'activity_window') and getattr(self, 'active_compact_run', False):
            self.activity_window.log.AppendText(line + "\r\n")
            self.activity_window.log.SelectionStart = self.activity_window.log.TextLength
            self.activity_window.log.ScrollToCaret()
            self.activity_window.status.Text = str(text)[:170]

    def emit(self, text):
        text = str(text)
        if text.startswith("ALERT|"):
            self.events.put(("alert", text[6:]))
        elif text.startswith("COUNTDOWN|"):
            info = text.split("|", 2)
            self.events.put(("countdown", "Cooldown {}: {}".format(info[1], info[2])))
        elif text.startswith(("PAUSED|", "POINTER_PAUSED|", "RESUMED|")):
            kind, message = text.split("|", 1)
            self.events.put(("pause_status", (kind != "RESUMED", message)))
        elif text.startswith("PROGRESS|"):
            parts = text.split("|")
            if len(parts) == 3 and int(parts[2]) > 0:
                self.events.put(("percent", 100*int(parts[1])//int(parts[2])))
        else:
            self.events.put(("log", text))

    def drain_events(self, sender, args):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "log":
                    self.log_line(data)
                elif kind == "scan_progress_refresh":
                    self.map_status_label.Text=map_status(MAP_FILE,self.cfg)
                elif kind == "scan_map_ready":
                    self.cfg['navigation_shards']=list(data)
                    self.cfg['shards']=supported_shards(data)
                    self.cfg['verified_order']=True
                    self.shard_text.Text=windows_text('\n'.join(self.cfg['shards']))
                    self.sort_confirm.Checked=True
                    self.refresh_exclusions()
                    self.refresh_test_shards()
                    self.map_status_label.Text=map_status(MAP_FILE,self.cfg)
                    self.save_settings()
                    self.log_line('Saved 27 verified shard names for Windows time zone '+timezone_key())
                elif kind == "test_passed":
                    if data in self.test_buttons:
                        self.cfg.setdefault('manual_test_passes', {})[data] = True
                        self.update_test_status()
                        self.save_settings()
                elif kind == "job_error":
                    self.pending_issue = data
                elif kind == "pause_status":
                    paused, message = data
                    self.pause_btn.Text = "RESUME" if paused else "PAUSE"
                    self.log_line(("PAUSED: " if paused else "RESUMED: ") + message)
                    self.activity_window.status.Text = (
                        ('PAUSE REQUESTED — current Razor action may finish. Escape again stops.'
                         if message.startswith('Escape pressed.') else
                         'PAUSED — leave game unchanged. Resume continues; Escape / Stop ends the run.')
                        if paused else 'Running — continuing the current operation.')
                    self.activity_window.status.ForeColor = NOTE if paused else INK
                elif kind == "stop_requested":
                    self.log_line("STOP REQUESTED: " + data)
                elif kind == "done":
                    self.log_line("RUN RESULT: " + str(data))
                    # Never bounce a halted run back to the full window.
                    # Preserve the error in Activity until explicit acknowledgement.
                    self.start_btn.Enabled = True
                    self.seed_start_btn.Enabled = True
                    self.tabs.Enabled = True
                    self.stop_btn.Enabled = False
                    self.pause_btn.Enabled = False
                    self.pause_btn.Text = "PAUSE"
                    self.pause_event.clear()
                    self.activity_window.escape_hint.Text = "Operation ended. Escape is released back to Windows."
                    self.status.Text = data
                    if self.active_compact_run:
                        self.activity_window.status.Text = self.pending_issue.title if self.pending_issue else data
                        self.activity_window.status.ForeColor = (RED if data.startswith("Halted")
                                                                 else GREEN if data.startswith("Ready") else INK)
                        self.activity_window.restore_button.Text = "ACKNOWLEDGE / RETURN TO MAIN"
                        self.activity_window.log.AppendText("\r\n=== {} ===\r\n".format(data))
                        self.activity_window.log.SelectionStart = self.activity_window.log.TextLength
                        self.activity_window.log.ScrollToCaret()
                        self.Hide()
                        self.activity_window.Show()
                        self.activity_window.WindowState = FormWindowState.Normal
                        self.activity_window.Activate()
                    if self.pending_issue:
                        self.activity_window.log.AppendText("\r\nNEXT STEPS: " + windows_text(self.pending_issue.message) + "\r\n")
                        self.report_ui_error(self.pending_issue, navigate=False, log=False)
                elif kind == "percent":
                    self.progress.Value = max(0, min(100, int(data)))
                    self.activity_window.progress.Value = self.progress.Value
                elif kind == "alert":
                    self.log_line("ALERT: " + data)
                    self.Text = "!  Krampuslauf  |  Attention needed"
                    try:
                        import winsound
                        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                        import ctypes
                        ctypes.windll.user32.FlashWindow(int(self.Handle.ToInt64()), True)
                    except Exception:
                        pass
                elif kind == "countdown":
                    self.status.Text = data
                    self.activity_window.status.Text = data
        except queue.Empty:
            pass

    def run_job(self, operation, compact=False):
        if self.busy():
            return
        self.stop_event.clear()
        self.pause_event.clear()
        self.active_compact_run = True
        self.pending_issue = None
        self.start_btn.Enabled = False
        self.seed_start_btn.Enabled = False
        self.tabs.Enabled = False
        self.stop_btn.Enabled = True
        self.pause_btn.Enabled = True
        self.pause_btn.Text = "PAUSE"
        # Complete Show/Activate BEFORE worker input. Otherwise Activity can
        # steal foreground focus halfway through the very first game click.
        self.show_activity_window(hide_main=compact)
        hotkey = EscapeHotkey(self.signal_escape)
        self.escape_hotkey = hotkey
        if hotkey.start():
            self.activity_window.escape_hint.Text = "ESC: PAUSE · ESC AGAIN: STOP · Click Resume to continue"
        else:
            self.activity_window.escape_hint.Text = "Escape unavailable — use the Pause / Stop buttons."
            self.log_line("Escape shortcut unavailable: " + hotkey.error)
        self.log_line("RUN STARTED: {}".format(
            "Gift Cycler" if operation.__name__ == "run" else
            "Character Seeder" if operation.__name__ == "run_seeder" else
            getattr(operation, "__name__", "operation")))
        def target():
            try:
                operation()
                status = "Ready — operation finished."
            except (Cancelled, BridgeCancelled, pg.FailSafeException) as exc:
                self.emit("STOPPED: " + str(exc))
                status = "Stopped"
            except Exception as exc:
                self.emit("HALTED: " + str(exc))
                self.events.put(("job_error", explain_error(exc)))
                status = "Halted — see activity log"
            finally:
                hotkey.close()
            self.events.put(("done", status))
        self.worker = threading.Thread(target=target, daemon=True)
        try:
            self.worker.start()
        except Exception:
            hotkey.close()
            self.events.put(("done", "Halted — could not start worker"))
            raise

    def signal_escape(self):
        """Hotkey-thread callback: set events only; never touch WinForms here."""
        action = escape_action(self.pause_event.is_set(), self.stop_event.is_set())
        if action == 'pause':
            self.pause_event.set()
            self.events.put(('pause_status', (True,
                'Escape pressed. Pause requested; a Razor action already in progress may finish. '
                'Leave the game screen unchanged. Click Resume, or press Escape again to stop.')))
        elif action == 'stop':
            self.stop_event.set()
            worker = self.game_worker
            bridge = worker.bridge if worker is not None else None
            if bridge is not None:
                bridge.abort()
            self.events.put(('stop_requested', 'Escape pressed while paused.'))

    def start_run(self, sender, args):
        if self.busy():
            return
        try:
            self.require_setup()
            self.save_settings()
            self.apply_verified_map()
            self.cfg["skip_slots"] = self.read_slot_rules()
            self.save_settings()
            self.chosen_window()
            issues = test_config(self.cfg)
            if issues:
                raise ValueError("Setup incomplete:\n- " + "\n- ".join(issues))
            self.require_active_account_profile()
            targets = run_shards(self.cfg)
            if not targets:
                raise ValueError("No included shards in the selected shard group.")
            total_slots = sum(len(occupied_slots_for(self.cfg, shard)) for _, shard in targets)
            text = ('This run will write history to your {} account.\n\n'
                    '{} included shards; up to {} character positions.\n'
                    'Character creation: {}.\n\nProceed?').format(
                        self.account_display_name(), len(targets), total_slots,
                        'ENABLED' if self.cfg.get('create_missing') else 'DISABLED')
            if MessageBox.Show(text, "Start cycling", MessageBoxButtons.YesNo,
                               MessageBoxIcon.Warning) != DialogResult.Yes:
                return
            cfg = json.loads(json.dumps(self.cfg))
            if len(game_windows()) != 1:
                raise RuntimeError("For safety, close extra official client.exe windows. One game client per Cycler run.")
            worker = MergedWorker(cfg, 'gift-cycle-'+self.cfg['gift_cycle_id'], 'Gift Cycler',
                                  self.stop_event, self.emit, self.pause_event)
            if cfg.get('create_missing',False):
                # Combined mode stores creation progress separately from gift progress.
                worker.seed_init(self.account_display_name())
                worker.check_seed_setup()
            self.game_worker = worker
            self.progress.Value = 0
            self.run_job(worker.run, compact=True)
        except Exception as exc:
            window_message(exc, error=True)

    def toggle_pause(self, sender, args):
        if not self.busy():
            return
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_btn.Text = "PAUSE"
            self.activity_window.pause_button.Text = "PAUSE"
            self.log_line("RESUME REQUESTED: continuing from the current game screen.")
        else:
            self.pause_event.set()
            self.pause_btn.Text = "RESUME"
            self.activity_window.pause_button.Text = "RESUME"
            self.log_line("PAUSE REQUESTED: leave the game screen unchanged. A Razor action already in progress may finish. Click Resume to continue; Escape or Stop ends the run.")

    def request_stop(self, sender, args):
        self.stop_event.set()
        worker = self.game_worker
        bridge = worker.bridge if worker is not None else None
        if bridge is not None:
            bridge.abort()
        self.log_line("Stop requested; bridge session invalidated. Current character may remain connected.")

    def bridge_test_preflight(self):
        self.save_settings()
        self.chosen_window()
        games = game_windows()
        if len(games) != 1:
            raise RuntimeError("Bridge testing requires exactly ONE active official Classic Client window. "
                               "Close extra client.exe windows before testing.")

    def test_probe(self, sender, args):
        if self.busy():
            return
        try:
            self.bridge_test_preflight()
        except Exception as exc:
            window_message(exc, error=True)
            return
        def job():
            self.emit("Testing local RE AutoStart bridge; no chat commands will be typed...")
            with BridgeSession(self.stop_event) as bridge:
                info = bridge.wait_status(timeout=12)
                if not info:
                    raise RuntimeError(
                        "No krampuslauf_bridge.py heartbeat after 12 seconds. Verify the default profile is "
                        "actually active and the bridge script is running. A character-linked Razor "
                        "profile can override default; verify Temporary Profile Isolation and restart. "
                        "Select default in Razor and retest.")
                self.emit("BRIDGE OK: connected to {} (instance {}).".format(
                    info['shard'], info['instance_id'][:8]))
                self.mark_test_pass('bridge')
        self.run_job(job)

    def test_logout(self, sender, args):
        if self.busy():
            return
        if MessageBox.Show("This will disconnect the CURRENT character using Misc.Disconnect().\n"
                           "Test only on a disposable character. Continue?",
                           "Test RE bridge logout", MessageBoxButtons.YesNo,
                           MessageBoxIcon.Warning) != DialogResult.Yes:
            return
        try:
            self.bridge_test_preflight()
        except Exception as exc:
            window_message(exc, error=True)
            return
        cfg = json.loads(json.dumps(self.cfg))
        def job():
            self.emit("Waiting for RE bridge and its shard identity...")
            with BridgeSession(self.stop_event) as bridge:
                info = bridge.wait_status(timeout=12)
                if not info:
                    raise RuntimeError("No active RE bridge. Enable AutoStart and log back in, or manually start it.")
                self.emit("RE bridge active on {}. Requesting scoped disconnect...".format(info['shard']))
                bridge.request_logout(info)
                self.emit("RE acknowledged disconnect. Waiting for the actual LOGIN menu...")
                checker = GameWorker(cfg, 'logout_verify', 'diagnostic',
                                     self.stop_event, self.emit, self.pause_event)
                deadline = checker.clock() + 12
                while checker.clock() < deadline:
                    if self.stop_event.is_set():
                        raise Cancelled('Stopped during logout verification')
                    if checker.state() == 'login':
                        self.emit('RE LOGOUT TEST PASSED: Classic Client returned to Login.')
                        self.mark_test_pass('logout')
                        return
                    time.sleep(.35)
                self.emit('RE LOGOUT UNVERIFIED: bridge acknowledged disconnect but the login screen marker '
                          'was not detected in 12 seconds. The test will NOT be marked green.')
        self.run_job(job)

    def refresh_test_shards(self):
        """Independent selection; the exclusion dropdown is only for exclusions."""
        from shard_policy import supported_shards
        picker = self.test_shard_pick
        old = str(picker.SelectedItem or "")
        picker.Items.Clear()
        for shard in supported_shards(self.cfg.get("shards", [])):
            picker.Items.Add(shard)
        if old in supported_shards(self.cfg.get("shards", [])):
            picker.SelectedItem = old
        elif picker.Items.Count:
            # Prefer the first off-screen shard when one is configured.
            picker.SelectedIndex = min(int(self.cfg.get("visible_rows", 9)), picker.Items.Count - 1)

    def diagnostic_move(self, x, y):
        """A failed move in a diagnostic pauses too; this helper never clicks."""
        while True:
            if self.stop_event.is_set():
                raise Cancelled('Stopped during cursor diagnostic')
            if self.pause_event.is_set():
                self.emit('PAUSED|Cursor diagnostic paused. Click Resume, or press Escape to stop.')
                while self.pause_event.is_set():
                    if self.stop_event.wait(.05):
                        raise Cancelled('Stopped during cursor diagnostic')
                self.emit('RESUMED|Continuing cursor diagnostic.')
                continue
            try:
                return native_mouse.move_cursor(x, y)
            except native_mouse.PointerInterrupted as exc:
                self.pause_event.set()
                self.emit('MOUSE DETAILS: ' + str(exc))

    def test_desktop_cursor(self, sender, args):
        """Non-clicking test of native pointer movement while GUI, not game, has focus."""
        if self.busy():
            return
        if MessageBox.Show(
                "Test Windows mouse movement WITHOUT focusing Classic Client.\n\n"
                "This moves the pointer around 80 pixels from its current position, "
                "does not click, and logs native Windows API results. Continue?",
                "Desktop mouse test", MessageBoxButtons.YesNo,
                MessageBoxIcon.Information) != DialogResult.Yes:
            return
        def job():
            left, top, width, height = native_mouse.virtual_desktop()
            start_x, start_y = native_mouse.cursor_position()
            x = start_x + (80 if start_x + 100 < left + width else -80)
            y = start_y + (60 if start_y + 80 < top + height else -60)
            self.emit("DESKTOP TEST: before={} target={} clip={}.".format(
                (start_x, start_y), (x, y), native_mouse.clip_rectangle()))
            result = self.diagnostic_move(x, y)
            self.emit("DESKTOP TEST: native input worked; {}.".format(result))
            time.sleep(.45)
            actual = native_mouse.cursor_position()
            self.emit("DESKTOP TEST: 450ms later pointer={}.".format(actual))
            if abs(actual[0] - x) > 3 or abs(actual[1] - y) > 3:
                raise RuntimeError("Desktop cursor was moved back by another process. "
                                   "Compare focus/input permissions and mouse control software.")
            self.emit("DESKTOP TEST PASSED. Now try Game Cursor (no click) with the shard list visible.")
            self.mark_test_pass('desktop_cursor')
        self.run_job(job)

    def test_cursor(self, sender, args):
        """No click: native Win32 attempt at the first shard, with clipping diagnostics."""
        if self.busy():
            return
        try:
            self.save_settings()
            self.chosen_window()
        except Exception as exc:
            window_message(exc, error=True)
            return
        if MessageBox.Show(
                "Open the SHARD LIST first.\n\nThe mouse will move to the first shard row "
                "using native Windows functions, PAUSE there, and NOT click. Continue?",
                "Test mouse position", MessageBoxButtons.YesNo,
                MessageBoxIcon.Information) != DialogResult.Yes:
            return
        cfg = json.loads(json.dumps(self.cfg))
        def job():
            game = focus_game(cfg["window_title"])
            area = game_area(cfg["window_title"])
            x, y = point_screen(cfg["window_title"], *cfg["points"]["first_row"])
            self.emit("GAME TEST: client HWND={} game area=({}, {}) {}x{}.".format(
                game._hWnd, area.left, area.top, area.width, area.height))
            self.emit("GAME TEST: target relative={} -> desktop=({}, {}), clip={}.".format(
                cfg["points"]["first_row"], x, y, native_mouse.clip_rectangle()))
            result = self.diagnostic_move(x, y)
            self.emit("GAME TEST: native movement result={}.".format(result))
            time.sleep(.45)
            actual = native_mouse.cursor_position()
            self.emit("GAME TEST: 450ms later pointer={}.".format(actual))
            if abs(actual[0] - x) > 3 or abs(actual[1] - y) > 3:
                raise RuntimeError("Classic Client or another process moved the cursor after native movement. "
                                   "Compare with Desktop Mouse test.")
            self.emit("GAME TEST PASSED: native cursor movement works with Classic Client focused. "
                      "No mouse click or keyboard action was sent.")
            self.mark_test_pass('game_cursor')
        self.run_job(job)

    def test_focus_comparison(self, sender, args):
        """Compare cursor behavior before and after CC activation; NEVER clicks."""
        if self.busy():
            return
        try:
            self.save_settings()
            self.chosen_window()
        except Exception as exc:
            window_message(exc, error=True)
            return
        if MessageBox.Show(
                "No clicking or typing will occur.\n\n"
                "First, the pointer moves to the first shard row while the GUI "
                "still has focus. Then Classic Client is focused and the pointer "
                "position is read again. Finally, the app attempts a second movement "
                "with Classic Client focused. Continue?",
                "Compare pointer before/after game focus",
                MessageBoxButtons.YesNo, MessageBoxIcon.Information) != DialogResult.Yes:
            return
        cfg = json.loads(json.dumps(self.cfg))
        def job():
            title = cfg["window_title"]
            x, y = point_screen(title, *cfg["points"]["first_row"])
            self.emit("FOCUS CHECK: game unfocused, moving to first row desktop=({}, {}).".format(x, y))
            pre = self.diagnostic_move(x, y)
            self.emit("FOCUS CHECK: before game focus cursor={} (moved={}).".format(
                native_mouse.cursor_position(), pre["final"]))
            time.sleep(.35)
            win = focus_game(title)
            time.sleep(.55)
            after_focus = native_mouse.cursor_position()
            self.emit("FOCUS CHECK: activated HWND={}, cursor after focus={}, clip={}.".format(
                win._hWnd, after_focus, native_mouse.clip_rectangle()))
            # Second target is an unobtrusive nearby point, still within the game area.
            area = game_area(title)
            x2 = min(x + 24, area.left + area.width - 10)
            y2 = min(y + 10, area.top + area.height - 10)
            try:
                result = native_mouse.move_cursor(x2, y2)
                self.emit("FOCUS CHECK: movement WITH game focused passed; final={}.".format(
                    result["final"]))
                if (abs(result['final'][0] - x2) <= 3 and
                        abs(result['final'][1] - y2) <= 3):
                    self.mark_test_pass('focus_check')
            except Exception as exc:
                self.emit("FOCUS CHECK: movement WITH game focused FAILED: {}".format(exc))
                self.emit("FOCUS CHECK: desktop input works, but the focused client or a "
                          "privilege/input restriction prevents cursor placement. "
                          "Check whether client.exe is elevated and the cycler is not; "
                          "try both at matching privilege levels. Do not run cycling yet.")
        self.run_job(job)

    def test_title_shard(self, sender, args):
        """Read only the shard suffix from selected `client.exe` caption."""
        try:
            win = self.chosen_window()
            names = list(dict.fromkeys(KNOWN_SHARDS + list(self.cfg["shards"])))
            detected = shard_from_title(win.title, names)
            if detected:
                self.log_line("TITLE TEST: shard suffix detected: {} (HWND {}).".format(
                    detected, win._hWnd))
                self.cfg.setdefault('manual_test_passes', {})['shard_title'] = True
                self.update_test_status()
                self.save_settings()
            else:
                self.log_line("TITLE TEST: no recognizable '(Shard Name)' suffix at this screen. "
                              "No account name or full caption was recorded.")
        except Exception as exc:
            window_message(exc, error=True)

    def test_last_shard(self, sender, args):
        """One Enter on the actual shard screen; never select a character."""
        if self.busy():
            return
        try:
            self.save_settings()
            self.chosen_window()
        except Exception as exc:
            window_message(exc, error=True)
            return
        prompt = (
            "Open the SHARD LIST after you have already visited a shard.\n\n"
            "This test clicks the last-shard button once, then waits for "
            "Character Selection. It does not press Enter and will NOT log "
            "into a character.\n\nContinue?"
        )
        if MessageBox.Show(prompt, "Test remembered-shard shortcut",
                           MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes:
            return
        cfg = json.loads(json.dumps(self.cfg))

        def job():
            worker = GameWorker(cfg, "manual_last_shard", "manual_last_shard",
                                self.stop_event, self.emit, self.pause_event)
            self.emit("LAST-SHARD TEST: checking that the game is on the shard-selection screen.")
            if worker.state() != "servers":
                raise RuntimeError("Last-shard test requires the detected shard-selection screen. Nothing was clicked.")
            worker.click(worker.cfg["points"]["last_shard"], expected="servers")
            self.emit("LAST-SHARD TEST: clicked the last-shard button once; waiting for character menu.")
            deadline = worker.clock() + 6.0
            last = "unknown"
            while worker.clock() < deadline:
                worker.sleep(.3)
                last = worker.state()
                if last == "characters":
                    self.emit("LAST-SHARD TEST PASSED: character menu detected. No character was entered.")
                    self.mark_test_pass('last_shard')
                    return
                if last == "login":
                    raise RuntimeError("Returned to login instead of character menu; shortcut not verified.")
            self.emit("LAST-SHARD TEST NOT VERIFIED: state={}; no more keyboard input was sent.".format(last))
        self.run_job(job)

    def test_scroll(self, sender, args):
        """Target an explicit shard, report actual mouse movement and verify menu."""
        if self.busy():
            return
        shard = str(self.test_shard_pick.SelectedItem or "")
        try:
            self.save_settings()
            self.chosen_window()
            if shard not in self.cfg.get("shards", []):
                raise RuntimeError("Choose a shard under Help / Status > Diagnostics.")
        except Exception as exc:
            window_message(exc, error=True)
            return
        cfg = json.loads(json.dumps(self.cfg))
        index = cfg["shards"].index(shard)
        from shard_policy import physical_index
        row_index = physical_index(cfg, index)
        visible = int(cfg["visible_rows"])
        scroll_count = max(0, row_index - (visible - 1))
        prompt = ("Open the SHARD LIST first.\n\n"
                  "Target: {} (row {}; {} DOWN clicks from the top).\n\n"
                  "Is the scrollbar ALREADY at the very TOP?\n\n"
                  "YES — skip the UP-arrow reset (fast test).\n"
                  "NO — reset to top with repeated UP clicks first.\n"
                  "CANCEL — do nothing.\n\n"
                  "The test will click the shard ONCE, then STOP on the character screen.\n"
                  "It will NOT press Enter or select any character.").format(
                      shard, row_index + 1, scroll_count)
        selection = MessageBox.Show(prompt, "Safe shard-selection test",
                                    MessageBoxButtons.YesNoCancel, MessageBoxIcon.Warning)
        if selection == DialogResult.Cancel:
            return
        skip_up_reset = selection == DialogResult.Yes
        def job():
            self.emit("TEST: Selecting {} (index {}, visible rows {}).".format(shard, index+1, visible))
            checker = GameWorker(cfg, "manual_click_diagnostic", "manual_click_diagnostic",
                                 self.stop_event, self.emit, self.pause_event)
            self.game_worker = checker
            if checker.state() != "servers":
                raise RuntimeError("Open the shard list before testing; no input sent.")
            if skip_up_reset:
                self.emit("TEST: user confirmed list is already at top; skipping UP-arrow reset.")
            else:
                for _ in range(int(cfg.get('scroll_reset_clicks', 18))):
                    checker.click(cfg['points']['scroll_up'], expected='servers')
                    checker.sleep(.085)
            for _ in range(scroll_count):
                checker.click(cfg['points']['scroll_down'], expected='servers')
                checker.sleep(.12)
            first = cfg['points']['first_row']
            row = min(row_index, visible - 1)
            click_pt = (first[0], first[1] + row * int(cfg['row_spacing']))
            evidence = checker.click(click_pt, expected='servers', settle=.35)
            self.emit('TEST: verified mouse input: {}.'.format(evidence))
            self.emit("TEST: shard clicked ONCE; no Enter or character-slot input will be sent.")
            deadline = checker.clock() + 6.0
            menu_state = "unknown"
            while checker.clock() < deadline:
                if self.stop_event.is_set():
                    raise Cancelled("Stopped by user")
                time.sleep(.30)
                try:
                    menu_state = checker.state()
                except Exception as exc:
                    self.emit("TEST: menu-marker check failed: {}".format(exc))
                    menu_state = "unknown"
                    break
                if menu_state == "characters":
                    break
                if menu_state == "login":
                    break
            if menu_state == "characters":
                detected = shard_from_title(
                    selected_window(cfg["window_title"]).title,
                    list(dict.fromkeys(KNOWN_SHARDS + list(cfg["shards"]))))
                if detected and detected != shard:
                    self.emit("WRONG SHARD: expected {}, window title says {}. "
                              "No character was entered. Correct the configured sort/order.".format(shard, detected))
                elif detected == shard:
                    self.emit("VERIFIED: character menu reached, window title confirms {}. "
                              "No character was entered.".format(shard))
                    self.mark_test_pass('shard_select')
                else:
                    self.emit("CHARACTER MENU: reached after selecting {}, but window "
                              "title contains no recognized shard suffix. Identity unverified.".format(shard))
            elif menu_state == "servers":
                self.emit("NOT SELECTED: still on shard list after one click. "
                          "No Enter was sent; test stopped safely.")
            else:
                self.emit("UNVERIFIED: screen marker result={}. "
                          "Stopped without pressing Enter or selecting a character.".format(menu_state))
        self.run_job(job)

    def confirm_profile_close(self):
        """Only the explicit Close anyway button permits closing with active isolation."""
        dialog = Form()
        dialog.Text = 'Restore your original profiles'
        dialog.ClientSize = Size(530, 214)
        dialog.StartPosition = FormStartPosition.CenterParent
        dialog.FormBorderStyle = FormBorderStyle.FixedDialog
        dialog.MinimizeBox = dialog.MaximizeBox = False
        dialog.BackColor, dialog.ForeColor = PANEL, INK
        dialog.AutoScaleDimensions = SizeF(96.0, 96.0)
        dialog.AutoScaleMode = AutoScaleMode.Dpi
        label(dialog, 'Temporary Razor profile isolation is still active.', 20, 18, 490, 28, True)
        label(dialog, 'Return to Setup > Profiles to restore your original links.\n'
                      'Close Razor and the game before restoring.\n\n'
                      'Your verified recovery backups will be kept.', 20, 52, 490, 92)
        back = button(dialog, 'Return to Profiles', 20, 160, 280, 36, lambda s, e: None, True)
        back.DialogResult = DialogResult.Cancel
        close = button(dialog, 'Close anyway', 316, 160, 194, 36, lambda s, e: None)
        close.DialogResult = DialogResult.OK
        dialog.AcceptButton = back
        dialog.CancelButton = back
        dialog.Shown += apply_caption_on_show
        try:
            return dialog.ShowDialog(self) == DialogResult.OK
        finally:
            dialog.Dispose()

    def before_close(self, sender, e):
        if self.busy():
            self.stop_event.set()
            worker = self.game_worker
            bridge = worker.bridge if worker is not None else None
            if bridge is not None:
                bridge.abort()
            e.Cancel = True
            window_message("Stop requested. Wait for automation to finish before closing.")
            return
        self.save_settings()
        try:
            state = session_status(APP_DIR)
        except Exception:
            state = {'active': False}
        if state['active'] and not self.confirm_profile_close():
            e.Cancel = True
            self.show_page('profiles')
            self.update_isolation_state()
            return
        self.ui_timer.Stop()


def main():
    Application.EnableVisualStyles()
    Application.SetCompatibleTextRenderingDefault(False)
    Application.Run(MainWindow())


if __name__ == "__main__":
    main()
