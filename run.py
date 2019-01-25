#!/usr/bin/env python3
import os, sys
from subprocess import Popen

os.chdir(os.path.dirname(os.path.abspath(__file__)))

Popen((sys.executable, 'batch_bot.py'))
Popen((sys.executable, 'batch_bot-recheck.py'))
