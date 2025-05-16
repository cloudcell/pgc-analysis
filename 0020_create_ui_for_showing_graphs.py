# use tkinter to create a ui to show the graphs
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
import duckdb
import io
from PIL import Image, ImageTk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

DB_PATH = 'brain_stats.duckdb'

class BrainStatsUI:
    def __init__(self, root):
        self.root = root
        self.root.title('Brain Stats Viewer')
        self.con = duckdb.connect(DB_PATH, read_only=True)
        self.setup_widgets()
        self.load_studies()
    
    def setup_widgets(self):
        frame = ttk.Frame(self.root)
        frame.pack(fill=tk.BOTH, expand=True)
        # Filter for studies (row 0)
        ttk.Label(frame, text="Filter:").grid(row=0, column=0, sticky=tk.W)
        self.filter_var = tk.StringVar()
        self.filter_entry = ttk.Entry(frame, textvariable=self.filter_var, width=20)
        self.filter_entry.grid(row=0, column=1, sticky=tk.W)
        self.filter_var.trace_add('write', self.on_filter_change)

        # Study selector (row 1)
        ttk.Label(frame, text="Study:").grid(row=1, column=0, sticky=tk.W)
        self.study_var = tk.StringVar()
        self.study_cb = ttk.Combobox(frame, textvariable=self.study_var, state='readonly', width=40)
        self.study_cb.grid(row=1, column=1, columnspan=5, sticky=tk.W+tk.E)
        self.study_cb.bind('<<ComboboxSelected>>', self.on_study_selected)

        # Type and Tag selectors (row 2)
        ttk.Label(frame, text="Type:").grid(row=2, column=0, sticky=tk.W)
        self.type_var = tk.StringVar(value='scalar')
        self.type_cb = ttk.Combobox(frame, textvariable=self.type_var, state='readonly', values=['scalar', 'image'])
        self.type_cb.grid(row=2, column=1, sticky=tk.W)
        self.type_cb.bind('<<ComboboxSelected>>', self.on_type_selected)

        ttk.Label(frame, text="Tag:").grid(row=2, column=2, sticky=tk.W)
        self.tag_var = tk.StringVar()
        self.tag_cb = ttk.Combobox(frame, textvariable=self.tag_var, state='readonly')
        self.tag_cb.grid(row=2, column=3, columnspan=3, sticky=tk.W+tk.E)
        self.tag_cb.bind('<<ComboboxSelected>>', self.on_tag_selected)

        # For scalars: plot area
        self.plot_frame = ttk.Frame(frame)
        self.plot_frame.grid(row=3, column=0, columnspan=6, sticky='nsew')
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(5, weight=1)

        # For images: image area
        self.image_label = ttk.Label(self.plot_frame)
        self.image_label.pack()
        self.image_nav_frame = ttk.Frame(self.plot_frame)
        self.image_nav_frame.pack()
        self.prev_btn = ttk.Button(self.image_nav_frame, text='Previous', command=self.prev_image)
        self.next_btn = ttk.Button(self.image_nav_frame, text='Next', command=self.next_image)
        self.prev_btn.pack(side=tk.LEFT)
        self.next_btn.pack(side=tk.LEFT)
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
        filter_str = self.filter_var.get().lower()
        if filter_str:
            filtered = [s for s in self._all_studies if filter_str in s.lower()]
        else:
            filtered = list(self._all_studies)
        self.study_cb['values'] = filtered
        if filtered:
            self.study_cb.current(0)
            self.on_study_selected()
        else:
            self.study_var.set('')
            self.tag_cb['values'] = []

    def on_study_selected(self, event=None):
        study = self.study_var.get()
        self.load_tags(study, self.type_var.get())

    def on_type_selected(self, event=None):
        study = self.study_var.get()
        self.load_tags(study, self.type_var.get())

    def load_tags(self, study, value_type):
        if not study:
            return
        if value_type == 'scalar':
            tags = [row[0] for row in self.con.execute("SELECT DISTINCT tag FROM scalars WHERE study=?", [study]).fetchall()]
        else:
            tags = [row[0] for row in self.con.execute("SELECT DISTINCT tag FROM images WHERE study=?", [study]).fetchall()]
        self.tag_cb['values'] = tags
        if tags:
            self.tag_cb.current(0)
            self.on_tag_selected()

    def on_tag_selected(self, event=None):
        if self.type_var.get() == 'scalar':
            self.show_scalar_plot()
        else:
            self.load_images()
            self.show_image()

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
        ax.plot(steps, values, marker='o')
        ax.set_title(f"{tag} ({study})")
        ax.set_xlabel("Step")
        ax.set_ylabel("Value")
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
                self.image_label.pack()
                self.image_nav_frame.pack()
                self.prev_btn.config(state=tk.DISABLED)
                self.next_btn.config(state=tk.DISABLED)
            except tk.TclError:
                pass
            return
        step, wall_time, img_format, img_data = self.images[self.img_idx]
        try:
            img = Image.open(io.BytesIO(img_data))
            img.thumbnail((500, 500))
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
        self.image_nav_frame.pack()
        self.prev_btn.config(state=tk.NORMAL if self.img_idx > 0 else tk.DISABLED)
        self.next_btn.config(state=tk.NORMAL if self.img_idx < len(self.images)-1 else tk.DISABLED)

    def prev_image(self):
        if self.img_idx > 0:
            self.img_idx -= 1
            self.show_image()

    def next_image(self):
        if self.img_idx < len(self.images)-1:
            self.img_idx += 1
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

