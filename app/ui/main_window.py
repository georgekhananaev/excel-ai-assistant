"""
Main window for the Excel AI Assistant.
This module contains the primary UI implementation.
"""

import asyncio
import os
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
from typing import Dict, List, Any, Optional, Tuple

# Local application imports
from app.config import AppConfig
from app.services.api_manager import APIManager
from app.services.data_manager import DataManager
from app.ui.components.batch_processor import BatchProcessor
from app.ui.components.status_bar import StatusBar
from app.ui.components.treeview import DataTreeview
from app.ui.dialogs.about_dialog import AboutDialog
from app.ui.dialogs.preferences_dialog import PreferencesDialog
from app.ui.dialogs.prompt_manager_dialog import PromptManagerDialog
from app.utils.logger import setup_logger
from app.utils.theme_manager import ThemeManager


class ExcelAIAssistantApp:
    """Main application class for Excel AI Assistant"""

    def __init__(self, root: tk.Tk, config: AppConfig, theme_manager: ThemeManager):
        """Initialize the main application window"""
        self.root = root
        self.config = config
        self.theme_manager = theme_manager

        # Ensure api_type is lowercase for consistency
        api_type = self.config.get('api_type', 'openai').lower()
        self.config.set('api_type', api_type)  # Save normalized value

        # Setup logger
        self.logger = setup_logger(
            "ExcelAIAssistant",
            level=self.config.get('log_level', 'INFO'),
            log_to_file=self.config.get('save_logs', True)
        )

        # Initialize services with proper API type handling
        self.api_manager = APIManager(
            api_key=self.config.get('api_key', ''),
            model=self._get_current_model_name(),
            api_type=api_type,
            ollama_url=self.config.get('ollama_url', 'http://localhost:11434'),
            openai_base_url=self.config.get('openai_base_url', ''),
            max_requests_per_minute=int(self.config.get('rate_limit', 20) or 0)
        )

        self.data_manager = DataManager()

        # Create menu and UI components
        self._create_menu()
        self._create_ui()

        # Set up event handlers
        self._setup_event_handlers()

        # Check for API key on startup
        self._check_api_key()

        # Setup asyncio event loop
        self._setup_asyncio_loop()

        # Log startup
        self.logger.info(f"Application started with API type: {api_type}")


    def _create_menu(self):
        """Create the main menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open...", command=self.open_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Save", command=self.save_file, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As...", command=self.save_file_as)

        # Recent files submenu
        self.recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="Recent Files", menu=self.recent_menu)
        self._update_recent_files_menu()

        file_menu.add_separator()
        file_menu.add_command(label="Export Results...")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy)

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Copy", accelerator="Ctrl+C")
        edit_menu.add_command(label="Paste", accelerator="Ctrl+V")
        edit_menu.add_separator()
        edit_menu.add_command(label="Preferences...", command=self._open_preferences)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)

        # Theme submenu
        theme_menu = tk.Menu(view_menu, tearoff=0)
        view_menu.add_cascade(label="Theme", menu=theme_menu)

        # Create theme radio buttons
        self.theme_var = tk.StringVar(value=self.theme_manager.get_theme())
        theme_menu.add_radiobutton(label="Light", value="light", variable=self.theme_var,
                                   command=lambda: self._change_theme("light"))
        theme_menu.add_radiobutton(label="Dark", value="dark", variable=self.theme_var,
                                   command=lambda: self._change_theme("dark"))
        theme_menu.add_radiobutton(label="System", value="system", variable=self.theme_var,
                                   command=lambda: self._change_theme("system"))

        view_menu.add_separator()
        view_menu.add_command(label="Data Summary", command=self._show_data_summary)
        view_menu.add_command(label="Column Statistics", command=self._show_column_stats)

        # AI menu
        ai_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="AI", menu=ai_menu)
        ai_menu.add_command(label="Test API Connection", command=self._test_api_connection)
        ai_menu.add_command(label="Manage Prompt Templates...", command=self._open_prompt_manager)
        ai_menu.add_separator()

        # Model submenu
        model_menu = tk.Menu(ai_menu, tearoff=0)
        ai_menu.add_cascade(label="Select Model", menu=model_menu)

        # Create model radio buttons
        self.model_var = tk.StringVar(value=self.config.get('model', ''))
        # Populate dynamically - will be filled when API is ready
        self._populate_model_menu(model_menu)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Documentation", command=self._open_documentation)
        help_menu.add_command(label="Check for Updates", command=self._check_for_updates)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self._show_about)

        # Set up keyboard shortcuts
        self.root.bind("<Control-o>", lambda event: self.open_file())
        self.root.bind("<Control-s>", lambda event: self.save_file())

    def _populate_model_menu(self, model_menu):
        """Populate model menu from API"""
        model_menu.delete(0, 'end')
        models = self.api_manager.get_available_models()
        for m in models:
            model_menu.add_radiobutton(
                label=m['id'], value=m['id'],
                variable=self.model_var,
                command=self._model_changed
            )

    def _create_ui(self):
        """Create the main UI components"""
        # Create main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Create toolbar
        self._create_toolbar(main_container)

        # Create paned window for resizable panels
        self.paned_window = ttk.PanedWindow(main_container, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel - control panel
        left_panel = ttk.Frame(self.paned_window, width=300)
        self.paned_window.add(left_panel, weight=1)

        # Right panel - data view
        right_panel = ttk.Frame(self.paned_window)
        self.paned_window.add(right_panel, weight=3)

        # Setup left panel contents (control panel)
        self._create_control_panel(left_panel)

        # Setup right panel contents (notebook with data and logs)
        self._create_data_panel(right_panel)

        # Create status bar
        self.status_bar = StatusBar(self.root)
        self.status_bar.set_status("Ready")

    def _create_toolbar(self, parent: ttk.Frame):
        """Create the toolbar with API type selector"""
        toolbar_frame = ttk.Frame(parent)
        toolbar_frame.pack(fill=tk.X, padx=5, pady=5)

        # File operations
        ttk.Button(toolbar_frame, text="Open", command=self.open_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_frame, text="Save", command=self.save_file).pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=5, fill=tk.Y)

        # API Type selection
        ttk.Label(toolbar_frame, text="API:").pack(side=tk.LEFT, padx=5)
        self.api_type_var = tk.StringVar(value=self.config.get('api_type', 'openai').lower())
        self.api_type_combobox = ttk.Combobox(toolbar_frame, textvariable=self.api_type_var, width=8, state="readonly")
        self.api_type_combobox['values'] = ["openai", "ollama"]  # Use lowercase values to match config
        self.api_type_combobox.pack(side=tk.LEFT, padx=2)

        # Set combobox to match current config
        self.api_type_combobox.set(self.api_type_var.get())

        # OpenAI specific settings (visible when OpenAI is selected)
        self.openai_frame = ttk.Frame(toolbar_frame)
        self.openai_frame.pack(side=tk.LEFT, padx=2)

        ttk.Label(self.openai_frame, text="API Key:").pack(side=tk.LEFT, padx=5)
        self.api_key_entry = ttk.Entry(self.openai_frame, width=25, show="*")
        self.api_key_entry.pack(side=tk.LEFT, padx=2)

        # Set API key from config
        api_key = self.config.get('api_key', '')
        if api_key:
            self.api_key_entry.insert(0, api_key)

        # Ollama specific settings (initially hidden)
        self.ollama_frame = ttk.Frame(toolbar_frame)

        ttk.Label(self.ollama_frame, text="Ollama URL:").pack(side=tk.LEFT, padx=5)
        self.ollama_url_var = tk.StringVar(value=self.config.get('ollama_url', 'http://localhost:11434'))
        ttk.Entry(self.ollama_frame, textvariable=self.ollama_url_var, width=20).pack(side=tk.LEFT, padx=2)

        ttk.Button(self.ollama_frame, text="Settings", command=self._open_ollama_settings).pack(side=tk.LEFT, padx=2)

        # Show the appropriate frame based on selected API type
        if self.api_type_var.get() == 'openai':
            self.openai_frame.pack(side=tk.LEFT, padx=2)
            self.ollama_frame.pack_forget()
        else:
            self.openai_frame.pack_forget()
            self.ollama_frame.pack(side=tk.LEFT, padx=2)

        # Test connection button
        ttk.Button(toolbar_frame, text="Test API", command=self._test_api_connection).pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=5, fill=tk.Y)

        # Model selection - now handles both API types
        ttk.Label(toolbar_frame, text="Model:").pack(side=tk.LEFT, padx=5)

        # Use a variable that will show the appropriate model based on API type
        self.model_var = tk.StringVar(value=self._get_current_model_name())
        self.model_combobox = ttk.Combobox(toolbar_frame, textvariable=self.model_var, width=15, state="readonly")
        self._update_model_list()  # Populate the model list
        self.model_combobox.pack(side=tk.LEFT, padx=2)

        # Add spacer to push theme selector to the right
        ttk.Frame(toolbar_frame).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Theme selector
        ttk.Label(toolbar_frame, text="Theme:").pack(side=tk.LEFT, padx=5)
        self.theme_combobox = ttk.Combobox(toolbar_frame, textvariable=self.theme_var, width=10, state="readonly")
        self.theme_combobox['values'] = ["Light", "Dark", "System"]
        self.theme_combobox.pack(side=tk.LEFT, padx=2)

        # Set combobox values
        current_theme = self.theme_manager.get_theme()
        if current_theme == "light":
            self.theme_combobox.set("Light")
        elif current_theme == "dark":
            self.theme_combobox.set("Dark")
        else:
            self.theme_combobox.set("System")

        # Bind combobox events
        self.theme_combobox.bind("<<ComboboxSelected>>", self._on_theme_changed)
        self.model_combobox.bind("<<ComboboxSelected>>", self._on_model_changed)
        self.api_type_combobox.bind("<<ComboboxSelected>>", self._on_api_type_changed)

        # Update API key when changed
        self.api_key_entry.bind("<FocusOut>", self._api_key_changed)

        # Update Ollama URL when changed
        self.ollama_url_var.trace_add("write", self._ollama_url_changed)


    def _get_current_model_name(self):
        """Get the appropriate model name based on current API type"""
        api_type = self.config.get('api_type', 'openai').lower()  # Ensure lowercase
        if api_type == 'ollama':
            return self.config.get('ollama_model', '')
        return self.config.get('model', '')


    def _update_model_list(self):
        """Update the model combobox based on selected API type"""
        api_type = self.api_type_var.get().lower()  # Ensure lowercase for consistency

        if api_type == 'openai':
            self.model_combobox.set("Loading...")
            threading.Thread(target=self._load_openai_models, daemon=True).start()
        else:  # ollama
            # Get available Ollama models
            self.model_combobox.set("Loading...")

            # Start a thread to load models
            threading.Thread(target=self._load_ollama_models, daemon=True).start()

    def _load_openai_models(self):
        """Load available OpenAI-compatible models in a background thread"""
        try:
            models = self.api_manager.get_available_models()
            model_names = [model["id"] for model in models]
            self.root.after(0, lambda: self._update_openai_models(model_names))
        except Exception as e:
            self.log(f"Error loading models: {str(e)}", "ERROR")
            self.root.after(0, lambda: self._update_openai_models([]))

    def _update_openai_models(self, model_names):
        """Update the UI with loaded OpenAI-compatible models"""
        if model_names:
            self.model_combobox['values'] = model_names
            current_model = self.config.get('model', '')
            if current_model in model_names:
                self.model_combobox.set(current_model)
            else:
                self.model_combobox.set(model_names[0])
                self.config.set('model', model_names[0])
            self.api_manager.set_model(self.model_combobox.get())
        else:
            self.model_combobox['values'] = ["No models found"]
            self.model_combobox.set("No models found")
            self.log("No models found. Make sure the API server is running.", "WARNING")

    def _load_ollama_models(self):
        """Load available Ollama models in a background thread"""
        try:
            # Ensure API manager is using Ollama
            self.api_manager.set_api_type('ollama')
            self.api_manager.set_ollama_url(self.ollama_url_var.get())

            # Get models
            models = self.api_manager.get_available_models()
            model_names = [model["name"] for model in models]

            # Update UI in main thread
            self.root.after(0, lambda: self._update_ollama_models(model_names))
        except Exception as e:
            self.log(f"Error loading Ollama models: {str(e)}", "ERROR")
            self.root.after(0, lambda: self._update_ollama_models([]))


    def _update_ollama_models(self, model_names):
        """Update the UI with loaded Ollama models"""
        if model_names:
            self.model_combobox['values'] = model_names

            # Set current model or first available
            current_model = self.config.get('ollama_model', '')
            if current_model in model_names:
                self.model_combobox.set(current_model)
            else:
                self.model_combobox.set(model_names[0])
                self.config.set('ollama_model', model_names[0])

            # Update API manager
            self.api_manager.set_model(self.model_combobox.get())
        else:
            # No models found
            self.model_combobox['values'] = ["No models found"]
            self.model_combobox.set("No models found")
            self.log("No Ollama models found. Make sure Ollama is running and models are installed.", "WARNING")

    def _on_api_type_changed(self, event=None):
        """Handle API type combobox selection"""
        api_type = self.api_type_var.get().lower()  # Ensure lowercase for consistency

        # Update config
        self.config.set('api_type', api_type)

        # Update API manager
        self.api_manager.set_api_type(api_type)

        # Show/hide appropriate frames
        if api_type == 'openai':
            self.openai_frame.pack(side=tk.LEFT, padx=2)
            self.ollama_frame.pack_forget()
        else:
            self.openai_frame.pack_forget()
            self.ollama_frame.pack(side=tk.LEFT, padx=2)

        # Update model list and set appropriate model
        self._update_model_list()

        # Log change
        self.log(f"API type changed to: {api_type}")


    def _on_model_changed(self, event=None):
        """Handle model combobox selection"""
        model = self.model_var.get()

        # Skip if in loading state
        if model == "Loading...":
            return

        # Update the right config value based on API type
        api_type = self.config.get('api_type', 'openai').lower()  # Ensure lowercase
        if api_type == 'openai':
            self.config.set('model', model)
        else:
            self.config.set('ollama_model', model)

        # Update API manager
        self.api_manager.set_model(model)

        # Log change
        self.log(f"Model changed to: {model}")

    def _create_control_panel(self, parent: ttk.Frame):
        """Create the control panel (left side)"""
        # Create a notebook for different control panels
        self.control_notebook = ttk.Notebook(parent)
        self.control_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Range selection tab
        range_frame = ttk.Frame(self.control_notebook)
        self.control_notebook.add(range_frame, text="Range")

        # Create a frame for range selection
        range_selection_frame = ttk.LabelFrame(range_frame, text="Cell Range")
        range_selection_frame.pack(fill=tk.X, padx=5, pady=5)

        # Range selection inputs
        ttk.Label(range_selection_frame, text="Start Row:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.start_row = ttk.Entry(range_selection_frame, width=10)
        self.start_row.grid(row=0, column=1, padx=5, pady=5)
        self.start_row.insert(0, "0")

        ttk.Label(range_selection_frame, text="End Row:").grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        self.end_row = ttk.Entry(range_selection_frame, width=10)
        self.end_row.grid(row=0, column=3, padx=5, pady=5)
        self.end_row.insert(0, "10")

        ttk.Label(range_selection_frame, text="Columns:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.columns_entry = ttk.Entry(range_selection_frame, width=30)
        self.columns_entry.grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky=tk.W + tk.E)

        # Column selector button
        ttk.Button(range_selection_frame, text="Select Columns", command=self._select_columns).grid(
            row=2, column=0, columnspan=4, padx=5, pady=5, sticky=tk.W + tk.E
        )

        # AI instruction frame
        instruction_frame = ttk.LabelFrame(range_frame, text="AI Instructions")
        instruction_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # System prompt
        ttk.Label(instruction_frame, text="System Prompt:").pack(anchor=tk.W, padx=5, pady=5)
        self.system_prompt = scrolledtext.ScrolledText(instruction_frame, height=3)
        self.system_prompt.pack(fill=tk.X, padx=5, pady=5)
        self.system_prompt.insert(tk.END, self.config.get(
            'default_system_prompt',
            "You are a data manipulation assistant. Transform the cell content according to the user's instructions. You returning just the manipulated data without any additional text."
        ))

        # User prompt
        ttk.Label(instruction_frame, text="Task Instructions:").pack(anchor=tk.W, padx=5, pady=5)
        self.user_prompt = scrolledtext.ScrolledText(instruction_frame, height=4)
        self.user_prompt.pack(fill=tk.X, padx=5, pady=5)
        self.user_prompt.insert(tk.END, "Capitalize all text in this cell.")

        # Prompt templates dropdown
        templates_frame = ttk.Frame(instruction_frame)
        templates_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(templates_frame, text="Templates:").pack(side=tk.LEFT, padx=5)

        # Get prompt templates from config
        prompt_templates = list(self.config.get_prompt_templates().keys())

        self.template_combobox = ttk.Combobox(templates_frame, values=prompt_templates, width=25)
        self.template_combobox.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        ttk.Button(templates_frame, text="Load", command=self._load_prompt_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(templates_frame, text="Save", command=self._save_prompt_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(templates_frame, text="Delete", command=self._delete_prompt_template).pack(side=tk.LEFT, padx=5)

        # Add Processing Parameters
        batch_frame = ttk.LabelFrame(range_frame, text="Processing Parameters")
        batch_frame.pack(fill=tk.X, padx=5, pady=5)

        # Use a grid for better cross-platform layout
        batch_frame.columnconfigure(0, weight=1)
        batch_frame.columnconfigure(1, weight=1)

        # Batch size
        ttk.Label(batch_frame, text="Batch Size:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.batch_size_var = tk.StringVar(value="10")
        # Use Entry instead of Spinbox for better cross-platform compatibility
        batch_size_entry = ttk.Entry(batch_frame, textvariable=self.batch_size_var, width=10)
        batch_size_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)

        # Temperature
        ttk.Label(batch_frame, text="Temperature:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        temp_frame = ttk.Frame(batch_frame)
        temp_frame.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)

        self.temperature_var = tk.DoubleVar(value=0.3)
        temp_scale = ttk.Scale(temp_frame, from_=0.0, to=1.0, length=100, orient=tk.HORIZONTAL,
                               variable=self.temperature_var, command=self._update_temperature_label)
        temp_scale.pack(side=tk.LEFT)

        self.temperature_label = ttk.Label(temp_frame, text="0.3", width=3)
        self.temperature_label.pack(side=tk.LEFT, padx=5)

        # Max tokens
        ttk.Label(batch_frame, text="Max Tokens:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.max_tokens_var = tk.StringVar(value="150")
        # Use Entry instead of Spinbox for better cross-platform compatibility
        max_tokens_entry = ttk.Entry(batch_frame, textvariable=self.max_tokens_var, width=10)
        max_tokens_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)

        # Save after batch checkbox
        # Enable auto-save by default
        self.save_after_batch_var = tk.BooleanVar(value=True)
        
        # Create a frame with highlight background for the auto-save checkbox
        auto_save_frame = ttk.Frame(batch_frame, relief=tk.GROOVE, borderwidth=2)
        auto_save_frame.grid(row=3, column=0, columnspan=2, sticky=tk.W+tk.E, padx=5, pady=8)
        
        auto_save_check = ttk.Checkbutton(
            auto_save_frame, 
            text="Auto-save after batch processing (saves changes immediately)",
            variable=self.save_after_batch_var
        )
        auto_save_check.pack(padx=10, pady=5, fill=tk.X)

        # Action buttons
        button_frame = ttk.Frame(range_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=10)

        ttk.Button(button_frame, text="Preview (Single Cell)", command=self._preview_transformation).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(button_frame, text="Run on Selected Range", command=self._run_transformation).pack(
            side=tk.LEFT, padx=5
        )

        # Analytics tab (create this separately for better organization)
        self._create_analytics_tab()

    def _create_analytics_tab(self):
        """Create the analytics tab - separate method for better organization"""
        # Analytics tab
        analytics_frame = ttk.Frame(self.control_notebook)
        self.control_notebook.add(analytics_frame, text="Analytics")

        # Column analytics
        analytics_col_frame = ttk.LabelFrame(analytics_frame, text="Column Analysis")
        analytics_col_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(analytics_col_frame, text="Column:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.analytics_column_var = tk.StringVar()

        # Here's the missing combobox
        self.analytics_column_combobox = ttk.Combobox(analytics_col_frame,
                                                      textvariable=self.analytics_column_var,
                                                      state="readonly")
        self.analytics_column_combobox.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W + tk.E)

        # Add the analyze button
        ttk.Button(analytics_col_frame, text="Analyze Column",
                   command=self._analyze_column).grid(
            row=1, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W + tk.E
        )

        # Cost estimation
        cost_frame = ttk.LabelFrame(analytics_frame, text="API Cost Estimation")
        cost_frame.pack(fill=tk.X, padx=5, pady=10)

        ttk.Button(cost_frame, text="Calculate Estimated Cost",
                   command=self._calculate_cost).pack(
            anchor=tk.W, padx=5, pady=5
        )

        # Add labels for cost info
        cost_info_frame = ttk.Frame(cost_frame)
        cost_info_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(cost_info_frame, text="Estimated tokens:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.estimated_tokens_label = ttk.Label(cost_info_frame, text="0")
        self.estimated_tokens_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(cost_info_frame, text="Estimated cost:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.estimated_cost_label = ttk.Label(cost_info_frame, text="$0.00")
        self.estimated_cost_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)


    def _delete_prompt_template(self):
        """Delete the currently selected prompt template"""
        template_name = self.template_combobox.get()
        if not template_name:
            messagebox.showinfo("Info", "No template selected")
            return

        # Confirm deletion
        if not messagebox.askyesno(
                "Confirm Delete",
                f"Are you sure you want to delete the template '{template_name}'? This cannot be undone.",
                icon=messagebox.WARNING
        ):
            return

        # Get prompt templates from config
        prompts = self.config.get_prompt_templates()

        # Check if template exists
        if template_name not in prompts:
            messagebox.showinfo("Info", f"Template '{template_name}' not found")
            return

        # Remove the template
        self.config.remove_prompt_template(template_name)

        # Save configuration
        self.config.save()

        # Update dropdown list
        prompt_templates = list(self.config.get_prompt_templates().keys())
        self.template_combobox['values'] = prompt_templates
        self.template_combobox.set("")  # Clear selection

        # Log the action
        self.log(f"Deleted prompt template: {template_name}")
        self.status_bar.set_status(f"Template '{template_name}' deleted", "info", auto_clear=True)

    def _create_data_panel(self, parent: ttk.Frame):
        """Create the data panel (right side)"""
        # Create a notebook for data and logs
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Data tab
        self.data_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.data_frame, text="Data")

        # Create the data treeview
        self.data_treeview = DataTreeview(self.data_frame)

        # Results tab (for showing transformed data)
        self.results_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.results_frame, text="Results")

        # Create a frame for filtering and sorting
        filter_frame = ttk.Frame(self.results_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT, padx=5)
        self.filter_entry = ttk.Entry(filter_frame, width=30)
        self.filter_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text="Apply", command=self._apply_filter).pack(side=tk.LEFT, padx=5)

        # Create the results treeview
        self.results_treeview_frame = ttk.Frame(self.results_frame)
        self.results_treeview_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create empty results treeview initially
        self.results_treeview = DataTreeview(self.results_treeview_frame, show_modified=True)

        # Log tab
        self.log_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.log_frame, text="Logs")

        # Add a toolbar to the log frame
        log_toolbar = ttk.Frame(self.log_frame)
        log_toolbar.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(log_toolbar, text="Clear Logs", command=self._clear_logs).pack(side=tk.LEFT, padx=5)
        ttk.Button(log_toolbar, text="Save Logs", command=self._save_logs).pack(side=tk.LEFT, padx=5)

        # Self-clearing checkbox
        self.auto_clear_logs_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(log_toolbar, text="Auto-clear on new operation",
                        variable=self.auto_clear_logs_var).pack(side=tk.LEFT, padx=5)

        # Create log display
        self.log_text = scrolledtext.ScrolledText(self.log_frame, height=20)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log_text.config(state=tk.DISABLED)

    def _setup_event_handlers(self):
        """Set up event handlers"""
        # Check if there are unsaved changes before closing
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_asyncio_loop(self):
        """Set up asyncio event loop for async operations"""
        # Create a new event loop
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Create batch processor
        self.batch_processor = BatchProcessor(self.root, self.api_manager, self.loop)

        # Start a thread to run the event loop
        self.loop_thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.loop_thread.start()

    def _run_event_loop(self):
        """Run asyncio event loop in the background"""
        try:
            # Set this thread's event loop
            asyncio.set_event_loop(self.loop)

            # Run the event loop
            self.loop.run_forever()
        except Exception as e:
            self.logger.error(f"Event loop error: {str(e)}")
            # Log the traceback for debugging
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")

    def _on_close(self):
        """Handle application close event"""
        # Check for unsaved changes
        if self.data_manager.modified:
            response = messagebox.askyesnocancel(
                "Unsaved Changes",
                "There are unsaved changes. Do you want to save before closing?",
                icon=messagebox.WARNING
            )

            if response is None:  # Cancel
                return
            elif response:  # Yes
                self.save_file()

        # Save configuration
        self._save_config()

        # Stop asyncio loop
        self.loop.call_soon_threadsafe(self.loop.stop)

        # Destroy the root window
        self.root.destroy()

    def _save_config(self):
        """Save current configuration"""
        # Save API key
        if hasattr(self, 'api_key_entry'):
            self.config.set('api_key', self.api_key_entry.get())

        # Save model
        if hasattr(self, 'model_var'):
            self.config.set('model', self.model_var.get())

        # Save theme
        if hasattr(self, 'theme_var'):
            theme = self.theme_var.get().lower()
            self.config.set('theme', theme)

        # Check if batch settings are initialized before saving them
        # This fixes the AttributeError when closing the app
        if hasattr(self, 'batch_size_var'):
            try:
                self.config.set('batch_size', int(self.batch_size_var.get()))
            except (ValueError, AttributeError):
                # Use default if conversion fails
                self.config.set('batch_size', 10)

        if hasattr(self, 'temperature_var'):
            try:
                self.config.set('temperature', float(self.temperature_var.get()))
            except (ValueError, AttributeError):
                # Use default if conversion fails
                self.config.set('temperature', 0.3)

        if hasattr(self, 'max_tokens_var'):
            try:
                self.config.set('max_tokens', int(self.max_tokens_var.get()))
            except (ValueError, AttributeError):
                # Use default if conversion fails
                self.config.set('max_tokens', 150)

        # Save default prompts if initialized
        if hasattr(self, 'system_prompt'):
            self.config.set('default_system_prompt', self.system_prompt.get("1.0", tk.END).strip())

        # Save configuration
        self.config.save()

    def log(self, message: str, level: str = "INFO"):
        """Add message to log with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level_prefix = f"[{level}]"

        self.log_text.config(state=tk.NORMAL)

        # Add different colors based on log level
        if level == "ERROR":
            self.log_text.insert(tk.END, f"{timestamp} {level_prefix} ", "timestamp")
            self.log_text.insert(tk.END, f"{message}\n", "error")
        elif level == "WARNING":
            self.log_text.insert(tk.END, f"{timestamp} {level_prefix} ", "timestamp")
            self.log_text.insert(tk.END, f"{message}\n", "warning")
        else:
            self.log_text.insert(tk.END, f"{timestamp} {level_prefix} ", "timestamp")
            self.log_text.insert(tk.END, f"{message}\n", "info")

        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

        # Also log to the logger
        if level == "ERROR":
            self.logger.error(message)
        elif level == "WARNING":
            self.logger.warning(message)
        else:
            self.logger.info(message)

    def _clear_logs(self):
        """Clear the log display"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _save_logs(self):
        """Save logs to a file"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")]
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self.log_text.get("1.0", tk.END))

            self.log(f"Logs saved to: {file_path}")
            self.status_bar.set_status(f"Logs saved")
        except Exception as e:
            self.log(f"Error saving logs: {str(e)}", "ERROR")
            messagebox.showerror("Error", f"Failed to save logs: {str(e)}")

    def _check_api_key(self):
        """Check if API key is set and valid"""
        api_key = self.api_key_entry.get()

        if not api_key:
            self.log("API key not set. Please enter your OpenAI API key.", "WARNING")
            self.status_bar.set_status("API key required", "warning")

    def _api_key_changed(self, event=None):
        """Handle API key change"""
        api_key = self.api_key_entry.get()

        # Update API key in the API manager
        self.api_manager.initialize(api_key)

        # Save to config
        self.config.set('api_key', api_key)

    def _ollama_url_changed(self, *args):
        """Handle Ollama URL change"""
        url = self.ollama_url_var.get()

        # Update URL in the API manager
        self.api_manager.set_ollama_url(url)

        # Save to config
        self.config.set('ollama_url', url)

    def _open_ollama_settings(self):
        """Open the Ollama settings dialog"""
        from app.ui.dialogs.ollama_settings_dialog import OllamaSettingsDialog
        OllamaSettingsDialog(self.root, self.config, self.api_manager, self._ollama_settings_updated)

    def _ollama_settings_updated(self):
        """Handle updates from Ollama settings dialog"""
        # Update the URL field
        self.ollama_url_var.set(self.config.get('ollama_url', 'http://localhost:11434'))

        # Refresh models
        self._update_model_list()

    def _model_changed(self):
        """Handle model change"""
        model = self.model_var.get()

        # Update model in the API manager
        self.api_manager.set_model(model)

        # Save to config
        self.config.set('model', model)

        self.log(f"Model changed to: {model}")

    def _change_theme(self, theme: str):
        """Change application theme"""
        self.theme_manager.set_theme(theme)
        self.config.set('theme', theme)

    def _on_theme_changed(self, event=None):
        """Handle theme combobox selection"""
        selected = self.theme_combobox.get()

        if selected == "Light":
            self._change_theme("light")
        elif selected == "Dark":
            self._change_theme("dark")
        else:  # System
            self._change_theme("system")

    def _update_temperature_label(self, value):
        """Update temperature label when slider is moved"""
        # Format temperature to 1 decimal place
        try:
            temp = float(value)
            self.temperature_label.config(text=f"{temp:.1f}")
        except (ValueError, tk.TclError):
            # Handle potential errors across platforms
            self.temperature_label.config(text="0.3")

    # def _update_temperature_label(self, value):
    #     """Update temperature label when slider is moved"""
    #     # Format temperature to 1 decimal place
    #     temp = float(value)
    #     self.temperature_label.config(text=f"{temp:.1f}")

    def _update_recent_files_menu(self):
        """Update the recent files menu"""
        # Clear existing menu items
        self.recent_menu.delete(0, tk.END)

        # Get recent files from config
        recent_files = self.config.get('recent_files', [])

        if not recent_files:
            self.recent_menu.add_command(label="No recent files", state=tk.DISABLED)
        else:
            # Add menu items for each recent file
            for file_path in recent_files:
                # Truncate path if it's too long
                display_path = file_path
                if len(display_path) > 50:
                    display_path = "..." + display_path[-47:]

                self.recent_menu.add_command(
                    label=display_path,
                    command=lambda p=file_path: self.open_file(p)
                )

            self.recent_menu.add_separator()
            self.recent_menu.add_command(label="Clear Recent Files", command=self._clear_recent_files)

    def _clear_recent_files(self):
        """Clear the recent files list"""
        self.config.clear_recent_files()
        self._update_recent_files_menu()

    def open_file(self, file_path=None):
        """Open Excel or CSV file"""
        if file_path is None:
            # Set the filetypes correctly for cross-platform compatibility
            filetypes = []
            if sys.platform == "darwin":  # macOS
                filetypes = [
                    ("Excel files", ".xlsx"),
                    ("Excel files", ".xls"),
                    ("CSV files", ".csv"),
                    ("All files", "*")
                ]
            else:  # Windows/Linux
                filetypes = [
                    ("Excel files", "*.xlsx;*.xls"),
                    ("CSV files", "*.csv"),
                    ("All files", "*.*")
                ]

            file_path = filedialog.askopenfilename(
                parent=self.root,
                title="Open File",
                filetypes=filetypes
            )

        if not file_path:
            return

        # Check if we have unsaved changes
        if self.data_manager.modified:
            response = messagebox.askyesno(
                "Unsaved Changes",
                "There are unsaved changes. Do you want to continue and discard these changes?",
                icon=messagebox.WARNING
            )
            if not response:
                return

        self.status_bar.set_status(f"Loading {os.path.basename(file_path)}...", "info")

        # Clear logs if auto-clear is enabled
        if self.auto_clear_logs_var.get():
            self._clear_logs()

        # Load file in a separate thread
        def load_thread():
            success, error_msg = self.data_manager.load_file(file_path)

            # Update UI in main thread
            self.root.after(0, lambda: self._update_after_file_load(success, error_msg, file_path))

        threading.Thread(target=load_thread).start()

    def _update_after_file_load(self, success, error_msg, file_path):
        """Update UI after file loading completes"""
        if success:
            # Update treeview
            self.data_treeview.set_data(self.data_manager.get_data())

            # Update column list
            self._update_column_lists()

            # Add to recent files
            self.config.add_recent_file(file_path)
            self._update_recent_files_menu()

            # Log success
            self.log(f"Opened file: {file_path}")
            self.status_bar.set_status(f"Loaded {os.path.basename(file_path)}")

            # Update window title
            self.root.title(f"Excel AI Assistant - {os.path.basename(file_path)}")
        else:
            self.log(f"Error opening file: {error_msg}", "ERROR")
            self.status_bar.set_status("Error loading file", "error")
            messagebox.showerror("Error", f"Failed to open file: {error_msg}")

    def _update_column_lists(self):
        """Update column lists in the UI"""
        if self.data_manager.df is None:
            return

        # Get column names
        columns = list(self.data_manager.df.columns)

        # Update columns entry
        self.columns_entry.delete(0, tk.END)
        self.columns_entry.insert(0, ",".join(columns))

        # Update analytics column dropdown
        self.analytics_column_combobox['values'] = columns
        if columns:
            self.analytics_column_combobox.current(0)

    def save_file(self, event=None):
        """Save current file"""
        if self.data_manager.df is None:
            messagebox.showinfo("Info", "No data to save")
            return

        if self.data_manager.file_path is None:
            return self.save_file_as()

        self.status_bar.set_status("Saving file...", "info")

        # Save file in a separate thread
        def save_thread():
            success, error_msg = self.data_manager.save_file()

            # Update UI in main thread
            self.root.after(0, lambda: self._update_after_file_save(success, error_msg))

        threading.Thread(target=save_thread).start()

    def save_file_as(self):
        """Save current file with a new name"""
        if self.data_manager.df is None:
            messagebox.showinfo("Info", "No data to save")
            return

        # Set the filetypes correctly for cross-platform compatibility
        filetypes = []
        if sys.platform == "darwin":  # macOS
            filetypes = [
                ("Excel files", ".xlsx"),
                ("CSV files", ".csv")
            ]
        else:  # Windows/Linux
            filetypes = [
                ("Excel files", "*.xlsx"),
                ("CSV files", "*.csv")
            ]

        file_path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save As",
            defaultextension=".xlsx",
            filetypes=filetypes
        )

        if not file_path:
            return

        self.status_bar.set_status("Saving file...", "info")

        # Save file in a separate thread
        def save_thread():
            success, error_msg = self.data_manager.save_file(file_path)

            # Update UI in main thread
            self.root.after(0, lambda: self._update_after_file_save(success, error_msg))

        threading.Thread(target=save_thread).start()
        return True

    def _update_after_file_save(self, success, error_msg):
        """Update UI after file saving completes"""
        if success:
            self.log(f"Saved file: {self.data_manager.file_path}")
            self.status_bar.set_status(f"Saved {os.path.basename(self.data_manager.file_path)}")

            # Add to recent files
            self.config.add_recent_file(self.data_manager.file_path)
            self._update_recent_files_menu()

            # Update window title
            self.root.title(f"Excel AI Assistant - {os.path.basename(self.data_manager.file_path)}")
        else:
            self.log(f"Error saving file: {error_msg}", "ERROR")
            self.status_bar.set_status("Error saving file", "error")
            messagebox.showerror("Error", f"Failed to save file: {error_msg}")

    def _select_columns(self):
        """Open a dialog to select columns"""
        if self.data_manager.df is None:
            messagebox.showinfo("Info", "No data loaded")
            return

        # Get current column selection
        selected_columns = [col.strip() for col in self.columns_entry.get().split(",") if col.strip()]

        # Create a dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Columns")
        dialog.geometry("300x400")
        dialog.transient(self.root)
        dialog.grab_set()

        # Make dialog modal
        dialog.focus_set()

        # Create a frame for the listbox
        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Select columns to include:").pack(anchor=tk.W, pady=5)

        # Create a listbox with checkboxes
        columns = list(self.data_manager.df.columns)

        # Create variables for checkbuttons
        self.column_vars = {}
        for col in columns:
            self.column_vars[col] = tk.BooleanVar(value=col in selected_columns)

        # Create a frame with scrollbar for checkbuttons
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Add canvas for scrolling
        canvas = tk.Canvas(list_frame, yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar.config(command=canvas.yview)

        # Create a frame inside the canvas
        checkbox_frame = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=checkbox_frame, anchor=tk.NW)

        # Add checkbuttons
        for col in columns:
            ttk.Checkbutton(checkbox_frame, text=col, variable=self.column_vars[col]).pack(anchor=tk.W, pady=2)

        # Update scroll region when checkbuttons are added
        checkbox_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox(tk.ALL))

        # Button frame
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Select All", command=lambda: self._select_all_columns(True)).pack(side=tk.LEFT,
                                                                                                         padx=5)
        ttk.Button(button_frame, text="Deselect All", command=lambda: self._select_all_columns(False)).pack(
            side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="OK", command=lambda: self._apply_column_selection(dialog)).pack(side=tk.RIGHT,
                                                                                                       padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def _select_all_columns(self, select: bool):
        """Select or deselect all columns"""
        for var in self.column_vars.values():
            var.set(select)

    def _apply_column_selection(self, dialog):
        """Apply column selection"""
        selected = [col for col, var in self.column_vars.items() if var.get()]

        # Update columns entry
        self.columns_entry.delete(0, tk.END)
        self.columns_entry.insert(0, ",".join(selected))

        dialog.destroy()


    def _test_api_connection(self):
        """Test the API connection based on selected API type"""
        api_type = self.api_type_var.get().lower()  # Ensure lowercase

        if api_type == 'openai':
            # Get API key
            api_key = self.api_key_entry.get()

            if not api_key:
                messagebox.showerror("Error", "API Key is required for OpenAI")
                return

            # Get selected model
            model = self.model_var.get()

            # Update API manager
            self.api_manager.set_api_type('openai')
            self.api_manager.initialize(api_key)
            self.api_manager.set_model(model)
        else:  # ollama
            # Update API manager
            url = self.ollama_url_var.get()
            model = self.model_var.get()

            self.api_manager.set_api_type('ollama')
            self.api_manager.set_ollama_url(url)
            self.api_manager.set_model(model)

        self.status_bar.set_status("Testing API connection...", "info")

        # Test in a separate thread to prevent UI freezing
        def test_thread():
            success, message = self.api_manager.test_connection()

            # Update UI in the main thread
            self.root.after(0, lambda: self._update_api_test_result(success, message))

        threading.Thread(target=test_thread, daemon=True).start()

    def _update_api_test_result(self, success: bool, message: str):
        """Update UI with API test result"""
        if success:
            messagebox.showinfo("API Test", "Connection successful!")
            self.log("API connection test: Success")
            self.status_bar.set_status("API connection successful", "success")
        else:
            messagebox.showerror("API Test Failed", f"Error: {message}")
            self.log(f"API connection test failed: {message}", "ERROR")
            self.status_bar.set_status("API connection failed", "error")

    def _preview_transformation(self):
        """Preview the transformation on a single cell"""
        if self.data_manager.df is None:
            messagebox.showinfo("Info", "No data loaded")
            return

        # Get selected range
        range_info, columns = self._get_selected_range()
        if range_info is None or not columns:
            return

        start_row, _ = range_info
        sample_col = columns[0]

        try:
            # Get cell content
            sample_cell_content = str(self.data_manager.get_cell_value(start_row, sample_col))

            self.status_bar.set_status("Calling API for preview...", "info")

            # Get prompts
            system_prompt = self.system_prompt.get("1.0", tk.END).strip()
            user_prompt = self.user_prompt.get("1.0", tk.END).strip()

            # Call API in a separate thread to prevent UI freezing
            def preview_thread():
                success, result, error = self.api_manager.process_single_cell(
                    sample_cell_content,
                    system_prompt,
                    user_prompt,
                    float(self.temperature_var.get()),
                    int(self.max_tokens_var.get())
                )

                # Update UI in the main thread
                self.root.after(0, lambda: self._update_preview_result(
                    success, result, error, start_row, sample_col, sample_cell_content
                ))

            threading.Thread(target=preview_thread).start()

        except Exception as e:
            self.log(f"Error preparing preview: {str(e)}", "ERROR")
            messagebox.showerror("Error", f"Failed to prepare preview: {str(e)}")
            self.status_bar.set_status("Preview failed", "error")

    def _update_preview_result(self, success: bool, result: str, error: str,
                               row: int, col: str, original: str):
        """Update UI with preview result"""
        if success and result:
            # Create preview window
            preview_window = tk.Toplevel(self.root)
            preview_window.title("Transformation Preview")
            preview_window.geometry("700x500")
            preview_window.transient(self.root)

            # Apply theme
            bg_color = self.theme_manager.get_theme_color('bg')
            fg_color = self.theme_manager.get_theme_color('fg')
            preview_window.configure(background=bg_color)

            # Header
            header_frame = ttk.Frame(preview_window)
            header_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Label(header_frame, text=f"Preview for Row {row}, Column: {col}").pack(side=tk.LEFT)

            # Comparison frame
            comparison_frame = ttk.Frame(preview_window)
            comparison_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            # Split frame into left and right sides
            comparison_frame.columnconfigure(0, weight=1)
            comparison_frame.columnconfigure(1, weight=1)
            comparison_frame.rowconfigure(1, weight=1)

            # Original content
            ttk.Label(comparison_frame, text="Original:").grid(row=0, column=0, sticky=tk.W, pady=5)
            original_text = scrolledtext.ScrolledText(comparison_frame, height=15)
            original_text.grid(row=1, column=0, sticky=tk.NSEW, padx=5, pady=5)
            original_text.insert(tk.END, original)
            original_text.config(state=tk.DISABLED)

            # Transformed content
            ttk.Label(comparison_frame, text="Transformed:").grid(row=0, column=1, sticky=tk.W, pady=5)
            transformed_text = scrolledtext.ScrolledText(comparison_frame, height=15)
            transformed_text.grid(row=1, column=1, sticky=tk.NSEW, padx=5, pady=5)
            transformed_text.insert(tk.END, result)
            transformed_text.config(state=tk.DISABLED)

            # Buttons
            button_frame = ttk.Frame(preview_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Button(button_frame, text="Apply to Cell",
                       command=lambda: self._apply_preview(row, col, result, preview_window)).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Close",
                       command=preview_window.destroy).pack(side=tk.RIGHT, padx=5)

            self.log(f"Preview transformation for cell [{row}, {col}] - Success")
            self.status_bar.set_status("Preview completed", "success")
        else:
            self.log(f"Preview failed: {error}", "ERROR")
            messagebox.showerror("Preview Failed", f"Error: {error}")
            self.status_bar.set_status("Preview failed", "error")

    def _apply_preview(self, row: int, col: str, value: str, window: tk.Toplevel):
        """Apply preview result to the cell"""
        success = self.data_manager.update_cell(row, col, value)

        if success:
            self.log(f"Applied transformation to cell [{row}, {col}]")
            self.status_bar.set_status("Transformation applied")

            # Update treeview
            self.data_treeview.update_cell(row, col, value)

            # Close preview window
            window.destroy()
        else:
            messagebox.showerror("Error", f"Failed to apply transformation to cell [{row}, {col}]")

    def _get_selected_range(self) -> Tuple[Optional[Tuple[int, int]], Optional[List[str]]]:
        """Get the selected range from inputs"""
        try:
            start_row = int(self.start_row.get())
            end_row_text = self.end_row.get().strip()

            if end_row_text.lower() in ("end", "all"):
                if self.data_manager.df is None:
                    messagebox.showerror("Error", "No data loaded")
                    return None, None
                end_row = len(self.data_manager.df)
            else:
                end_row = int(end_row_text)

            # Get columns
            columns_text = self.columns_entry.get().strip()
            if columns_text:
                columns = [col.strip() for col in columns_text.split(",") if col.strip()]

                # Validate columns
                if self.data_manager.df is not None:
                    invalid_cols = [col for col in columns if col not in self.data_manager.df.columns]
                    if invalid_cols:
                        messagebox.showerror("Error", f"Invalid columns: {', '.join(invalid_cols)}")
                        return None, None
            else:
                if self.data_manager.df is not None:
                    columns = list(self.data_manager.df.columns)
                else:
                    columns = []

            return (start_row, end_row), columns

        except ValueError as e:
            messagebox.showerror("Error", f"Invalid range: {str(e)}")
            return None, None
            
    def _select_context_columns(self, processing_columns):
        """Show a dialog to select context columns for processing"""
        if self.data_manager.df is None:
            return None
            
        # Get all possible columns that aren't already selected for processing
        all_columns = list(self.data_manager.df.columns)
        available_columns = [col for col in all_columns if col not in processing_columns]
        
        if not available_columns:
            # No additional columns available for context
            return None
            
        # Create dialog to select context columns
        context_dialog = tk.Toplevel(self.root)
        context_dialog.title("Select Context Columns")
        context_dialog.geometry("400x500")  # Increased height to ensure buttons are visible
        context_dialog.transient(self.root)
        context_dialog.grab_set()
        context_dialog.update_idletasks()  # Force geometry update
        
        # Set up dialog layout
        ttk.Label(context_dialog, text="Select columns to provide context for AI processing:", 
                 wraplength=380).pack(pady=10, padx=10)
        
        # Add explanation text
        explanation = ttk.Label(context_dialog, text="Context columns provide additional information to the AI when processing cells. "
                               "For example, you might want to include a 'Name' column as context when processing a 'Description' column.",
                               wraplength=380)
        explanation.pack(pady=5, padx=10)
        
        # Create frame for checkboxes
        checkbox_frame = ttk.Frame(context_dialog)
        checkbox_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        
        # Add a canvas with scrollbar for many columns
        canvas = tk.Canvas(checkbox_frame)
        scrollbar = ttk.Scrollbar(checkbox_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Add checkboxes for columns
        column_vars = {}
        for col in available_columns:
            var = tk.BooleanVar(value=False)
            column_vars[col] = var
            ttk.Checkbutton(scrollable_frame, text=col, variable=var).pack(anchor=tk.W, pady=2)
        
        # Add buttons
        button_frame = ttk.Frame(context_dialog)
        button_frame.pack(pady=10, fill=tk.X)
        
        # Selected columns variable to return
        selected_context = []
        
        # OK button command
        def on_ok():
            nonlocal selected_context
            selected_context = [col for col, var in column_vars.items() if var.get()]
            context_dialog.destroy()
        
        # Cancel button command
        def on_cancel():
            nonlocal selected_context
            selected_context = []
            context_dialog.destroy()
        
        ttk.Button(button_frame, text="OK", command=on_ok).pack(side=tk.RIGHT, padx=10)
        ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side=tk.RIGHT, padx=10)
        
        # Wait for dialog to close
        self.root.wait_window(context_dialog)
        
        return selected_context if selected_context else None

    def _run_transformation(self):
        """Run the transformation on the selected range"""
        if self.data_manager.df is None:
            messagebox.showinfo("Info", "No data loaded")
            return

        # Get selected range
        range_info, columns = self._get_selected_range()
        if range_info is None or not columns:
            return
            
        # Ask for context columns if needed
        context_columns = self._select_context_columns(columns)

        start_row, end_row = range_info

        # Check if range is valid
        if self.data_manager.df is None or start_row < 0 or start_row >= len(self.data_manager.df):
            messagebox.showerror("Error", "Invalid row range")
            return

        if end_row > len(self.data_manager.df):
            end_row = len(self.data_manager.df)

        # Get cells to process with context columns
        cells_to_process = self.data_manager.get_range(start_row, end_row, columns, context_columns)

        if not cells_to_process:
            messagebox.showinfo("Info", "No cells to process in the selected range")
            return

        # Confirm operation
        total_cells = len(cells_to_process)
        if total_cells > 50:  # Warn if processing many cells
            if not messagebox.askyesno(
                    "Confirm",
                    f"This will process {total_cells} cells using the API, which may incur costs. Continue?",
                    icon=messagebox.WARNING
            ):
                return

        # Get batch size
        try:
            batch_size = int(self.batch_size_var.get())
            if batch_size < 1:
                batch_size = 10
        except ValueError:
            batch_size = 10

        # Get prompts
        system_prompt = self.system_prompt.get("1.0", tk.END).strip()
        user_prompt = self.user_prompt.get("1.0", tk.END).strip()
        
        # Initialize progress window reference to None initially
        self.progress_window = None

        # Create progress window
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Processing")
        progress_window.geometry("500x250")
        progress_window.transient(self.root)
        progress_window.grab_set()

        # Make dialog modal
        progress_window.focus_set()
        
        # Store reference to progress window
        self.progress_window = progress_window
        
        # Add protocol handler for window closing
        def on_close():
            # Auto-save if enabled when user closes window
            if self.save_after_batch_var.get() and self.data_manager.modified:
                try:
                    self.log("Saving changes before closing progress window...")
                    success, msg = self.data_manager.save_file()
                    if success:
                        self.log("Changes saved successfully")
                        # Refresh main window
                        self._refresh_data_view()
                    else:
                        self.log(f"Failed to save: {msg}", "ERROR")
                except Exception as e:
                    self.log(f"Error during save: {str(e)}", "ERROR")
            
            # Cancel processing
            self.batch_processor.cancel_processing()
            
            # Update status
            self.status_bar.set_status("Processing cancelled by closing window", "warning")
            
            # Destroy window
            progress_window.destroy()
            
        # Set protocol for window close event
        progress_window.protocol("WM_DELETE_WINDOW", on_close)

        # Apply theme
        bg_color = self.theme_manager.get_theme_color('bg')
        progress_window.configure(background=bg_color)

        # Progress frame
        progress_frame = ttk.Frame(progress_window)
        progress_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ttk.Label(progress_frame, text="Processing cells...").pack(padx=10, pady=10)

        # Progress bar and label
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, maximum=total_cells)
        progress_bar.pack(fill=tk.X, padx=10, pady=5)

        self.progress_status = ttk.Label(progress_frame, text="Starting...")
        self.progress_status.pack(padx=10, pady=5)

        # Counts
        counts_frame = ttk.Frame(progress_frame)
        counts_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(counts_frame, text="Processed:").grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)
        self.processed_count = ttk.Label(counts_frame, text="0")
        self.processed_count.grid(row=0, column=1, padx=5, pady=2, sticky=tk.W)

        ttk.Label(counts_frame, text="Successful:").grid(row=1, column=0, padx=5, pady=2, sticky=tk.W)
        self.success_count = ttk.Label(counts_frame, text="0")
        self.success_count.grid(row=1, column=1, padx=5, pady=2, sticky=tk.W)

        ttk.Label(counts_frame, text="Failed:").grid(row=2, column=0, padx=5, pady=2, sticky=tk.W)
        self.failed_count = ttk.Label(counts_frame, text="0")
        self.failed_count.grid(row=2, column=1, padx=5, pady=2, sticky=tk.W)

        # Cancel button
        self.cancel_button = ttk.Button(progress_frame, text="Cancel", command=lambda: self._cancel_processing())
        self.cancel_button.pack(pady=10)

        # Set processing flag
        self.processing_cancelled = False

        # Log start
        self.log(f"Starting batch processing of {total_cells} cells")
        self.status_bar.set_status("Processing cells...", "info")

        # Process in batches using the batch processor
        self.batch_processor.process_batches(
            cells_to_process,
            system_prompt,
            user_prompt,
            batch_size,
            float(self.temperature_var.get()),
            int(self.max_tokens_var.get()),
            progress_callback=self._update_batch_progress,
            completion_callback=self._processing_completed
        )

    def _cancel_processing(self):
        """Cancel batch processing with error handling"""
        try:
            # Cancel the batch processor
            self.batch_processor.cancel_processing()
            self.log("Processing cancelled by user", "WARNING")
            
            # If auto-save is enabled and data is modified, save changes made so far
            if self.save_after_batch_var.get() and self.data_manager.modified:
                try:
                    self.log("Saving changes made before cancellation...")
                    success, error_msg = self.data_manager.save_file()
                    if success:
                        self.log("Changes saved successfully")
                        self.status_bar.set_status("Processing cancelled, changes saved", "warning")
                    else:
                        self.log(f"Failed to save changes: {error_msg}", "ERROR")
                        self.status_bar.set_status("Processing cancelled, save failed", "error")
                except Exception as e:
                    self.log(f"Error during auto-save: {str(e)}", "ERROR")
                    self.status_bar.set_status("Processing cancelled, auto-save error", "error")
            else:
                self.status_bar.set_status("Processing cancelled", "warning")
        except Exception as e:
            # Catch any errors to prevent application crash
            self.log(f"Error during cancellation: {str(e)}", "ERROR")
            self.status_bar.set_status("Processing cancelled with errors", "error")

    def _update_batch_progress(self, processed: int, success_count: int, error_count: int, total: int, status: str):
        """Update batch processing progress with error handling"""
        try:
            # Check if progress window exists and is valid
            if not hasattr(self, 'progress_window') or not self.progress_window.winfo_exists():
                # Only log progress to console
                progress_percentage = (processed / total) * 100 if total > 0 else 0
                if processed % 10 == 0 or processed == total:
                    self.log(f"Progress: {processed}/{total} cells processed ({progress_percentage:.1f}%)")
                return
            
            # Update progress bar
            progress_value = min(processed, total)
            progress_percentage = (progress_value / total) * 100 if total > 0 else 0

            # Update status text - use try/except for each UI update
            try:
                if hasattr(self, 'progress_status') and self.progress_status.winfo_exists():
                    self.progress_status.config(text=status)
            except Exception:
                pass

            # Update counts - use try/except for each UI update
            try:
                if hasattr(self, 'processed_count') and self.processed_count.winfo_exists():
                    self.processed_count.config(text=str(processed))
            except Exception:
                pass
                
            try:
                if hasattr(self, 'success_count') and self.success_count.winfo_exists():
                    self.success_count.config(text=str(success_count))
            except Exception:
                pass
                
            try:
                if hasattr(self, 'failed_count') and self.failed_count.winfo_exists():
                    self.failed_count.config(text=str(error_count))
            except Exception:
                pass

            # Log progress
            if processed % 10 == 0 or processed == total:
                self.log(f"Progress: {processed}/{total} cells processed ({progress_percentage:.1f}%)")
                
        except Exception as e:
            # If any error occurs, just log it and continue
            print(f"Error updating progress: {str(e)}")
            # Still log progress to console
            if processed % 10 == 0 or processed == total:
                progress_percentage = (processed / total) * 100 if total > 0 else 0
                self.log(f"Progress: {processed}/{total} cells processed ({progress_percentage:.1f}%)")

    def _refresh_data_view(self):
        """Refresh the data view with the current file data"""
        try:
            self.log("Refreshing view with saved data...")
            # Reload the saved file to ensure UI is synchronized with file
            if self.data_manager.file_path and os.path.exists(self.data_manager.file_path):
                # Keep a reference to the current file path
                current_path = self.data_manager.file_path
                # Reload the file to refresh the data
                success, error_msg = self.data_manager.load_file(current_path)
                if success:
                    self.log("View refreshed with saved data")
                    # Update the treeview with fresh data
                    self.data_treeview.set_data(self.data_manager.get_data())
                    
                    # Update column list
                    self._update_column_lists()
                else:
                    self.log(f"Error refreshing view: {error_msg}", "ERROR")
        except Exception as e:
            # Handle any exception that might occur during the refresh
            self.log(f"Error refreshing view: {str(e)}", "ERROR")

    def _processing_completed(self, results: List[Dict[str, Any]], success_count: int, error_count: int):
        """Handle batch processing completion"""
        try:
            # Check if progress window still exists, if not abort
            if not hasattr(self, 'progress_window') or not self.progress_window.winfo_exists():
                self.log("Processing dialog was closed - aborting completion")
                return
                
            # Get only successful results
            successful_results = [r for r in results if r.get('success', False)]
            
            # Update data manager with results, passing auto_save flag from UI setting
            auto_save_enabled = self.save_after_batch_var.get()
            success, error = self.data_manager.update_range(
                successful_results, 
                auto_save=auto_save_enabled
            )

            # Update treeview to show changes
            self.data_treeview.update_batch(successful_results)
            
            # Force reload data if auto-save is enabled to ensure UI reflects saved changes
            if auto_save_enabled and success_count > 0 and self.data_manager.file_path:
                self._refresh_data_view()

            # Log completion
            self.log(
                f"Processing completed: {len(results)} cells processed, {success_count} successful, {error_count} failed")
            
            # Add auto-save status to log if enabled
            if auto_save_enabled and success_count > 0:
                self.log(f"Auto-save completed for file: {self.data_manager.file_path}")
                self.status_bar.set_status(f"Processing completed and saved: {success_count} successful, {error_count} failed")
            else:
                self.status_bar.set_status(f"Processing completed: {success_count} successful, {error_count} failed")
                
            # Clean up progress window references
            if hasattr(self, 'progress_window') and self.progress_window.winfo_exists():
                self.progress_window.destroy()
            self.progress_window = None
                
        except Exception as e:
            self.log(f"Error during processing completion: {str(e)}", "ERROR")
            self.status_bar.set_status("Error during processing completion", "error")

    def _apply_filter(self):
        """Apply filter to results treeview"""
        filter_text = self.filter_entry.get().strip()
        if not filter_text:
            # Reset filter
            if hasattr(self, 'filtered_df'):
                self.results_treeview.set_data(self.filtered_df)
            return

        # Apply filter
        if hasattr(self, 'filtered_df') and self.filtered_df is not None:
            self.results_treeview.filter_data(filter_text)

    def _calculate_cost(self):
        """Calculate estimated API cost for the selected range"""
        if self.data_manager.df is None:
            messagebox.showinfo("Info", "No data loaded")
            return

        # Get selected range
        range_info, columns = self._get_selected_range()
        if range_info is None or not columns:
            return

        start_row, end_row = range_info
        total_cells = (end_row - start_row) * len(columns)

        # Estimate tokens per cell (rough approximation)
        system_prompt = self.system_prompt.get("1.0", tk.END).strip()
        user_prompt = self.user_prompt.get("1.0", tk.END).strip()

        # Estimate system prompt tokens (roughly 4 chars per token)
        system_tokens = len(system_prompt) / 4
        user_tokens = len(user_prompt) / 4

        # Estimate average cell content length (sample first 10 cells)
        sample_cells = self.data_manager.get_range(start_row, min(start_row + 10, end_row), columns[:1])
        avg_cell_length = sum(len(str(cell['content'])) for cell in sample_cells) / len(
            sample_cells) if sample_cells else 20

        # Average tokens per cell (input + output)
        avg_input_tokens = system_tokens + user_tokens + (avg_cell_length / 4)
        avg_output_tokens = float(self.max_tokens_var.get())
        avg_tokens_per_cell = avg_input_tokens + avg_output_tokens

        # Total estimated tokens
        total_tokens = avg_tokens_per_cell * total_cells

        # Cost estimation (rough approximation)
        model = self.model_var.get()

        # Price per 1000 tokens - approximation, 0 for local models
        prices = {
            "gpt-3.5-turbo": 0.002,
            "gpt-3.5-turbo-16k": 0.004,
            "gpt-4": 0.06,
            "gpt-4-turbo": 0.03,
            "gpt-4o": 0.03,
            "gpt-4o-mini": 0.015,
        }

        price_per_1k = prices.get(model, 0.002)
        estimated_cost = (total_tokens / 1000) * price_per_1k

        # Update UI
        self.estimated_tokens_label.config(text=f"{int(total_tokens):,}")
        self.estimated_cost_label.config(text=f"${estimated_cost:.2f}")

        # Show detailed breakdown
        messagebox.showinfo(
            "Cost Estimation",
            f"Estimated API usage for {total_cells:,} cells:\n\n"
            f"Avg. tokens per cell: {avg_tokens_per_cell:.1f}\n"
            f"Total tokens: {int(total_tokens):,}\n"
            f"Estimated cost: ${estimated_cost:.2f}\n\n"
            f"(This is an approximation based on average cell content length)"
        )

    def _analyze_column(self):
        """Analyze the selected column"""
        if self.data_manager.df is None:
            messagebox.showinfo("Info", "No data loaded")
            return

        column = self.analytics_column_var.get()
        if not column:
            messagebox.showinfo("Info", "No column selected")
            return

        try:
            # Get column analysis
            analysis = self.data_manager.analyze_column(column)

            if "error" in analysis:
                messagebox.showerror("Error", analysis["error"])
                return

            # Show analysis dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Column Analysis: {column}")
            dialog.geometry("600x500")
            dialog.transient(self.root)

            # Main frame with padding
            main_frame = ttk.Frame(dialog, padding=10)
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Header
            header_frame = ttk.Frame(main_frame)
            header_frame.pack(fill=tk.X, pady=5)

            ttk.Label(header_frame, text=f"Column: {column}", font=("Helvetica", 12, "bold")).pack(side=tk.LEFT)
            ttk.Label(header_frame, text=f"Type: {analysis['type']}").pack(side=tk.RIGHT)

            # Basic info
            info_frame = ttk.LabelFrame(main_frame, text="Statistics")
            info_frame.pack(fill=tk.X, pady=5)

            # Create a grid for stats
            info_frame.columnconfigure(0, weight=1)
            info_frame.columnconfigure(1, weight=1)

            row = 0
            ttk.Label(info_frame, text="Count:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=2)
            ttk.Label(info_frame, text=f"{analysis['count']:,}").grid(row=row, column=1, sticky=tk.W, padx=10, pady=2)

            row += 1
            ttk.Label(info_frame, text="Missing:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=2)
            ttk.Label(info_frame, text=f"{analysis['missing']:,}").grid(row=row, column=1, sticky=tk.W, padx=10, pady=2)

            row += 1
            ttk.Label(info_frame, text="Unique:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=2)
            ttk.Label(info_frame, text=f"{analysis['unique']:,}").grid(row=row, column=1, sticky=tk.W, padx=10, pady=2)

            # Add type-specific stats
            if analysis['type'] in ('integer', 'float'):
                # Add numeric stats with null handling
                numeric_stats = [
                    ("Minimum", "min"),
                    ("Maximum", "max"),
                    ("Mean", "mean"),
                    ("Median", "median")
                ]

                for label, key in numeric_stats:
                    if key in analysis and analysis[key] is not None:
                        row += 1
                        ttk.Label(info_frame, text=f"{label}:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=2)
                        ttk.Label(info_frame, text=f"{analysis[key]:,}").grid(row=row, column=1, sticky=tk.W, padx=10,
                                                                              pady=2)

            # Most common values section
            values_frame = ttk.LabelFrame(main_frame, text="Most Common Values")
            values_frame.pack(fill=tk.BOTH, expand=True, pady=5)

            # Create a scrollable frame for common values
            values_canvas = tk.Canvas(values_frame)
            values_scrollbar = ttk.Scrollbar(values_frame, orient=tk.VERTICAL, command=values_canvas.yview)
            values_canvas.configure(yscrollcommand=values_scrollbar.set)

            values_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            values_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            values_content = ttk.Frame(values_canvas)
            values_canvas.create_window((0, 0), window=values_content, anchor=tk.NW)

            # Add most common values
            if "most_common" in analysis and analysis["most_common"]:
                for i, (value, count) in enumerate(analysis.get('most_common', {}).items()):
                    ttk.Label(values_content, text=str(value)).grid(row=i, column=0, sticky=tk.W, padx=10, pady=2)
                    ttk.Label(values_content, text=f"{count:,}").grid(row=i, column=1, sticky=tk.W, padx=10, pady=2)
            else:
                ttk.Label(values_content, text="No common values data available").grid(row=0, column=0, sticky=tk.W,
                                                                                       padx=10, pady=2)

            values_content.update_idletasks()
            values_canvas.config(scrollregion=values_canvas.bbox(tk.ALL))

            # Button frame
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=10)

            ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            # Catch any unexpected errors and show them
            error_msg = f"Error analyzing column: {str(e)}"
            self.log(error_msg, "ERROR")
            messagebox.showerror("Error", error_msg)

            # Show more detailed error for debugging
            import traceback
            self.log(traceback.format_exc(), "ERROR")

    def _analyze_missing_values(self):
        """Analyze missing values in the dataset"""
        if self.data_manager.df is None:
            messagebox.showinfo("Info", "No data loaded")
            return

        # Get data summary
        summary = self.data_manager.get_data_summary()

        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Missing Values Analysis")
        dialog.geometry("600x400")
        dialog.transient(self.root)

        # Main frame with padding
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        ttk.Label(main_frame, text="Missing Values Analysis", font=("Helvetica", 12, "bold")).pack(pady=5)

        # Missing values table
        table_frame = ttk.Frame(main_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Create treeview for missing values
        columns = ["column", "missing", "total", "percentage"]
        tree = ttk.Treeview(table_frame, columns=columns, show="headings")

        # Configure columns
        tree.heading("column", text="Column")
        tree.heading("missing", text="Missing")
        tree.heading("total", text="Total")
        tree.heading("percentage", text="Percentage")

        tree.column("column", width=150)
        tree.column("missing", width=100)
        tree.column("total", width=100)
        tree.column("percentage", width=100)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Add data
        total_rows = summary["rows"]
        for i, (column, missing) in enumerate(summary["missing_values"].items()):
            percentage = (missing / total_rows) * 100 if total_rows > 0 else 0
            tree.insert("", tk.END, values=[
                column,
                f"{missing:,}",
                f"{total_rows:,}",
                f"{percentage:.1f}%"
            ])

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

    def _show_data_summary(self):
        """Show data summary dialog"""
        if self.data_manager.df is None:
            messagebox.showinfo("Info", "No data loaded")
            return

        summary = self.data_manager.get_data_summary()

        # Create summary dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Data Summary")
        dialog.geometry("700x500")
        dialog.transient(self.root)

        # Main frame with padding
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Basic info
        info_frame = ttk.LabelFrame(main_frame, text="Basic Information")
        info_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(info_frame, text=f"Rows: {summary['rows']:,}").grid(row=0, column=0, padx=10, pady=5, sticky=tk.W)
        ttk.Label(info_frame, text=f"Columns: {summary['columns']:,}").grid(row=0, column=1, padx=10, pady=5,
                                                                            sticky=tk.W)

        # Create notebook for different summaries
        summary_notebook = ttk.Notebook(main_frame)
        summary_notebook.pack(fill=tk.BOTH, expand=True, pady=10)

        # Column types tab
        types_frame = ttk.Frame(summary_notebook)
        summary_notebook.add(types_frame, text="Column Types")

        # Create treeview for column types
        types_tree = ttk.Treeview(types_frame, columns=["column", "type"], show="headings")
        types_tree.heading("column", text="Column")
        types_tree.heading("type", text="Data Type")
        types_tree.column("column", width=200)
        types_tree.column("type", width=100)

        types_scrollbar = ttk.Scrollbar(types_frame, orient=tk.VERTICAL, command=types_tree.yview)
        types_tree.configure(yscrollcommand=types_scrollbar.set)

        types_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        types_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Add column types
        for column, dtype in summary["column_types"].items():
            types_tree.insert("", tk.END, values=[column, dtype])

        # Missing values tab
        missing_frame = ttk.Frame(summary_notebook)
        summary_notebook.add(missing_frame, text="Missing Values")

        # Create treeview for missing values
        missing_tree = ttk.Treeview(missing_frame, columns=["column", "missing", "percentage"], show="headings")
        missing_tree.heading("column", text="Column")
        missing_tree.heading("missing", text="Missing Values")
        missing_tree.heading("percentage", text="Percentage")
        missing_tree.column("column", width=200)
        missing_tree.column("missing", width=100)
        missing_tree.column("percentage", width=100)

        missing_scrollbar = ttk.Scrollbar(missing_frame, orient=tk.VERTICAL, command=missing_tree.yview)
        missing_tree.configure(yscrollcommand=missing_scrollbar.set)

        missing_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        missing_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Add missing values
        total_rows = summary["rows"]
        for column, missing in summary["missing_values"].items():
            percentage = (missing / total_rows) * 100 if total_rows > 0 else 0
            missing_tree.insert("", tk.END, values=[
                column,
                f"{missing:,}",
                f"{percentage:.1f}%"
            ])

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="Export Summary", command=lambda: self._export_summary(summary)).pack(
            side=tk.LEFT)

    def _export_summary(self, summary):
        """Export data summary to a file"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"Data Summary\n")
                f.write(f"===========\n\n")
                f.write(f"Basic Information:\n")
                f.write(f"Rows: {summary['rows']:,}\n")
                f.write(f"Columns: {summary['columns']:,}\n\n")

                f.write(f"Column Types:\n")
                for column, dtype in summary["column_types"].items():
                    f.write(f"- {column}: {dtype}\n")
                f.write("\n")

                f.write(f"Missing Values:\n")
                total_rows = summary["rows"]
                for column, missing in summary["missing_values"].items():
                    if missing > 0:
                        percentage = (missing / total_rows) * 100
                        f.write(f"- {column}: {missing:,} ({percentage:.1f}%)\n")
                f.write("\n")

                f.write(f"Column Statistics:\n")
                for column, stats in summary["column_stats"].items():
                    f.write(f"- {column}:\n")
                    for stat_name, stat_value in stats.items():
                        if stat_name == "most_common":
                            f.write(f"  {stat_name}: {dict(list(stat_value.items())[:5])}\n")
                        else:
                            f.write(f"  {stat_name}: {stat_value}\n")

            self.log(f"Exported data summary to: {file_path}")
            self.status_bar.set_status("Summary exported")

        except Exception as e:
            self.log(f"Error exporting summary: {str(e)}", "ERROR")
            messagebox.showerror("Error", f"Failed to export summary: {str(e)}")

    def _show_column_stats(self):
        """Show column statistics dialog"""
        if self.data_manager.df is None:
            messagebox.showinfo("Info", "No data loaded")
            return

        # Get column statistics
        summary = self.data_manager.get_data_summary()
        column_stats = summary["column_stats"]

        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Column Statistics")
        dialog.geometry("700x500")
        dialog.transient(self.root)

        # Main frame with padding
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Column selection
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill=tk.X, pady=5)

        ttk.Label(select_frame, text="Select Column:").pack(side=tk.LEFT, padx=5)

        column_var = tk.StringVar()
        columns = list(self.data_manager.df.columns)
        column_dropdown = ttk.Combobox(select_frame, textvariable=column_var, values=columns, state="readonly",
                                       width=30)
        column_dropdown.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        if columns:
            column_dropdown.current(0)

        # Stats display
        stats_frame = ttk.LabelFrame(main_frame, text="Statistics")
        stats_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Create a text widget for statistics
        stats_text = scrolledtext.ScrolledText(stats_frame, wrap=tk.WORD, width=80, height=20)
        stats_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        stats_text.config(state=tk.DISABLED)

        # Function to update stats display
        def update_stats(*args):
            column = column_var.get()
            if not column or column not in column_stats:
                return

            stats = column_stats[column]
            col_type = summary["column_types"][column]

            stats_text.config(state=tk.NORMAL)
            stats_text.delete("1.0", tk.END)

            stats_text.insert(tk.END, f"Column: {column}\n")
            stats_text.insert(tk.END, f"Type: {col_type}\n\n")

            for stat_name, stat_value in stats.items():
                if stat_name == "most_common":
                    stats_text.insert(tk.END, f"Most Common Values:\n")
                    for value, count in stat_value.items():
                        stats_text.insert(tk.END, f"  {value}: {count:,}\n")
                else:
                    # Format numeric values
                    if isinstance(stat_value, (int, float)):
                        stats_text.insert(tk.END, f"{stat_name.capitalize()}: {stat_value:,}\n")
                    else:
                        stats_text.insert(tk.END, f"{stat_name.capitalize()}: {stat_value}\n")

            stats_text.config(state=tk.DISABLED)

        # Bind dropdown change to update stats
        column_var.trace_add("write", update_stats)

        # Initial update
        if columns:
            update_stats()

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

    # These methods have been removed as part of the application's refactoring to eliminate
    # visualization functionality per the requirements

    def _open_preferences(self):
        """Open the preferences dialog"""
        preferences_dialog = PreferencesDialog(
            self.root,
            self.config,
            callback=self._preferences_updated
        )

    def _preferences_updated(self, settings):
        """Handle preferences updates"""
        # Apply theme changes
        if 'theme' in settings:
            self.theme_manager.set_theme(settings['theme'])
            self.theme_var.set(settings['theme'])

        # Apply model changes
        if 'model' in settings:
            self.model_var.set(settings['model'])
            self.api_manager.set_model(settings['model'])

        # Apply rate limit and base URL changes before re-initializing the client
        if 'rate_limit' in settings:
            self.api_manager.max_requests_per_minute = int(settings['rate_limit'] or 0)
        if 'openai_base_url' in settings:
            self.api_manager.openai_base_url = settings['openai_base_url']

        # Apply API key changes
        if 'api_key' in settings:
            self.api_key_entry.delete(0, tk.END)
            self.api_key_entry.insert(0, settings['api_key'])
            self.api_manager.initialize(settings['api_key'])

        # Other settings that might need UI updates
        self.log("Preferences updated")

    def _open_prompt_manager(self):
        """Open the prompt template manager dialog"""
        prompt_manager_dialog = PromptManagerDialog(
            self.root,
            self.config,
            callback=self._prompt_templates_updated
        )

    def _prompt_templates_updated(self):
        """Handle prompt templates updates"""
        # Update template dropdown
        prompt_templates = list(self.config.get_prompt_templates().keys())
        self.template_combobox['values'] = prompt_templates

        self.log("Prompt templates updated")

    def _load_prompt_template(self):
        """Load the selected prompt template"""
        template_name = self.template_combobox.get()
        if not template_name:
            return

        # Get template data
        prompts = self.config.get_prompt_templates()
        if template_name not in prompts:
            return

        prompt_data = prompts[template_name]

        # Handle both string and dictionary formats
        if isinstance(prompt_data, str):
            # Simple format (just the prompt text)
            self.user_prompt.delete("1.0", tk.END)
            self.user_prompt.insert(tk.END, prompt_data)
        else:
            # Dictionary format (with metadata)
            self.user_prompt.delete("1.0", tk.END)
            self.user_prompt.insert(tk.END, prompt_data.get("prompt", ""))

        self.log(f"Loaded prompt template: {template_name}")

    def _save_prompt_template(self):
        """Save the current prompt as a template"""
        # Ask for a name
        template_name = tk.simpledialog.askstring(
            "Save Template",
            "Enter a name for this template:",
            parent=self.root
        )

        if not template_name:
            return

        # Get prompt text
        prompt_text = self.user_prompt.get("1.0", tk.END).strip()

        if not prompt_text:
            messagebox.showerror("Error", "Prompt template cannot be empty")
            return

        # Check if template already exists
        if template_name in self.config.get_prompt_templates():
            if not messagebox.askyesno(
                    "Confirm Replace",
                    f"A template named '{template_name}' already exists. Replace it?",
                    icon=messagebox.WARNING
            ):
                return

        # Save template
        template_data = {
            "category": "Custom",
            "description": "",
            "prompt": prompt_text
        }

        self.config.add_prompt_template(template_name, template_data)
        self.config.save()

        # Update template dropdown
        prompt_templates = list(self.config.get_prompt_templates().keys())
        self.template_combobox['values'] = prompt_templates
        self.template_combobox.set(template_name)

        self.log(f"Saved prompt template: {template_name}")

    def _open_documentation(self):
        """Open documentation website"""
        import webbrowser
        webbrowser.open("https://github.com/georgekhananaev/excel-ai-assistant")

    def _check_for_updates(self):
        """Check for application updates"""
        messagebox.showinfo(
            "Check for Updates",
            "You are using the latest version of Excel AI Assistant (v1.0.0)."
        )

    def _show_about(self):
        """Show about dialog"""
        AboutDialog(self.root)
