"""Progress Dialog Module - GUI progress indicator using tkinter."""

import tkinter as tk
from tkinter import ttk
import threading
from typing import Optional, Callable
from loguru import logger


class ProgressDialog:
    """A popup progress dialog window."""
    
    def __init__(self, title: str = "CitationSculptor - Processing"):
        self.title = title
        self.root: Optional[tk.Tk] = None
        self.progress_var: Optional[tk.DoubleVar] = None
        self.status_var: Optional[tk.StringVar] = None
        self.count_var: Optional[tk.StringVar] = None
        self.task_var: Optional[tk.StringVar] = None
        self._cancelled = False
        self._thread: Optional[threading.Thread] = None
        
    def show(self, total: int, task_name: str = "Processing..."):
        """Show the progress dialog."""
        self.root = tk.Tk()
        self.root.title(self.title)
        self.root.geometry("450x180")
        self.root.resizable(False, False)
        
        # Center the window on screen
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'+{x}+{y}')
        
        # Keep on top
        self.root.attributes('-topmost', True)
        
        # Create frame with padding
        frame = ttk.Frame(self.root, padding="20 20 20 20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Task name label (e.g., "Processing Journal Articles")
        self.task_var = tk.StringVar(value=task_name)
        task_label = ttk.Label(frame, textvariable=self.task_var, font=('Helvetica', 12, 'bold'))
        task_label.pack(anchor=tk.W)
        
        # Status label (e.g., "Article #33...")
        self.status_var = tk.StringVar(value="Starting...")
        status_label = ttk.Label(frame, textvariable=self.status_var, font=('Helvetica', 10))
        status_label.pack(anchor=tk.W, pady=(5, 10))
        
        # Progress bar
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            frame, 
            variable=self.progress_var,
            maximum=total,
            length=400,
            mode='determinate'
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 10))
        
        # Count label (e.g., "5 / 11 (45%)")
        self.count_var = tk.StringVar(value=f"0 / {total} (0%)")
        self._total = total
        count_label = ttk.Label(frame, textvariable=self.count_var, font=('Helvetica', 10))
        count_label.pack(anchor=tk.E)
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Start the event loop in a separate thread if needed
        self.root.update()
        
    def update(self, current: int, status: str = ""):
        """Update the progress dialog."""
        if self.root is None:
            return
            
        try:
            if self.progress_var:
                self.progress_var.set(current)
            if self.status_var and status:
                self.status_var.set(status)
            if self.count_var:
                percentage = int((current / self._total) * 100) if self._total > 0 else 0
                self.count_var.set(f"{current} / {self._total} ({percentage}%)")
            
            self.root.update()
        except tk.TclError:
            # Window was closed
            pass
    
    def set_task(self, task_name: str):
        """Update the task name."""
        if self.task_var:
            self.task_var.set(task_name)
            if self.root:
                self.root.update()
    
    def close(self):
        """Close the progress dialog."""
        if self.root:
            try:
                self.root.destroy()
            except tk.TclError:
                pass
            self.root = None
    
    def _on_close(self):
        """Handle window close button."""
        self._cancelled = True
        self.close()
    
    @property
    def cancelled(self) -> bool:
        """Check if user cancelled."""
        return self._cancelled


class MultiTaskProgressDialog:
    """A progress dialog that can handle multiple sequential tasks."""
    
    def __init__(self, title: str = "CitationSculptor - Processing"):
        self.title = title
        self.root: Optional[tk.Tk] = None
        self._cancelled = False
        self._current_task = 0
        self._tasks = []
        
    def show(self, tasks: list):
        """
        Show the multi-task progress dialog.
        
        Args:
            tasks: List of (task_name, total_count) tuples
        """
        self._tasks = tasks
        total_items = sum(count for _, count in tasks)
        
        self.root = tk.Tk()
        self.root.title(self.title)
        self.root.geometry("500x250")
        self.root.resizable(False, False)
        
        # Center the window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - 250
        y = (self.root.winfo_screenheight() // 2) - 125
        self.root.geometry(f'+{x}+{y}')
        self.root.attributes('-topmost', True)
        
        # Main frame
        frame = ttk.Frame(self.root, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Overall progress section
        ttk.Label(frame, text="Overall Progress", font=('Helvetica', 11, 'bold')).pack(anchor=tk.W)
        
        self.overall_var = tk.DoubleVar(value=0)
        self.overall_bar = ttk.Progressbar(frame, variable=self.overall_var, maximum=total_items, length=450)
        self.overall_bar.pack(fill=tk.X, pady=(5, 15))
        
        self.overall_count = tk.StringVar(value=f"0 / {total_items}")
        ttk.Label(frame, textvariable=self.overall_count).pack(anchor=tk.E)
        
        # Separator
        ttk.Separator(frame, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # Current task section
        self.task_var = tk.StringVar(value="Starting...")
        ttk.Label(frame, textvariable=self.task_var, font=('Helvetica', 11, 'bold')).pack(anchor=tk.W)
        
        self.status_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.status_var, font=('Helvetica', 9)).pack(anchor=tk.W, pady=(2, 5))
        
        self.task_progress_var = tk.DoubleVar(value=0)
        self.task_bar = ttk.Progressbar(frame, variable=self.task_progress_var, maximum=100, length=450)
        self.task_bar.pack(fill=tk.X, pady=(0, 5))
        
        self.task_count = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.task_count).pack(anchor=tk.E)
        
        # Handle close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self._overall_completed = 0
        self._total_items = total_items
        self.root.update()
        
    def start_task(self, task_index: int):
        """Start a new task."""
        if task_index < len(self._tasks):
            task_name, total = self._tasks[task_index]
            self._current_task = task_index
            self._current_task_total = total
            self._current_task_completed = 0
            
            if self.task_var:
                self.task_var.set(task_name)
            if self.task_progress_var:
                self.task_progress_var.set(0)
                self.task_bar.configure(maximum=total)
            if self.task_count:
                self.task_count.set(f"0 / {total}")
            if self.root:
                self.root.update()
    
    def update_task(self, current: int, status: str = ""):
        """Update current task progress."""
        if self.root is None:
            return
            
        try:
            self._current_task_completed = current
            
            if self.task_progress_var:
                self.task_progress_var.set(current)
            if self.status_var and status:
                self.status_var.set(status)
            if self.task_count:
                self.task_count.set(f"{current} / {self._current_task_total}")
            
            # Update overall progress
            completed_before = sum(self._tasks[i][1] for i in range(self._current_task))
            total_completed = completed_before + current
            
            if self.overall_var:
                self.overall_var.set(total_completed)
            if self.overall_count:
                self.overall_count.set(f"{total_completed} / {self._total_items}")
            
            self.root.update()
        except tk.TclError:
            pass
    
    def close(self):
        """Close the dialog."""
        if self.root:
            try:
                self.root.destroy()
            except tk.TclError:
                pass
            self.root = None
    
    def _on_close(self):
        self._cancelled = True
        self.close()
    
    @property
    def cancelled(self) -> bool:
        return self._cancelled

