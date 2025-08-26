#!/usr/bin/env python
"""
Script to run the DAMFC simulation.
"""

import sys
import os
import runpy

if __name__ == "__main__":
    print("Starting DAMFC Simulation Framework...")
    print("-" * 50)
    
    # Check if output directory exists, create if not
    output_dir = os.path.join(os.path.dirname(__file__), 'output')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")
    
    # Add the damfc directory to Python path so imports work
    damfc_path = os.path.join(os.path.dirname(__file__), 'damfc')
    sys.path.insert(0, damfc_path)
    
    # Run main.py as a script (this will execute the if __name__ == "__main__" block)
    main_path = os.path.join(damfc_path, 'main.py')
    runpy.run_path(main_path, run_name="__main__")
    
    print("-" * 50)
    print("Simulation complete. Check the output/ folder for results.")