# -*- coding: utf-8 -*-
import sys
import os

# Adds the current directory to the path so python can import app
sys.path.insert(0, os.path.dirname(__file__))

# Import the Flask app
from app import app as application
