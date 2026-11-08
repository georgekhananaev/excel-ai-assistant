"""
Preferences dialog for Excel AI Assistant with Ollama support.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, Callable

from app.config import AppConfig
from app.ui.dialogs.ollama_settings_dialog import OllamaSettingsDialog


class PreferencesDialog:
    """Preferences dialog for application settings"""

    def __init__(self, parent: tk.Tk, config: AppConfig, api_manager=None,
                 callback: Callable[[Dict[str, Any]], None] = None):
        """
        Initialize the preferences dialog

        Args:
            parent: Parent window
            config: Application configuration
            api_manager: API manager for testing connections
            callback: Callback function to call when preferences are saved
        """
        self.parent = parent
        self.config = config
        self.api_manager = api_manager
        self.callback = callback

        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Preferences")
        # Increase the dialog size to ensure all content is visible
        self.dialog.geometry("650x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Make dialog modal
        self.dialog.focus_set()

        # Center on parent
        self.dialog.update_idletasks()
        width = self.dialog.winfo_width()
        height = self.dialog.winfo_height()
        x = (parent.winfo_width() // 2) - (width // 2) + parent.winfo_x()
        y = (parent.winfo_height() // 2) - (height // 2) + parent.winfo_y()
        self.dialog.geometry(f"+{x}+{y}")

        # Initialize UI
        self._create_ui()
        self._load_settings()

    def _create_ui(self):
        """Create dialog UI"""
        # Main frame with padding
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create tabs
        self._create_general_tab()
        self._create_api_tab()
        self._create_appearance_tab()
        self._create_advanced_tab()

        # Buttons at the bottom
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Save", command=self._save_settings).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Apply", command=self._apply_settings).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Reset to Defaults", command=self._reset_defaults).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Restore All Settings", command=self._restore_all_settings).pack(side=tk.LEFT,
                                                                                                       padx=5)

    def _create_general_tab(self):
        """Create general settings tab"""
        general_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(general_frame, text="General")

        # File settings
        file_frame = ttk.LabelFrame(general_frame, text="File Settings", padding=10)
        file_frame.pack(fill=tk.X, pady=5)

        # Recent files limit
        ttk.Label(file_frame, text="Maximum recent files:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)

        self.max_recent_files_var = tk.StringVar()
        max_recent_spinner = ttk.Spinbox(file_frame, from_=1, to=20, width=5, textvariable=self.max_recent_files_var)
        max_recent_spinner.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)

        ttk.Button(file_frame, text="Clear Recent Files", command=self._clear_recent_files).grid(
            row=1, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5
        )

        # Auto-save settings
        autosave_frame = ttk.LabelFrame(general_frame, text="Auto-save Settings", padding=10)
        autosave_frame.pack(fill=tk.X, pady=10)

        self.autosave_var = tk.BooleanVar()
        ttk.Checkbutton(autosave_frame, text="Enable auto-save", variable=self.autosave_var).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5
        )

        ttk.Label(autosave_frame, text="Auto-save interval (minutes):").grid(
            row=1, column=0, sticky=tk.W, padx=5, pady=5
        )

        self.autosave_interval_var = tk.StringVar()
        autosave_spinner = ttk.Spinbox(autosave_frame, from_=1, to=60, width=5, textvariable=self.autosave_interval_var)
        autosave_spinner.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)

        # Default prompts
        prompts_frame = ttk.LabelFrame(general_frame, text="Default Prompts", padding=10)
        prompts_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        ttk.Label(prompts_frame, text="Default system prompt:").pack(anchor=tk.W, padx=5, pady=5)

        self.default_system_prompt = tk.Text(prompts_frame, height=5, width=50)
        self.default_system_prompt.pack(fill=tk.X, padx=5, pady=5)

    def _create_api_tab(self):
        """Create API settings tab with both OpenAI and Ollama options"""
        api_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(api_frame, text="API")

        # API Type selection
        api_type_frame = ttk.LabelFrame(api_frame, text="API Type", padding=10)
        api_type_frame.pack(fill=tk.X, pady=5)

        self.api_type_var = tk.StringVar(value="openai")
        ttk.Radiobutton(api_type_frame, text="OpenAI", value="openai", variable=self.api_type_var,
                        command=self._api_type_changed).pack(anchor=tk.W, padx=5, pady=2)
        ttk.Radiobutton(api_type_frame, text="Ollama (Local)", value="ollama", variable=self.api_type_var,
                        command=self._api_type_changed).pack(anchor=tk.W, padx=5, pady=2)

        # Create a notebook for API-specific settings
        self.api_notebook = ttk.Notebook(api_frame)
        self.api_notebook.pack(fill=tk.BOTH, expand=True, pady=10)

        # OpenAI settings tab
        openai_frame = ttk.Frame(self.api_notebook, padding=10)
        self.api_notebook.add(openai_frame, text="OpenAI Settings")

        # API key
        api_key_frame = ttk.LabelFrame(openai_frame, text="API Key", padding=10)
        api_key_frame.pack(fill=tk.X, pady=5)

        ttk.Label(api_key_frame, text="OpenAI API Key:").pack(anchor=tk.W, padx=5, pady=5)

        self.api_key_var = tk.StringVar()
        api_key_entry = ttk.Entry(api_key_frame, textvariable=self.api_key_var, width=40, show="*")
        api_key_entry.pack(fill=tk.X, padx=5, pady=5)

        # Show/hide key
        self.show_key_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(api_key_frame, text="Show key", variable=self.show_key_var,
                        command=lambda: api_key_entry.configure(show="" if self.show_key_var.get() else "*")).pack(
            anchor=tk.W, padx=5, pady=5
        )

        # OpenAI-compatible server (LM Studio, vLLM, etc.)
        base_url_frame = ttk.LabelFrame(openai_frame, text="API Base URL", padding=10)
        base_url_frame.pack(fill=tk.X, pady=5)
        ttk.Label(base_url_frame, text="Leave empty for OpenAI, or use e.g. http://localhost:1234/v1 for LM Studio:").pack(
            anchor=tk.W, padx=5, pady=5
        )
        self.openai_base_url_var = tk.StringVar()
        ttk.Entry(base_url_frame, textvariable=self.openai_base_url_var, width=40).pack(fill=tk.X, padx=5, pady=5)

        # Default model
        model_frame = ttk.LabelFrame(openai_frame, text="Default Model", padding=10)
        model_frame.pack(fill=tk.X, pady=10)

        self.model_var = tk.StringVar()
        ttk.Entry(model_frame, textvariable=self.model_var, width=30).pack(
            fill=tk.X, padx=5, pady=5
        )

        # Ollama settings tab
        ollama_frame = ttk.Frame(self.api_notebook, padding=10)
        self.api_notebook.add(ollama_frame, text="Ollama Settings")

        # URL field
        url_frame = ttk.LabelFrame(ollama_frame, text="Ollama Server", padding=10)
        url_frame.pack(fill=tk.X, pady=5)

        ttk.Label(url_frame, text="Ollama URL:").pack(anchor=tk.W, padx=5, pady=5)

        self.ollama_url_var = tk.StringVar()
        ttk.Entry(url_frame, textvariable=self.ollama_url_var, width=40).pack(fill=tk.X, padx=5, pady=5)

        # Advanced Ollama settings button
        ttk.Button(ollama_frame, text="Advanced Ollama Settings...",
                   command=self._open_ollama_settings).pack(anchor=tk.W, padx=5, pady=10)

        # API usage settings (common for both APIs)
        usage_frame = ttk.LabelFrame(api_frame, text="API Usage Settings", padding=10)
        usage_frame.pack(fill=tk.X, pady=10)

        ttk.Label(usage_frame, text="Rate limit (requests per minute):").grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=5
        )

        self.rate_limit_var = tk.StringVar()
        ttk.Spinbox(usage_frame, from_=1, to=60, width=5, textvariable=self.rate_limit_var).grid(
            row=0, column=1, sticky=tk.W, padx=5, pady=5
        )

        ttk.Label(usage_frame, text="Maximum tokens per request:").grid(
            row=1, column=0, sticky=tk.W, padx=5, pady=5
        )

        self.max_tokens_var = tk.StringVar()
        ttk.Spinbox(usage_frame, from_=50, to=4000, increment=50, width=5, textvariable=self.max_tokens_var).grid(
            row=1, column=1, sticky=tk.W, padx=5, pady=5
        )

        ttk.Label(usage_frame, text="Default temperature:").grid(
            row=2, column=0, sticky=tk.W, padx=5, pady=5
        )

        temp_frame = ttk.Frame(usage_frame)
        temp_frame.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)

        self.temperature_var = tk.DoubleVar()
        temp_scale = ttk.Scale(temp_frame, from_=0.0, to=1.0, length=100, orient=tk.HORIZONTAL,
                               variable=self.temperature_var, command=self._update_temp_label)
        temp_scale.pack(side=tk.LEFT)

        self.temp_label = ttk.Label(temp_frame, text="0.0", width=3)
        self.temp_label.pack(side=tk.LEFT, padx=5)

    def _api_type_changed(self):
        """Handle API type selection change"""
        # Switch to the appropriate tab in the API notebook
        api_type = self.api_type_var.get()
        if api_type == "openai":
            self.api_notebook.select(0)  # Switch to OpenAI tab
        else:
            self.api_notebook.select(1)  # Switch to Ollama tab

    def _open_ollama_settings(self):
        """Open the advanced Ollama settings dialog"""
        if self.api_manager:
            OllamaSettingsDialog(self.dialog, self.config, self.api_manager, self._ollama_settings_updated)
        else:
            messagebox.showinfo("Not Available",
                                "API Manager not available. Please apply changes and reopen preferences.")

    def _ollama_settings_updated(self):
        """Handle updates from Ollama settings dialog"""
        # Update the URL field
        self.ollama_url_var.set(self.config.get('ollama_url', 'http://localhost:11434'))

    def _create_appearance_tab(self):
        """Create appearance settings tab"""
        appearance_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(appearance_frame, text="Appearance")

        # Theme settings
        theme_frame = ttk.LabelFrame(appearance_frame, text="Theme", padding=10)
        theme_frame.pack(fill=tk.X, pady=5)

        self.theme_var = tk.StringVar()
        ttk.Radiobutton(theme_frame, text="Light", value="light", variable=self.theme_var).pack(anchor=tk.W, padx=5,
                                                                                                pady=2)
        ttk.Radiobutton(theme_frame, text="Dark", value="dark", variable=self.theme_var).pack(anchor=tk.W, padx=5,
                                                                                              pady=2)
        ttk.Radiobutton(theme_frame, text="System", value="system", variable=self.theme_var).pack(anchor=tk.W, padx=5,
                                                                                                  pady=2)

        # Font settings
        font_frame = ttk.LabelFrame(appearance_frame, text="Fonts", padding=10)
        font_frame.pack(fill=tk.X, pady=10)

        ttk.Label(font_frame, text="UI font size:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)

        self.ui_font_size_var = tk.StringVar()
        ttk.Spinbox(font_frame, from_=8, to=16, width=5, textvariable=self.ui_font_size_var).grid(
            row=0, column=1, sticky=tk.W, padx=5, pady=5
        )

        ttk.Label(font_frame, text="Data display font size:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)

        self.data_font_size_var = tk.StringVar()
        ttk.Spinbox(font_frame, from_=8, to=16, width=5, textvariable=self.data_font_size_var).grid(
            row=1, column=1, sticky=tk.W, padx=5, pady=5
        )

        # Table display settings
        table_frame = ttk.LabelFrame(appearance_frame, text="Table Display", padding=10)
        table_frame.pack(fill=tk.X, pady=10)

        self.auto_resize_columns_var = tk.BooleanVar()
        ttk.Checkbutton(table_frame, text="Auto-resize columns", variable=self.auto_resize_columns_var).pack(
            anchor=tk.W, padx=5, pady=5
        )

        ttk.Label(table_frame, text="Default column width:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)

        self.column_width_var = tk.StringVar()
        ttk.Spinbox(table_frame, from_=50, to=300, increment=10, width=5, textvariable=self.column_width_var).grid(
            row=1, column=1, sticky=tk.W, padx=5, pady=5
        )

        self.alternating_rows_var = tk.BooleanVar()
        ttk.Checkbutton(table_frame, text="Use alternating row colors", variable=self.alternating_rows_var).pack(
            anchor=tk.W, padx=5, pady=5
        )

        self.highlight_modified_var = tk.BooleanVar()
        ttk.Checkbutton(table_frame, text="Highlight modified cells", variable=self.highlight_modified_var).pack(
            anchor=tk.W, padx=5, pady=5
        )

    def _create_advanced_tab(self):
        """Create advanced settings tab"""
        advanced_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(advanced_frame, text="Advanced")

        # Logging settings
        logging_frame = ttk.LabelFrame(advanced_frame, text="Logging", padding=10)
        logging_frame.pack(fill=tk.X, pady=5)

        self.save_logs_var = tk.BooleanVar()
        ttk.Checkbutton(logging_frame, text="Save logs to file", variable=self.save_logs_var).pack(
            anchor=tk.W, padx=5, pady=5
        )

        ttk.Label(logging_frame, text="Log level:").pack(anchor=tk.W, padx=5, pady=5)

        self.log_level_var = tk.StringVar()
        log_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        ttk.Combobox(logging_frame, textvariable=self.log_level_var, values=log_levels, state="readonly").pack(
            fill=tk.X, padx=5, pady=5
        )

        # Batch processing
        batch_frame = ttk.LabelFrame(advanced_frame, text="Batch Processing", padding=10)
        batch_frame.pack(fill=tk.X, pady=10)

        ttk.Label(batch_frame, text="Default batch size:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)

        self.batch_size_var = tk.StringVar()
        ttk.Spinbox(batch_frame, from_=1, to=50, width=5, textvariable=self.batch_size_var).grid(
            row=0, column=1, sticky=tk.W, padx=5, pady=5
        )

        self.retry_on_error_var = tk.BooleanVar()
        ttk.Checkbutton(batch_frame, text="Automatically retry failed requests", variable=self.retry_on_error_var).pack(
            anchor=tk.W, padx=5, pady=5
        )

        ttk.Label(batch_frame, text="Maximum retries:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)

        self.max_retries_var = tk.StringVar()
        ttk.Spinbox(batch_frame, from_=1, to=5, width=5, textvariable=self.max_retries_var).grid(
            row=2, column=1, sticky=tk.W, padx=5, pady=5
        )

        # Performance
        perf_frame = ttk.LabelFrame(advanced_frame, text="Performance", padding=10)
        perf_frame.pack(fill=tk.X, pady=10)

        ttk.Label(perf_frame, text="Maximum rows to display:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)

        self.max_display_rows_var = tk.StringVar()
        ttk.Spinbox(perf_frame, from_=100, to=10000, increment=100, width=7,
                    textvariable=self.max_display_rows_var).grid(
            row=0, column=1, sticky=tk.W, padx=5, pady=5
        )

        self.use_threading_var = tk.BooleanVar()
        ttk.Checkbutton(perf_frame, text="Use multi-threading for processing", variable=self.use_threading_var).pack(
            anchor=tk.W, padx=5, pady=5
        )

    def _update_temp_label(self, value):
        """Update temperature label when slider is moved"""
        self.temp_label.config(text=f"{float(value):.1f}")

    def _load_settings(self):
        """Load settings from config"""
        # General settings
        self.max_recent_files_var.set(str(self.config.get('max_recent_files', 10)))
        self.autosave_var.set(self.config.get('autosave', False))
        self.autosave_interval_var.set(str(self.config.get('autosave_interval', 5)))
        self.default_system_prompt.delete("1.0", tk.END)
        self.default_system_prompt.insert(tk.END, self.config.get('default_system_prompt', ''))

        # API settings
        self.api_type_var.set(self.config.get('api_type', 'openai'))
        self.api_key_var.set(self.config.get('api_key', ''))
        self.model_var.set(self.config.get('model', 'gpt-4o-mini'))
        self.openai_base_url_var.set(self.config.get('openai_base_url', ''))
        self.ollama_url_var.set(self.config.get('ollama_url', 'http://localhost:11434'))
        self.rate_limit_var.set(str(self.config.get('rate_limit', 20)))
        self.max_tokens_var.set(str(self.config.get('max_tokens', 150)))
        self.temperature_var.set(float(self.config.get('temperature', 0.3)))
        self._update_temp_label(self.temperature_var.get())

        # Select the appropriate API tab
        self._api_type_changed()

        # Appearance settings
        self.theme_var.set(self.config.get('theme', 'system'))
        self.ui_font_size_var.set(str(self.config.get('ui_font_size', 10)))
        self.data_font_size_var.set(str(self.config.get('data_font_size', 10)))
        self.auto_resize_columns_var.set(self.config.get('auto_resize_columns', True))
        self.column_width_var.set(str(self.config.get('column_width', 100)))
        self.alternating_rows_var.set(self.config.get('alternating_rows', True))
        self.highlight_modified_var.set(self.config.get('highlight_modified', True))

        # Advanced settings
        self.save_logs_var.set(self.config.get('save_logs', True))
        self.log_level_var.set(self.config.get('log_level', 'INFO'))
        self.batch_size_var.set(str(self.config.get('batch_size', 10)))
        self.retry_on_error_var.set(self.config.get('retry_on_error', True))
        self.max_retries_var.set(str(self.config.get('max_retries', 3)))
        self.max_display_rows_var.set(str(self.config.get('max_display_rows', 1000)))
        self.use_threading_var.set(self.config.get('use_threading', True))

    def _save_settings(self):
        """Save settings and close dialog"""
        self._apply_settings()
        self.dialog.destroy()

    def _apply_settings(self):
        """Apply settings without closing dialog"""
        # Collect settings
        settings = self._get_current_settings()

        # Update config
        for key, value in settings.items():
            self.config.set(key, value)

        # Save config
        self.config.save()

        # Call callback if provided
        if self.callback:
            self.callback(settings)

    def _get_current_settings(self) -> Dict[str, Any]:
        """Get current settings from UI"""
        settings = {}

        # General settings
        try:
            settings['max_recent_files'] = int(self.max_recent_files_var.get())
        except ValueError:
            settings['max_recent_files'] = 10

        settings['autosave'] = self.autosave_var.get()

        try:
            settings['autosave_interval'] = int(self.autosave_interval_var.get())
        except ValueError:
            settings['autosave_interval'] = 5

        settings['default_system_prompt'] = self.default_system_prompt.get("1.0", tk.END).strip()

        # API settings
        settings['api_type'] = self.api_type_var.get()
        settings['api_key'] = self.api_key_var.get()
        settings['model'] = self.model_var.get()
        settings['openai_base_url'] = self.openai_base_url_var.get().strip()
        settings['ollama_url'] = self.ollama_url_var.get()

        try:
            settings['rate_limit'] = int(self.rate_limit_var.get())
        except ValueError:
            settings['rate_limit'] = 20

        try:
            settings['max_tokens'] = int(self.max_tokens_var.get())
        except ValueError:
            settings['max_tokens'] = 150

        settings['temperature'] = float(self.temperature_var.get())

        # Appearance settings
        settings['theme'] = self.theme_var.get()

        try:
            settings['ui_font_size'] = int(self.ui_font_size_var.get())
        except ValueError:
            settings['ui_font_size'] = 10

        try:
            settings['data_font_size'] = int(self.data_font_size_var.get())
        except ValueError:
            settings['data_font_size'] = 10

        settings['auto_resize_columns'] = self.auto_resize_columns_var.get()

        try:
            settings['column_width'] = int(self.column_width_var.get())
        except ValueError:
            settings['column_width'] = 100

        settings['alternating_rows'] = self.alternating_rows_var.get()
        settings['highlight_modified'] = self.highlight_modified_var.get()

        # Advanced settings
        settings['save_logs'] = self.save_logs_var.get()
        settings['log_level'] = self.log_level_var.get()

        try:
            settings['batch_size'] = int(self.batch_size_var.get())
        except ValueError:
            settings['batch_size'] = 10

        settings['retry_on_error'] = self.retry_on_error_var.get()

        try:
            settings['max_retries'] = int(self.max_retries_var.get())
        except ValueError:
            settings['max_retries'] = 3

        try:
            settings['max_display_rows'] = int(self.max_display_rows_var.get())
        except ValueError:
            settings['max_display_rows'] = 1000

        settings['use_threading'] = self.use_threading_var.get()

        return settings

    def _reset_defaults(self):
        """Reset all settings to defaults"""
        # Default settings
        defaults = {
            'max_recent_files': 10,
            'autosave': False,
            'autosave_interval': 5,
            'default_system_prompt': 'You are a data manipulation assistant. Transform the cell content according to the user\'s instructions.',
            'api_type': 'openai',
            'api_key': '',
            'model': 'gpt-4o-mini',
            'openai_base_url': '',
            'ollama_url': 'http://localhost:11434',
            'ollama_model': '',
            'rate_limit': 20,
            'max_tokens': 150,
            'temperature': 0.3,
            'theme': 'system',
            'ui_font_size': 10,
            'data_font_size': 10,
            'auto_resize_columns': True,
            'column_width': 100,
            'alternating_rows': True,
            'highlight_modified': True,
            'save_logs': True,
            'log_level': 'INFO',
            'batch_size': 10,
            'retry_on_error': True,
            'max_retries': 3,
            'max_display_rows': 1000,
            'use_threading': True
        }

        # Reset config to defaults
        for key, value in defaults.items():
            self.config.set(key, value)

        # Reload settings in UI
        self._load_settings()

    def _restore_all_settings(self):
        """Reset all settings including prompts to factory defaults"""
        if messagebox.askyesno(
                "Restore All Settings",
                "This will reset ALL settings including prompts to factory defaults. This cannot be undone. Continue?",
                icon=messagebox.WARNING
        ):
            # Use the new method to restore all defaults
            self.config.restore_defaults(include_prompts=True)

            # Reload settings in UI
            self._load_settings()

            # Show confirmation
            messagebox.showinfo("Restore Completed", "All settings have been restored to factory defaults.")

            # Run callback if provided to update the main application
            if self.callback:
                self.callback(self.config.get_all())

    def _clear_recent_files(self):
        """Clear the recent files list"""
        self.config.clear_recent_files()
        messagebox.showinfo("Recent Files", "Recent files list has been cleared.")
