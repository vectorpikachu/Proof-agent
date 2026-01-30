#!/usr/bin/env python3
"""
Script to copy files starting with 'pfstate_emb' or 'lemma_emb' 
from /data2/lhz/experimental-results/ to emb_prompts_only/,
preserving the directory structure.
"""

import os
import shutil
from pathlib import Path

def copy_emb_files():
    source_dir = Path("/data2/lhz/experimental-results")
    target_dir = source_dir / "emb_prompts_only"
    
    # Create target directory if it doesn't exist
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"Created/verified target directory: {target_dir}")
    
    # Counters for reporting
    copied_count = 0
    skipped_count = 0
    
    # Walk through all files in source directory
    for root, dirs, files in os.walk(source_dir):
        # Skip the target directory itself to avoid recursion
        if "emb_prompts_only" in root:
            continue
            
        for file in files:
            # Check if file starts with pfstate_emb or lemma_emb
            if file.startswith("pfstat_emb") or file.startswith("lemma_emb"):
                source_path = Path(root) / file
                
                # Calculate relative path from source directory
                relative_path = source_path.relative_to(source_dir)
                target_path = target_dir / relative_path
                
                # Create target directory structure if needed
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy the file
                try:
                    shutil.copy2(source_path, target_path)
                    print(f"Copied: {relative_path}")
                    copied_count += 1
                except Exception as e:
                    print(f"Error copying {relative_path}: {e}")
                    skipped_count += 1
            else:
                skipped_count += 1
    
    print(f"\nSummary:")
    print(f"  Files copied: {copied_count}")
    print(f"  Files skipped: {skipped_count}")

if __name__ == "__main__":
    copy_emb_files()

