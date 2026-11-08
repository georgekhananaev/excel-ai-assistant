"""
Configuration manager for the Excel AI Assistant.
Handles loading, saving, and accessing application configuration settings.
"""

import json
import platform
from pathlib import Path


class AppConfig:
    """Application configuration manager"""

    def __init__(self):
        """Initialize configuration with default values"""
        # Default configuration
        self._config = {
            # API settings
            'api_type': 'openai',  # 'openai' or 'ollama'
            'api_key': '',  # API key (required for real OpenAI, any string for LM Studio)
            'model': 'gpt-4o-mini',  # Selected OpenAI-compatible model
            # Empty = official OpenAI API. Set e.g. http://localhost:1234/v1 for LM Studio.
            'openai_base_url': '',
            'ollama_url': 'http://localhost:11434',  # Ollama API URL
            'ollama_model': '',  # Selected Ollama model
            'rate_limit': 20,  # Max requests per minute, 0 = no limit

            # UI settings
            'theme': 'system',
            'recent_files': [],
            'max_recent_files': 10,

            # Default prompts
            'default_system_prompt': 'You are a data manipulation assistant. Transform the cell content according to the user\'s instructions.',

            # Processing settings
            'temperature': 0.3,
            'max_tokens': 150,
            'batch_size': 10,  # Number of cells to process in a batch

            # Display settings
            'column_width': 100,
            'auto_resize_columns': True,

            # Logging settings
            'save_logs': True,
            'log_level': 'INFO',

            # Predefined prompts
            'prompts': {
                # Basic text transformation
                'Capitalize': 'Capitalize all text in this cell.',
                'To Uppercase': 'Convert all text to uppercase.',
                'To Lowercase': 'Convert all text to lowercase.',
                'Sentence Case': 'Format the text in sentence case (capitalize first letter of each sentence).',
                'Title Case': 'Format the text in title case (capitalize first letter of each word, except for articles, prepositions, and conjunctions).',
                'Remove Extra Spaces': 'Remove all extra whitespace, including double spaces and leading/trailing spaces.',

                # Data formatting
                'Format Date': 'Format this as a standard date (YYYY-MM-DD).',
                'Format Phone Number': 'Format this as a standard phone number.',
                'Format Currency': 'Format this as a standard currency value.',
                'Format Percentage': 'Format this as a percentage.',
                'Extract Numbers': 'Extract all numbers from this text.',
                'Format Address': 'Format this as a properly structured address with standard capitalization.',
                'Format Email': 'Format this as a proper email address (lowercase, no extra spaces).',

                # Content transformation
                'Summarize': 'Summarize this text in one sentence.',
                'Expand': 'Expand this abbreviated or short text with more details while maintaining its meaning.',
                'Bullet Points': 'Convert this text into a bulleted list of key points.',
                'Fix Grammar': 'Fix any grammar or spelling errors in this text.',
                'Simplify': 'Simplify this text to make it easier to understand while preserving the key information.',
                'Formalize': 'Rewrite this text in a more formal, professional tone.',
                'Casualize': 'Rewrite this text in a more casual, conversational tone.',

                # Code and markup handling
                'Format JSON': 'Format this as valid, properly indented JSON.',
                'Format XML': 'Format this as valid, properly indented XML.',
                'Format CSV': 'Format this as valid CSV with proper delimiters and escaping.',
                'HTML to Text': 'Convert this HTML to well-structured plain text, preserving the semantic structure.',
                'Markdown to Text': 'Convert this Markdown to plain text while preserving the content structure.',
                'Clean Code': 'Clean up and format this code snippet with proper indentation and style.',

                # Multi-language translation
                'Translate to English': 'Translate this text to English.',
                'Translate to Arabic': 'Translate this text to Arabic.',
                'Translate to Hebrew': 'Translate this text to Hebrew.',

                # Data cleanup
                'Remove Duplicates': 'Remove any duplicate information from this text.',
                'Remove HTML Tags': 'Remove all HTML tags from this text, keeping only the content.',
                'Fix Encoding Issues': 'Fix text encoding issues like garbled characters or HTML entities.',
                'Fill Blank': 'Complete the blank or missing information in this cell based on context from surrounding cells.',
                'Standardize Format': 'Standardize the format of this data according to conventions.',
                'Extract Dates': 'Extract all dates from this text and format them consistently.',

                # Name handling
                'Split Name': 'Split this full name into separate first name and last name components.',
                'Format Name': 'Format this name with proper capitalization and spacing.',
                'Extract Initials': 'Extract the initials from this name.',

                # Special formats
                'Convert to Citation': 'Convert this reference information to a proper citation format.',
            }
        }

        # Load configuration from file
        self._config_file = self._get_config_path()
        self._load()

    def _get_config_path(self):
        """Get the platform-specific configuration file path"""
        system = platform.system()
        home = Path.home()

        if system == 'Windows':
            config_dir = home / 'AppData' / 'Roaming' / 'ExcelAIAssistant'
        elif system == 'Darwin':  # macOS
            config_dir = home / 'Library' / 'Application Support' / 'ExcelAIAssistant'
        else:  # Linux and others
            config_dir = home / '.config' / 'excel-ai-assistant'

        # Create directory if it doesn't exist
        config_dir.mkdir(parents=True, exist_ok=True)

        return config_dir / 'config.json'

    def _load(self):
        """Load configuration from file"""
        try:
            if self._config_file.exists():
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)

                    # Special handling for prompt templates - merge instead of replace
                    if 'prompts' in loaded_config and 'prompts' in self._config:
                        # First, save the default prompts
                        default_prompts = self._config['prompts'].copy()

                        # Update with loaded prompts
                        self._config.update(loaded_config)

                        # Merge prompts dictionaries, giving priority to user's custom prompts
                        # but ensuring all default prompts are present
                        merged_prompts = default_prompts.copy()
                        merged_prompts.update(self._config['prompts'])
                        self._config['prompts'] = merged_prompts
                    else:
                        # Regular update for other config items
                        self._config.update(loaded_config)
        except Exception as e:
            print(f"Error loading configuration: {e}")
            # Continue with default configuration

    def save(self):
        """Save current configuration to file"""
        try:
            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2)
        except Exception as e:
            print(f"Error saving configuration: {e}")

    def get(self, key, default=None):
        """Get a configuration value"""
        return self._config.get(key, default)

    def set(self, key, value):
        """Set a configuration value"""
        self._config[key] = value

    def get_all(self):
        """Get a copy of the entire configuration"""
        return self._config.copy()

    def get_active_model(self):
        """Get the currently active model info"""
        api_type = self.get('api_type', 'openai')
        model_key = 'ollama_model' if api_type == 'ollama' else 'model'
        return {
            'api_type': api_type,
            'model': self.get(model_key, '')
        }

    def set_active_model(self, api_type, model):
        """Set the active model"""
        self.set('api_type', api_type)
        self.set('ollama_model' if api_type == 'ollama' else 'model', model)

    def add_recent_file(self, file_path):
        """Add a file to the recent files list"""
        recent_files = self.get('recent_files', [])

        # Remove if already in list
        if file_path in recent_files:
            recent_files.remove(file_path)

        # Add to beginning of list
        recent_files.insert(0, file_path)

        # Trim to max size
        max_count = self.get('max_recent_files', 10)
        if len(recent_files) > max_count:
            recent_files = recent_files[:max_count]

        self.set('recent_files', recent_files)

    def clear_recent_files(self):
        """Clear the recent files list"""
        self.set('recent_files', [])

    def get_prompt_templates(self):
        """Get the saved prompt templates"""
        return self.get('prompts', {})

    def add_prompt_template(self, name, prompt):
        """Add or update a prompt template"""
        prompts = self.get_prompt_templates()
        prompts[name] = prompt
        self.set('prompts', prompts)

    def remove_prompt_template(self, name):
        """Remove a prompt template"""
        prompts = self.get_prompt_templates()
        if name in prompts:
            del prompts[name]
            self.set('prompts', prompts)

    def restore_defaults(self, include_prompts=False):
        """
        Reset configuration to default values

        Args:
            include_prompts: Whether to reset prompt templates as well
        """
        # Default settings
        defaults = {
            # API settings
            'api_type': 'openai',
            'api_key': '',
            'model': 'gpt-4o-mini',
            'openai_base_url': '',
            'ollama_url': 'http://localhost:11434',
            'ollama_model': '',
            'rate_limit': 20,

            # UI settings
            'theme': 'system',
            'max_recent_files': 10,

            # Default prompts
            'default_system_prompt': 'You are a data manipulation assistant. Transform the cell content according to the user\'s instructions.',

            # Processing settings
            'temperature': 0.3,
            'max_tokens': 150,
            'batch_size': 10,

            # Display settings
            'column_width': 100,
            'auto_resize_columns': True,

            # Logging settings
            'save_logs': True,
            'log_level': 'INFO',
        }

        # Reset config to defaults (keeping recent files)
        recent_files = self._config.get('recent_files', [])

        for key, value in defaults.items():
            self._config[key] = value

        # Keep recent files unless explicitly resetting everything
        if not include_prompts:
            self._config['recent_files'] = recent_files
        else:
            self._config['recent_files'] = []
            # Reset prompts to defaults
            default_prompts = {
                # Basic text transformation
                'Capitalize': 'Capitalize all text in this cell.',
                'To Uppercase': 'Convert all text to uppercase.',
                'To Lowercase': 'Convert all text to lowercase.',
                'Sentence Case': 'Format the text in sentence case (capitalize first letter of each sentence).',
                'Title Case': 'Format the text in title case (capitalize first letter of each word, except for articles, prepositions, and conjunctions).',
                'Remove Extra Spaces': 'Remove all extra whitespace, including double spaces and leading/trailing spaces.',

                # Data formatting
                'Format Date': 'Format this as a standard date (YYYY-MM-DD).',
                'Format Phone Number': 'Format this as a standard phone number.',
                'Format Currency': 'Format this as a standard currency value.',
                'Format Percentage': 'Format this as a percentage.',
                'Extract Numbers': 'Extract all numbers from this text.',
                'Format Address': 'Format this as a properly structured address with standard capitalization.',
                'Format Email': 'Format this as a proper email address (lowercase, no extra spaces).',

                # Content transformation
                'Summarize': 'Summarize this text in one sentence.',
                'Expand': 'Expand this abbreviated or short text with more details while maintaining its meaning.',
                'Bullet Points': 'Convert this text into a bulleted list of key points.',
                'Fix Grammar': 'Fix any grammar or spelling errors in this text.',
                'Simplify': 'Simplify this text to make it easier to understand while preserving the key information.',
                'Formalize': 'Rewrite this text in a more formal, professional tone.',
                'Casualize': 'Rewrite this text in a more casual, conversational tone.',

                # Code and markup handling
                'Format JSON': 'Format this as valid, properly indented JSON.',
                'Format XML': 'Format this as valid, properly indented XML.',
                'Format CSV': 'Format this as valid CSV with proper delimiters and escaping.',
                'HTML to Text': 'Convert this HTML to well-structured plain text, preserving the semantic structure.',
                'Markdown to Text': 'Convert this Markdown to plain text while preserving the content structure.',
                'Clean Code': 'Clean up and format this code snippet with proper indentation and style.',

                # Multi-language translation
                'Translate to English': 'Translate this text to English.',
                'Translate to Arabic': 'Translate this text to Arabic.',
                'Translate to Hebrew': 'Translate this text to Hebrew.',

                # Data cleanup
                'Remove Duplicates': 'Remove any duplicate information from this text.',
                'Remove HTML Tags': 'Remove all HTML tags from this text, keeping only the content.',
                'Fix Encoding Issues': 'Fix text encoding issues like garbled characters or HTML entities.',
                'Fill Blank': 'Complete the blank or missing information in this cell based on context from surrounding cells.',
                'Standardize Format': 'Standardize the format of this data according to conventions.',
                'Extract Dates': 'Extract all dates from this text and format them consistently.',

                # Name handling
                'Split Name': 'Split this full name into separate first name and last name components.',
                'Format Name': 'Format this name with proper capitalization and spacing.',

                # Special formats
                'Convert to Citation': 'Convert this reference information to a proper citation format.',
            }
            self._config['prompts'] = default_prompts

        # Save the restored defaults
        self.save()

