#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb  3 00:06:12 2025

@author: lukerichards
"""
from pathlib import Path

class PathFinder:

    def find(self, directory=None, suffix=None, prefix=None,
             file_and_directory=False):
        """
        Modernized version of your file finder using pathlib
        Returns sorted list of matching Path objects
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {dir_path}")
    
        # Normalize input parameters
        ext_tuple = tuple(suffix) if isinstance(suffix, list) else suffix
        start_tuple = tuple(prefix) if isinstance(prefix, list) else prefix
    
        matches = []
        for path in dir_path.rglob('*'):
            if not path.is_file():
                continue
    
            # Check extensions
            if ext_tuple and path.suffix not in ext_tuple:
                continue
                
            # Check filename prefixes
            if start_tuple and not path.name.startswith(start_tuple):
                continue
    
            else:
                matches.append(path)
    
        if not matches:
            raise FileNotFoundError(f"No files found matching criteria in {dir_path}")
    
        # Sort by modification time
        sorted_paths = sorted(matches, key=lambda p: p.stat().st_mtime)
        
        if file_and_directory:
            dirs = list({p.parent for p in sorted_paths})
            dirs.sort(key=lambda p: p.stat().st_mtime)
            return sorted_paths, dirs
            
        return sorted_paths