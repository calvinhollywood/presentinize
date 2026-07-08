#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Presentinize — Bildschirm-Annotation für Screen-Recordings.
Menüleisten-App (LSUIElement), reines AppKit / PyObjC, keine externen Abhängigkeiten.

Linksklick auf das Stift-Icon  = Zeichnen an/aus (golden = aktiv)
Rechtsklick auf das Icon       = Menü (Zeichnen, Löschen, Rückgängig, Beenden)
Shortcuts: fn+Ctrl+P und ⌥⌘D  = Zeichnen an/aus (global; braucht ggf. Bedienungshilfen-Freigabe)

Im Zeichenmodus:
  1–6 = Werkzeug (Freihand, Pfeil, Rechteck, Ellipse, Linie, Highlighter)
  ⌘Z = Rückgängig, Backspace = alles löschen, Esc = Zeichnen beenden
  Spotlight (🔦): Scrollrad oder ↑/↓ = Kreisgröße, Esc = Spotlight beenden
"""

import math
import objc
from AppKit import *          # noqa: F401,F403  (bewusst: Single-File-AppKit-App)
from Foundation import (
    NSObject, NSMakeRect, NSMakePoint, NSUnionRect, NSInsetRect,
    NSNotificationCenter,
)

# ----------------------------------------------------------------------------
# Brand / Konstanten
# ----------------------------------------------------------------------------

def _rgb(r, g, b, a=1.0):
    return NSColor.colorWithSRGBRed_green_blue_alpha_(r / 255.0, g / 255.0, b / 255.0, a)

GOLD        = _rgb(0xC9, 0xA8, 0x4C)
GOLD_DIM    = _rgb(0xC9, 0xA8, 0x4C, 0.30)
PANEL_BG    = _rgb(0x16, 0x16, 0x18, 0.92)
PANEL_EDGE  = _rgb(0xFF, 0xFF, 0xFF, 0.12)
RED_TINT    = _rgb(0xE5, 0x48, 0x3F)

COLORS = [
    ("Rot",     _rgb(0xE5, 0x48, 0x3F)),
    ("Gold",    GOLD),
    ("Grün",    _rgb(0x3F, 0xB9, 0x5E)),
    ("Blau",    _rgb(0x3E, 0x8B, 0xE5)),
    ("Weiß",    _rgb(0xF5, 0xF5, 0xF5)),
    ("Schwarz", _rgb(0x11, 0x11, 0x11)),
]

WIDTHS = [3.0, 6.0, 12.0]

TOOLS = [
    ("free",      "scribble",        "Freihand (1)"),
    ("arrow",     "arrow.up.right",  "Pfeil (2)"),
    ("rect",      "rectangle",       "Rechteck (3)"),
    ("ellipse",   "circle",          "Ellipse (4)"),
    ("line",      "line.diagonal",   "Linie (5)"),
    ("highlight", "highlighter",     "Highlighter (6)"),
]

KEY_P, KEY_D, KEY_Z = 35, 2, 6
KEY_ESC, KEY_BACKSPACE = 53, 51
KEY_UP, KEY_DOWN = 126, 125

SPOT_MIN, SPOT_MAX = 40.0, 600.0


def symbol_image(name, point_size=15.0, weight=NSFontWeightMedium):
    img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, name)
    if img is None:
        return None
    cfg = NSImageSymbolConfiguration.configurationWithPointSize_weight_(point_size, weight)
    out = img.imageWithSymbolConfiguration_(cfg)
    return out or img


# ----------------------------------------------------------------------------
# Fenster-Subklassen (Punkt 9: Key-Window-Verhalten)
# ----------------------------------------------------------------------------

class OverlayWindow(NSWindow):
    def canBecomeKeyWindow(self):
        return True

    def canBecomeMainWindow(self):
        return False


class ToolbarPanel(NSPanel):
    def canBecomeKeyWindow(self):
        return False


# ----------------------------------------------------------------------------
# Zeichenfläche
# ----------------------------------------------------------------------------

class DrawView(NSView):
    def initWithFrame_app_(self, frame, app):
        self = objc.super(DrawView, self).initWithFrame_(frame)
        if self is None:
            return None
        self.app = app
        self.strokes = []          # abgeschlossene Striche
        self.current = None        # Strich in Arbeit
        self.spotlight = False
        self.spot_radius = 180.0
        self.mouse = NSMakePoint(frame.size.width / 2.0, frame.size.height / 2.0)
        self._tracking = None
        return self

    def isFlipped(self):
        return False

    def acceptsFirstResponder(self):
        return True

    def updateTrackingAreas(self):
        objc.super(DrawView, self).updateTrackingAreas()
        if self._tracking is not None:
            self.removeTrackingArea_(self._tracking)
        opts = (NSTrackingMouseMoved | NSTrackingActiveAlways | NSTrackingInVisibleRect)
        self._tracking = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            self.bounds(), opts, self, None)
        self.addTrackingArea_(self._tracking)

    # -- Spotlight ------------------------------------------------------------

    @objc.python_method
    def spot_rect(self, center, radius):
        return NSMakeRect(center.x - radius, center.y - radius, radius * 2, radius * 2)

    @objc.python_method
    def invalidate_spot(self, old_center, new_center):
        # Punkt 5: nur die betroffene Region neu zeichnen, nie das ganze Fenster.
        r = self.spot_radius
        dirty = NSUnionRect(self.spot_rect(old_center, r), self.spot_rect(new_center, r))
        dirty = NSInsetRect(dirty, -70.0, -70.0)   # Ring + Cursor-Pfeil abdecken
        self.setNeedsDisplayInRect_(dirty)

    @objc.python_method
    def set_spot_radius(self, radius):
        old = self.spot_radius
        self.spot_radius = max(SPOT_MIN, min(SPOT_MAX, radius))
        big = max(old, self.spot_radius)
        dirty = NSInsetRect(self.spot_rect(self.mouse, big), -70.0, -70.0)
        self.setNeedsDisplayInRect_(dirty)

    def mouseMoved_(self, event):
        if not self.spotlight:
            return
        old = self.mouse
        self.mouse = self.convertPoint_fromView_(event.locationInWindow(), None)
        self.invalidate_spot(old, self.mouse)

    def scrollWheel_(self, event):
        if not self.spotlight:
            return
        self.set_spot_radius(self.spot_radius + event.scrollingDeltaY() * 2.0)

    # -- Zeichnen -------------------------------------------------------------

    def mouseDown_(self, event):
        if self.spotlight:
            return
        p = self.convertPoint_fromView_(event.locationInWindow(), None)
        tool = self.app.tool
        color = COLORS[self.app.color_idx][1]
        width = WIDTHS[self.app.width_idx]
        if tool == "highlight":
            color = color.colorWithAlphaComponent_(0.35)
            width = width * 3.0
        self.current = {"tool": tool, "color": color, "width": width,
                        "p1": p, "p2": p, "points": [p]}
        self.setNeedsDisplay_(True)

    def mouseDragged_(self, event):
        if self.spotlight or self.current is None:
            return
        p = self.convertPoint_fromView_(event.locationInWindow(), None)
        self.current["p2"] = p
        if self.current["tool"] in ("free", "highlight"):
            self.current["points"].append(p)
        self.setNeedsDisplay_(True)

    def mouseUp_(self, event):
        if self.spotlight or self.current is None:
            return
        p = self.convertPoint_fromView_(event.locationInWindow(), None)
        self.current["p2"] = p
        if self.current["tool"] in ("free", "highlight"):
            self.current["points"].append(p)
        self.strokes.append(self.current)
        self.current = None
        self.setNeedsDisplay_(True)

    @objc.python_method
    def undo(self):
        if self.strokes:
            self.strokes.pop()
            self.setNeedsDisplay_(True)

    @objc.python_method
    def clear(self):
        self.strokes = []
        self.current = None
        self.setNeedsDisplay_(True)

    # -- Rendering ------------------------------------------------------------

    @objc.python_method
    def _path_for(self, s):
        tool = s["tool"]
        p1, p2 = s["p1"], s["p2"]
        path = NSBezierPath.bezierPath()
        path.setLineWidth_(s["width"])
        path.setLineCapStyle_(NSLineCapStyleRound)
        path.setLineJoinStyle_(NSLineJoinStyleRound)
        if tool in ("free", "highlight"):
            pts = s["points"]
            if not pts:
                return path
            path.moveToPoint_(pts[0])
            for p in pts[1:]:
                path.lineToPoint_(p)
        elif tool == "line" or tool == "arrow":
            path.moveToPoint_(p1)
            path.lineToPoint_(p2)
        elif tool == "rect":
            r = NSMakeRect(min(p1.x, p2.x), min(p1.y, p2.y),
                           abs(p2.x - p1.x), abs(p2.y - p1.y))
            path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(r, 8.0, 8.0)
            path.setLineWidth_(s["width"])
        elif tool == "ellipse":
            r = NSMakeRect(min(p1.x, p2.x), min(p1.y, p2.y),
                           abs(p2.x - p1.x), abs(p2.y - p1.y))
            path = NSBezierPath.bezierPathWithOvalInRect_(r)
            path.setLineWidth_(s["width"])
        return path

    @objc.python_method
    def _draw_stroke(self, s):
        s["color"].set()
        self._path_for(s).stroke()
        if s["tool"] == "arrow":
            p1, p2 = s["p1"], s["p2"]
            dx, dy = p2.x - p1.x, p2.y - p1.y
            if abs(dx) < 0.5 and abs(dy) < 0.5:
                return
            ang = math.atan2(dy, dx)
            head = max(14.0, s["width"] * 3.5)
            spread = math.radians(26.0)
            tri = NSBezierPath.bezierPath()
            tri.moveToPoint_(p2)
            tri.lineToPoint_(NSMakePoint(p2.x - head * math.cos(ang - spread),
                                         p2.y - head * math.sin(ang - spread)))
            tri.lineToPoint_(NSMakePoint(p2.x - head * math.cos(ang + spread),
                                         p2.y - head * math.sin(ang + spread)))
            tri.closePath()
            tri.fill()

    @objc.python_method
    def _draw_cursor_arrow(self, at):
        """Großer goldener Pfeil-Cursor mit dunkler Kontur (Hotspot = Spitze)."""
        s = 2.6  # Skalierung eines klassischen Cursor-Umrisses
        pts = [(0, 0), (0, -16), (3.8, -12.5), (6.5, -18), (9.3, -16.6),
               (6.6, -11.2), (11.3, -11.2)]
        path = NSBezierPath.bezierPath()
        path.moveToPoint_(NSMakePoint(at.x + pts[0][0] * s, at.y + pts[0][1] * s))
        for (px, py) in pts[1:]:
            path.lineToPoint_(NSMakePoint(at.x + px * s, at.y + py * s))
        path.closePath()
        GOLD.set()
        path.fill()
        _rgb(0x11, 0x11, 0x11).set()
        path.setLineWidth_(2.0)
        path.setLineJoinStyle_(NSLineJoinStyleRound)
        path.stroke()

    def drawRect_(self, rect):
        for s in self.strokes:
            self._draw_stroke(s)
        if self.current is not None:
            self._draw_stroke(self.current)

        if self.spotlight:
            circle = self.spot_rect(self.mouse, self.spot_radius)
            dim = NSBezierPath.bezierPathWithRect_(self.bounds())
            dim.appendBezierPath_(NSBezierPath.bezierPathWithOvalInRect_(circle))
            dim.setWindingRule_(NSWindingRuleEvenOdd)
            NSColor.colorWithSRGBRed_green_blue_alpha_(0, 0, 0, 0.55).set()
            dim.fill()
            ring = NSBezierPath.bezierPathWithOvalInRect_(circle)
            ring.setLineWidth_(3.0)
            GOLD.set()
            ring.stroke()
            self._draw_cursor_arrow(self.mouse)


# ----------------------------------------------------------------------------
# Toolbar
# ----------------------------------------------------------------------------

class ToolbarBGView(NSView):
    """Dunkles Glas-Panel; leerer Bereich ist Drag-Fläche."""

    def initWithFrame_(self, frame):
        self = objc.super(ToolbarBGView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._drag_origin = None
        self.setWantsLayer_(True)
        layer = self.layer()
        layer.setBackgroundColor_(PANEL_BG.CGColor())
        layer.setCornerRadius_(14.0)
        layer.setBorderWidth_(1.0)
        layer.setBorderColor_(PANEL_EDGE.CGColor())
        return self

    def mouseDown_(self, event):
        self._drag_origin = event.locationInWindow()

    def mouseDragged_(self, event):
        if self._drag_origin is None:
            return
        w = self.window()
        p = event.locationInWindow()
        f = w.frame()
        w.setFrameOrigin_(NSMakePoint(
            f.origin.x + (p.x - self._drag_origin.x),
            f.origin.y + (p.y - self._drag_origin.y)))

    def mouseUp_(self, event):
        self._drag_origin = None


# ----------------------------------------------------------------------------
# App-Delegate
# ----------------------------------------------------------------------------

class AppDelegate(NSObject):

    # -- Lifecycle ------------------------------------------------------------

    def applicationDidFinishLaunching_(self, note):
        self.drawing = False
        self.tool = "free"
        self.color_idx = 0
        self.width_idx = 1

        self.tool_buttons = {}
        self.color_buttons = []
        self.width_buttons = []
        self.spot_button = None

        self._build_status_item()
        self._build_overlay()
        self._build_toolbar()
        self._install_monitors()

        # Punkt 7: Beamer / Auflösungswechsel
        NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            self, b"screensChanged:",
            NSApplicationDidChangeScreenParametersNotification, None)

    def applicationShouldHandleReopen_hasVisibleWindows_(self, app, flag):
        # Punkt 6: Doppelklick auf die laufende App togglet Zeichnen.
        self.toggleDrawing_(None)
        return False

    def applicationWillTerminate_(self, note):
        if self.draw_view.spotlight:
            NSCursor.unhide()

    # -- Statusleiste ----------------------------------------------------------

    @objc.python_method
    def _build_status_item(self):
        self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength)
        btn = self.status_item.button()
        btn.setImage_(symbol_image("pencil.tip.crop.circle", 17.0) or
                      symbol_image("pencil", 17.0))
        btn.setTarget_(self)
        btn.setAction_(b"statusClicked:")
        btn.sendActionOn_(NSEventMaskLeftMouseUp | NSEventMaskRightMouseUp)

        self.menu = NSMenu.alloc().init()
        self.menu.setDelegate_(self)
        self.menu_toggle = self.menu.addItemWithTitle_action_keyEquivalent_(
            "Zeichnen an", b"toggleDrawing:", "")
        self.menu.addItemWithTitle_action_keyEquivalent_(
            "Alles löschen", b"clearAll:", "")
        self.menu.addItemWithTitle_action_keyEquivalent_(
            "Rückgängig", b"undoStroke:", "")
        self.menu.addItem_(NSMenuItem.separatorItem())
        self.menu.addItemWithTitle_action_keyEquivalent_(
            "Presentinize beenden", b"terminate:", "q")

    def statusClicked_(self, sender):
        event = NSApp.currentEvent()
        if event is not None and event.type() in (
                NSEventTypeRightMouseUp, NSEventTypeRightMouseDown):
            self.menu_toggle.setTitle_("Zeichnen aus" if self.drawing else "Zeichnen an")
            self.status_item.setMenu_(self.menu)
            self.status_item.button().performClick_(None)
        else:
            self.toggleDrawing_(None)

    def menuDidClose_(self, menu):
        # Menü wieder abhängen, damit Linksklick weiter togglet.
        self.status_item.setMenu_(None)

    @objc.python_method
    def _update_status_tint(self):
        btn = self.status_item.button()
        btn.setContentTintColor_(GOLD if self.drawing else None)

    # -- Overlay ---------------------------------------------------------------

    @objc.python_method
    def _screen_frame(self):
        screen = NSScreen.mainScreen() or NSScreen.screens()[0]
        return screen.frame()

    @objc.python_method
    def _build_overlay(self):
        frame = self._screen_frame()
        self.overlay = OverlayWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame, NSWindowStyleMaskBorderless, NSBackingStoreBuffered, False)
        self.overlay.setReleasedWhenClosed_(False)
        self.overlay.setOpaque_(False)
        self.overlay.setBackgroundColor_(NSColor.clearColor())
        self.overlay.setHasShadow_(False)
        # Punkt 2: unter der Menüleiste bleiben, sonst ist die App unentkommbar.
        self.overlay.setLevel_(NSMainMenuWindowLevel - 1)
        self.overlay.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces |
            NSWindowCollectionBehaviorFullScreenAuxiliary |
            NSWindowCollectionBehaviorStationary)
        self.overlay.setIgnoresMouseEvents_(True)
        self.overlay.setAcceptsMouseMovedEvents_(True)

        bounds = NSMakeRect(0, 0, frame.size.width, frame.size.height)
        self.draw_view = DrawView.alloc().initWithFrame_app_(bounds, self)
        self.overlay.setContentView_(self.draw_view)
        self.overlay.orderFrontRegardless()

    def screensChanged_(self, note):
        frame = self._screen_frame()
        self.overlay.setFrame_display_(frame, True)
        self.draw_view.setFrame_(NSMakeRect(0, 0, frame.size.width, frame.size.height))
        self._position_toolbar()
        self.draw_view.setNeedsDisplay_(True)

    # -- Toolbar ---------------------------------------------------------------

    @objc.python_method
    def _make_button(self, x, symbol, action, tooltip, w=36.0, h=30.0, tint=None):
        btn = NSButton.alloc().initWithFrame_(NSMakeRect(x, 8, w, h))
        btn.setBordered_(False)
        # Punkt 3: sonst steht überall das Wort "Button".
        btn.setTitle_("")
        btn.setImagePosition_(1)  # NSImageOnly
        btn.setImage_(symbol_image(symbol, 15.0))
        btn.setButtonType_(NSButtonTypeMomentaryChange)
        btn.setTarget_(self)
        btn.setAction_(action)
        btn.setToolTip_(tooltip)
        btn.setWantsLayer_(True)
        btn.layer().setCornerRadius_(7.0)
        btn.setContentTintColor_(tint or NSColor.whiteColor())
        return btn

    @objc.python_method
    def _build_toolbar(self):
        H = 46.0
        x = 10.0
        gap, sep = 4.0, 14.0
        widgets = []

        for i, (tool_id, symbol, tip) in enumerate(TOOLS):
            b = self._make_button(x, symbol, b"toolClicked:", tip)
            b.setTag_(i)
            self.tool_buttons[tool_id] = b
            widgets.append(b)
            x += 36.0 + gap
        x += sep

        for i, (name, color) in enumerate(COLORS):
            b = NSButton.alloc().initWithFrame_(NSMakeRect(x, 13, 20, 20))
            b.setBordered_(False)
            b.setTitle_("")
            b.setImagePosition_(1)
            b.setButtonType_(NSButtonTypeMomentaryChange)
            b.setTarget_(self)
            b.setAction_(b"colorClicked:")
            b.setTag_(i)
            b.setToolTip_(name)
            b.setWantsLayer_(True)
            b.layer().setBackgroundColor_(color.CGColor())
            b.layer().setCornerRadius_(10.0)
            self.color_buttons.append(b)
            widgets.append(b)
            x += 20.0 + 6.0
        x += sep

        for i, width in enumerate(WIDTHS):
            b = self._make_button(x, "circle.fill", b"widthClicked:",
                                  "Strichstärke %g" % width, w=30.0)
            b.setImage_(symbol_image("circle.fill", 6.0 + i * 4.0))
            b.setTag_(i)
            self.width_buttons.append(b)
            widgets.append(b)
            x += 30.0 + gap
        x += sep

        self.spot_button = self._make_button(x, "flashlight.on.fill",
                                             b"toggleSpotlight:", "Spotlight")
        widgets.append(self.spot_button)
        x += 36.0 + gap
        widgets.append(self._make_button(x, "arrow.uturn.backward",
                                         b"undoStroke:", "Rückgängig (⌘Z)"))
        x += 36.0 + gap
        widgets.append(self._make_button(x, "trash",
                                         b"clearAll:", "Alles löschen (⌫)"))
        x += 36.0 + sep
        exit_btn = self._make_button(x, "xmark.circle.fill", b"stopDrawing:",
                                     "Zeichnen beenden (Esc)", tint=RED_TINT)
        widgets.append(exit_btn)
        x += 36.0 + 10.0

        rect = NSMakeRect(0, 0, x, H)
        self.toolbar = ToolbarPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            rect,
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered, False)
        self.toolbar.setReleasedWhenClosed_(False)
        self.toolbar.setOpaque_(False)
        self.toolbar.setBackgroundColor_(NSColor.clearColor())
        self.toolbar.setHasShadow_(True)
        self.toolbar.setLevel_(NSMainMenuWindowLevel + 2)
        self.toolbar.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces |
            NSWindowCollectionBehaviorFullScreenAuxiliary)
        self.toolbar.setMovableByWindowBackground_(True)

        bg = ToolbarBGView.alloc().initWithFrame_(NSMakeRect(0, 0, x, H))
        for wdg in widgets:
            bg.addSubview_(wdg)
        self.toolbar.setContentView_(bg)
        self._position_toolbar()
        self._refresh_toolbar_state()

    @objc.python_method
    def _position_toolbar(self):
        frame = self._screen_frame()
        tb = self.toolbar.frame()
        self.toolbar.setFrameOrigin_(NSMakePoint(
            frame.origin.x + (frame.size.width - tb.size.width) / 2.0,
            frame.origin.y + 80.0))

    @objc.python_method
    def _refresh_toolbar_state(self):
        for tool_id, btn in self.tool_buttons.items():
            active = (tool_id == self.tool)
            btn.layer().setBackgroundColor_(
                (GOLD if active else NSColor.clearColor()).CGColor())
            btn.setContentTintColor_(
                _rgb(0x11, 0x11, 0x11) if active else NSColor.whiteColor())
        for i, btn in enumerate(self.color_buttons):
            btn.layer().setBorderWidth_(2.5 if i == self.color_idx else 0.0)
            btn.layer().setBorderColor_(NSColor.whiteColor().CGColor())
        for i, btn in enumerate(self.width_buttons):
            active = (i == self.width_idx)
            btn.layer().setBackgroundColor_(
                (GOLD_DIM if active else NSColor.clearColor()).CGColor())
            btn.setContentTintColor_(GOLD if active else NSColor.whiteColor())
        if self.spot_button is not None:
            on = self.draw_view.spotlight
            self.spot_button.layer().setBackgroundColor_(
                (GOLD if on else NSColor.clearColor()).CGColor())
            self.spot_button.setContentTintColor_(
                _rgb(0x11, 0x11, 0x11) if on else NSColor.whiteColor())

    # -- Aktionen ---------------------------------------------------------------

    def toolClicked_(self, sender):
        self.tool = TOOLS[sender.tag()][0]
        self._refresh_toolbar_state()

    def colorClicked_(self, sender):
        self.color_idx = sender.tag()
        self._refresh_toolbar_state()

    def widthClicked_(self, sender):
        self.width_idx = sender.tag()
        self._refresh_toolbar_state()

    def toggleDrawing_(self, sender):
        self.setDrawing_(not self.drawing)

    def stopDrawing_(self, sender):
        self.setDrawing_(False)

    def setDrawing_(self, on):
        if on == self.drawing:
            return
        self.drawing = on
        if on:
            self.overlay.setIgnoresMouseEvents_(False)
            self.overlay.orderFrontRegardless()
            NSApp.activateIgnoringOtherApps_(True)
            self.overlay.makeKeyAndOrderFront_(None)
            self.overlay.makeFirstResponder_(self.draw_view)
            self.toolbar.orderFrontRegardless()
        else:
            if self.draw_view.spotlight:
                self._set_spotlight(False)
            self.overlay.setIgnoresMouseEvents_(True)
            self.toolbar.orderOut_(None)
        self._update_status_tint()
        self._refresh_toolbar_state()

    def undoStroke_(self, sender):
        self.draw_view.undo()

    def clearAll_(self, sender):
        self.draw_view.clear()

    def toggleSpotlight_(self, sender):
        self._set_spotlight(not self.draw_view.spotlight)

    @objc.python_method
    def _set_spotlight(self, on):
        v = self.draw_view
        if on == v.spotlight:
            return
        v.spotlight = on
        if on:
            if not self.drawing:
                self.setDrawing_(True)
            mouse = NSEvent.mouseLocation()
            f = self.overlay.frame()
            v.mouse = NSMakePoint(mouse.x - f.origin.x, mouse.y - f.origin.y)
            NSCursor.hide()
        else:
            NSCursor.unhide()   # Cursor IMMER wieder einblenden!
        v.setNeedsDisplay_(True)
        self._refresh_toolbar_state()

    # -- Event-Monitore ----------------------------------------------------------

    @objc.python_method
    def _is_hotkey(self, event):
        flags = event.modifierFlags()
        code = event.keyCode()
        if code == KEY_P and (flags & NSEventModifierFlagControl) \
                and (flags & NSEventModifierFlagFunction):
            return True
        if code == KEY_D and (flags & NSEventModifierFlagCommand) \
                and (flags & NSEventModifierFlagOption):
            return True
        return False

    @objc.python_method
    def _install_monitors(self):
        # Globaler Monitor: Toggle-Hotkeys, auch wenn eine andere App fokussiert ist.
        def global_handler(event):
            if self._is_hotkey(event):
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    b"toggleDrawing:", None, False)
        self._global_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            NSEventMaskKeyDown, global_handler)

        # Lokaler Monitor (Punkt 8): Werkzeug-Tasten nur, wenn das Overlay Key ist.
        def local_handler(event):
            if self._is_hotkey(event):
                self.toggleDrawing_(None)
                return None
            if not self.drawing or NSApp.keyWindow() is not self.overlay:
                return event
            return self._handle_draw_key(event)
        self._local_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            NSEventMaskKeyDown, local_handler)

    @objc.python_method
    def _handle_draw_key(self, event):
        code = event.keyCode()
        flags = event.modifierFlags()
        chars = event.charactersIgnoringModifiers() or ""
        v = self.draw_view

        if code == KEY_ESC:
            if v.spotlight:
                self._set_spotlight(False)
            else:
                self.setDrawing_(False)
            return None
        if v.spotlight and code in (KEY_UP, KEY_DOWN):
            v.set_spot_radius(v.spot_radius + (25.0 if code == KEY_UP else -25.0))
            return None
        if (flags & NSEventModifierFlagCommand) and chars.lower() == "z":
            v.undo()
            return None
        if code == KEY_BACKSPACE:
            v.clear()
            return None
        if chars in ("1", "2", "3", "4", "5", "6"):
            self.tool = TOOLS[int(chars) - 1][0]
            self._refresh_toolbar_state()
            return None
        return event


# ----------------------------------------------------------------------------

def main():
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()


if __name__ == "__main__":
    main()
