# use tkinter to create a ui to show the graphs
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
import duckdb
import io
from PIL import Image, ImageTk
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator, LogLocator
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import json
import os

DB_PATH = 'brain_stats.duckdb'

class BrainStatsUI:
    def __init__(self, root):
        self.root = root
        self.root.title('Brain Stats Viewer')
        try:
            icon_img = tk.PhotoImage(file='assets/CLOUDCELL-32x32-0.png')
            self.root.iconphoto(True, icon_img)
        except Exception as e:
            try:
                self.root.iconbitmap('assets/CLOUDCELL-32x32.ico')
            except Exception:
                pass  # Ignore icon error if running on Linux/Wayland or missing icon
        self._icon_img = icon_img if 'icon_img' in locals() else None  # Prevent garbage collection
        self.con = duckdb.connect(DB_PATH, read_only=True)
        self.settings_file = 'brain_stats_settings.json'
        self.setup_widgets()
        self.load_settings()
        self.load_studies()
        
        # Save settings when closing the app
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Track window and pane resize events
        self.save_timer_id = None
        self.root.bind("<Configure>", self.on_window_configure)
        self.paned.bind("<ButtonRelease-1>", self.on_sash_release)
    
    def setup_widgets(self):
        # Controls pane (fixed height)
        controls_frame = ttk.Frame(self.root)
        controls_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=1, expand=False)
        controls_frame.pack_propagate(False)
        # Filter for studies (row 0)
        ttk.Label(controls_frame, text="Filter:").grid(row=0, column=0, sticky=tk.W)
        self.filter_var = tk.StringVar()
        self.filter_entry = ttk.Entry(controls_frame, textvariable=self.filter_var, width=20)
        self.filter_entry.grid(row=0, column=1, sticky=tk.W)
        self.filter_var.trace_add('write', self.on_filter_change)

        # Study selector (row 1)
        ttk.Label(controls_frame, text="Study:").grid(row=1, column=0, sticky=tk.W)
        self.study_var = tk.StringVar()
        self.study_cb = ttk.Combobox(controls_frame, textvariable=self.study_var, state='readonly', width=40)
        self.study_cb.grid(row=1, column=1, columnspan=5, sticky=tk.W+tk.E, ipady=0, pady=0)
        self.study_cb.bind('<<ComboboxSelected>>', self.on_study_selected)

        # Type and Tag selectors (row 2)
        ttk.Label(controls_frame, text="Type:").grid(row=2, column=0, sticky=tk.W)
        self.type_var = tk.StringVar(value='scalar')
        self.type_cb = ttk.Combobox(controls_frame, textvariable=self.type_var, state='readonly', values=['scalar', 'image'])
        self.type_cb.grid(row=2, column=1, sticky=tk.W, ipady=0, pady=0)
        self.type_cb.bind('<<ComboboxSelected>>', self.on_type_selected)

        ttk.Label(controls_frame, text="Tag:").grid(row=2, column=2, sticky=tk.W)
        self.tag_var = tk.StringVar()
        self.tag_cb = ttk.Combobox(controls_frame, textvariable=self.tag_var, state='readonly', width=40)
        self.tag_cb.grid(row=2, column=3, columnspan=2, sticky=tk.W+tk.E, ipady=0, pady=0)
        self.tag_cb.bind('<<ComboboxSelected>>', self.on_tag_selected)

        # Log scale checkbox (row 2)
        self.log_scale_var = tk.BooleanVar(value=False)
        self.log_scale_cb = ttk.Checkbutton(controls_frame, text="Log Y", variable=self.log_scale_var, command=self.on_plot_parameter_change)
        self.log_scale_cb.grid(row=2, column=5, sticky=tk.W, ipady=0, pady=0)
        
        # Show dots checkbox
        self.show_dots_var = tk.BooleanVar(value=True)
        self.show_dots_cb = ttk.Checkbutton(controls_frame, text="Show Dots", variable=self.show_dots_var, command=self.on_plot_parameter_change)
        self.show_dots_cb.grid(row=2, column=6, sticky=tk.W, ipady=0, pady=0)
        
        # Horizontal grid lines checkbox
        self.hgrid_var = tk.BooleanVar(value=False)
        self.hgrid_cb = ttk.Checkbutton(controls_frame, text="H-Grid", variable=self.hgrid_var, command=self.on_plot_parameter_change)
        self.hgrid_cb.grid(row=2, column=7, sticky=tk.W, ipady=0, pady=0)
        
        # Vertical grid lines checkbox
        self.vgrid_var = tk.BooleanVar(value=False)
        self.vgrid_cb = ttk.Checkbutton(controls_frame, text="V-Grid", variable=self.vgrid_var, command=self.on_plot_parameter_change)
        self.vgrid_cb.grid(row=2, column=8, sticky=tk.W, ipady=0, pady=0)
        
        # Grid color selection (row 3)
        ttk.Label(controls_frame, text="Grid Color:").grid(row=3, column=0, sticky=tk.W)
        self.grid_color_var = tk.StringVar(value="gray")
        self.grid_color_cb = ttk.Combobox(controls_frame, textvariable=self.grid_color_var, state='readonly', 
                                      values=["gray", "black", "blue", "green", "red", "orange"])
        self.grid_color_cb.grid(row=3, column=1, sticky=tk.W, ipady=0, pady=0)
        self.grid_color_cb.bind('<<ComboboxSelected>>', self.on_plot_parameter_change)
        
        # Line color selection (row 3)
        ttk.Label(controls_frame, text="Line Color:").grid(row=3, column=2, sticky=tk.W)
        self.line_color_var = tk.StringVar(value="blue")
        self.line_color_cb = ttk.Combobox(controls_frame, textvariable=self.line_color_var, state='readonly', 
                                      values=["blue", "black", "red", "green", "orange", "purple"])
        self.line_color_cb.grid(row=3, column=3, sticky=tk.W, ipady=0, pady=0)
        self.line_color_cb.bind('<<ComboboxSelected>>', self.on_plot_parameter_change)

        # Paned window for resizable split
        self.paned = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        self.paned.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        # Top pane: plot area
        self.plot_frame = ttk.Frame(self.paned)
        self.paned.add(self.plot_frame, weight=3)
        self.plot_frame.pack_propagate(False)
        # Bottom pane: image area
        self.image_frame = ttk.Frame(self.paned)
        self.paned.add(self.image_frame, weight=2)
        self.image_frame.pack_propagate(False)
        # For images: image area widgets (grid layout for full expansion)
        self.image_frame.rowconfigure(0, weight=1)
        self.image_frame.rowconfigure(1, weight=0)
        self.image_frame.rowconfigure(2, weight=0)
        self.image_frame.rowconfigure(3, weight=0)
        self.image_frame.columnconfigure(0, weight=1)
        self.image_label = ttk.Label(self.image_frame)
        self.image_label.grid(row=0, column=0, sticky='nsew')
        self.sample_id_label = ttk.Label(self.image_frame, text="")
        self.sample_id_label.grid(row=1, column=0, sticky='ew')
        self.image_nav_frame = ttk.Frame(self.image_frame)
        self.image_nav_frame.grid(row=2, column=0, sticky='ew')
        self.prev_btn = ttk.Button(self.image_nav_frame, text='Previous', command=self.prev_image)
        self.next_btn = ttk.Button(self.image_nav_frame, text='Next', command=self.next_image)
        self.prev_btn.pack(side=tk.LEFT)
        self.next_btn.pack(side=tk.LEFT)
        # Add slider for image navigation
        self.image_slider = tk.Scale(self.image_frame, from_=0, to=0, orient=tk.HORIZONTAL, showvalue=0, command=self.on_slider_move)
        self.image_slider.grid(row=3, column=0, sticky='ew', pady=5)
        self.img_idx = 0
        self.images = []
        # Do not destroy image_label or image_nav_frame, only update their content
        self.hide_image_widgets()

    def load_studies(self):
        self._all_studies = [row[0] for row in self.con.execute("SELECT DISTINCT study FROM scalars UNION SELECT DISTINCT study FROM images").fetchall()]
        self._all_studies = sorted(self._all_studies)
        self.update_study_list()

    def on_filter_change(self, *args):
        self.update_study_list()

    def update_study_list(self):
        filter_text = self.filter_var.get().lower()
        cursor_pos = self.filter_entry.index(tk.INSERT)
        
        if filter_text:
            filtered = [s for s in self._all_studies if filter_text in s.lower()]
        else:
            filtered = self._all_studies
            
        self.study_cb['values'] = filtered
        
        # Try to maintain current selection if it's still in the filtered list
        current_study = self.study_var.get()
        if filtered:
            if current_study not in filtered:
                # Check if we have a saved study to restore
                if hasattr(self, 'last_settings') and self.last_settings['last_study'] in filtered:
                    self.study_var.set(self.last_settings['last_study'])
                    # Also restore type if possible
                    if self.last_settings['last_type'] in ['scalar', 'image']:
                        self.type_var.set(self.last_settings['last_type'])
                else:
                    self.study_cb.current(0)
                self.on_study_selected()
        else:
            self.study_var.set('')
            self.tag_cb['values'] = []
        # Restore focus and cursor position after update
        def refocus():
            self.filter_entry.focus_set()
            self.filter_entry.icursor(cursor_pos)
        self.root.after(1, refocus)

    def on_study_selected(self, event=None):
        study = self.study_var.get()
        self.load_tags(study, self.type_var.get())

    def on_type_selected(self, event=None):
        study = self.study_var.get()
        self.load_tags(study, self.type_var.get())
        if self.type_var.get() == 'scalar':
            self.show_scalar_plot()

    def load_tags(self, study, value_type):
        if not study:
            return
        if value_type == 'scalar':
            tags = [row[0] for row in self.con.execute("SELECT DISTINCT tag FROM scalars WHERE study=?", [study]).fetchall()]
        else:
            tags = [row[0] for row in self.con.execute("SELECT DISTINCT tag FROM images WHERE study=?", [study]).fetchall()]
        tags = sorted(tags)
        self.tag_cb['values'] = tags
        
        if tags:
            # Try to restore saved tag if available
            if hasattr(self, 'last_settings') and self.last_settings['last_tag'] in tags:
                self.tag_var.set(self.last_settings['last_tag'])
            else:
                self.tag_cb.current(0)
            self.on_tag_selected()
        else:
            # No tags available for this study/type
            self.tag_var.set('')
            if value_type == 'scalar':
                # Clear any existing plot
                if hasattr(self, 'scalar_canvas'):
                    self.scalar_canvas.get_tk_widget().pack_forget()
            else:
                # Clear any existing image
                self.images = []
                self.img_idx = 0
                self.hide_image_widgets()

    def on_tag_selected(self, event=None):
        if self.type_var.get() == 'scalar':
            self.show_scalar_plot()
        else:
            self.load_images()
            self.show_image()

    def on_plot_parameter_change(self, event=None):
        """Unified handler for any plot parameter change (log scale, dots, grid, colors)"""
        if self.type_var.get() == 'scalar':
            self.show_scalar_plot()
        self.save_settings()
        
    def save_settings(self):
        """Save current settings to a JSON file"""
        # Get window geometry
        geometry = self.root.geometry()
        # Get pane sash position
        try:
            sash_pos = self.paned.sashpos(0)
            print(f"Saving sash position: {sash_pos}")
        except Exception as e:
            print(f"Could not get sash position: {e}")
            sash_pos = 0
            
        settings = {
            # UI control settings
            'log_scale': self.log_scale_var.get(),
            'show_dots': self.show_dots_var.get(),
            'h_grid': self.hgrid_var.get(),
            'v_grid': self.vgrid_var.get(),
            'grid_color': self.grid_color_var.get(),
            'line_color': self.line_color_var.get(),
            
            # Last viewed data
            'last_study': self.study_var.get() if hasattr(self, 'study_var') else '',
            'last_type': self.type_var.get() if hasattr(self, 'type_var') else '',
            'last_tag': self.tag_var.get() if hasattr(self, 'tag_var') else '',
            
            # Window layout
            'window_geometry': geometry,
            'pane_sash_position': sash_pos
        }
        
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
            print(f"Settings saved to {self.settings_file}")
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def load_settings(self):
        """Load settings from JSON file if it exists"""
        if not os.path.exists(self.settings_file):
            print(f"No settings file found at {self.settings_file}")
            return
            
        try:
            with open(self.settings_file, 'r') as f:
                settings = json.load(f)
                
            # Apply loaded settings for UI controls
            if 'log_scale' in settings:
                self.log_scale_var.set(settings['log_scale'])
            if 'show_dots' in settings:
                self.show_dots_var.set(settings['show_dots'])
            if 'h_grid' in settings:
                self.hgrid_var.set(settings['h_grid'])
            if 'v_grid' in settings:
                self.vgrid_var.set(settings['v_grid'])
            if 'grid_color' in settings and settings['grid_color'] in self.grid_color_cb['values']:
                self.grid_color_var.set(settings['grid_color'])
            if 'line_color' in settings and settings['line_color'] in self.line_color_cb['values']:
                self.line_color_var.set(settings['line_color'])
                
            # We'll handle study/type/tag selection after loading studies
            self.last_settings = {
                'last_study': settings.get('last_study', ''),
                'last_type': settings.get('last_type', ''),
                'last_tag': settings.get('last_tag', '')
            }
            
            # Apply window layout settings after a short delay to ensure widgets are ready
            def apply_layout():
                # Set window geometry
                if 'window_geometry' in settings:
                    try:
                        self.root.geometry(settings['window_geometry'])
                    except Exception as e:
                        print(f"Could not restore window geometry: {e}")
                
                # Set pane sash position
                if 'pane_sash_position' in settings:
                    try:
                        sash_pos = int(settings['pane_sash_position'])
                        print(f"Restoring sash position to: {sash_pos}")
                        self.paned.sashpos(0, sash_pos)
                    except Exception as e:
                        print(f"Could not restore pane positions: {e}")
            
            # Apply layout after a longer delay to ensure widgets are fully ready
            self.root.after(300, apply_layout)
                
            print(f"Settings loaded from {self.settings_file}")
        except Exception as e:
            print(f"Error loading settings: {e}")
    
    def on_window_configure(self, event):
        """Called when window is resized"""
        # Only respond to root window configure events, not child widgets
        if event.widget == self.root:
            self.debounced_save()
    
    def on_sash_release(self, event):
        """Called when pane sash is released after dragging"""
        self.debounced_save()
    
    def debounced_save(self):
        """Save settings with debouncing to prevent excessive saves"""
        # Cancel any pending save
        if self.save_timer_id:
            self.root.after_cancel(self.save_timer_id)
        
        # Schedule a new save after a short delay
        self.save_timer_id = self.root.after(500, self.save_settings)
    
    def on_close(self):
        """Save settings when closing the app"""
        # Cancel any pending save
        if self.save_timer_id:
            self.root.after_cancel(self.save_timer_id)
        # Save immediately
        self.save_settings()
        self.root.destroy()

    def show_scalar_plot(self):
        self.hide_image_widgets()
        # Remove previous matplotlib canvas if present
        if hasattr(self, 'scalar_canvas') and self.scalar_canvas is not None:
            self.scalar_canvas.get_tk_widget().destroy()
            self.scalar_canvas = None
        study = self.study_var.get()
        tag = self.tag_var.get()
        if not study or not tag:
            return
        rows = self.con.execute("SELECT step, value FROM scalars WHERE study=? AND tag=? ORDER BY step", [study, tag]).fetchall()
        if not rows:
            messagebox.showinfo("No data", "No scalar data found.")
            return
        steps, values = zip(*rows)
        fig, ax = plt.subplots(figsize=(6,4))
        line_color = self.line_color_var.get()
        if self.show_dots_var.get():
            ax.plot(steps, values, marker='o', color=line_color)
        else:
            ax.plot(steps, values, color=line_color)
        ax.set_title(f"{tag} ({study})")
        ax.set_xlabel("Step")
        ax.set_ylabel("Value")
        # First set scale, which affects grid behavior
        if getattr(self, 'log_scale_var', None) and self.log_scale_var.get():
            ax.set_yscale('log')
            # Also add more ticks for denser grid in log mode
            ax.yaxis.set_minor_locator(LogLocator(subs=range(2, 10)))
        else:
            # Add more y-axis ticks for denser grid in linear mode
            ax.yaxis.set_minor_locator(AutoMinorLocator(4))
            
        # Add minor x-axis ticks for denser grid
        ax.xaxis.set_minor_locator(AutoMinorLocator(4))
        
        # Apply grid settings
        grid_color = self.grid_color_var.get()
        
        # Horizontal grid
        if getattr(self, 'hgrid_var', None) and self.hgrid_var.get():
            # Major grid lines
            ax.yaxis.grid(True, which='major', linestyle='-', alpha=0.5, color=grid_color)
            # Minor grid lines
            ax.yaxis.grid(True, which='minor', linestyle=':', alpha=0.3, color=grid_color)
        else:
            ax.yaxis.grid(False)
        
        # Vertical grid
        if getattr(self, 'vgrid_var', None) and self.vgrid_var.get():
            # Major grid lines
            ax.xaxis.grid(True, which='major', linestyle='-', alpha=0.5, color=grid_color)
            # Minor grid lines
            ax.xaxis.grid(True, which='minor', linestyle=':', alpha=0.3, color=grid_color)
        else:
            ax.xaxis.grid(False)
        fig.tight_layout()
        self.scalar_canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
        self.scalar_canvas.draw()
        self.scalar_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        plt.close(fig)

    def load_images(self):
        study = self.study_var.get()
        tag = self.tag_var.get()
        self.images = self.con.execute(
            "SELECT step, wall_time, image_format, image_data FROM images WHERE study=? AND tag=? ORDER BY step", [study, tag]
        ).fetchall()
        self.img_idx = 0

    def show_image(self):
        self.hide_scalar_widgets()
        # Only update widgets if they still exist (not destroyed by Tkinter)
        if not hasattr(self, 'image_label') or not hasattr(self, 'image_nav_frame'):
            return
        try:
            self.image_label.winfo_exists()
            self.image_nav_frame.winfo_exists()
        except tk.TclError:
            return
        if not self.images:
            try:
                self.image_label.config(image='', text="No images found.")
                self.image_label.image = None
                self.sample_id_label.config(text="")
                self.image_label.pack()
                self.sample_id_label.pack()
                self.image_nav_frame.pack()
                self.prev_btn.config(state=tk.DISABLED)
                self.next_btn.config(state=tk.DISABLED)
                self.image_slider.config(state=tk.DISABLED)
            except tk.TclError:
                pass
            return
        step, wall_time, img_format, img_data = self.images[self.img_idx]
        try:
            img = Image.open(io.BytesIO(img_data))
            # Use a much larger size to effectively fill the available space
            img.thumbnail((1500, 1500))
            img_tk = ImageTk.PhotoImage(img)
            self.image_label.config(image=img_tk, text="")
            self.image_label.image = img_tk
        except Exception as e:
            try:
                self.image_label.config(image='', text=f"Could not load image: {e}")
                self.image_label.image = None
            except tk.TclError:
                pass
        self.image_label.pack()
        self.sample_id_label.config(text=f"Sample ID: {step}")
        self.sample_id_label.pack()
        self.image_nav_frame.pack()
        self.prev_btn.config(state=tk.NORMAL if self.img_idx > 0 else tk.DISABLED)
        self.next_btn.config(state=tk.NORMAL if self.img_idx < len(self.images)-1 else tk.DISABLED)
        # Update slider
        if len(self.images) > 1:
            self.image_slider.config(state=tk.NORMAL, from_=0, to=len(self.images)-1)
            self.image_slider.set(self.img_idx)
        else:
            self.image_slider.config(state=tk.DISABLED, from_=0, to=0)

    def prev_image(self):
        if self.img_idx > 0:
            self.img_idx -= 1
            self.show_image()

    def next_image(self):
        if self.img_idx < len(self.images)-1:
            self.img_idx += 1
            self.show_image()

    def on_slider_move(self, value):
        idx = int(float(value))
        if idx != self.img_idx and 0 <= idx < len(self.images):
            self.img_idx = idx
            self.show_image()

    def hide_image_widgets(self):
        self.image_label.pack_forget()
        self.image_nav_frame.pack_forget()
    def hide_scalar_widgets(self):
        pass  # For future extension

def main():
    root = tk.Tk()
    app = BrainStatsUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()

