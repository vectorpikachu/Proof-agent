#!/usr/bin/env python3
"""
Script to clean hammer cache by removing files where the result is None.

This script scans all files in hammer cache directory/directories, loads each pickle file,
and either:
1. DELETE mode (default): Deletes files if the result (first element of tuple) is None
2. COPY mode (--output-dir): Copies files with non-None results to an output directory
   - Supports multiple input directories for merging caches
   - Overwrites duplicate cache files (same filename) from later directories
"""

import os
import pickle
import argparse
import shutil
from typing import Tuple, Optional


def load_cache_file(filepath: str) -> Optional[Tuple]:
    """
    Load a cache file and return its contents.
    
    Args:
        filepath: Path to the cache file
        
    Returns:
        The cached tuple (result, err) or None if loading failed
    """
    try:
        with open(filepath, 'rb') as f:
            return pickle.load(f)
    except Exception as e:
        print(f"Warning: Failed to load {filepath}: {e}")
        return None


def copy_successful_cache(hammer_cache_dirs: list, output_dir: str, dry_run: bool = False) -> None:
    """
    Copy hammer cache files where result is NOT None to output directory.
    Processes multiple source directories and overwrites duplicates.
    
    Args:
        hammer_cache_dirs: List of directories containing hammer cache files
        output_dir: Directory to copy successful cache files to
        dry_run: If True, only print what would be copied without actually copying
    """
    # Create output directory if it doesn't exist (unless dry run)
    if not dry_run and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        print(f"Created output directory: {output_dir}")
    
    total_copied_count = 0
    total_skipped_count = 0
    total_failed_count = 0
    total_files_scanned = 0
    total_overwritten_count = 0

    copied_files = set[str]([])
    
    for dir_idx, hammer_cache_dir in enumerate(hammer_cache_dirs, 1):
        print(f"\n{'='*60}")
        print(f"Processing directory {dir_idx}/{len(hammer_cache_dirs)}: {hammer_cache_dir}")
        print(f"{'='*60}")
        
        if not os.path.exists(hammer_cache_dir):
            print(f"Error: Directory {hammer_cache_dir} does not exist - skipping")
            continue
        
        if not os.path.isdir(hammer_cache_dir):
            print(f"Error: {hammer_cache_dir} is not a directory - skipping")
            continue
        
        files = os.listdir(hammer_cache_dir)
        dir_files = len(files)
        copied_count = 0
        skipped_count = 0
        failed_count = 0
        overwritten_count = 0
        
        print(f"Scanning {dir_files} files in {hammer_cache_dir}")
        
        for filename in files:
            filepath = os.path.join(hammer_cache_dir, filename)
            
            # Skip if it's not a file
            if not os.path.isfile(filepath):
                continue
            
            # Load the cache file
            cached_data = load_cache_file(filepath)
            
            if cached_data is None:
                # Failed to load - could be corrupt
                failed_count += 1
                continue
            
            # Check if it's a tuple with at least one element
            if not isinstance(cached_data, tuple) or len(cached_data) < 1:
                print(f"Warning: Unexpected format in {filepath}")
                failed_count += 1
                continue
            
            result = cached_data[0]
            
            # Copy if result is NOT None
            if result is not None:
                output_filepath = os.path.join(output_dir, filename)
                is_overwrite = filename in copied_files
                copied_files.add(filename)
                
                if dry_run:
                    action = "overwrite" if is_overwrite else "copy"
                    print(f"Would {action}: {filepath} -> {output_filepath}")
                    if is_overwrite:
                        overwritten_count += 1
                    else:
                        copied_count += 1
                else:
                    try:
                        shutil.copy2(filepath, output_filepath)
                        action = "Overwrote" if is_overwrite else "Copied"
                        print(f"{action}: {filename}")
                        if is_overwrite:
                            overwritten_count += 1
                    except Exception as e:
                        print(f"Error copying {filepath}: {e}")
                        failed_count += 1
                        continue
            else:
                skipped_count += 1
        
        print(f"\nDirectory Summary:")
        print(f"  Files scanned: {dir_files}")
        print(f"  Files {'that would be ' if dry_run else ''}copied (result != None): {copied_count}")
        print(f"  Files {'that would be ' if dry_run else ''}overwritten: {overwritten_count}")
        print(f"  Files skipped (result == None): {skipped_count}")
        print(f"  Files with errors: {failed_count}")
        
        total_files_scanned += dir_files
        total_copied_count += copied_count
        total_skipped_count += skipped_count
        total_failed_count += failed_count
        total_overwritten_count += overwritten_count
    
    print(f"\n{'='*60}")
    print(f"{'DRY RUN - ' if dry_run else ''}TOTAL SUMMARY (across all directories):")
    print(f"{'='*60}")
    print(f"  Directories processed: {len(hammer_cache_dirs)}")
    print(f"  Total files scanned: {total_files_scanned}")
    print(f"  Total files {'that would be ' if dry_run else ''}copied (result != None): {total_copied_count}")
    print(f"  Total files {'that would be ' if dry_run else ''}overwritten: {total_overwritten_count}")
    print(f"  Total files skipped (result == None): {total_skipped_count}")
    print(f"  Total files with errors: {total_failed_count}")


