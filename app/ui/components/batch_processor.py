"""
Batch processing component for Excel AI Assistant.
Handles async batch processing of cells.
"""

import asyncio
import tkinter as tk
from typing import List, Dict, Any, Callable

from app.services.api_manager import APIManager


# noinspection PyTypeChecker
class BatchProcessor:
    """Handles batch processing of cells"""

    def __init__(self, root: tk.Tk, api_manager: APIManager, loop):
        """Initialize the batch processor"""
        self.root = root
        self.api_manager = api_manager
        self.loop = loop
        self.processing_cancelled = False
        self.current_task = None

    def process_batches(
            self,
            cells: List[Dict[str, Any]],
            system_prompt: str,
            user_prompt: str,
            batch_size: int,
            temperature: float,
            max_tokens: int,
            progress_callback: Callable[[int, int, int, int, str], None],
            completion_callback: Callable[[List[Dict[str, Any]], int, int], None]
    ):
        """
        Process cells in batches

        Args:
            cells: List of cell dictionaries with 'row', 'col', 'content' keys
            system_prompt: System prompt to use
            user_prompt: User prompt template
            batch_size: Size of batches to process
            temperature: Temperature parameter for API
            max_tokens: Maximum tokens for API response
            progress_callback: Callback function for progress updates
            completion_callback: Callback function when all processing is done
        """
        self.processing_cancelled = False

        # Create an async task for processing
        self.current_task = asyncio.run_coroutine_threadsafe(
            self._process_batches_async(
                cells,
                system_prompt,
                user_prompt,
                batch_size,
                temperature,
                max_tokens,
                progress_callback,
                completion_callback
            ),
            self.loop
        )

    def cancel_processing(self):
        """Cancel ongoing processing"""
        self.processing_cancelled = True

        if self.current_task and not self.current_task.done():
            self.current_task.cancel()

    async def _process_batches_async(
            self,
            cells: List[Dict[str, Any]],
            system_prompt: str,
            user_prompt: str,
            batch_size: int,
            temperature: float,
            max_tokens: int,
            progress_callback: Callable[[int, int, int, int, str], None],
            completion_callback: Callable[[List[Dict[str, Any]], int, int], None]
    ):
        """Process cells in batches asynchronously"""
        # Initialize counters
        processed = 0
        success_count = 0
        error_count = 0
        all_results = []

        try:
            # Split cells into batches
            batches = [cells[i:i + batch_size] for i in range(0, len(cells), batch_size)]

            for batch_idx, batch in enumerate(batches):
                if self.processing_cancelled:
                    break

                # Update status with batch info
                status_text = f"Processing batch {batch_idx + 1} of {len(batches)}..."
                self._update_progress(progress_callback, processed, success_count, error_count, len(cells), status_text)

                # Process each cell in the batch individually
                batch_results = []
                for cell_idx, cell in enumerate(batch):
                    if self.processing_cancelled:
                        break

                    # Process the cell
                    success, result, error = await self._process_single_cell_async(
                        cell, system_prompt, user_prompt, temperature, max_tokens
                    )

                    # Create result dictionary
                    cell_result = {
                        'row': cell['row'],
                        'col': cell['col'],
                        'success': success,
                        'result': result,
                        'error': error
                    }
                    batch_results.append(cell_result)

                    # Update counters
                    processed += 1
                    if success:
                        success_count += 1
                    else:
                        error_count += 1

                    # Update progress
                    self._update_batch_progress(
                        progress_callback, processed, success_count, error_count,
                        len(cells), cell_idx + 1, len(batch), batch_idx, len(batches)
                    )

                    # Small delay between cells to avoid rate limiting
                    await asyncio.sleep(0.0)

                # Add to all results
                all_results.extend(batch_results)

                # Update progress after batch
                status_text = f"Completed batch {batch_idx + 1} of {len(batches)}"
                self._update_progress(progress_callback, processed, success_count, error_count, len(cells), status_text)

                # Small delay between batches
                await asyncio.sleep(0.0)

            # Final update
            status = "Processing completed" if not self.processing_cancelled else "Processing cancelled"
            self._update_progress(progress_callback, processed, success_count, error_count, len(cells), status)

            # Call completion callback
            self._call_completion(completion_callback, all_results, success_count, error_count)

        except asyncio.CancelledError:
            # Handle cancellation
            self._update_progress(progress_callback, processed, success_count, error_count, len(cells),
                                  "Processing cancelled")
            self._call_completion(completion_callback, all_results, success_count, error_count)

        except Exception as e:
            # Handle other exceptions
            status = f"Error: {str(e)}"
            self._update_progress(progress_callback, processed, success_count, error_count, len(cells), status)
            self._call_completion(completion_callback, all_results, success_count, error_count)

    async def _process_single_cell_async(
            self,
            cell: Dict[str, Any],
            system_prompt: str,
            user_prompt: str,
            temperature: float,
            max_tokens: int
    ):
        """Process a single cell asynchronously"""
        try:
            cell_content = str(cell['content'])
            
            # Get context data from the cell if present
            context_data = cell.get('context_data', None)
            
            # Use a Future to run the API call in the default executor
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.api_manager.process_single_cell(
                    cell_content, system_prompt, user_prompt, temperature, max_tokens, context_data
                )
            )

            # Return the result (success, result, error)
            return result
        except Exception as e:
            return False, None, str(e)

    def _update_progress(
            self,
            callback: Callable[[int, int, int, int, str], None],
            processed: int,
            success_count: int,
            error_count: int,
            total: int,
            status: str
    ):
        """Update progress in main thread with error handling"""
        if callback:
            def safe_callback():
                try:
                    # Check if the window still exists before updating UI
                    if self.root.winfo_exists():
                        callback(processed, success_count, error_count, total, status)
                except Exception as e:
                    # Log error but don't crash
                    print(f"Error updating progress: {str(e)}")
            
            # Schedule the safe callback
            self.root.after(0, safe_callback)

    def _update_batch_progress(
            self,
            callback: Callable[[int, int, int, int, str], None],
            processed: int,
            success_count: int,
            error_count: int,
            total: int,
            batch_current: int,
            batch_total: int,
            batch_idx: int,
            total_batches: int
    ):
        """Update progress for a batch in main thread with error handling"""
        if callback:
            # Create status text
            status = f"Processing batch {batch_idx + 1} of {total_batches}: {batch_current}/{batch_total} cells"

            # Safe callback with error handling
            def safe_callback():
                try:
                    # Check if the window still exists before updating UI
                    if self.root.winfo_exists():
                        callback(processed, success_count, error_count, total, status)
                except Exception as e:
                    # Log error but don't crash
                    print(f"Error updating batch progress: {str(e)}")
            
            # Update in main thread
            self.root.after(0, safe_callback)

    def _call_completion(
            self,
            callback: Callable[[List[Dict[str, Any]], int, int], None],
            results: List[Dict[str, Any]],
            success_count: int,
            error_count: int
    ):
        """Call completion callback in main thread with error handling"""
        if callback:
            # Use a wrapped function to handle possible exceptions
            def safe_callback():
                try:
                    callback(results, success_count, error_count)
                except Exception as e:
                    print(f"Error in completion callback: {str(e)}")
                    # Log error to console but prevent crash
                    import logging
                    logging.exception("Error in batch completion callback")
            
            # Schedule the safe callback
            self.root.after(0, safe_callback)
