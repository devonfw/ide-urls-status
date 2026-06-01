#!/usr/bin/env python3
"""
Script to efficiently copy all status.json files preserving their directory structure.
Supports resumable operation with progress tracking to avoid reprocessing files.

Usage:
    python copy_status_json.py <SOURCE_DIRECTORY>

Args:
    SOURCE_DIRECTORY  - Path to the source directory containing status.json files (REQUIRED)
"""

import json
import shutil
import sys
from pathlib import Path
from typing import Set, List, Tuple
from datetime import datetime


class StatusJsonCopier:
    def __init__(self, source: Path, target: Path, progress_file: Path):
        """
        Initialize the copier.

        Args:
            source: Root source directory to search for status.json files
            target: Target directory to copy files to
            progress_file: File to track migration progress
        """
        self.source = source
        self.target = target
        self.progress_file = progress_file
        self.completed_files: Set[str] = set()
        self.failed_files: List[Tuple[str, str]] = []
        self.successful_count = 0
        self.files_copied_this_run = 0

    def load_progress(self) -> None:
        """Load progress from the progress file if it exists."""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, "r") as f:
                    data = json.load(f)
                    self.completed_files = set(data.get("completed", []))
                    self.failed_files = data.get("failed", [])
                    self.successful_count = len(self.completed_files)
                    print(f"Loaded progress: {self.successful_count} files already copied")
                    if self.failed_files:
                        print(f"Found {len(self.failed_files)} previously failed files")
            except Exception as e:
                print(f"Error loading progress file: {e}")
                print("    Starting fresh migration...")

    def save_progress(self) -> None:
        """Save current progress to the progress file."""
        progress_data = {
            "completed": list(self.completed_files),
            "failed": self.failed_files,
            "total_successful": self.successful_count,
            "timestamp": datetime.now().isoformat(),
        }
        try:
            self.progress_file.write_text(json.dumps(progress_data, indent=2))
        except Exception as e:
            print(f"Error saving progress: {e}")

    def find_status_json_files(self) -> List[Path]:
        """
        Find all status.json files in the source directory.

        Returns:
            List of Path objects pointing to status.json files
        """
        print("Searching for status.json files...")
        files = list(self.source.rglob("status.json"))
        # Exclude the progress file itself and the script
        files = [f for f in files if f != self.progress_file and f.parent != self.source]
        print(f"    Found {len(files)} status.json files")
        return files

    def copy_file(self, source_file: Path) -> bool:
        """
        Copy a single file preserving directory structure.

        Args:
            source_file: Path to the file to copy

        Returns:
            True if successful, False otherwise
        """
        try:
            # Calculate relative path from source root
            relative_path = source_file.relative_to(self.source)
            target_file = self.target / relative_path

            # Create parent directories if they don't exist
            target_file.parent.mkdir(parents=True, exist_ok=True)

            # Copy the file
            shutil.copy2(source_file, target_file)
            return True

        except Exception as e:
            error_msg = str(e)
            self.failed_files.append((str(source_file), error_msg))
            print(f"Error copying {source_file.name}: {error_msg}")
            return False

    def print_progress_bar(self, current: int, total: int, failed: int = 0) -> None:
        """Print a single-line progress bar."""
        percent = (current / total) * 100
        bar_length = 30
        filled = int(bar_length * current / total)
        bar = "=" * filled + "-" * (bar_length - filled)

        # Print on same line by using \r (carriage return)
        print(f"\r[{bar}] {current:,}/{total:,} | {percent:5.1f}% | Failed: {failed:,}", end="", flush=True)

    def run(self) -> None:
        """Execute the migration process."""
        print("\n" + "=" * 70)
        print("STATUS.JSON MIGRATION TOOL")
        print("=" * 70)
        print(f"Source:   {self.source}")
        print(f"Target:   {self.target}")
        print(f"Progress: {self.progress_file}")
        print("=" * 70 + "\n")

        # Load existing progress
        self.load_progress()

        # Find all files
        all_files = self.find_status_json_files()

        if not all_files:
            print("[OK] No status.json files found to copy!")
            return

        # Filter out already completed files
        remaining_files = [f for f in all_files if str(f.relative_to(self.source)) not in self.completed_files]

        if not remaining_files:
            print(f"All {self.successful_count} files have already been copied!")
            print("     Migration complete with no new files to process.")
            return

        print(f"Files to process: {len(remaining_files)} (of {len(all_files)} total)")
        print("     Starting migration...\n")

        # Process each file
        for idx, source_file in enumerate(remaining_files, 1):
            if self.copy_file(source_file):
                self.completed_files.add(str(source_file.relative_to(self.source)))
                self.successful_count += 1
                self.files_copied_this_run += 1
                self.save_progress()

            # Update progress bar
            self.print_progress_bar(idx, len(remaining_files), len(self.failed_files))

        # Print summary
        print("\n\n" + "=" * 70)
        print("MIGRATION SUMMARY")
        print("=" * 70)
        print(f" Successfully copied:  {self.successful_count:,} files")
        print(f"Failed:                {len(self.failed_files):,} files")
        print(f"Copied this run:       {self.files_copied_this_run:,} files")
        print("=" * 70)

        if self.failed_files:
            print("\n Failed files:")
            for source, error in self.failed_files:
                print(f"  * {source}")
                print(f"    Error: {error}")

        if self.successful_count > 0:
            print(f"\n Migration progress saved to: {self.progress_file}")


def parse_arguments():
    """Parse command-line arguments and return source, target, and progress paths."""
    if len(sys.argv) < 2:
        print("Error: Missing required argument")
        print("\nUsage:")
        print("  python copy_status_json.py <SOURCE_DIRECTORY>")
        print("\nArgs:")
        print("  SOURCE_DIRECTORY  - Path to the source directory containing status.json files")
        sys.exit(1)

    if len(sys.argv) > 2:
        print("Error: Too many arguments (only 1 argument allowed)")
        print("\nUsage:")
        print("  python copy_status_json.py <SOURCE_DIRECTORY>")
        sys.exit(1)

    source_path = Path(sys.argv[1])
    # Target is the directory where this script is located
    target_path = Path(__file__).parent

    # Create progress file in the target directory
    progress_file = target_path / ".copy_progress.json"

    return source_path, target_path, progress_file


def main():
    # Parse arguments
    source_path, target_path, progress_file = parse_arguments()

    # Check if source directory exists
    if not source_path.exists():
        print(f"Error: Source directory not found: {source_path}")
        sys.exit(1)

    # Create copier and run migration
    copier = StatusJsonCopier(source_path, target_path, progress_file)

    try:
        copier.run()
    except KeyboardInterrupt:
        print("\n\n Migration interrupted by user")
        copier.save_progress()
        print(f"Progress saved. You can resume by running the script again.")
        sys.exit(0)
    except Exception as e:
        print(f"\n Fatal error: {e}")
        copier.save_progress()
        sys.exit(1)


if __name__ == "__main__":
    main()

