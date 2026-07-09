import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stakemap_app import StakeMapApp

def main():
    app = StakeMapApp()
    app.run()

if __name__ == "__main__":
    main()
