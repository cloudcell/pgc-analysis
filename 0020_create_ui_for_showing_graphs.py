# use tkinter to create a ui to show the graphs
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from tkinter.scrolledtext import ScrolledText
import duckdb
import io
from PIL import Image, ImageTk
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator, LogLocator
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import json
import os
import datetime
import numpy as np


# replace the string "Brain" with "PGC" in the tag when displayed on the graphs/charts


def create_folder(path):
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except Exception as e:
        messagebox.showerror("Error", f"Could not create folder:\n{e}")
        return False

DB_PATH = 'brain_stats.duckdb'

class BrainStatsUI:
    def create_folder_and_save_plot(self):
        """Prompt for a new folder, create it, and open the save dialog there."""
        parent = filedialog.askdirectory(title="Select parent directory for new folder")
        if not parent:
            return
        folder_name = simpledialog.askstring("Create Folder", "Enter new folder name:")
        if not folder_name:
            return
        new_folder = os.path.join(parent, folder_name)
        if not create_folder(new_folder):
            return
        self.save_plot_as_png(initialdir=new_folder)

    def __init__(self, root):
        self.root = root
        self.root.title('PGC Stats Viewer')
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
        
        # Get available machines
        self.machines = ['All'] + self.load_machines()
        
        # Define color palette for multiple lines
        self.color_palette = ['blue', 'red', 'green', 'purple', 'orange', 'brown', 'pink', 'gray', 'olive', 'cyan']
        
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
        # Filter for studies and machine selector (row 0)
        ttk.Label(controls_frame, text="Filter:").grid(row=0, column=0, sticky=tk.W)
        self.filter_var = tk.StringVar()
        self.filter_entry = ttk.Entry(controls_frame, textvariable=self.filter_var, width=20)
        self.filter_entry.grid(row=0, column=1, sticky=tk.W)
        self.filter_var.trace_add('write', self.on_filter_change)
        
        ttk.Label(controls_frame, text="Machine:").grid(row=0, column=2, sticky=tk.W, padx=(10, 0))
        self.machine_var = tk.StringVar(value='All')
        self.machine_cb = ttk.Combobox(controls_frame, textvariable=self.machine_var, state='readonly', values=self.machines, width=10)
        self.machine_cb.grid(row=0, column=3, sticky=tk.W)
        self.machine_cb.bind('<<ComboboxSelected>>', self.on_filter_change)

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
        
        # Top pane: plot area with tag list on left
        self.plot_pane = ttk.PanedWindow(self.paned, orient=tk.HORIZONTAL)
        self.paned.add(self.plot_pane, weight=3)
        
        # Left side: tag list for multi-selection
        self.tag_list_frame = ttk.Frame(self.plot_pane)
        self.plot_pane.add(self.tag_list_frame, weight=1)
        
        # Create a frame for the tag list with consistent packing
        tag_list_container = ttk.Frame(self.tag_list_frame)
        tag_list_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tag list label
        ttk.Label(tag_list_container, text="Available Tags:").pack(side=tk.TOP, anchor=tk.W, pady=5)
        
        # Tag listbox with scrollbar in a frame
        listbox_frame = ttk.Frame(tag_list_container)
        listbox_frame.pack(fill=tk.BOTH, expand=True)
        
        self.tag_listbox = tk.Listbox(listbox_frame, selectmode=tk.MULTIPLE, exportselection=0)
        self.tag_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tag_listbox.bind('<<ListboxSelect>>', self.on_tag_listbox_select)
        
        tag_scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.tag_listbox.yview)
        tag_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tag_listbox.config(yscrollcommand=tag_scrollbar.set)
        
        # Plot button
        self.plot_button = ttk.Button(tag_list_container, text="Plot Selected", command=self.plot_selected_tags)
        self.plot_button.pack(side=tk.BOTTOM, fill=tk.X, pady=5)
        
        # Right side: plot area
        self.plot_frame = ttk.Frame(self.plot_pane)
        self.plot_pane.add(self.plot_frame, weight=3)
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

    def load_machines(self):
        """Load all available machine names from the database"""
        machines = [row[0] for row in self.con.execute("SELECT DISTINCT machine FROM scalars").fetchall()]
        return sorted(machines)
    
    def load_studies(self):
        studies = [row[0] for row in self.con.execute("SELECT DISTINCT study FROM scalars").fetchall()]
        self.studies = sorted(studies)
        self.update_study_list()

    def on_filter_change(self, *args):
        self.update_study_list()

    def update_study_list(self):
        filter_text = self.filter_var.get().lower()
        machine_filter = self.machine_var.get()
        
        # Apply machine filter if not 'All'
        if machine_filter != 'All':
            # Get studies for the selected machine
            query = "SELECT DISTINCT study FROM scalars WHERE machine = ?"
            machine_studies = [row[0] for row in self.con.execute(query, [machine_filter]).fetchall()]
            # Filter the studies list
            filtered_by_machine = [s for s in self.studies if s in machine_studies]
        else:
            filtered_by_machine = self.studies
        
        # Then apply text filter
        if filter_text:
            filtered_studies = [s for s in filtered_by_machine if filter_text in s.lower()]
        else:
            filtered_studies = filtered_by_machine
            
        self.study_cb['values'] = filtered_studies
        
        # Try to maintain current selection if it's still in the filtered list
        current_study = self.study_var.get()
        if filtered_studies:
            if current_study not in filtered_studies:
                # Restore last selected values if they exist
                if 'last_machine' in self.last_settings and self.last_settings['last_machine'] in self.machines:
                    self.machine_var.set(self.last_settings['last_machine'])
                
                if 'last_study' in self.last_settings and self.last_settings['last_study'] in self.studies:
                    self.study_var.set(self.last_settings['last_study'])
                    self.on_study_selected()
                
                if 'last_type' in self.last_settings:
                    self.type_var.set(self.last_settings['last_type'])
                    self.on_type_selected()
                self.study_cb.current(0)
                self.on_study_selected()
        else:
            self.study_var.set('')
            self.tag_cb['values'] = []
        
        # Save settings
        self.save_settings()
        
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
        
        # Store original tags but display formatted tags
        self.original_tags = tags
        display_tags = [self.format_tag_for_display(tag) for tag in tags]
        
        # Set the combobox values to the display tags
        self.tag_cb['values'] = display_tags
        
        # Update the tag listbox for multi-selection
        self.tag_listbox.delete(0, tk.END)  # Clear existing items
        for display_tag in display_tags:
            self.tag_listbox.insert(tk.END, display_tag)
            
        # Create mapping from display tag to original tag
        self.display_to_original = {display_tags[i]: tags[i] for i in range(len(tags))}
        
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
            'last_machine': self.machine_var.get() if hasattr(self, 'machine_var') else '',
            
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
    
    def show_plot_context_menu(self, event):
        """Show context menu on right-click on the plot"""
        if hasattr(self, 'current_figure'):
            # Create a context menu
            context_menu = tk.Menu(self.root, tearoff=0)
            context_menu.add_command(label="Save as PNG...", command=self.save_plot_as_png)
            context_menu.add_command(label="Create Folder and Save...", command=self.create_folder_and_save_plot)
            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                # Make sure to release the grab
                context_menu.grab_release()
    
    def save_plot_as_png(self, initialdir=None):
        """Save the current plot as a PNG file"""
        if not hasattr(self, 'current_figure'):
            return
            
        # Generate default filename based on study and tag
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Sanitize study and tag names by removing problematic characters
        safe_study = self.sanitize_filename(self.current_study)
        safe_tag = self.sanitize_filename(self.current_tag)
        
        default_filename = f"{safe_study}_{safe_tag}_{timestamp}.png"
        
        # Ask user for save location
        options = {
            'defaultextension': ".png",
            'filetypes': [("PNG files", "*.png"), ("All files", "*.*")],
            'initialfile': default_filename
        }
        if initialdir:
            options['initialdir'] = initialdir
        filename = filedialog.asksaveasfilename(**options)
        
        if filename:
            try:
                self.current_figure.savefig(filename, dpi=300, bbox_inches='tight')
                print(f"Plot saved to {filename}")
            except Exception as e:
                print(f"Error saving plot: {e}")
                
    def create_folder_and_save_plot(self):
        """Create a new folder and save the plot in it"""
        # Ask user for new folder name
        new_folder_name = simpledialog.askstring("Create Folder", "Enter new folder name")
        if not new_folder_name:
            return
        
        # Create the new folder
        try:
            os.mkdir(new_folder_name)
        except Exception as e:
            print(f"Error creating folder: {e}")
            return
        
        # Save the plot in the new folder
        self.save_plot_as_png(initialdir=new_folder_name)
                
    def sanitize_filename(self, filename):
        """Remove characters that are problematic in filenames"""
        if not filename:
            return "unnamed"
            
        # Replace slashes, backslashes and other problematic characters
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        result = filename
        for char in invalid_chars:
            result = result.replace(char, '_')
            
        return result
        
    def format_tag_for_display(self, tag):
        """Replace 'Brain' with 'PGC' in tag names for display"""
        if tag:
            return tag.replace("Brain", "PGC")
        return tag
    
    def on_tag_listbox_select(self, event):
        """Handle tag listbox selection changes"""
        # This just tracks selections, actual plotting happens when the Plot button is clicked
        selected_indices = self.tag_listbox.curselection()
        if selected_indices and self.type_var.get() == 'scalar':
            self.plot_button.config(state=tk.NORMAL)
        else:
            self.plot_button.config(state=tk.DISABLED)
    
    def plot_selected_tags(self):
        """Plot all selected tags from the listbox"""
        self.hide_image_widgets()
        # Remove previous matplotlib canvas if present
        if hasattr(self, 'scalar_canvas'):
            self.scalar_canvas.get_tk_widget().pack_forget()
        
        study = self.study_var.get()
        if not study:
            return
            
        # Get selected tags
        selected_indices = self.tag_listbox.curselection()
        if not selected_indices:
            return
            
        # Get display tags from listbox
        selected_display_tags = [self.tag_listbox.get(i) for i in selected_indices]
        
        # Convert display tags to original tags for database queries
        selected_original_tags = [self.display_to_original.get(display_tag, display_tag) 
                                for display_tag in selected_display_tags]
        
        # Create plot
        fig, ax = plt.subplots(figsize=(6,4))
        
        # Set up scale first
        if getattr(self, 'log_scale_var', None) and self.log_scale_var.get():
            ax.set_yscale('log')
            ax.yaxis.set_minor_locator(LogLocator(subs=range(2, 10)))
        else:
            ax.yaxis.set_minor_locator(AutoMinorLocator(4))
            
        # Add minor x-axis ticks for denser grid
        ax.xaxis.set_minor_locator(AutoMinorLocator(4))
        
        # Apply grid settings
        grid_color = self.grid_color_var.get()
        
        # Horizontal grid
        if getattr(self, 'hgrid_var', None) and self.hgrid_var.get():
            ax.yaxis.grid(True, which='major', linestyle='-', alpha=0.5, color=grid_color)
            ax.yaxis.grid(True, which='minor', linestyle=':', alpha=0.3, color=grid_color)
        else:
            ax.yaxis.grid(False)
        
        # Vertical grid
        if getattr(self, 'vgrid_var', None) and self.vgrid_var.get():
            ax.xaxis.grid(True, which='major', linestyle='-', alpha=0.5, color=grid_color)
            ax.xaxis.grid(True, which='minor', linestyle=':', alpha=0.3, color=grid_color)
        else:
            ax.xaxis.grid(False)
        
        # Get base color
        base_color_idx = self.color_palette.index(self.line_color_var.get()) if self.line_color_var.get() in self.color_palette else 0
        
        # Plot each selected tag
        for i, tag_pair in enumerate(zip(selected_display_tags, selected_original_tags)):
            display_tag, original_tag = tag_pair
            
            # Get data for this tag
            rows = self.con.execute("SELECT step, value FROM scalars WHERE study=? AND tag=? ORDER BY step", [study, original_tag]).fetchall()
            if not rows:
                continue
                
            # Get color for this line (cycling through palette)
            color_idx = (base_color_idx + i) % len(self.color_palette)
            line_color = self.color_palette[color_idx]
            
            # Plot the data
            steps, values = zip(*rows)
            if self.show_dots_var.get():
                ax.plot(steps, values, marker='o', color=line_color, label=display_tag)
            else:
                ax.plot(steps, values, color=line_color, label=display_tag)
        
        # Set title and labels
        ax.set_title(f"Multiple Tags ({study})")
        ax.set_xlabel("Step")
        ax.set_ylabel("Value")
        
        # Add legend
        ax.legend()
        
        fig.tight_layout()
        self.scalar_canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
        self.scalar_canvas.draw()
        canvas_widget = self.scalar_canvas.get_tk_widget()
        canvas_widget.pack(fill=tk.BOTH, expand=True)
        
        # Store the figure for saving
        self.current_figure = fig
        self.current_tag = "multiple_tags"
        self.current_study = study
        
        # Add right-click menu for saving
        canvas_widget.bind("<Button-3>", self.show_plot_context_menu)
        plt.close(fig)
    
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
        if hasattr(self, 'scalar_canvas'):
            self.scalar_canvas.get_tk_widget().pack_forget()
        
        study = self.study_var.get()
        display_tag = self.tag_var.get()
        if not study or not display_tag:
            return
            
        # Convert display tag back to original tag for database query
        original_tag = self.display_to_original.get(display_tag, display_tag)
        
        rows = self.con.execute("SELECT step, value FROM scalars WHERE study=? AND tag=? ORDER BY step", [study, original_tag]).fetchall()
        if not rows:
            return
        steps, values = zip(*rows)
        fig, ax = plt.subplots(figsize=(6,4))
        line_color = self.line_color_var.get()
        if self.show_dots_var.get():
            ax.plot(steps, values, marker='o', color=line_color, label=display_tag)
        else:
            ax.plot(steps, values, color=line_color, label=display_tag)
        ax.set_title(f"{display_tag} ({study})")
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
            
        # Add legend if needed
        ax.legend()
            
        fig.tight_layout()
        self.scalar_canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
        self.scalar_canvas.draw()
        canvas_widget = self.scalar_canvas.get_tk_widget()
        canvas_widget.pack(fill=tk.BOTH, expand=True)
        
        # Store the figure for saving
        self.current_figure = fig
        self.current_tag = display_tag
        self.current_study = study
        
        # Add right-click menu for saving
        canvas_widget.bind("<Button-3>", self.show_plot_context_menu)
        plt.close(fig)

    def load_images(self):
        study = self.study_var.get()
        display_tag = self.tag_var.get()
        
        # Convert display tag back to original tag for database query
        original_tag = self.display_to_original.get(display_tag, display_tag)
        
        self.images = self.con.execute(
            "SELECT step, wall_time, image_format, image_data FROM images WHERE study=? AND tag=? ORDER BY step", [study, original_tag]
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