def clear_hammer_cache(hammer_cache_dir: str, dry_run: bool = False) -> None:
    """
    Clear hammer cache files where result is None.
    
    Args:
        hammer_cache_dir: Directory containing hammer cache files
        dry_run: If True, only print what would be deleted without actually deleting
    """
    if not os.path.exists(hammer_cache_dir):
        print(f"Error: Directory {hammer_cache_dir} does not exist")
        return
    
    if not os.path.isdir(hammer_cache_dir):
        print(f"Error: {hammer_cache_dir} is not a directory")
        return
    
    files = os.listdir(hammer_cache_dir)
    total_files = len(files)
    deleted_count = 0
    failed_count = 0
    
    print(f"Scanning {total_files} files in {hammer_cache_dir}")
    
    for filename in files:
        filepath = os.path.join(hammer_cache_dir, filename)
        
        # Skip if it's not a file
        if not os.path.isfile(filepath):
            continue
        
        # Load the cache file
        cached_data = load_cache_file(filepath)
        
        if cached_data is None:
            # Failed to load - could be corrupt
            failed_count += 1
            continue
        
        # Check if it's a tuple with at least one element
        if not isinstance(cached_data, tuple) or len(cached_data) < 1:
            print(f"Warning: Unexpected format in {filepath}")
            failed_count += 1
            continue
        
        result = cached_data[0]
        
        # Delete if result is None
        if result is None:
            if dry_run:
                print(f"Would delete: {filepath}")
            else:
                try:
                    os.remove(filepath)
                    print(f"Deleted: {filepath}")
                except Exception as e:
                    print(f"Error deleting {filepath}: {e}")
                    failed_count += 1
                    continue
            deleted_count += 1
    
    print(f"\n{'DRY RUN - ' if dry_run else ''}Summary:")
    print(f"  Total files scanned: {total_files}")
    print(f"  Files {'that would be ' if dry_run else ''}deleted: {deleted_count}")
    print(f"  Files with errors: {failed_count}")
    print(f"  Files kept: {total_files - deleted_count - failed_count}")


def main():
    parser = argparse.ArgumentParser(
        description='Manage hammer cache files: delete files where result is None OR copy files where result is not None',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Delete mode: Remove files where result is None (default)
  %(prog)s /path/to/hammer_cache

  # Copy mode: Copy files where result is NOT None to output directory (single source)
  %(prog)s /path/to/hammer_cache --output-dir /path/to/output

  # Copy mode: Merge multiple cache directories (overwrites duplicates)
  %(prog)s /path/to/cache1 /path/to/cache2 /path/to/cache3 --output-dir /path/to/merged_output

  # Dry run to preview changes
  %(prog)s /path/to/hammer_cache --dry-run
  %(prog)s /path/to/cache1 /path/to/cache2 --output-dir /path/to/output --dry-run
        """
    )
    parser.add_argument(
        'hammer_cache_dirs',
        type=str,
        nargs='+',
        help='Path(s) to hammer cache directory/directories. Multiple directories can be specified for copy mode.'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Output directory to copy successful cache files (result != None). If specified, enters COPY mode instead of DELETE mode. Supports multiple input directories.'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually making changes'
    )
    
    args = parser.parse_args()
    
    if args.output_dir:
        # Copy mode: copy files with result != None
        print("=== COPY MODE: Copying files with non-None results ===")
        if len(args.hammer_cache_dirs) > 1:
            print(f"=== Merging {len(args.hammer_cache_dirs)} cache directories ===\n")
        print(args.hammer_cache_dirs)
        copy_successful_cache(args.hammer_cache_dirs, args.output_dir, dry_run=args.dry_run)
    else:
        # Delete mode: delete files with result == None
        if len(args.hammer_cache_dirs) > 1:
            print("Warning: Multiple directories specified but DELETE mode only processes first directory.")
            print("Use --output-dir for COPY mode to process multiple directories.\n")
        print("=== DELETE MODE: Removing files with None results ===\n")
        clear_hammer_cache(args.hammer_cache_dirs[0], dry_run=args.dry_run)


if __name__ == '__main__':
    main()

