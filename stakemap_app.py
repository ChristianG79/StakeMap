import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser, font as tkfont
import json
import random
import math
import os
import sys
import logging
import colorsys

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from mpl_toolkits.mplot3d import Axes3D

from i18n import I18n


VIEWS = ["Spherical", "3D Scatter", "2D Matrix"]
SETTINGS_FILE = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "StakeMap", "settings.json",
)


def _random_color():
    h = random.random()
    s = 0.55 + random.random() * 0.35
    v = 0.65 + random.random() * 0.35
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"


class StakeMapApp:
    def __init__(self):
        self.root = tk.Tk()
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(family="Segoe UI", size=10)
        self.root.option_add("*Font", default_font)
        self.i18n = I18n("en")
        self.nodes = []
        self.connections = []
        self.selected_node = None
        self.current_view = "Spherical"
        self.filepath = None
        self.project_name = ""
        self.categories = {}
        self.settings = self._load_settings()
        self._setup_logging()

        self.root.title(self.i18n.t("app_title"))
        self.root.state("zoomed")
        self.root.minsize(1000, 600)

        if self.settings.get("language"):
            self.i18n.set_language(self.settings["language"])

        self._build_menu()
        self._build_ui()
        self._update_plot()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Persistent settings ───────────────────────────────
    def _load_settings(self):
        default = {"language": "en", "log_level": "INFO"}
        try:
            os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    return {**default, **json.load(f)}
        except Exception:
            pass
        return dict(default)

    def _save_settings(self):
        try:
            os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _setup_logging(self):
        if getattr(sys, "frozen", False):
            log_dir = os.path.dirname(sys.executable)
        else:
            log_dir = os.getcwd()
        log_path = os.path.join(log_dir, "stakemap.log")
        level_name = self.settings.get("log_level", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)
        logging.basicConfig(
            filename=log_path,
            level=level,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            force=True,
        )
        logging.info(f"Logging started (level={level_name})")

    def _cat_names(self):
        return sorted(self.categories.keys())

    def _cat_color(self, name):
        cat = self.categories.get(name)
        if cat:
            return cat["color"]
        return "#888888"

    def _cat_radius(self, name):
        names = self._cat_names()
        try:
            idx = names.index(name)
            return 1.0 + idx * 0.8
        except ValueError:
            return 3.0

    def _ensure_category(self, name):
        if not name:
            return
        if name not in self.categories:
            self.categories[name] = {"color": _random_color()}

    # ── Menu ──────────────────────────────────────────────
    def _build_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_m = tk.Menu(menubar, tearoff=0)
        file_m.add_command(label=self.i18n.t("menu_new_project"), command=self._new_project, accelerator="Ctrl+N")
        file_m.add_command(label=self.i18n.t("menu_open_project"), command=self._open_file, accelerator="Ctrl+O")
        file_m.add_command(label=self.i18n.t("menu_save"), command=self._save_file, accelerator="Ctrl+S")
        file_m.add_command(label=self.i18n.t("menu_save_as"), command=self._save_as_file)
        file_m.add_separator()
        export_m = tk.Menu(file_m, tearoff=0)
        export_m.add_command(label=self.i18n.t("menu_export_png"), command=lambda: self._export_image("png"))
        export_m.add_command(label=self.i18n.t("menu_export_jpg"), command=lambda: self._export_image("jpg"))
        export_m.add_command(label=self.i18n.t("menu_export_pdf"), command=lambda: self._export_image("pdf"))
        export_m.add_separator()
        export_m.add_command(label=self.i18n.t("menu_export_glb"), command=self._export_glb)
        export_m.add_separator()
        export_m.add_command(label=self.i18n.t("menu_export_mp4"), command=self._export_mp4)
        file_m.add_cascade(label=self.i18n.t("menu_export"), menu=export_m)
        file_m.add_separator()
        file_m.add_command(label=self.i18n.t("exit"), command=self.root.quit)
        menubar.add_cascade(label=self.i18n.t("file"), menu=file_m)

        self.root.bind_all("<Control-n>", lambda e: self._new_project())
        self.root.bind_all("<Control-o>", lambda e: self._open_file())
        self.root.bind_all("<Control-s>", lambda e: self._save_file())

        settings_m = tk.Menu(menubar, tearoff=0)
        settings_m.add_command(label=self.i18n.t("menu_manage_categories"), command=self._show_categories_dialog)
        settings_m.add_separator()
        lang_m = tk.Menu(settings_m, tearoff=0)
        lang_m.add_command(label=self.i18n.t("lang_en"), command=lambda: self._set_language("en"))
        lang_m.add_command(label=self.i18n.t("lang_de"), command=lambda: self._set_language("de"))
        lang_m.add_command(label=self.i18n.t("lang_fr"), command=lambda: self._set_language("fr"))
        lang_m.add_command(label=self.i18n.t("lang_it"), command=lambda: self._set_language("it"))
        settings_m.add_cascade(label=self.i18n.t("language"), menu=lang_m)
        settings_m.add_separator()
        log_m = tk.Menu(settings_m, tearoff=0)
        self._log_level_var = tk.StringVar(value=self.settings.get("log_level", "INFO"))
        for lvl in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            log_m.add_radiobutton(label=self.i18n.t("log_level_" + lvl.lower()), variable=self._log_level_var, value=lvl,
                                  command=lambda v=lvl: self._set_log_level(v))
        settings_m.add_cascade(label=self.i18n.t("menu_logging_level"), menu=log_m)
        menubar.add_cascade(label=self.i18n.t("settings"), menu=settings_m)

        help_m = tk.Menu(menubar, tearoff=0)
        help_m.add_command(label=self.i18n.t("about"), command=self._show_about)
        menubar.add_cascade(label=self.i18n.t("help"), menu=help_m)

    # ── Categories dialog ─────────────────────────────────
    def _show_categories_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title(self.i18n.t("cat_dialog_title"))
        dlg.geometry("420x350")
        dlg.transient(self.root)
        dlg.grab_set()

        frame = ttk.Frame(dlg, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        listbox = tk.Listbox(frame, height=10)
        listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        btn_row = ttk.Frame(frame)
        btn_row.pack(fill=tk.X)

        def refresh():
            listbox.delete(0, tk.END)
            for name in self._cat_names():
                color = self._cat_color(name)
                listbox.insert(tk.END, f"{name}  {color}")

        refresh()

        def add_cat():
            name = tk.simpledialog.askstring(self.i18n.t("cat_add_title"), self.i18n.t("cat_add_prompt"), parent=dlg)
            if name and name.strip():
                self._ensure_category(name.strip())
                refresh()
                self._refresh_cat_cb()

        def remove_cat():
            sel = listbox.curselection()
            if not sel:
                return
            name = self._cat_names()[sel[0]]
            if messagebox.askyesno(self.i18n.t("cat_remove_title"), self.i18n.t("cat_remove_confirm", name=name), parent=dlg):
                if name in self.categories:
                    del self.categories[name]
                    refresh()
                    self._refresh_cat_cb()

        def pick_color():
            sel = listbox.curselection()
            if not sel:
                return
            name = self._cat_names()[sel[0]]
            current = self.categories[name]["color"]
            rgb, hex_ = colorchooser.askcolor(current, title=self.i18n.t("cat_color_title", name=name), parent=dlg)
            if hex_:
                self.categories[name]["color"] = hex_
                refresh()
                self._update_plot()

        ttk.Button(btn_row, text=self.i18n.t("cat_add_btn"), command=add_cat).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text=self.i18n.t("cat_remove_btn"), command=remove_cat).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text=self.i18n.t("cat_color_btn"), command=pick_color).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text=self.i18n.t("cat_close_btn"), command=dlg.destroy).pack(side=tk.RIGHT, padx=2)

    def _refresh_cat_cb(self):
        names = self._cat_names()
        if hasattr(self, "cat_var"):
            self.cat_cb["values"] = names
            if not self.cat_var.get() and names:
                self.cat_var.set(names[0])

    # ── Main UI layout ────────────────────────────────────
    def _build_ui(self):
        bottom = ttk.Frame(self.root)
        bottom.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(bottom, text=self.i18n.t("exit"), command=self.root.quit).pack(
            side=tk.RIGHT, padx=10, pady=4)

        self.paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)

        self.left_frame = ttk.Frame(self.paned, width=380)
        self.paned.add(self.left_frame, weight=0)

        self.right_frame = ttk.Frame(self.paned)
        self.paned.add(self.right_frame, weight=1)

        self._build_control_panel()
        self._build_plot()

    def _build_control_panel(self):
        px = 10
        py = 4

        notebook = ttk.Notebook(self.left_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        general = ttk.Frame(notebook)
        nodes_tab = ttk.Frame(notebook)
        notebook.add(general, text=self.i18n.t("tab_general"))
        notebook.add(nodes_tab, text=self.i18n.t("tab_nodes"))

        # ═══════════════════════════════════════════════════════
        # General tab
        # ═══════════════════════════════════════════════════════
        ttk.Label(
            general,
            text=self.i18n.t("stakeholder_map"),
            font=("Segoe UI", 14, "bold"),
        ).pack(pady=(10, 2), padx=px, anchor=tk.W)

        proj_row = ttk.Frame(general)
        proj_row.pack(fill=tk.X, padx=px, pady=(0, 2))
        ttk.Label(proj_row, text=self.i18n.t("project_label")).pack(side=tk.LEFT)
        self.proj_var = tk.StringVar(value=self.project_name)
        proj_entry = ttk.Entry(proj_row, textvariable=self.proj_var, state="readonly")
        proj_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        self.new_project_btn = ttk.Button(general, text=self.i18n.t("button_new_project"),
                                          command=self._new_project)
        self.new_project_btn.pack(fill=tk.X, padx=px, pady=(0, py))

        ttk.Separator(general, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=px, pady=py)

        # ── View selector ──
        view_f = ttk.LabelFrame(general, text=self.i18n.t("view_label"))
        view_f.pack(fill=tk.X, padx=px, pady=py)
        self.view_var = tk.StringVar(value=self.current_view)
        view_cb = ttk.Combobox(view_f, textvariable=self.view_var, values=VIEWS, state="readonly")
        view_cb.pack(fill=tk.X, padx=px, pady=py)
        self.view_var.trace_add("write", lambda *a: self._on_view_changed())

        # ── Add Node form ──
        add_f = ttk.LabelFrame(general, text=self.i18n.t("add_node"))
        add_f.pack(fill=tk.X, padx=px, pady=py)

        ttk.Label(add_f, text=self.i18n.t("name")).pack(padx=px, pady=py, anchor=tk.W)
        self.name_var = tk.StringVar()
        ttk.Entry(add_f, textvariable=self.name_var).pack(fill=tk.X, padx=px, pady=py)

        ttk.Label(add_f, text=self.i18n.t("category")).pack(padx=px, pady=py, anchor=tk.W)
        self.cat_var = tk.StringVar()
        cat_names = self._cat_names()
        self.cat_cb = ttk.Combobox(add_f, textvariable=self.cat_var, values=cat_names)
        self.cat_cb.pack(fill=tk.X, padx=px, pady=py)
        if cat_names:
            self.cat_var.set(cat_names[0])

        ttk.Label(add_f, text=self.i18n.t("influence")).pack(padx=px, pady=py, anchor=tk.W)
        self.inf_var = tk.IntVar(value=5)
        ttk.Scale(add_f, from_=1, to=10, variable=self.inf_var, orient=tk.HORIZONTAL).pack(
            fill=tk.X, padx=px, pady=py)
        self.inf_lbl = ttk.Label(add_f, text="5")
        self.inf_lbl.pack(padx=px, pady=py, anchor=tk.E)
        self.inf_var.trace_add("write", lambda *a: self.inf_lbl.config(text=str(self.inf_var.get())))

        ttk.Label(add_f, text=self.i18n.t("interest")).pack(padx=px, pady=py, anchor=tk.W)
        self.int_var = tk.IntVar(value=5)
        ttk.Scale(add_f, from_=1, to=10, variable=self.int_var, orient=tk.HORIZONTAL).pack(
            fill=tk.X, padx=px, pady=py)
        self.int_lbl = ttk.Label(add_f, text="5")
        self.int_lbl.pack(padx=px, pady=py, anchor=tk.E)
        self.int_var.trace_add("write", lambda *a: self.int_lbl.config(text=str(self.int_var.get())))

        ttk.Button(add_f, text=self.i18n.t("add"), command=self._add_node).pack(
            fill=tk.X, padx=px, pady=(5, 10))

        # ── Connections ──
        conn_f = ttk.LabelFrame(general, text=self.i18n.t("connections_label"))
        conn_f.pack(fill=tk.X, padx=px, pady=py)

        ttk.Label(conn_f, text=self.i18n.t("source_label")).pack(padx=px, pady=(4, 0), anchor=tk.W)
        self.src_var = tk.StringVar()
        self.src_cb = ttk.Combobox(conn_f, textvariable=self.src_var, state="readonly")
        self.src_cb.pack(fill=tk.X, padx=px, pady=py)

        ttk.Label(conn_f, text=self.i18n.t("target_label")).pack(padx=px, pady=(0, 0), anchor=tk.W)
        self.tgt_var = tk.StringVar()
        self.tgt_cb = ttk.Combobox(conn_f, textvariable=self.tgt_var, state="readonly")
        self.tgt_cb.pack(fill=tk.X, padx=px, pady=py)

        ttk.Label(conn_f, text=self.i18n.t("priority_label")).pack(padx=px, pady=(0, 0), anchor=tk.W)
        prio_frame = ttk.Frame(conn_f)
        prio_frame.pack(fill=tk.X, padx=px, pady=py)
        self.prio_var = tk.IntVar(value=3)
        prio_scale = ttk.Scale(prio_frame, from_=1, to=5, variable=self.prio_var,
                               orient=tk.HORIZONTAL,
                               command=lambda v: self.prio_lbl.config(text=str(int(float(v)))))
        prio_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.prio_lbl = ttk.Label(prio_frame, text="3", width=3)
        self.prio_lbl.pack(side=tk.RIGHT, padx=(4, 0))

        ttk.Button(conn_f, text=self.i18n.t("button_connect"), command=self._add_connection).pack(
            fill=tk.X, padx=px, pady=(0, 4))

        self.conn_listbox = tk.Listbox(conn_f, height=4)
        self.conn_listbox.pack(fill=tk.X, padx=px, pady=py)
        self.conn_listbox.bind("<Delete>", lambda e: self._remove_connection())

        ttk.Button(conn_f, text=self.i18n.t("button_remove_connection"), command=self._remove_connection).pack(
            fill=tk.X, padx=px, pady=(0, 8))

        self._refresh_connection_cbs()
        self._refresh_connections_list()

        ttk.Separator(general, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=px, pady=py)
        ttk.Button(general, text=self.i18n.t("exit"), command=self.root.quit).pack(
            fill=tk.X, padx=px, pady=(2, 8))

        # ═══════════════════════════════════════════════════════
        # Nodes tab
        # ═══════════════════════════════════════════════════════
        list_f = ttk.LabelFrame(nodes_tab, text=self.i18n.t("nodes"))
        list_f.pack(fill=tk.BOTH, expand=True, padx=px, pady=py)

        cols = ("name", "category", "influence", "interest")
        self.tree = ttk.Treeview(list_f, columns=cols, show="headings", height=8)
        self.tree.heading("name", text=self.i18n.t("name"))
        self.tree.heading("category", text=self.i18n.t("category"))
        self.tree.heading("influence", text=self.i18n.t("influence"))
        self.tree.heading("interest", text=self.i18n.t("interest"))
        self.tree.column("name", width=110)
        self.tree.column("category", width=80)
        self.tree.column("influence", width=55)
        self.tree.column("interest", width=55)

        vsb = ttk.Scrollbar(list_f, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=5, padx=(5, 0))
        vsb.pack(side=tk.RIGHT, fill=tk.Y, pady=5, padx=(0, 5))

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", self._on_cell_edit)
        self.tree.bind("<Delete>", lambda e: self._delete_node())

        btn_row = ttk.Frame(list_f)
        btn_row.pack(fill=tk.X, pady=(0, 5), padx=5)
        ttk.Button(btn_row, text=self.i18n.t("delete_selected"),
                   command=self._delete_node).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(btn_row, text=self.i18n.t("button_edit"), command=self._edit_node).pack(side=tk.LEFT)

    # ── Plot area ─────────────────────────────────────────
    def _build_plot(self):
        self.plot_frame = ttk.Frame(self.right_frame)
        self.plot_frame.pack(fill=tk.BOTH, expand=True)
        self._create_plot_widgets()

    def _create_plot_widgets(self):
        for w in self.plot_frame.winfo_children():
            w.destroy()

        self.fig = Figure(figsize=(8, 6), dpi=100)
        if self.current_view in ("3D Scatter", "Spherical"):
            self.ax = self.fig.add_subplot(111, projection="3d")
        else:
            self.ax = self.fig.add_subplot(111)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
        self.toolbar.update()
        self.toolbar.pack(side=tk.BOTTOM, fill=tk.X)

    # ── View switching ────────────────────────────────────
    def _on_view_changed(self):
        new_view = self.view_var.get()
        if new_view == self.current_view:
            return
        self.current_view = new_view
        self._create_plot_widgets()
        self._update_plot()

    # ── Node operations ───────────────────────────────────
    def _add_node(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning(self.i18n.t("warning"), self.i18n.t("name_required"))
            return
        if any(n["name"] == name for n in self.nodes):
            messagebox.showwarning(self.i18n.t("warning"), self.i18n.t("name_exists"))
            return

        cat = self.cat_var.get().strip()
        if not cat:
            messagebox.showwarning(self.i18n.t("warning"), self.i18n.t("category_required"))
            return

        self._ensure_category(cat)

        inf = self.inf_var.get()
        interest = self.int_var.get()

        x = (interest - 1) / 9 * 8 - 4
        y = (inf - 1) / 9 * 8 - 4
        z = random.uniform(-3, 3)

        self.nodes.append({
            "name": name,
            "category": cat,
            "influence": inf,
            "interest": interest,
            "x": x,
            "y": y,
            "z": z,
            "color": self._cat_color(cat),
        })

        self._refresh_tree()
        self._refresh_connection_cbs()
        self._update_plot()
        self._auto_save()

        self.name_var.set("")
        self.inf_var.set(5)
        self.int_var.set(5)

    def _delete_node(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning(self.i18n.t("warning"), self.i18n.t("select_node"))
            return
        name = self.tree.item(sel[0])["values"][0]
        self.nodes = [n for n in self.nodes if n["name"] != name]
        self.connections = [c for c in self.connections
                            if c["source"] != name and c["target"] != name]
        self._refresh_tree()
        self._refresh_connection_cbs()
        self._refresh_connections_list()
        self._update_plot()
        self._auto_save()

    def _edit_node(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning(self.i18n.t("warning"), self.i18n.t("select_node"))
            return
        vals = self.tree.item(sel[0])["values"]
        orig_name = vals[0]
        node = next((n for n in self.nodes if n["name"] == orig_name), None)
        if node is None:
            return
        dlg = tk.Toplevel(self.root)
        dlg.title(self.i18n.t("edit_title", name=orig_name))
        dlg.geometry("300x250")
        dlg.transient(self.root)
        dlg.grab_set()
        f = ttk.Frame(dlg, padding=10)
        f.pack(fill=tk.BOTH, expand=True)
        ttk.Label(f, text=self.i18n.t("edit_name")).pack(anchor=tk.W)
        name_var = tk.StringVar(value=node["name"])
        ttk.Entry(f, textvariable=name_var).pack(fill=tk.X, pady=(0, 6))
        ttk.Label(f, text=self.i18n.t("edit_category")).pack(anchor=tk.W)
        cat_var = tk.StringVar(value=node["category"])
        ttk.Combobox(f, textvariable=cat_var, values=self._cat_names()).pack(
            fill=tk.X, pady=(0, 6))
        ttk.Label(f, text=self.i18n.t("edit_influence")).pack(anchor=tk.W)
        inf_var = tk.IntVar(value=node["influence"])
        ttk.Scale(f, from_=1, to=10, variable=inf_var, orient=tk.HORIZONTAL).pack(
            fill=tk.X, pady=(0, 2))
        inf_lbl = ttk.Label(f, text=str(inf_var.get()))
        inf_lbl.pack(anchor=tk.E)
        inf_var.trace_add("write", lambda *a: inf_lbl.config(text=str(inf_var.get())))
        ttk.Label(f, text=self.i18n.t("edit_interest")).pack(anchor=tk.W)
        int_var = tk.IntVar(value=node["interest"])
        ttk.Scale(f, from_=1, to=10, variable=int_var, orient=tk.HORIZONTAL).pack(
            fill=tk.X, pady=(0, 2))
        int_lbl = ttk.Label(f, text=str(int_var.get()))
        int_lbl.pack(anchor=tk.E)
        int_var.trace_add("write", lambda *a: int_lbl.config(text=str(int_var.get())))
        def save():
            n = name_var.get().strip()
            cat = cat_var.get().strip()
            if not n or not cat:
                return
            if n != orig_name and any(x["name"] == n for x in self.nodes):
                messagebox.showwarning(self.i18n.t("warning"), self.i18n.t("name_exists"), parent=dlg)
                return
            self._ensure_category(cat)
            old_name = node["name"]
            node["name"] = n
            node["category"] = cat
            node["influence"] = inf_var.get()
            node["interest"] = int_var.get()
            node["x"] = (node["interest"] - 1) / 9 * 8 - 4
            node["y"] = (node["influence"] - 1) / 9 * 8 - 4
            node["color"] = self._cat_color(cat)
            if n != old_name:
                for c in self.connections:
                    if c["source"] == old_name:
                        c["source"] = n
                    if c["target"] == old_name:
                        c["target"] = n
            self._refresh_tree()
            self._refresh_connection_cbs()
            self._refresh_connections_list()
            self._update_plot()
            self._auto_save()
            dlg.destroy()
        ttk.Button(f, text=self.i18n.t("edit_save"), command=save).pack(pady=(8, 0))

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        self.selected_node = self.tree.item(sel[0])["values"][0] if sel else None

    def _on_cell_edit(self, event):
        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not item or not column:
            return
        col_idx = int(column.replace("#", "")) - 1
        fields = ("name", "category", "influence", "interest")
        if col_idx < 0 or col_idx >= len(fields):
            return
        field = fields[col_idx]
        current = self.tree.item(item)["values"][col_idx]
        name = self.tree.item(item)["values"][0]

        x, y, w, h = self.tree.bbox(item, column)

        if field == "category":
            entry = ttk.Combobox(self.tree, values=self._cat_names())
        else:
            entry = ttk.Entry(self.tree)
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, str(current))
        entry.select_range(0, tk.END)
        entry.focus()

        def commit(_e=None):
            new_value = entry.get().strip()
            entry.destroy()
            node = next((n for n in self.nodes if n["name"] == name), None)
            if node is None:
                return

            if field in ("influence", "interest"):
                try:
                    new_value = int(float(new_value))
                    if not 1 <= new_value <= 10:
                        return
                except ValueError:
                    return

            if field == "name":
                if not new_value:
                    return
                if new_value != name and any(n["name"] == new_value for n in self.nodes):
                    return
                for c in self.connections:
                    if c["source"] == name:
                        c["source"] = new_value
                    if c["target"] == name:
                        c["target"] = new_value

            if field == "category" and new_value:
                self._ensure_category(new_value)

            node[field] = new_value
            if field in ("influence", "interest"):
                node["x"] = (node["interest"] - 1) / 9 * 8 - 4
                node["y"] = (node["influence"] - 1) / 9 * 8 - 4
            if field in ("category",):
                node["color"] = self._cat_color(node["category"])

            self._refresh_tree()
            self._refresh_connection_cbs()
            self._update_plot()
            self._auto_save()

        entry.bind("<Return>", commit)
        entry.bind("<Escape>", lambda e: entry.destroy())
        entry.bind("<FocusOut>", commit)

    def _refresh_tree(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for n in self.nodes:
            self.tree.insert("", tk.END, values=(
                n["name"], n["category"], str(n["influence"]), str(n["interest"])))

    # ── Connection operations ─────────────────────────────
    def _refresh_connection_cbs(self):
        pn = self.project_name or "Project"
        names = [n["name"] for n in self.nodes]
        if pn not in names:
            names.append(pn)
        self.src_cb["values"] = names
        self.tgt_cb["values"] = names
        if names:
            if not self.src_var.get() or self.src_var.get() not in names:
                self.src_var.set(names[0] if names else "")
            if not self.tgt_var.get() or self.tgt_var.get() not in names:
                self.tgt_var.set(names[-1] if len(names) > 1 else names[0] if names else "")
        else:
            self.src_var.set("")
            self.tgt_var.set("")

    def _refresh_connections_list(self):
        self.conn_listbox.delete(0, tk.END)
        for c in self.connections:
            self.conn_listbox.insert(
                tk.END, f"{c['source']} \u2192 {c['target']}  [{c['priority']}]")

    def _add_connection(self):
        src = self.src_var.get()
        tgt = self.tgt_var.get()
        prio = self.prio_var.get()
        if not src or not tgt:
            return
        if src == tgt:
            messagebox.showwarning(self.i18n.t("warning"), self.i18n.t("cannot_connect_self"))
            return
        if any((c["source"] == src and c["target"] == tgt) or
               (c["source"] == tgt and c["target"] == src) for c in self.connections):
            return
        self.connections.append({"source": src, "target": tgt, "priority": prio})
        self._refresh_connections_list()
        self._update_plot()
        self._auto_save()

    def _remove_connection(self):
        sel = self.conn_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self.connections):
            self.connections.pop(idx)
            self._refresh_connections_list()
            self._update_plot()
            self._auto_save()

    # ── Plot renderers ────────────────────────────────────
    def _update_plot(self):
        if self.current_view == "3D Scatter":
            self._render_view_3d()
        elif self.current_view == "2D Matrix":
            self._render_view_2d()
        elif self.current_view == "Spherical":
            self._render_view_spherical()

    def _render_view_3d(self):
        self.ax.clear()
        self.ax.set_xlabel("Interest")
        self.ax.set_ylabel("Influence")
        self.ax.set_zlabel("Engagement")
        self.ax.set_title(self.i18n.t("stakeholder_map"))

        if not self.nodes:
            self.ax.set_xlim(-5, 5)
            self.ax.set_ylim(-5, 5)
            self.ax.set_zlim(-4, 4)
            self.canvas.draw()
            return

        self.ax.scatter(0, 0, 0, c=["#eeeeee"], s=180, edgecolors="#555", linewidth=2, zorder=10)
        self.ax.text(0, 0, 0.4, self.project_name, fontsize=10, ha="center", va="center",
                     weight="bold", zorder=11)

        for n in self.nodes:
            size = max(60, n["influence"] * 35)
            self.ax.scatter(
                n["x"], n["y"], n["z"],
                c=[self._cat_color(n["category"])], s=size, alpha=0.85,
                edgecolors="black", linewidth=0.5)
            self.ax.text(
                n["x"], n["y"], n["z"] + 0.35, n["name"], fontsize=9, ha="center",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.75))

        self._draw_connections_3d(alpha=0.3)
        self.ax.set_xlim(-5, 5)
        self.ax.set_ylim(-5, 5)
        self.ax.set_zlim(-4, 4)
        self.canvas.draw()

    def _render_view_2d(self):
        self.ax.clear()
        self.ax.set_xlabel("Interest")
        self.ax.set_ylabel("Influence")
        self.ax.set_title(self.i18n.t("stakeholder_map"))
        self.ax.set_xlim(0, 11)
        self.ax.set_ylim(0, 11)
        self.ax.set_xticks(range(1, 11))
        self.ax.set_yticks(range(1, 11))

        self.ax.axhline(y=5.5, color="gray", linestyle="--", alpha=0.4)
        self.ax.axvline(x=5.5, color="gray", linestyle="--", alpha=0.4)
        self.ax.text(8, 9.5, "Manage Closely", fontsize=10, ha="center", alpha=0.5, style="italic")
        self.ax.text(2.5, 9.5, "Keep Satisfied", fontsize=10, ha="center", alpha=0.5, style="italic")
        self.ax.text(8, 1.5, "Keep Informed", fontsize=10, ha="center", alpha=0.5, style="italic")
        self.ax.text(2.5, 1.5, "Monitor", fontsize=10, ha="center", alpha=0.5, style="italic")

        self.ax.scatter(5.5, 5.5, c=["#eeeeee"], s=250, edgecolors="#555", linewidth=2, zorder=10)
        self.ax.text(5.5, 5.6, self.project_name, fontsize=10, ha="center", va="center",
                     weight="bold", zorder=11)

        if not self.nodes:
            self.canvas.draw()
            return

        for n in self.nodes:
            size = max(60, n["influence"] * 35)
            self.ax.scatter(
                n["interest"], n["influence"],
                c=[self._cat_color(n["category"])], s=size, alpha=0.85,
                edgecolors="black", linewidth=0.5, zorder=5)
            self.ax.text(
                n["interest"], n["influence"] + 0.3, n["name"], fontsize=9, ha="center",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.75), zorder=6)

        self._draw_connections_2d(alpha=0.4)
        self.canvas.draw()

    def _render_view_spherical(self):
        self.ax.clear()
        self.ax.set_axis_off()
        self.ax.set_title(self.i18n.t("stakeholder_map"))

        if not self.nodes:
            self.ax.set_xlim(-7, 7)
            self.ax.set_ylim(-7, 7)
            self.ax.set_zlim(-4, 4)
            self.canvas.draw()
            return

        cat_groups = {}
        for n in self.nodes:
            cat_groups.setdefault(n["category"], []).append(n)
        sorted_cats = sorted(cat_groups.keys())
        n_cats = len(sorted_cats)

        for i, cat in enumerate(sorted_cats):
            start = i / n_cats * 2 * math.pi
            end = (i + 1) / n_cats * 2 * math.pi
            nodes_in_cat = sorted(cat_groups[cat], key=lambda n: n["interest"])
            for j, n in enumerate(nodes_in_cat):
                angle = start + (j + 0.5) / len(nodes_in_cat) * (end - start)
                r = self._cat_radius(cat)
                z = (n["influence"] - 1) / 9 * 6 - 3
                n["_sx"] = r * math.cos(angle)
                n["_sy"] = r * math.sin(angle)
                n["_sz"] = z

        max_r = max(self._cat_radius(n["category"]) for n in self.nodes) + 0.5

        self._draw_connections_spherical(alpha=0.3)

        self.ax.scatter(0, 0, 0, c=["#eeeeee"], s=250, edgecolors="#555", linewidth=2, zorder=10)
        self.ax.text(0, 0, 0.4, self.project_name, fontsize=10, ha="center", va="center",
                     weight="bold", zorder=11)

        for n in self.nodes:
            size = max(60, n["influence"] * 35)
            self.ax.scatter(
                n["_sx"], n["_sy"], n["_sz"],
                c=[self._cat_color(n["category"])], s=size, alpha=0.85,
                edgecolors="black", linewidth=0.5)
            self.ax.text(
                n["_sx"], n["_sy"], n["_sz"] + 0.35, n["name"], fontsize=9, ha="center",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.75))

        self.ax.set_xlim(-max_r, max_r)
        self.ax.set_ylim(-max_r, max_r)
        self.ax.set_zlim(-4, 4)
        self.canvas.draw()

    # ── Connection drawing helpers ────────────────────────
    @staticmethod
    def _conn_lw(priority):
        return 0.4 + priority * 0.7

    def _node_or_project(self, name, pos3d, pos2d):
        if name == self.project_name or name == "Project":
            return pos3d if pos3d else pos2d
        n = next((x for x in self.nodes if x["name"] == name), None)
        if n is None:
            return None
        return n

    def _draw_connections_3d(self, alpha=0.3):
        for c in self.connections:
            n1 = self._node_or_project(c["source"], (0, 0, 0), None)
            n2 = self._node_or_project(c["target"], (0, 0, 0), None)
            if n1 is None or n2 is None:
                continue
            x1, y1, z1 = n1 if isinstance(n1, tuple) else (n1["x"], n1["y"], n1["z"])
            x2, y2, z2 = n2 if isinstance(n2, tuple) else (n2["x"], n2["y"], n2["z"])
            self.ax.plot([x1, x2], [y1, y2], [z1, z2],
                         color="gray", alpha=alpha,
                         linewidth=self._conn_lw(c["priority"]), linestyle="-")

    def _draw_connections_2d(self, alpha=0.3):
        proj_pos = (5.5, 5.5)
        for c in self.connections:
            n1 = self._node_or_project(c["source"], None, proj_pos)
            n2 = self._node_or_project(c["target"], None, proj_pos)
            if n1 is None or n2 is None:
                continue
            x1, y1 = n1 if isinstance(n1, tuple) else (n1["interest"], n1["influence"])
            x2, y2 = n2 if isinstance(n2, tuple) else (n2["interest"], n2["influence"])
            self.ax.plot([x1, x2], [y1, y2],
                         color="gray", alpha=alpha,
                         linewidth=self._conn_lw(c["priority"]), linestyle="-", zorder=1)

    def _draw_connections_spherical(self, alpha=0.3):
        for c in self.connections:
            n1 = self._node_or_project(c["source"], (0, 0, 0), None)
            n2 = self._node_or_project(c["target"], (0, 0, 0), None)
            if n1 is None or n2 is None:
                continue
            if isinstance(n1, tuple):
                x1, y1, z1 = n1
            elif "_sx" in n1:
                x1, y1, z1 = n1["_sx"], n1["_sy"], n1["_sz"]
            else:
                continue
            if isinstance(n2, tuple):
                x2, y2, z2 = n2
            elif "_sx" in n2:
                x2, y2, z2 = n2["_sx"], n2["_sy"], n2["_sz"]
            else:
                continue
            self.ax.plot([x1, x2], [y1, y2], [z1, z2],
                         color="gray", alpha=alpha,
                         linewidth=self._conn_lw(c["priority"]))

    # ── Project name ──────────────────────────────────────
    def _update_project_display(self):
        self.proj_var.set(self.project_name)
        if self.project_name:
            self.root.title(f"{self.i18n.t('app_title')} - {self.project_name}")
        else:
            self.root.title(self.i18n.t("app_title"))

    def _auto_save(self):
        if self.filepath:
            try:
                with open(self.filepath, "w", encoding="utf-8") as f:
                    json.dump(self._serialize(), f, indent=2, ensure_ascii=False)
            except Exception:
                pass

    def _on_close(self):
        self._auto_save()
        self.root.destroy()

    def _set_project_button(self, active: bool):
        if active:
            self.new_project_btn.config(text=self.i18n.t("button_close_project"), command=self._close_project)
        else:
            self.new_project_btn.config(text=self.i18n.t("button_new_project"), command=self._new_project)

    def _close_project(self):
        if not messagebox.askyesno(self.i18n.t("confirm_close_project_title"), self.i18n.t("confirm_close_project_msg")):
            return
        self.nodes = []
        self.connections = []
        self.categories = {}
        self.filepath = None
        self.project_name = ""
        self._refresh_tree()
        self._refresh_connection_cbs()
        self._refresh_connections_list()
        self._create_plot_widgets()
        self._update_plot()
        self._update_project_display()
        self._set_project_button(False)

    # ── File operations ───────────────────────────────────
    def _serialize(self):
        return {
            "project_name": self.project_name,
            "categories": self.categories,
            "nodes": [{k: v for k, v in n.items() if not k.startswith("_")}
                      for n in self.nodes],
            "connections": self.connections,
            "view": self.current_view,
        }

    def _deserialize(self, data):
        self.nodes = data.get("nodes", [])
        self.project_name = data.get("project_name", "")
        self.categories = data.get("categories", {})
        raw = data.get("connections", [])
        self.connections = []
        for c in raw:
            if isinstance(c, dict):
                self.connections.append({
                    "source": c["source"], "target": c["target"],
                    "priority": c.get("priority", 3)})
            elif isinstance(c, (list, tuple)) and len(c) == 2:
                self.connections.append({"source": c[0], "target": c[1], "priority": 3})
        self.current_view = data.get("view", "Spherical")
        for n in self.nodes:
            self._ensure_category(n.get("category", ""))

    def _new_project(self):
        if self.nodes and not messagebox.askyesno(self.i18n.t("confirm_new_project_title"), self.i18n.t("confirm_new_project_msg")):
            return
        name = tk.simpledialog.askstring(self.i18n.t("new_project_title"), self.i18n.t("new_project_prompt"), parent=self.root)
        if not name or not name.strip():
            return
        name = name.strip()
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[(self.i18n.t("filter_stakemap"), "*.json"), (self.i18n.t("filter_json"), "*.json"),
                       (self.i18n.t("filter_all"), "*.*")])
        if not path:
            return

        self.nodes = []
        self.connections = []
        self.categories = {}
        self.filepath = path
        self.project_name = name
        self.current_view = "Spherical"
        self._write_file(path)
        self._refresh_tree()
        self._refresh_connection_cbs()
        self._refresh_connections_list()
        self._create_plot_widgets()
        self._update_plot()
        self._update_project_display()
        self._set_project_button(True)

    def _open_file(self):
        path = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[(self.i18n.t("filter_stakemap"), "*.json"), (self.i18n.t("filter_json"), "*.json"),
                       (self.i18n.t("filter_all"), "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._deserialize(data)
            self.filepath = path
            if not self.project_name:
                self.project_name = os.path.splitext(os.path.basename(path))[0]
            self.view_var.set(self.current_view)
            self._refresh_cat_cb()
            self._refresh_tree()
            self._refresh_connection_cbs()
            self._refresh_connections_list()
            self._create_plot_widgets()
            self._update_plot()
            self._update_project_display()
            self._set_project_button(True)
        except Exception as e:
            messagebox.showerror(self.i18n.t("export_error"), self.i18n.t("file_open_error", err=e))

    def _save_file(self):
        if self.filepath:
            self._write_file(self.filepath)
        else:
            self._save_as_file()

    def _save_as_file(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[(self.i18n.t("filter_stakemap"), "*.json"), (self.i18n.t("filter_json"), "*.json"),
                       (self.i18n.t("filter_all"), "*.*")])
        if path:
            self.filepath = path
            self._write_file(path)

    def _write_file(self, path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._serialize(), f, indent=2, ensure_ascii=False)
            self._update_project_display()
        except Exception as e:
            messagebox.showerror(self.i18n.t("export_error"), self.i18n.t("file_save_error", err=e))

    # ── Logging ────────────────────────────────────────────
    def _set_log_level(self, level: str):
        self.settings["log_level"] = level
        self._save_settings()
        logging.getLogger().setLevel(getattr(logging, level))
        logging.info(f"Log level changed to {level}")

    # ── Language switching ────────────────────────────────
    def _set_language(self, lang: str):
        self.i18n.set_language(lang)
        self.settings["language"] = lang
        self._save_settings()

        self.root.config(menu=tk.Menu(self.root))
        self._build_menu()

        self.current_view = self.view_var.get() if hasattr(self, "view_var") else "Spherical"

        for w in self.left_frame.winfo_children():
            w.destroy()
        self._build_control_panel()
        self._update_project_display()
        if self.project_name:
            self._set_project_button(True)

        self._update_plot()

    # ── Export ────────────────────────────────────────────
    def _export_image(self, fmt):
        ext = fmt
        if fmt == "jpg":
            ext = "jpeg"
        path = filedialog.asksaveasfilename(
            defaultextension=f".{fmt}",
            filetypes=[(self.i18n.t(f"filter_{fmt}"), f"*.{fmt}"), (self.i18n.t("filter_all"), "*.*")],
        )
        if path:
            try:
                self.fig.savefig(path, format=ext, dpi=200, bbox_inches="tight")
            except Exception as e:
                messagebox.showerror(self.i18n.t("export_error"), str(e))

    def _export_glb(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".glb",
            filetypes=[(self.i18n.t("filter_glb"), "*.glb"), (self.i18n.t("filter_all"), "*.*")],
        )
        if not path:
            return
        try:
            self._write_glb(path)
        except ImportError:
            messagebox.showinfo(
                self.i18n.t("export_glb_title"),
                self.i18n.t("export_glb_msg"),
            )
        except Exception as e:
            messagebox.showerror(self.i18n.t("export_error"), str(e))

    def _export_mp4(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".mp4",
            filetypes=[(self.i18n.t("filter_mp4"), "*.mp4"), (self.i18n.t("filter_all"), "*.*")],
        )
        if not path:
            return
        if self.current_view not in ("Spherical", "3D Scatter"):
            messagebox.showinfo(self.i18n.t("export_mp4_title"),
                                self.i18n.t("export_mp4_3d_required"))
            return
        if not hasattr(self, "ax"):
            messagebox.showinfo(self.i18n.t("export_mp4_title"), self.i18n.t("export_mp4_no_plot"))
            return

        from matplotlib.animation import FFMpegWriter

        orig_azim = self.ax.azim
        orig_elev = self.ax.elev
        try:
            fps = 30
            seconds = 8
            n_frames = fps * seconds
            writer = FFMpegWriter(fps=fps, metadata=dict(artist="StakeMap"), bitrate=5000)

            old_title = self.root.title()
            with writer.saving(self.fig, path, dpi=150):
                for i in range(n_frames):
                    t = i / n_frames
                    angle = 2 * math.pi * t * 2
                    self.ax.view_init(
                        elev=orig_elev + 15 * math.sin(angle),
                        azim=orig_azim + math.degrees(angle),
                    )
                    self.fig.canvas.draw()
                    writer.grab_frame()
                    if i % 10 == 0:
                        pct = int((i + 1) / n_frames * 100)
                        self.root.title(self.i18n.t("export_mp4_progress", pct=pct))

            self.ax.view_init(elev=orig_elev, azim=orig_azim)
            self.fig.canvas.draw_idle()
            self.root.title(old_title)
        except Exception as e:
            try:
                self.ax.view_init(elev=orig_elev, azim=orig_azim)
                self.fig.canvas.draw_idle()
            except Exception:
                pass
            self.root.title(old_title)
            msg = str(e)
            if "ffmpeg" in msg.lower():
                msg = self.i18n.t("export_mp4_no_ffmpeg")
            messagebox.showerror(self.i18n.t("export_error"), msg)
            return

        messagebox.showinfo(self.i18n.t("export_mp4_title"),
                            self.i18n.t("export_mp4_success", path=os.path.basename(path)))

    @staticmethod
    def _glb_label_mesh(text, position, font_size=28):
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np
        import trimesh
        from trimesh.visual import TextureVisuals

        try:
            font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", font_size)
        except Exception:
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()

        temp = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        td = ImageDraw.Draw(temp)
        bbox = td.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0] + 20
        th = bbox[3] - bbox[1] + 12

        img = Image.new("RGBA", (max(tw, 1), max(th, 1)), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        # thin white outline for readability on any background
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                if ox or oy:
                    d.text((8 - bbox[0] + ox, 5 - bbox[1] + oy), text,
                           fill=(255, 255, 255, 255), font=font)
        d.text((8 - bbox[0], 5 - bbox[1]), text, fill=(0, 0, 0, 255),
               font=font)

        scale = 0.008
        w = max(tw * scale, 0.01)
        h = max(th * scale, 0.01)
        plane = trimesh.creation.box((w, h, 0.003))

        plane.visual = TextureVisuals(image=img)

        plane.apply_translation(position + np.array([0.0, 0.0, 0.5]))
        return plane

    def _write_glb(self, path):
        import trimesh
        import numpy as np

        meshes = []

        def _pos(name):
            if name == self.project_name or name == "Project":
                return np.array([0.0, 0.0, 0.0])
            n = next((x for x in self.nodes if x["name"] == name), None)
            if n is None:
                return None
            return np.array([n.get("_sx", n["x"]),
                             n.get("_sy", n["y"]),
                             n.get("_sz", n["z"])])

        # project sphere + label
        c = trimesh.creation.icosphere(subdivisions=2, radius=0.35)
        c.visual.vertex_colors = [230, 230, 230, 255]
        meshes.append(c)
        meshes.append(self._glb_label_mesh(self.project_name, np.array([0.0, 0.0, 0.0]), 34))

        # stakeholder spheres + labels
        for n in self.nodes:
            pos = _pos(n["name"])
            if pos is None:
                continue
            col = self._cat_color(n["category"])
            rgb = [int(col[i:i+2], 16) for i in (1, 3, 5)]
            r = max(0.15, n["influence"] * 0.06)
            s = trimesh.creation.icosphere(subdivisions=2, radius=r)
            s.visual.vertex_colors = [*rgb, 220]
            s.apply_translation(pos)
            meshes.append(s)
            meshes.append(self._glb_label_mesh(n["name"], pos))

        # connection cylinders
        for conn in self.connections:
            p1 = _pos(conn["source"])
            p2 = _pos(conn["target"])
            if p1 is None or p2 is None:
                continue
            diff = p2 - p1
            dist = float(np.linalg.norm(diff))
            if dist < 0.01:
                continue
            cyl = trimesh.creation.cylinder(radius=0.03 * conn.get("priority", 3),
                                            height=dist, sections=8)
            cyl.visual.vertex_colors = [160, 160, 160, 180]
            mid = (p1 + p2) / 2.0
            z = np.array([0.0, 0.0, 1.0])
            direction = diff / dist
            if abs(np.dot(direction, z)) > 0.999:
                z = np.array([0.0, 1.0, 0.0])
            x = np.cross(direction, z)
            x /= np.linalg.norm(x)
            y = np.cross(x, direction)
            rot = np.column_stack([x, y, direction])
            T = np.eye(4)
            T[:3, :3] = rot
            T[:3, 3] = mid
            cyl.apply_transform(T)
            meshes.append(cyl)

        scene = trimesh.Scene(meshes)
        scene.export(path, file_type="glb")

    # ── About ─────────────────────────────────────────────
    def _show_about(self):
        messagebox.showinfo(
            self.i18n.t("about"),
            self.i18n.t("about_text"),
        )

    # ── Run ───────────────────────────────────────────────
    def run(self):
        self.root.mainloop()
