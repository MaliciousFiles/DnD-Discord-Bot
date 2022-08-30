import asyncio
import json
import os
import os.path as path
import platform
from tkinter import *
from tkinter.messagebox import askyesno

import re
import requests
import interactions
from interactions.ext.tasks import IntervalTrigger, create_task
import pystray
from PIL import Image
from appdirs import *
from dotenv import get_key, set_key

# Dirs
#
appname = "D&D Bot"
appauthor = "MaliciousFiles"
roaming_dir = user_data_dir(appname, appauthor, roaming=True)

if not path.exists(roaming_dir):
    os.makedirs(roaming_dir)

env_file = path.join(roaming_dir, ".env")
if not path.exists(env_file):
    with open(env_file, "x") as f:
        pass

data_file = path.join(roaming_dir, "data.json")
if not path.exists(data_file):
    with open(data_file, "x") as f:
        f.write("{}")

try:
    __file__ = __file__
except NameError:
    __file__ = sys.executable
icon_file = path.join(path.dirname(path.realpath(__file__)), "icon.png")

with open(data_file) as f:
    try:
        data = json.load(f)
    except json.JSONDecodeError:
        data = {}

def center(window):
    window.update_idletasks()

    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    size = tuple(int(_) for _ in window.geometry().split('+')[0].split('x'))
    x = screen_width/2 - size[0]/2
    y = screen_height/2 - size[1]/2

    window.geometry("+%d+%d" % (x, y))


def set_and_get_env(key: str, prompt: str, on_exit=None) -> str:
    window = Tk()
    window.title(appname)
    window.tk.call('wm', 'iconphoto', window._w, PhotoImage(file=icon_file))

    center(window)

    label = Label(window, text=prompt)
    label.pack(pady=(2.5, 7.5))

    def finish(event=None):
        set_key(env_file, key, input_.get(1.0, "end-1c"))
        window.destroy()

    frame = Frame(window)
    frame.pack(side=BOTTOM)

    input_ = Text(frame, height=1, width=30)
    input_.pack(side=LEFT, padx=(2.5, 0), pady=(0, 2.5))
    input_.bind("<Return>", finish)

    submit = Button(frame, text="Submit", command=finish)
    submit.pack(side=LEFT, padx=(10, 2.5), pady=(0, 2.5))

    def on_close():
        if askyesno("Confirm", "Are you sure you want to exit?"):
            window.destroy()

            if on_exit:
                on_exit()

            os._exit(0)

    window.protocol("WM_DELETE_WINDOW", on_close)

    window.mainloop()

    return get_key(env_file, key)


def get_or_set_env(key: str, prompt: str, on_exit=None) -> str:
    if not get_key(env_file, key):
        return set_and_get_env(key, prompt, on_exit)
    else:
        return get_key(env_file, key)


def quit_app():
    with open(data_file, "w") as f:
        json.dump(data, f)

    icon.visible = False
    icon.stop()

    os._exit(0)


token = get_or_set_env("BOT_AUTH_TOKEN", "Enter your Discord bot's Authentication Token:", quit_app)

error = True
while error:
    error = False
    try:
        bot = interactions.Client("MTAxMzk2NDc0MzE4NDIyODM4Mw.Gm7AhJ.RAUgGwrVdUOBLKfwMHBh7SNoKdhtyw2FgYXagM")
    except Exception as e:
        print(e)
        error = True
        set_and_get_env("BOT_AUTH_TOKEN", "Saved Discord Authentication Token is invalid! Enter the correct one below, then the app will restart:")

        os.startfile(__file__)
        os._exit(0)


@bot.event
async def on_ready():
    icon.visible = True

    for guild in bot.guilds:
        if not data.__contains__(str(guild.id)):
            data[str(guild.id)] = {}


@bot.event
async def on_guild_join(guild):
    data[str(guild.id)] = {}


@bot.event
async def on_guild_remove(guild):
    del data[str(guild.id)]


# Commands
@bot.command(
    name="link",
    description="Link your Adventurer's Codex character sheet.",
    scope=bot.guilds,
    options=[
        interactions.Option(
            name="link",
            description="The share link of your character sheet.",
            type=interactions.OptionType.STRING,
            required=True,
        )
    ]
)
async def link(ctx: interactions.CommandContext, link: str):
    r = None
    try:
        r = requests.get(link)
    except requests.exceptions.MissingSchema:
        pass

    pattern = re.compile("(https://)?(app.adventurerscodex.com/share/[a-z0-9]{12})")

    if not pattern.match(link) and (not r or r.status_code != 200):
        await ctx.send(embeds=interactions.Embed(title="Invalid Link", description="Link does not match format of Adventurer's Codex 'share' links!", color=interactions.Color.red()))
    else:
        await ctx.send(embeds=interactions.Embed(title="Link Saved", description="Character sheet link saved!", color=interactions.Color.green()))
        data[str(ctx.guild.id)][str(ctx.author.id)] = link if link.startswith("https://") else "https://"+link

def confirm_quit():
    if askyesno("Confirm", "Are you sure you want to exit?"):
        quit_app()


menu = (
    pystray.MenuItem("Confirm Quit", confirm_quit, default=True, visible=False),
    pystray.MenuItem("Quit", quit_app)
)
icon = pystray.Icon(name=appname, icon=Image.open(icon_file), title=appname, menu=menu)


icon.run(lambda thing: bot.start())