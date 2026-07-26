import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import threading
import time
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any
import os
import math
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Rectangle, Circle, FancyBboxPatch
from matplotlib.lines import Line2D
from src.sensor_simulator import SensorSimulator
from src.routing_engine import RoutingEngine
from src.pushbullet_notifier import PushbulletNotifier


class ProfessionalDashboard:
    COLORS = {
        'bg_primary': '#0F141B',
        'bg_secondary': '#1C222C',
        'bg_panel': '#222B36',
        'bg_card': '#283240',
        'bg_input': '#1A222C',
        'accent_primary': '#00A3E0',
        'accent_secondary': '#0077B6',
        'accent_dark': '#005A8C',
        'safe': '#00C853',
        'warning': '#FFC107',
        'danger': '#FF1744',
        'critical': '#D50000',
        'flashover': '#8B0000',
        'info': '#00BCD4',
        'text_primary': '#E8EDF2',
        'text_secondary': '#9BA8B8',
        'text_muted': '#6A7A8A',
        'text_dark': '#0F141B',
        'border': '#33404D',
        'border_light': '#455A64',
        'exit': '#00E676',
        'route': '#00E676',
        'selected': '#00A3E0',
        'hover': '#2A3A4A'
    }
    ICONS = {
        'temperature': '◆',
        'smoke': '◇',
        'exits': '⊞',
        'fire': '●',
        'sensors': '◈',
        'routing': '▶',
        'eta': '◉',
        'safe': '◆',
        'warning': '▲',
        'danger': '◆',
        'critical': '■',
        'flashover': '◆',
        'info': '▶',
        'selected': '◉',
        'exit': '⊞',
        'route': '▶'
    }
    FONTS = {
        'header_large': ('Helvetica', 18, 'bold'),
        'header_medium': ('Helvetica', 14, 'bold'),
        'header_small': ('Helvetica', 12, 'bold'),
        'body': ('Helvetica', 12),
        'body_bold': ('Helvetica', 12, 'bold'),
        'small': ('Helvetica', 12),
        'small_bold': ('Helvetica', 12, 'bold'),
        'mono': ('Courier', 12),
        'mono_bold': ('Courier', 12, 'bold'),
    }
    FIRE_LEVELS = {
        'none': {'label': 'Safe', 'color': '#00C853', 'bg': '#1A3A2A', 'icon': '◆'},
        'low': {'label': 'Low Fire', 'color': '#FFC107', 'bg': '#3A3A1A', 'icon': '▲'},
        'medium': {'label': 'Medium Fire', 'color': '#FF9100', 'bg': '#3A2A1A', 'icon': '●'},
        'high': {'label': 'High Fire', 'color': '#FF1744', 'bg': '#3A1A1A', 'icon': '■'},
        'flashover': {'label': 'Flashover', 'color': '#8B0000', 'bg': '#2A0A0A', 'icon': '◆'}
    }
    FIRE_SENSORS = {
        'none': {'temperature': 25, 'smoke_density': 10, 'flame_presence': False},
        'low': {'temperature': 80, 'smoke_density': 200, 'flame_presence': True},
        'medium': {'temperature': 180, 'smoke_density': 450, 'flame_presence': True},
        'high': {'temperature': 320, 'smoke_density': 700, 'flame_presence': True},
        'flashover': {'temperature': 700, 'smoke_density': 1200, 'flame_presence': True}
    }

    def __init__(self, root):
        self.root = root
        self.root.title("Smart Building Emergency Management System")
        self.root.geometry("1600x1000")
        self.root.minsize(1400, 800)
        self.root.configure(bg=self.COLORS['bg_primary'])

        self.simulator = SensorSimulator()
        self.engine = RoutingEngine()
        self.notifier = PushbulletNotifier()

        self.simulator.start()
        self.notifier.start()

        self.running = True
        self.update_interval = 500
        self.route_history = []
        self.selected_node = None
        self.alert_sent = False
        self.last_fire_check = 0
        self.fire_check_interval = 3.0

        self.node_fire_levels = {}
        self.sensor_data_cache = {}

        self.animation_phase = 0
        self.animations_enabled = True
        self.arrow_items = []

        self.incident_events = []
        self.max_incident_events = 50

        self.canvas_cache = {
            'nodes': {},
            'labels': {},
            'status_icons': {},
            'exit_markers': {},
            'route_items': [],
            'route_glow_items': [],
            'arrow_items': []
        }

        self.route_info_text = None

        self._build_ui()

        self._update_display()
        self._animate_routes()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._log_incident("System Initialized", "System startup complete", "info")
        self._log_incident("Ready", f"Monitoring {len(self.engine.nodes)} nodes", "info")

        if not self.notifier.is_configured:
            self._log_incident("Warning", "Pushbullet not configured - add API key", "warning")

    def _build_ui(self):
        self.main_container = tk.Frame(self.root, bg=self.COLORS['bg_primary'])
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._build_kpi_dashboard()

        self.columns_container = tk.Frame(
            self.main_container,
            bg=self.COLORS['bg_primary']
        )
        self.columns_container.pack(fill=tk.BOTH, expand=True, pady=10)

        self.columns_container.grid_columnconfigure(0, weight=1)
        self.columns_container.grid_columnconfigure(1, weight=7)
        self.columns_container.grid_columnconfigure(2, weight=2)
        self.columns_container.grid_rowconfigure(0, weight=1)

        self.left_panel = self._build_left_panel(self.columns_container)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        self.center_panel = self._build_center_panel(self.columns_container)
        self.center_panel.grid(row=0, column=1, sticky="nsew", padx=5)

        self.right_panel = self._build_right_panel(self.columns_container)
        self.right_panel.grid(row=0, column=2, sticky="nsew", padx=(5, 0))

    def _build_kpi_dashboard(self):
        kpi_container = tk.Frame(
            self.main_container,
            bg=self.COLORS['bg_secondary'],
            height=80
        )
        kpi_container.pack(fill=tk.X, pady=(0, 10))
        kpi_container.pack_propagate(False)

        kpis = [
            ('Avg Temperature', 'kpi_temp', '25°C', '#00BCD4'),
            ('Avg Smoke Density', 'kpi_smoke', '12 PPM', '#00BCD4'),
            ('Safe Exits', 'kpi_exits', '0', '#00C853'),
            ('Active Fire Zones', 'kpi_fires', '0', '#FF1744'),
            ('Sensors Online', 'kpi_sensors', '0/0', '#00A3E0'),
            ('Evacuation Time', 'kpi_eta', '0s', '#00E676')
        ]

        self.kpi_vars = {}

        for i, (label, key, default, color) in enumerate(kpis):
            card = tk.Frame(
                kpi_container,
                bg=self.COLORS['bg_card'],
                relief=tk.FLAT,
                bd=0
            )
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2, pady=5)

            tk.Label(
                card,
                text=label,
                font=self.FONTS['small'],
                fg=self.COLORS['text_secondary'],
                bg=self.COLORS['bg_card']
            ).pack(anchor='w', padx=10, pady=(5, 0))

            var = tk.StringVar(value=default)
            self.kpi_vars[key] = var

            tk.Label(
                card,
                textvariable=var,
                font=('Helvetica', 16, 'bold'),
                fg=color,
                bg=self.COLORS['bg_card']
            ).pack(anchor='w', padx=10, pady=(0, 5))

    def _build_left_panel(self, parent):
        panel = tk.Frame(
            parent,
            bg=self.COLORS['bg_secondary'],
            relief=tk.FLAT,
            bd=0
        )

        canvas = tk.Canvas(panel, bg=self.COLORS['bg_secondary'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.COLORS['bg_secondary'])

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._build_section_header(
            scrollable_frame,
            "EMERGENCY STATUS",
            self.COLORS['text_primary']
        )

        self.status_indicator = tk.Frame(
            scrollable_frame,
            bg=self.COLORS['bg_card'],
            height=60,
            relief=tk.FLAT
        )
        self.status_indicator.pack(fill=tk.X, pady=(0, 10))
        self.status_indicator.pack_propagate(False)

        self.status_text = tk.Label(
            self.status_indicator,
            text="SYSTEM ACTIVE",
            font=('Helvetica', 14, 'bold'),
            fg=self.COLORS['safe'],
            bg=self.COLORS['bg_card']
        )
        self.status_text.pack(anchor='w', padx=15)

        self._build_section_header(
            scrollable_frame,
            "FIRE SEVERITY",
            self.COLORS['text_secondary']
        )

        legend_frame = tk.Frame(
            scrollable_frame,
            bg=self.COLORS['bg_card'],
            relief=tk.FLAT
        )
        legend_frame.pack(fill=tk.X, pady=(0, 10))

        for level, data in self.FIRE_LEVELS.items():
            row = tk.Frame(legend_frame, bg=self.COLORS['bg_card'])
            row.pack(fill=tk.X, padx=10, pady=2)

            tk.Label(
                row,
                text=data['icon'],
                fg=data['color'],
                bg=self.COLORS['bg_card'],
                font=('Helvetica', 12)
            ).pack(side=tk.LEFT)

            tk.Label(
                row,
                text=data['label'],
                font=self.FONTS['small'],
                fg=self.COLORS['text_primary'],
                bg=self.COLORS['bg_card']
            ).pack(side=tk.LEFT, padx=5)

        self._build_section_header(
            scrollable_frame,
            "SYSTEM HEALTH",
            self.COLORS['text_secondary']
        )

        health_frame = tk.Frame(
            scrollable_frame,
            bg=self.COLORS['bg_card'],
            relief=tk.FLAT
        )
        health_frame.pack(fill=tk.X, pady=(0, 10))

        self.health_text = tk.Text(
            health_frame,
            height=4,
            font=self.FONTS['mono'],
            bg=self.COLORS['bg_card'],
            fg=self.COLORS['text_secondary'],
            relief=tk.FLAT,
            wrap=tk.WORD,
            padx=10,
            pady=5
        )
        self.health_text.pack(fill=tk.X)

        self._build_section_header(
            scrollable_frame,
            "INCIDENT TIMELINE",
            self.COLORS['text_secondary']
        )

        self.timeline_frame = tk.Frame(
            scrollable_frame,
            bg=self.COLORS['bg_card'],
            relief=tk.FLAT
        )
        self.timeline_frame.pack(fill=tk.BOTH, expand=True)

        self.timeline_text = tk.Text(
            self.timeline_frame,
            height=8,
            font=self.FONTS['mono'],
            bg=self.COLORS['bg_card'],
            fg=self.COLORS['text_secondary'],
            relief=tk.FLAT,
            wrap=tk.WORD,
            padx=10,
            pady=5
        )
        self.timeline_text.pack(fill=tk.BOTH, expand=True)

        return panel

    def _build_center_panel(self, parent):
        panel = tk.Frame(
            parent,
            bg=self.COLORS['bg_secondary'],
            relief=tk.FLAT,
            bd=0
        )

        self.floor_canvas = tk.Canvas(
            panel,
            bg=self.COLORS['bg_secondary'],
            highlightthickness=0,
            relief=tk.FLAT
        )
        self.floor_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.floor_canvas.bind('<Button-1>', self._on_canvas_click)
        self.floor_canvas.bind('<Motion>', self._on_canvas_hover)

        self._build_section_header(
            panel,
            "FLOOR PLAN - EVACUATION MAP",
            self.COLORS['text_secondary'],
            pack_side=tk.TOP
        )

        return panel

    def _build_right_panel(self, parent):
        panel = tk.Frame(
            parent,
            bg=self.COLORS['bg_secondary'],
            relief=tk.FLAT,
            bd=0
        )

        self._build_section_header(
            panel,
            "INCIDENT CONTROL",
            self.COLORS['text_primary']
        )

        node_frame = tk.LabelFrame(
            panel,
            text="SELECTED NODE",
            font=self.FONTS['header_small'],
            fg=self.COLORS['text_primary'],
            bg=self.COLORS['bg_panel'],
            relief=tk.FLAT
        )
        node_frame.pack(fill=tk.X, pady=5)

        self.node_info = tk.Text(
            node_frame,
            height=10,
            font=self.FONTS['mono'],
            bg=self.COLORS['bg_card'],
            fg=self.COLORS['text_primary'],
            relief=tk.FLAT,
            wrap=tk.WORD,
            padx=10,
            pady=5
        )
        self.node_info.pack(fill=tk.X, padx=5, pady=5)
        self.node_info.insert(tk.END, "Select a node on the floor plan")

        route_frame = tk.LabelFrame(
            panel,
            text="ROUTE INFORMATION",
            font=self.FONTS['header_small'],
            fg=self.COLORS['text_primary'],
            bg=self.COLORS['bg_panel'],
            relief=tk.FLAT
        )
        route_frame.pack(fill=tk.X, pady=5)

        self.route_info_text = tk.Text(
            route_frame,
            height=6,
            font=self.FONTS['mono'],
            bg=self.COLORS['bg_card'],
            fg=self.COLORS['text_primary'],
            relief=tk.FLAT,
            wrap=tk.WORD,
            padx=10,
            pady=5
        )
        self.route_info_text.pack(fill=tk.X, padx=5, pady=5)
        self.route_info_text.insert(tk.END, "Route information will appear here")

        control_frame = tk.LabelFrame(
            panel,
            text="FIRE CONTROL",
            font=self.FONTS['header_small'],
            fg=self.COLORS['text_primary'],
            bg=self.COLORS['bg_panel'],
            relief=tk.FLAT
        )
        control_frame.pack(fill=tk.X, pady=5)

        self.selected_display = tk.Label(
            control_frame,
            text="No node selected",
            font=self.FONTS['body'],
            fg=self.COLORS['text_secondary'],
            bg=self.COLORS['bg_panel']
        )
        self.selected_display.pack(pady=5)

        level_frame = tk.Frame(control_frame, bg=self.COLORS['bg_panel'])
        level_frame.pack(fill=tk.X, padx=5, pady=5)

        self.fire_level_var = tk.StringVar(value='none')

        for level, data in self.FIRE_LEVELS.items():
            btn = tk.Button(
                level_frame,
                text=data['label'],
                bg=self.COLORS['bg_card'],
                fg=data['color'],
                font=self.FONTS['small_bold'],
                relief=tk.FLAT,
                bd=0,
                padx=8,
                pady=4,
                cursor='hand2',
                command=lambda l=level: self._set_selected_fire_level(l)
            )
            btn.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True)

            btn.bind('<Enter>', lambda e, b=btn: b.configure(bg=self.COLORS['hover']))
            btn.bind('<Leave>', lambda e, b=btn: b.configure(bg=self.COLORS['bg_card']))

        action_frame = tk.LabelFrame(
            panel,
            text="ACTIONS",
            font=self.FONTS['header_small'],
            fg=self.COLORS['text_primary'],
            bg=self.COLORS['bg_panel'],
            relief=tk.FLAT
        )
        action_frame.pack(fill=tk.X, pady=5)

        actions = [
            ('Find Route', self._calculate_route, '#00A3E0'),
            ('Send Alert', self._send_alert_dialog, '#FF1744'),
            ('Clear All', self._clear_all, '#FFC107'),
            ('Generate Report', self._generate_report, '#00BCD4')
        ]

        for label, command, color in actions:
            btn = tk.Button(
                action_frame,
                text=label,
                font=self.FONTS['body_bold'],
                bg=self.COLORS['bg_card'],
                fg=color,
                relief=tk.FLAT,
                bd=0,
                padx=10,
                pady=8,
                cursor='hand2',
                command=command
            )
            btn.pack(fill=tk.X, padx=5, pady=3)

            btn.bind('<Enter>', lambda e, b=btn: b.configure(bg=self.COLORS['hover']))
            btn.bind('<Leave>', lambda e, b=btn: b.configure(bg=self.COLORS['bg_card']))

        return panel

    def _build_section_header(self, parent, text, color, pack_side=tk.TOP):
        header = tk.Frame(
            parent,
            bg=self.COLORS['bg_secondary'],
            height=30
        )
        header.pack(side=pack_side, fill=tk.X, pady=(10, 5))
        header.pack_propagate(False)

        tk.Frame(
            header,
            bg=color,
            width=3,
            height=20
        ).pack(side=tk.LEFT, padx=5, pady=5)

        tk.Label(
            header,
            text=text,
            font=self.FONTS['header_small'],
            fg=color,
            bg=self.COLORS['bg_secondary']
        ).pack(side=tk.LEFT, padx=5)

    def _draw_floor_plan(self):
        self.floor_canvas.delete("all")

        pos = self.engine.node_positions
        if not pos:
            return

        max_x = max([p[0] for p in pos.values()]) * 100 + 120
        max_y = max([p[1] for p in pos.values()]) * 100 + 120

        self.floor_canvas.config(scrollregion=(0, 0, max_x + 20, max_y + 20))

        for i in range(0, int(max_x / 50) + 2):
            x = i * 50
            self.floor_canvas.create_line(
                x, 0, x, max_y,
                fill='#1A2530',
                width=1
            )
        for i in range(0, int(max_y / 50) + 2):
            y = i * 50
            self.floor_canvas.create_line(
                0, y, max_x, y,
                fill='#1A2530',
                width=1
            )

        self._draw_rooms(pos)
        self._draw_corridors(pos)
        self._draw_nodes(pos)
        self._draw_animated_route(pos)
        self._draw_exits(pos)
        self._draw_selection_highlight(pos)

    def _draw_rooms(self, pos):
        rooms = {}

        for node_id, (x, y) in pos.items():
            room_key = (int(x / 2), int(y / 2))
            if room_key not in rooms:
                rooms[room_key] = []
            rooms[room_key].append((node_id, x, y))

        for room_key, nodes in rooms.items():
            if len(nodes) < 2:
                continue

            xs = [n[1] for n in nodes]
            ys = [n[2] for n in nodes]
            min_x = min(xs) * 100 - 20
            max_x = max(xs) * 100 + 20
            min_y = min(ys) * 100 - 20
            max_y = max(ys) * 100 + 20

            self.floor_canvas.create_rectangle(
                min_x, min_y, max_x, max_y,
                outline='#2A3A4A',
                fill='#1A2530',
                width=1.5,
                dash=(4, 4)
            )

            mid_x = (min_x + max_x) / 2
            mid_y = (min_y + max_y) / 2
            self.floor_canvas.create_text(
                mid_x, mid_y,
                text=f"Room {len(nodes)}",
                font=('Helvetica', 8),
                fill='#3A4A5A'
            )

    def _draw_corridors(self, pos):
        for node in self.engine.nodes:
            node_id = node['id']
            if node_id not in pos:
                continue

            x1, y1 = pos[node_id]
            x1 = x1 * 100 + 60
            y1 = y1 * 100 + 60

            for conn in node.get('connections', []):
                if conn not in pos:
                    continue

                x2, y2 = pos[conn]
                x2 = x2 * 100 + 60
                y2 = y2 * 100 + 60

                fire_level = self.node_fire_levels.get(conn, 'none')

                if fire_level == 'flashover':
                    color = self.COLORS['flashover']
                    width = 3
                elif fire_level == 'high':
                    color = self.COLORS['danger']
                    width = 2.5
                elif fire_level == 'medium':
                    color = self.COLORS['warning']
                    width = 2
                elif fire_level == 'low':
                    color = '#FFC107'
                    width = 1.5
                else:
                    color = '#3A4A5A'
                    width = 1.5

                self.floor_canvas.create_line(
                    x1, y1, x2, y2,
                    fill=color,
                    width=width,
                    smooth=True
                )

    def _draw_nodes(self, pos):
        self.canvas_cache['nodes'] = {}
        self.canvas_cache['labels'] = {}
        self.canvas_cache['status_icons'] = {}

        for node_id, (x, y) in pos.items():
            x = x * 100 + 60
            y = y * 100 + 60

            fire_level = self.node_fire_levels.get(node_id, 'none')
            is_exit = node_id in self.engine.exits

            if fire_level == 'flashover':
                color = self.COLORS['flashover']
                size = 22
                glow = True
                icon = '◆'
            elif fire_level == 'high':
                color = self.COLORS['danger']
                size = 20
                glow = True
                icon = '■'
            elif fire_level == 'medium':
                color = '#FF9100'
                size = 18
                glow = True
                icon = '●'
            elif fire_level == 'low':
                color = '#FFC107'
                size = 16
                glow = False
                icon = '▲'
            else:
                color = '#3A4A5A'
                size = 14
                glow = False
                icon = '○'

            if glow:
                try:
                    for i in range(3, 0, -1):
                        self.floor_canvas.create_oval(
                            x - size - i*5, y - size - i*5,
                            x + size + i*5, y + size + i*5,
                            outline='',
                            fill=color
                        )
                except:
                    pass

            node_item = self.floor_canvas.create_oval(
                x - size, y - size,
                x + size, y + size,
                fill=color,
                outline='#4A5A6A',
                width=2,
                tags=(node_id, 'node')
            )
            self.canvas_cache['nodes'][node_id] = node_item

            label_item = self.floor_canvas.create_text(
                x, y - size - 12,
                text=node_id,
                font=('Helvetica', 7, 'bold'),
                fill='#8A9AAB',
                tags=(node_id, 'label')
            )
            self.canvas_cache['labels'][node_id] = label_item

            icon_item = self.floor_canvas.create_text(
                x, y + 2,
                text=icon,
                font=('Helvetica', 10),
                fill='#FFFFFF',
                tags=(node_id, 'icon')
            )
            self.canvas_cache['status_icons'][node_id] = icon_item

            if fire_level != 'none':
                level_label = fire_level.upper()
                if fire_level == 'flashover':
                    level_label = 'FLASH'
                self.floor_canvas.create_text(
                    x, y + size + 12,
                    text=level_label,
                    font=('Helvetica', 6, 'bold'),
                    fill=color,
                    tags=(node_id, 'level')
                )

    def _draw_animated_route(self, pos):
        for item in self.canvas_cache.get('route_items', []):
            try:
                self.floor_canvas.delete(item)
            except:
                pass
        for item in self.canvas_cache.get('route_glow_items', []):
            try:
                self.floor_canvas.delete(item)
            except:
                pass
        self.canvas_cache['route_items'] = []
        self.canvas_cache['route_glow_items'] = []
        self.canvas_cache['arrow_items'] = []

        if not self.route_history:
            return

        path = self.route_history[-1]['path']
        if len(path) < 2:
            return

        route_points = []
        for node in path:
            if node in pos:
                x = pos[node][0] * 100 + 60
                y = pos[node][1] * 100 + 60
                route_points.append((x, y))

        if len(route_points) < 2:
            return

        for i in range(len(route_points) - 1):
            x1, y1 = route_points[i]
            x2, y2 = route_points[i + 1]

            try:
                item = self.floor_canvas.create_line(
                    x1, y1, x2, y2,
                    fill='#00E676',
                    width=5,
                    capstyle='round',
                    joinstyle='round',
                    tags=('route',)
                )
                self.canvas_cache['route_items'].append(item)
            except:
                pass

            try:
                glow_item = self.floor_canvas.create_line(
                    x1, y1, x2, y2,
                    fill='#66E676',
                    width=12,
                    capstyle='round',
                    joinstyle='round',
                    tags=('route_glow',)
                )
                self.canvas_cache['route_glow_items'].append(glow_item)
            except:
                pass

            num_arrows = max(1, int(self._distance_points((x1, y1), (x2, y2)) / 40))

            for j in range(num_arrows):
                t = (j + 0.5) / num_arrows
                mid_x = x1 + (x2 - x1) * t
                mid_y = y1 + (y2 - y1) * t

                angle = math.atan2(y2 - y1, x2 - x1)
                arrow_len = 12

                arrow_data = {
                    'x': mid_x,
                    'y': mid_y,
                    'angle': angle,
                    'phase': (j / num_arrows) * 2 * math.pi,
                    'speed': 0.05
                }
                self.canvas_cache['arrow_items'].append(arrow_data)

                try:
                    arrow_item = self.floor_canvas.create_polygon(
                        mid_x + arrow_len * math.cos(angle),
                        mid_y + arrow_len * math.sin(angle),
                        mid_x + 6 * math.cos(angle + 2.5),
                        mid_y + 6 * math.sin(angle + 2.5),
                        mid_x + 6 * math.cos(angle - 2.5),
                        mid_y + 6 * math.sin(angle - 2.5),
                        fill='#00E676',
                        outline='',
                        tags=('arrow',)
                    )
                    self.canvas_cache['route_items'].append(arrow_item)
                except:
                    pass

    def _distance_points(self, p1, p2):
        return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

    def _draw_exits(self, pos):
        for node_id in self.engine.exits:
            if node_id not in pos:
                continue

            x = pos[node_id][0] * 100 + 60
            y = pos[node_id][1] * 100 + 60

            fire_level = self.node_fire_levels.get(node_id, 'none')
            is_blocked = fire_level in ['high', 'flashover']

            if is_blocked:
                self.floor_canvas.create_rectangle(
                    x - 18, y - 18,
                    x + 18, y + 18,
                    fill='#4A4A5A',
                    outline='#FF1744',
                    width=2,
                    tags=(node_id, 'exit')
                )
                self.floor_canvas.create_text(
                    x, y,
                    text='X',
                    font=('Helvetica', 16, 'bold'),
                    fill='#FF1744',
                    tags=(node_id, 'exit_label')
                )
            else:
                try:
                    for i in range(3, 0, -1):
                        self.floor_canvas.create_oval(
                            x - 22 - i*3, y - 22 - i*3,
                            x + 22 + i*3, y + 22 + i*3,
                            outline='',
                            fill='#66E676'
                        )
                except:
                    pass

                self.floor_canvas.create_rectangle(
                    x - 20, y - 20,
                    x + 20, y + 20,
                    fill='#00E676',
                    outline='#00C853',
                    width=2,
                    tags=(node_id, 'exit')
                )
                self.floor_canvas.create_text(
                    x, y,
                    text='EXIT',
                    font=('Helvetica', 8, 'bold'),
                    fill='#0F141B',
                    tags=(node_id, 'exit_label')
                )

    def _draw_selection_highlight(self, pos):
        if not self.selected_node or self.selected_node not in pos:
            return

        x = pos[self.selected_node][0] * 100 + 60
        y = pos[self.selected_node][1] * 100 + 60

        radius = 30 + 5 * math.sin(self.animation_phase * 0.05)
        self.floor_canvas.create_oval(
            x - radius, y - radius,
            x + radius, y + radius,
            outline='#00A3E0',
            width=3,
            dash=(8, 4),
            tags=('selection',)
        )

    def _animate_routes(self):
        if not self.running:
            return

        self.animation_phase += 1

        try:
            if self.route_history and self.engine.node_positions:
                if self.animation_phase % 3 == 0:
                    self._draw_floor_plan()
        except:
            pass

        self.root.after(100, self._animate_routes)

    def _update_display(self):
        if not self.running:
            return

        try:
            sensor_data = self.simulator.get_sensor_data()
            self.sensor_data_cache = sensor_data

            for node_id in sensor_data:
                if node_id in self.node_fire_levels:
                    sensor_data[node_id]['fire_level'] = self.node_fire_levels[node_id]

            self.engine.update_weights(sensor_data)

            self._draw_floor_plan()

            self._update_kpis(sensor_data)

            self._update_health(sensor_data)

            if self.selected_node:
                self._update_node_info(self.selected_node, sensor_data)

            self._check_auto_notify(sensor_data)
            
            self.notifier.update()

        except Exception as e:
            traceback.print_exc()
            self._log_incident("Error", f"Update error: {e}", "error")

        self.root.after(self.update_interval, self._update_display)

    def _check_auto_notify(self, sensor_data):
        fire_nodes = []

        for node_id, data in sensor_data.items():
            flame = data.get('flame_presence', False)
            temp = data.get('temperature', 0)
            smoke = data.get('smoke_density', 0)
            fire_level = self.node_fire_levels.get(node_id, 'none')

            if fire_level != 'none' and fire_level != 'low':
                fire_nodes.append(node_id)

        if fire_nodes and not self.alert_sent:
            def send_alert():
                for node_id in fire_nodes:
                    self.notifier.process_fire_update(
                        node_id,
                        self.node_fire_levels.get(node_id, 'none'),
                        sensor_data.get(node_id, {})
                    )
                self.root.after(0, lambda: self._log_incident(
                    "Fire Alert", f"Auto-alert: Fire at {', '.join(fire_nodes)}", "critical"
                ))

            threading.Thread(target=send_alert, daemon=True).start()
            self.alert_sent = True

        elif not fire_nodes:
            self.alert_sent = False

    def _update_kpis(self, sensor_data):
        temps = [d.get('temperature', 0) for d in sensor_data.values()]
        avg_temp = sum(temps) / len(temps) if temps else 0
        self.kpi_vars['kpi_temp'].set(f'{avg_temp:.1f}°C')

        smokes = [d.get('smoke_density', 0) for d in sensor_data.values()]
        avg_smoke = sum(smokes) / len(smokes) if smokes else 0
        self.kpi_vars['kpi_smoke'].set(f'{avg_smoke:.0f} PPM')

        safe_exits = sum(1 for e in self.engine.exits 
                        if self.node_fire_levels.get(e, 'none') not in ['high', 'flashover'])
        self.kpi_vars['kpi_exits'].set(str(safe_exits))

        fire_zones = sum(1 for level in self.node_fire_levels.values() 
                        if level not in ['none'])
        self.kpi_vars['kpi_fires'].set(str(fire_zones))

        total = len(sensor_data)
        active = sum(1 for d in sensor_data.values() 
                    if d.get('battery_status', 0) > 20)
        self.kpi_vars['kpi_sensors'].set(f'{active}/{total}')

        if self.route_history:
            path_len = self.route_history[-1]['path_length']
            eta = path_len * 2
            self.kpi_vars['kpi_eta'].set(f'{eta}s')
        else:
            self.kpi_vars['kpi_eta'].set('0s')

    def _update_health(self, sensor_data):
        self.health_text.delete(1.0, tk.END)

        issues = []
        warnings = []

        for node_id, data in sensor_data.items():
            battery = data.get('battery_status', 0)
            if battery < 20:
                issues.append(f"{node_id}: Low battery ({battery:.0f}%)")
            elif battery < 40:
                warnings.append(f"{node_id}: Battery {battery:.0f}%")

        offline = sum(1 for d in sensor_data.values() 
                     if d.get('battery_status', 0) < 20)
        if offline > 0:
            issues.append(f"{offline} sensors offline")

        fire_zones = sum(1 for level in self.node_fire_levels.values() 
                        if level not in ['none'])
        if fire_zones > 0:
            warnings.append(f"{fire_zones} active fire zones")

        if issues:
            self.health_text.insert(tk.END, "CRITICAL ISSUES:\n")
            for issue in issues[:5]:
                self.health_text.insert(tk.END, f"  * {issue}\n")
        elif warnings:
            self.health_text.insert(tk.END, "WARNINGS:\n")
            for warning in warnings[:5]:
                self.health_text.insert(tk.END, f"  * {warning}\n")
        else:
            self.health_text.insert(tk.END, "All systems operational")

    def _update_node_info(self, node_id, sensor_data):
        self.node_info.delete(1.0, tk.END)

        data = sensor_data.get(node_id, {})
        fire_level = self.node_fire_levels.get(node_id, 'none')
        weight = self.engine.node_weights.get(node_id, 1.0)

        info = f"NODE: {node_id}\n"
        info += "-" * 25 + "\n\n"
        info += f"Status: {self.FIRE_LEVELS[fire_level]['label']}\n"
        info += f"Temperature: {data.get('temperature', 0):.1f}°C\n"
        info += f"Smoke Density: {data.get('smoke_density', 0):.0f} PPM\n"
        info += f"Battery: {data.get('battery_status', 0):.0f}%\n"
        info += f"Route Cost: {weight:.1f}\n"
        info += f"Connected Nodes: {len(self.engine.graph.get(node_id, {}))}\n"

        if fire_level == 'flashover':
            info += "\nRECOMMENDATION: EVACUATE IMMEDIATELY"
        elif fire_level == 'high':
            info += "\nRECOMMENDATION: AVOID THIS AREA"
        elif fire_level == 'medium':
            info += "\nRECOMMENDATION: Proceed with caution"
        elif fire_level == 'low':
            info += "\nRECOMMENDATION: Monitor conditions"
        else:
            info += "\nRECOMMENDATION: Safe - Proceed normally"

        self.node_info.insert(tk.END, info)

    def _on_canvas_click(self, event):
        clicked = self.floor_canvas.find_closest(event.x, event.y)
        if clicked:
            tags = self.floor_canvas.gettags(clicked)
            for tag in tags:
                if tag.startswith('N-'):
                    self.selected_node = tag
                    self._log_incident("Selection", f"Selected node {tag}", "info")
                    self.root.title(f"Smart Building EMS - Selected: {tag}")

                    self.selected_display.config(text=f"Selected: {tag}")
                    self._update_node_info(tag, self.sensor_data_cache)
                    self._draw_floor_plan()

                    self._calculate_route()
                    break

    def _on_canvas_hover(self, event):
        clicked = self.floor_canvas.find_closest(event.x, event.y)
        if clicked:
            tags = self.floor_canvas.gettags(clicked)
            for tag in tags:
                if tag.startswith('N-'):
                    self.floor_canvas.config(cursor='hand2')
                    return

        self.floor_canvas.config(cursor='')

    def _set_selected_fire_level(self, level: str):
        if not self.selected_node:
            messagebox.showwarning("No Selection", "Please select a node first")
            return

        self._set_fire_levels([self.selected_node], level)
        self._log_incident("Fire Control", f"Set {level} on {self.selected_node}", 
                          "critical" if level != 'none' else "info")

    def _set_fire_levels(self, node_ids: List[str], level: str):
        sensor_values = self.FIRE_SENSORS.get(level, self.FIRE_SENSORS['none'])

        for node_id in node_ids:
            self.node_fire_levels[node_id] = level

            self.simulator.manual_override(node_id, {
                'temperature': sensor_values['temperature'],
                'smoke_density': sensor_values['smoke_density'],
                'flame_presence': sensor_values['flame_presence'],
                'fire_level': level,
                'status': 'critical' if level != 'none' else 'normal'
            })

        sensor_data = self.simulator.get_sensor_data()
        for node_id in sensor_data:
            if node_id in self.node_fire_levels:
                sensor_data[node_id]['fire_level'] = self.node_fire_levels[node_id]

        self.engine.update_weights(sensor_data)

        for node_id in node_ids:
            self.notifier.process_fire_update(
                node_id,
                level,
                sensor_data.get(node_id, {})
            )

        if self.selected_node:
            self._calculate_route()

    def _calculate_route(self):
        if not self.selected_node:
            messagebox.showwarning("No Selection", "Please select a node first")
            return

        self._log_incident("Route Calculation", 
                          f"Calculating route from {self.selected_node}", 
                          "info")

        try:
            route_info = self.engine.get_route_info(self.selected_node)

            self.route_history.append({
                'timestamp': datetime.now(),
                'start_node': self.selected_node,
                **route_info
            })

            if len(self.route_history) > 10:
                self.route_history = self.route_history[-10:]

            path_str = " -> ".join(route_info['path'][:5])
            if len(route_info['path']) > 5:
                path_str += f" ... -> {route_info['path'][-1]}"

            status = "SAFE" if route_info['is_safe'] else f"HAZARDS ({route_info['hazard_count']})"
            self._log_incident("Route Found", 
                              f"Path: {len(route_info['path'])} nodes, {status}", 
                              "success" if route_info['is_safe'] else "warning")

            if self.route_info_text:
                self.route_info_text.delete(1.0, tk.END)
                self.route_info_text.insert(tk.END, 
                    f"Route from {self.selected_node}\n"
                    f"Length: {route_info['path_length']} nodes\n"
                    f"Cost: {route_info['total_cost']:.2f}\n"
                    f"Hazards: {route_info['hazard_count']}\n"
                    f"Status: {'SAFE' if route_info['is_safe'] else 'HAZARDS DETECTED'}\n\n"
                    f"Path:\n{path_str}"
                )

            def send_route():
                self.notifier.process_route_update(route_info)

            threading.Thread(target=send_route, daemon=True).start()

            self._draw_floor_plan()

        except Exception as e:
            self._log_incident("Error", f"Route calculation failed: {e}", "error")
            traceback.print_exc()
            messagebox.showerror("Route Error", f"Failed to calculate route: {e}")

    def _send_alert_dialog(self):
        if not self.notifier.is_configured:
            messagebox.showwarning("Not Configured", 
                                  "Pushbullet not configured. Add API key.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Send Alert")
        dialog.geometry("400x300")
        dialog.configure(bg=self.COLORS['bg_secondary'])
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(
            dialog,
            text="Send Emergency Alert",
            font=self.FONTS['header_medium'],
            fg=self.COLORS['text_primary'],
            bg=self.COLORS['bg_secondary']
        ).pack(pady=20)

        tk.Label(
            dialog,
            text="Alert Type:",
            font=self.FONTS['body'],
            fg=self.COLORS['text_secondary'],
            bg=self.COLORS['bg_secondary']
        ).pack()

        alert_var = tk.StringVar(value="evacuation")
        ttk.Combobox(
            dialog,
            textvariable=alert_var,
            values=['evacuation', 'fire_detected', 'route_updated', 'exit_blocked', 'all_clear'],
            state='readonly',
            width=20
        ).pack(pady=5)

        tk.Label(
            dialog,
            text="Custom Message:",
            font=self.FONTS['body'],
            fg=self.COLORS['text_secondary'],
            bg=self.COLORS['bg_secondary']
        ).pack(pady=(10, 0))

        msg_text = tk.Text(dialog, height=4, width=40, bg=self.COLORS['bg_input'],
                          fg=self.COLORS['text_primary'], relief=tk.FLAT)
        msg_text.pack(pady=5, padx=20)

        def send():
            alert_type = alert_var.get()
            custom_msg = msg_text.get(1.0, tk.END).strip()
            
            if alert_type == 'evacuation':
                self.notifier.process_critical_event(
                    custom_msg or "Evacuation required - follow indicated route",
                    severity=4
                )
            elif alert_type == 'fire_detected':
                self.notifier.process_critical_event(
                    custom_msg or "Fire detected - evacuate immediately",
                    severity=3
                )
            elif alert_type == 'route_updated':
                self.notifier.process_critical_event(
                    custom_msg or "Route updated - follow new evacuation path",
                    severity=2
                )
            elif alert_type == 'exit_blocked':
                self.notifier.process_critical_event(
                    custom_msg or "Exit blocked - use alternate route",
                    severity=4
                )
            elif alert_type == 'all_clear':
                self.notifier.process_critical_event(
                    custom_msg or "All clear - emergency resolved",
                    severity=1
                )

            self._log_incident("Alert", f"Sent {alert_type} alert", "info")
            messagebox.showinfo("Success", "Alert sent successfully!")
            dialog.destroy()

        btn_frame = tk.Frame(dialog, bg=self.COLORS['bg_secondary'])
        btn_frame.pack(pady=20)

        tk.Button(
            btn_frame,
            text="Send Alert",
            bg=self.COLORS['danger'],
            fg='white',
            font=self.FONTS['body_bold'],
            relief=tk.FLAT,
            padx=20,
            pady=8,
            cursor='hand2',
            command=send
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            btn_frame,
            text="Cancel",
            bg=self.COLORS['bg_card'],
            fg=self.COLORS['text_secondary'],
            font=self.FONTS['body'],
            relief=tk.FLAT,
            padx=20,
            pady=8,
            cursor='hand2',
            command=dialog.destroy
        ).pack(side=tk.LEFT, padx=5)

    def _generate_report(self):
        report = f"""
        ==============================================================
        SMART BUILDING EMERGENCY MANAGEMENT SYSTEM
        INCIDENT REPORT
        ==============================================================

        Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

        --- SYSTEM STATUS --------------------------------------------
        Total Nodes: {len(self.engine.nodes)}
        Fire Zones: {len([l for l in self.node_fire_levels.values() if l != 'none'])}
        Safe Exits: {sum(1 for e in self.engine.exits if self.node_fire_levels.get(e, 'none') not in ['high', 'flashover'])}

        --- ROUTE HISTORY --------------------------------------------
        Routes Calculated: {len(self.route_history)}

        --- INCIDENT TIMELINE ----------------------------------------
        """

        for event in self.incident_events[-10:]:
            report += f"\n  {event['time']} [{event['level']}] {event['description']}"

        report += f"""
        ==============================================================
        """

        dialog = tk.Toplevel(self.root)
        dialog.title("Incident Report")
        dialog.geometry("600x500")
        dialog.configure(bg=self.COLORS['bg_secondary'])
        dialog.transient(self.root)

        text = tk.Text(dialog, font=self.FONTS['mono'], bg=self.COLORS['bg_input'],
                      fg=self.COLORS['text_primary'], relief=tk.FLAT, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert(tk.END, report)
        text.config(state=tk.DISABLED)

        tk.Button(
            dialog,
            text="Close",
            bg=self.COLORS['bg_card'],
            fg=self.COLORS['text_primary'],
            font=self.FONTS['body'],
            relief=tk.FLAT,
            padx=20,
            pady=8,
            cursor='hand2',
            command=dialog.destroy
        ).pack(pady=10)

    def _clear_all(self):
        if messagebox.askyesno("Confirm Clear", "Clear all fire levels and routes?"):
            self.node_fire_levels = {node['id']: 'none' for node in self.engine.nodes}

            self.simulator._initialize_sensors()
            self.simulator.manual_overrides.clear()

            self.route_history.clear()
            self.selected_node = None
            self.alert_sent = False

            sensor_data = self.simulator.get_sensor_data()
            for node_id in sensor_data:
                sensor_data[node_id]['fire_level'] = 'none'
            self.engine.update_weights(sensor_data)

            self.selected_display.config(text="No node selected")
            self.node_info.delete(1.0, tk.END)
            self.node_info.insert(tk.END, "Select a node on the floor plan")
            if self.route_info_text:
                self.route_info_text.delete(1.0, tk.END)
                self.route_info_text.insert(tk.END, "Route information will appear here")
            self.root.title("Smart Building EMS")

            self._log_incident("System", "All hazards cleared", "info")

            self._draw_floor_plan()

    def _log_incident(self, title: str, description: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        event = {
            'time': timestamp,
            'title': title,
            'description': description,
            'level': level
        }

        self.incident_events.insert(0, event)
        if len(self.incident_events) > self.max_incident_events:
            self.incident_events = self.incident_events[:self.max_incident_events]

        self.timeline_text.delete(1.0, tk.END)

        for event in self.incident_events[:20]:
            color = {
                'critical': '#FF1744',
                'warning': '#FFC107',
                'success': '#00C853',
                'info': '#00BCD4',
                'error': '#FF1744'
            }.get(event['level'], '#9BA8B8')

            self.timeline_text.insert(tk.END, f"[{event['time']}] ", 'time')
            self.timeline_text.insert(tk.END, f"{event['description']}\n", 'desc')

        self.timeline_text.tag_config('time', foreground='#6A7A8A')
        self.timeline_text.tag_config('desc', foreground='#E8EDF2')

    def _on_close(self):
        if messagebox.askokcancel("Quit", "Exit Smart Building EMS?"):
            self.running = False
            self.simulator.stop()
            self.root.destroy()


def main():
    os.makedirs("data", exist_ok=True)

    if not os.path.exists("data/pushbullet_config.json"):
        from src.pushbullet_notifier import PushbulletNotifier
        PushbulletNotifier()

    root = tk.Tk()
    app = ProfessionalDashboard(root)
    root.mainloop()


if __name__ == "__main__":
    main()