# """
# Configuration manager for the Excel AI Assistant.
# Handles loading, saving, and accessing application configuration settings.
# """
#
# import json
# import platform
# from pathlib import Path
#
#
# class AppConfig:
#     """Application configuration manager"""
#
#     def __init__(self):
#         """Initialize configuration with default values"""
#         # Default configuration
#         self._config = {
#             # API settings
#             'api_type': 'openai',  # 'openai' or 'ollama'
#             'api_key': '',  # OpenAI API key
#             'model': 'gpt-3.5-turbo',  # Current selected model
#             'ollama_url': 'http://localhost:11434',  # Ollama API URL
#             'ollama_model': 'llama3',  # Default Ollama model
#
#             # UI settings
#             'theme': 'system',
#             'recent_files': [],
#             'max_recent_files': 10,
#
#             # Default prompts
#             'default_system_prompt': 'You are a data manipulation assistant. Transform the cell content according to the user\'s instructions.',
#
#             # Processing settings
#             'temperature': 0.3,
#             'max_tokens': 150,
#             'batch_size': 10,  # Number of cells to process in a batch
#
#             # Display settings
#             'column_width': 100,
#             'auto_resize_columns': True,
#
#             # Logging settings
#             'save_logs': True,
#             'log_level': 'INFO',
#
#             # Predefined prompts
#             'prompts': {
#                 # Basic text transformation
#                 'Capitalize': 'Capitalize all text in this cell.',
#                 'To Uppercase': 'Convert all text to uppercase.',
#                 'To Lowercase': 'Convert all text to lowercase.',
#                 'Sentence Case': 'Format the text in sentence case (capitalize first letter of each sentence).',
#                 'Title Case': 'Format the text in title case (capitalize first letter of each word, except for articles, prepositions, and conjunctions).',
#                 'Remove Extra Spaces': 'Remove all extra whitespace, including double spaces and leading/trailing spaces.',
#
#                 # Data formatting
#                 'Format Date': 'Format this as a standard date (YYYY-MM-DD).',
#                 'Format Phone Number': 'Format this as a standard phone number.',
#                 'Format Currency': 'Format this as a standard currency value.',
#                 'Format Percentage': 'Format this as a percentage.',
#                 'Extract Numbers': 'Extract all numbers from this text.',
#                 'Format Address': 'Format this as a properly structured address with standard capitalization.',
#                 'Format Email': 'Format this as a proper email address (lowercase, no extra spaces).',
#
#                 # Content transformation
#                 'Summarize': 'Summarize this text in one sentence.',
#                 'Expand': 'Expand this abbreviated or short text with more details while maintaining its meaning.',
#                 'Bullet Points': 'Convert this text into a bulleted list of key points.',
#                 'Fix Grammar': 'Fix any grammar or spelling errors in this text.',
#                 'Simplify': 'Simplify this text to make it easier to understand while preserving the key information.',
#                 'Formalize': 'Rewrite this text in a more formal, professional tone.',
#                 'Casualize': 'Rewrite this text in a more casual, conversational tone.',
#
#                 # Code and markup handling
#                 'Format JSON': 'Format this as valid, properly indented JSON.',
#                 'Format XML': 'Format this as valid, properly indented XML.',
#                 'Format CSV': 'Format this as valid CSV with proper delimiters and escaping.',
#                 'HTML to Text': 'Convert this HTML to well-structured plain text, preserving the semantic structure.',
#                 'Markdown to Text': 'Convert this Markdown to plain text while preserving the content structure.',
#                 'Clean Code': 'Clean up and format this code snippet with proper indentation and style.',
#
#                 # Multi-language translation
#                 'Translate to English': 'Translate this text to English.',
#                 'Translate to Arabic': 'Translate this text to Arabic.',
#                 'Translate to Hebrew': 'Translate this text to Hebrew.',
#
#                 # Data cleanup
#                 'Remove Duplicates': 'Remove any duplicate information from this text.',
#                 'Remove HTML Tags': 'Remove all HTML tags from this text, keeping only the content.',
#                 'Fix Encoding Issues': 'Fix text encoding issues like garbled characters or HTML entities.',
#                 'Fill Blank': 'Complete the blank or missing information in this cell based on context from surrounding cells.',
#                 'Standardize Format': 'Standardize the format of this data according to conventions.',
#                 'Extract Dates': 'Extract all dates from this text and format them consistently.',
#
#                 # Name handling
#                 'Split Name': 'Split this full name into separate first name and last name components.',
#                 'Format Name': 'Format this name with proper capitalization and spacing.',
#                 'Extract Initials': 'Extract the initials from this name.',
#
#                 # Special formats
#                 'Convert to Citation': 'Convert this reference information to a proper citation format.',
#             }
#         }
#
#         # Load configuration from file
#         self._config_file = self._get_config_path()
#         self._load()
#
#     def _get_config_path(self):
#         """Get the platform-specific configuration file path"""
#         system = platform.system()
#         home = Path.home()
#
#         if system == 'Windows':
#             config_dir = home / 'AppData' / 'Roaming' / 'ExcelAIAssistant'
#         elif system == 'Darwin':  # macOS
#             config_dir = home / 'Library' / 'Application Support' / 'ExcelAIAssistant'
#         else:  # Linux and others
#             config_dir = home / '.config' / 'excel-ai-assistant'
#
#         # Create directory if it doesn't exist
#         config_dir.mkdir(parents=True, exist_ok=True)
#
#         return config_dir / 'config.json'
#
#     def _load(self):
#         """Load configuration from file"""
#         try:
#             if self._config_file.exists():
#                 with open(self._config_file, 'r', encoding='utf-8') as f:
#                     loaded_config = json.load(f)
#
#                     # Special handling for prompt templates - merge instead of replace
#                     if 'prompts' in loaded_config and 'prompts' in self._config:
#                         # First, save the default prompts
#                         default_prompts = self._config['prompts'].copy()
#
#                         # Update with loaded prompts
#                         self._config.update(loaded_config)
#
#                         # Merge prompts dictionaries, giving priority to user's custom prompts
#                         # but ensuring all default prompts are present
#                         merged_prompts = default_prompts.copy()
#                         merged_prompts.update(self._config['prompts'])
#                         self._config['prompts'] = merged_prompts
#                     else:
#                         # Regular update for other config items
#                         self._config.update(loaded_config)
#         except Exception as e:
#             print(f"Error loading configuration: {e}")
#             # Continue with default configuration
#
#     def save(self):
#         """Save current configuration to file"""
#         try:
#             with open(self._config_file, 'w', encoding='utf-8') as f:
#                 json.dump(self._config, f, indent=2)
#         except Exception as e:
#             print(f"Error saving configuration: {e}")
#
#     def get(self, key, default=None):
#         """Get a configuration value"""
#         return self._config.get(key, default)
#
#     def set(self, key, value):
#         """Set a configuration value"""
#         self._config[key] = value
#
#     def get_all(self):
#         """Get a copy of the entire configuration"""
#         return self._config.copy()
#
#     def get_active_model(self):
#         """Get the currently active model info"""
#         api_type = self.get('api_type', 'openai')
#         if api_type == 'openai':
#             return {
#                 'api_type': 'openai',
#                 'model': self.get('model', 'gpt-3.5-turbo')
#             }
#         else:  # ollama
#             return {
#                 'api_type': 'ollama',
#                 'model': self.get('ollama_model', 'llama3')
#             }
#
#     def set_active_model(self, api_type, model):
#         """Set the active model"""
#         self.set('api_type', api_type)
#         if api_type == 'openai':
#             self.set('model', model)
#         else:  # ollama
#             self.set('ollama_model', model)
#
#     def add_recent_file(self, file_path):
#         """Add a file to the recent files list"""
#         recent_files = self.get('recent_files', [])
#
#         # Remove if already in list
#         if file_path in recent_files:
#             recent_files.remove(file_path)
#
#         # Add to beginning of list
#         recent_files.insert(0, file_path)
#
#         # Trim to max size
#         max_count = self.get('max_recent_files', 10)
#         if len(recent_files) > max_count:
#             recent_files = recent_files[:max_count]
#
#         self.set('recent_files', recent_files)
#
#     def clear_recent_files(self):
#         """Clear the recent files list"""
#         self.set('recent_files', [])
#
#     def get_prompt_templates(self):
#         """Get the saved prompt templates"""
#         return self.get('prompts', {})
#
#     def add_prompt_template(self, name, prompt):
#         """Add or update a prompt template"""
#         prompts = self.get_prompt_templates()
#         prompts[name] = prompt
#         self.set('prompts', prompts)
#
#     def remove_prompt_template(self, name):
#         """Remove a prompt template"""
#         prompts = self.get_prompt_templates()
#         if name in prompts:
#             del prompts[name]
#             self.set('prompts', prompts)
