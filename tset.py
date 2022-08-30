import asyncio
import json
import os
import os.path as path
import platform
from tkinter import *
from tkinter.messagebox import askyesno

import interactions
from interactions.ext.tasks import IntervalTrigger, create_task
import pystray
from PIL import Image
from appdirs import *
from dotenv import get_key, set_key

client = interactions.Client("MTAxMzk2NDc0MzE4NDIyODM4Mw.Gm7AhJ.RAUgGwrVdUOBLKfwMHBh7SNoKdhtyw2FgYXagM")

client.start()