import atexit
import builtins
import json
import os
import os.path as path
import re
import signal
import subprocess
import sys
from tkinter import *
from tkinter.messagebox import askyesno
from zipfile import ZipFile

import interactions
import pystray
import requests
from PIL import Image
from appdirs import *
from dotenv import get_key, set_key

from ZSDR import roll_dice
from monster_scraper import cache_monsters

# TODO: make all embeds use the same formatting (periods, bolded inputs, etc)
# TODO: make most set commands also work as querying

SHARE_PREFIX = "https://app.adventurerscodex.com/share/"

DM_ROLE_KEY = "dm_role"
PLAYER_ROLE_KEY = "player_role"

INITIATIVE_KEY = "initiative"
INIT_EMBEDS_KEY = "initiative_embeds"
CURRENT_INITIATIVE_KEY = "current_initiative"

DATES_KEY = "dates"
TIMELINE_KEY = "timeline"
CAMPAIGN_START_KEY = "campaign_start"
CURRENT_DATE_KEY = "current_date"
CALENDAR_KEY = "calendar"

MONEY_KEY = "money"
EXPENSES_KEY = "expenses"
INCOME_KEY = "income"

MONTHS = ["Hammer", "Alturiak", "Ches", "Tarsakh", "Mirtul", "Kythorn", "Flamerule", "Eleasis", "Eleint", "Marpenoth",
          "Uktar", "Nightal"]
ALL_SPELLS = {}
SPELLS_BY_CLASS_AND_LEVEL = {}


def populate_spells():
    global ALL_SPELLS

    r = requests.get("http://dnd5e.wikidot.com/spells")
    pattern = re.compile("<a href=\"/spell:(.+?)\">(.+?)</a>")

    for match in pattern.finditer(r.text):
        ALL_SPELLS[match.group(2)] = match.group(1)

        # spell_r = requests.get("http://dnd5e.wikidot.com/spell:"+match.group(1))
        # spell_pattern = re.compile("spells:(.+?)\"")
        #
        # level_match = re.search("<em>([0-9]).+?-level|(cantrip).+?<\/em>", spell_r.text)
        # level = level_match.group(1) or level_match.group(2)
        #
        # for spell_group_match in spell_pattern.finditer(spell_r.text):
        #     spell_group = spell_group_match.group(1)
        #
        #     if spell_group not in SPELLS_BY_CLASS_AND_LEVEL:
        #         SPELLS_BY_CLASS_AND_LEVEL[spell_group] = {}
        #     if level not in SPELLS_BY_CLASS_AND_LEVEL[spell_group]:
        #         SPELLS_BY_CLASS_AND_LEVEL[spell_group][level] = {}
        #
        #     SPELLS_BY_CLASS_AND_LEVEL[spell_group][level][match.group(2)] = match.group(1)

    ALL_SPELLS = {key: ALL_SPELLS[key] for key in sorted(ALL_SPELLS)}


populate_spells()

# Dirs
#
appname = "D&D Bot"
appauthor = "MaliciousFiles"
roaming_dir = user_data_dir(appname, appauthor, roaming=True)
cache_dir = user_cache_dir(appname, appauthor)

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

MONSTER_COUNT = 2825
MONSTER_CR = ["1/8", "1/4", "1/2"] + [str(i) for i in range(1, 31)]
MONSTER_STATS = {}
MONSTER_ID_BY_NAME = {}
MONSTER_NAME_BY_ID = {}


def populate_monsters():
    reprint_cache = {}
    for key, value in MONSTER_STATS.items():
        name = value["name"]

        if name not in reprint_cache:
            has_reprints = len(list(filter(lambda stats: stats["name"] == name, MONSTER_STATS.values()))) > 1
            reprint_cache[name] = has_reprints
        else:
            has_reprints = reprint_cache[name]

        name = name + (" (" + key.split("-")[-1] + ")" if has_reprints else "")
        MONSTER_ID_BY_NAME[name] = key
        MONSTER_NAME_BY_ID[key] = name


MONSTER_STATS_CACHED = MONSTER_STATBLOCKS_CACHED = False
while not MONSTER_STATS_CACHED or not MONSTER_STATBLOCKS_CACHED:
    if not MONSTER_STATS_CACHED:
        monster_stats_file = path.join(cache_dir, "stats.json")
        if path.exists(monster_stats_file):
            with open(monster_stats_file) as f:
                MONSTER_STATS = json.load(f)
            MONSTER_STATS_CACHED = len(MONSTER_STATS) == MONSTER_COUNT

    if not MONSTER_STATBLOCKS_CACHED:
        monster_statblocks_file = path.join(cache_dir, "statblocks.zip")
        if path.exists(monster_statblocks_file):
            with ZipFile(monster_statblocks_file) as zipfile:
                for id_ in MONSTER_STATS:
                    MONSTER_STATBLOCKS_CACHED = len(zipfile.namelist()) == MONSTER_COUNT

    if __name__ == '__main__':
        cache_monsters(not MONSTER_STATS_CACHED and monster_stats_file,
                       not MONSTER_STATBLOCKS_CACHED and path.dirname(monster_statblocks_file))

populate_monsters()

try:
    __file__ = __file__
except NameError:
    __file__ = sys.executable
icon_file = path.join(path.dirname(path.realpath(__file__)), "icon.png")

with open(data_file) as f:
    try:
        DATA = json.load(f)  # TODO: make this convert the proper string integers into integers
    except json.JSONDecodeError:
        DATA = {}


def save_data():
    with open(data_file, "w") as f:
        json.dump(DATA, f)


def center(window):
    window.update_idletasks()

    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    size = tuple(int(_) for _ in window.geometry().split('+')[0].split('x'))
    x = screen_width / 2 - size[0] / 2
    y = screen_height / 2 - size[1] / 2

    window.geometry("+%d+%d" % (x, y))


def set_and_get_env(key: str, prompt: str, strip=False, on_exit=None) -> str:
    window = Tk()
    window.title(appname)
    window.tk.call('wm', 'iconphoto', window._w, PhotoImage(file=icon_file))

    center(window)

    label = Label(window, text=prompt)
    label.pack(pady=(2.5, 7.5))

    def finish(event=None):
        i = input_.get(1.0, "end-1c")

        if strip:
            i = i.strip()

        set_key(env_file, key, i)
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


def get_or_set_env(key: str, prompt: str, strip=False, on_exit=None) -> str:
    if not get_key(env_file, key):
        return set_and_get_env(key, prompt, strip, on_exit)
    else:
        return get_key(env_file, key)


def quit_app(thing1=None, thing2=None):
    save_data()

    with open(monster_stats_file, "w") as f:
        json.dump(MONSTER_STATS, f)

    icon.visible = False
    icon.stop()

    os._exit(0)


token = get_or_set_env("BOT_AUTH_TOKEN", "Enter your Discord bot's Authentication Token:", True, quit_app).strip()

error = True
while error:
    error = False
    try:
        bot = interactions.Client(token)
    except Exception as e:
        print("[EXCEPTION] " + str(e))
        error = True
        set_and_get_env("BOT_AUTH_TOKEN",
                        "Saved Discord Authentication Token is invalid! Enter the correct one below, then the app will restart:",
                        True)

        subprocess.Popen([sys.executable, __file__], start_new_session=True, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)

        os._exit(0)


@bot.event
async def on_ready():
    icon.visible = True

    for guild in bot.guilds:
        if str(guild.id) not in DATA:
            DATA[str(guild.id)] = {}


@bot.event
async def on_guild_join(guild):
    DATA[str(guild.id)] = {}


@bot.event
async def on_guild_remove(guild):
    del DATA[str(guild.id)]


async def check_dm(ctx: interactions.CommandContext, player: interactions.Member):
    if DM_ROLE_KEY not in DATA[str(ctx.guild.id)]:
        await ctx.send(embeds=interactions.Embed(title="DM Role Not Found",
                                                 description="Use `/dm-role` to set a DM role doing this",
                                                 color=interactions.Color.red()), ephemeral=True)
        return False

    dm_role_id = int(DATA[str(ctx.guild.id)][DM_ROLE_KEY])
    if dm_role_id not in player.roles:
        await ctx.send(embeds=interactions.Embed(title="Must be DM", description="You must have " + (
            await ctx.guild.get_role(dm_role_id)).mention + " to do this", color=interactions.Color.red()),
                       ephemeral=True)
        return False

    return True


async def check_char_sheet(ctx: interactions.CommandContext, player: interactions.Member, self: bool = True):
    if not str(player.id) in DATA[str(ctx.guild.id)]:
        await ctx.send(embeds=interactions.Embed(title="No Character Linked",
                                                 description="Use `/account` to link your Adventurer's Codex account~~, and `/character` to set the character to use~~" if self else player.mention + " does not have an Adventurer's Codex character linked",
                                                 color=interactions.Color.red()), ephemeral=True)
        return False

    return True


def get_ability(player_id: str, ability: str, saving_throw: bool = False):
    if not (
            ability == "Strength" or ability == "Dexterity" or ability == "Constitution" or ability == "Intelligence" or ability == "Wisdom" or ability == "Charisma"):
        saving_throw = False

    r = requests.get(SHARE_PREFIX + player_id)

    match = re.search("[> ]" + ability + "[<\n].+?" + ("Saving Throw.+?" if saving_throw else "") + " ([+-] ?[0-9])", r.text,
                         re.RegexFlag.DOTALL)

    return (match.group(1).replace(" ", ""), "fa-check" in (r.text[match.span()[0]:match.span()[1]+50] if saving_throw else r.text[match.span()[0]-100:match.span()[1]]))


def get_stat(player_id: str, stat: str):
    r = requests.get(SHARE_PREFIX + player_id)

    pattern = re.compile("(?<=[> ]" + stat + "[<\n]).+? (-?[0-9])", re.RegexFlag.DOTALL)
    return pattern.search(r.text).group(1)


def add_to_initiative(guild: interactions.Guild, name: str, initiative: int, modifier: int):
    initiative_l = DATA[str(guild.id)][INITIATIVE_KEY]
    new_value = [name, str(initiative), str(modifier)]

    if len(initiative_l) == 0:
        initiative_l.append(new_value)
        return True

    index = None

    for idx, value in enumerate(initiative_l):
        if initiative > int(value[1]) or (initiative == int(value[1]) and modifier > int(value[2])):
            initiative_l.insert(idx, new_value)

            index = idx
            break
        elif idx == len(initiative_l) - 1:
            initiative_l.append(new_value)

            index = len(initiative_l) - 1
            break

    if index and index <= int(DATA[str(guild.id)][CURRENT_INITIATIVE_KEY]):
        DATA[str(guild.id)][CURRENT_INITIATIVE_KEY] = int(DATA[str(guild.id)][CURRENT_INITIATIVE_KEY]) + 1
        save_data()
    return index is not None


def is_date_later(date, check):
    date = [int(s) for s in date.split("-")]
    check = [int(s) for s in check.split("-")]

    return check[2] >= date[2] and check[1] >= date[1] and check[0] > date[0]


def get_spell_stat(text: str, stat: str):
    return re.sub("<.+?>|\n", "",
                  re.search("<strong>" + stat + ":</strong> (.+?)<[^/]+?>", text, flags=re.RegexFlag.DOTALL).group(1))


def format_date(guild: interactions.Guild, date):
    dates = DATA[str(guild.id)][DATES_KEY]

    date = [int(s) for s in date.split("-")]

    return f"{date[0]} {MONTHS[date[1]]}, {date[2]}{' ' + dates[CALENDAR_KEY] if CALENDAR_KEY in dates else ''}"


CALLBACK_IDS = {}


async def confirm_action(ctx, id: str, callback):
    confirm_message = "yes, I am sure"

    if id not in CALLBACK_IDS: CALLBACK_IDS[id] = 0
    modal = interactions.Modal(title="Confirm", components=[
        interactions.TextInput(style=interactions.TextStyleType.SHORT, label=f"Type '{confirm_message}' to confirm",
                               custom_id="confirm", required=True, min_length=len(confirm_message),
                               max_length=len(confirm_message), placeholder=confirm_message)],
                               custom_id=f"{id}-{CALLBACK_IDS[id]}")
    CALLBACK_IDS[id] += 1

    @bot.modal(modal)
    async def modal_response(ctx: interactions.ComponentContext, response: str):
        if response.lower() == confirm_message.lower():
            await callback(ctx)

    await ctx.popup(modal)
    await ctx.send(embeds=interactions.Embed(title=":warning: Confirm :warning:",
                                             description="Please confirm in the popup menu. This action **cannot be undone**!",
                                             color=interactions.Color.yellow()), ephemeral=True)
    # embed = interactions.Embed(title=":warning: Confirm :warning:", description="Are you sure you want to continue? This action **cannot be undone**!\n\n*10*", color=interactions.Color.yellow())
    # message = await ctx.send(embeds=embed, components=[interactions.Button(style=interactions.ButtonStyle.PRIMARY, label="Cancel", custom_id="confirm_cancel"), confirm_button])

    # try:
    #     i = 10
    #     while i > 0:
    #         embed.description = embed.description.replace(str(i), str(i-1))
    #         await message.edit(embeds=embed)
    #
    #         i -= 1
    #         await asyncio.sleep(1)
    #
    #     await message.delete()
    # except interactions.api.error.LibraryException:
    #     return


@bot.command(
    name="help",
    description="Help function to describe every command.",
    options=[
        interactions.Option(
            name="command",
            description="The name of the base command to further inspect.",
            type=interactions.OptionType.STRING,
            choices=[
                interactions.Choice(name="roll", value="roll"),
                interactions.Choice(name="init", value="init"),
                interactions.Choice(name="date", value="date"),
                interactions.Choice(name="money", value="money"),
                interactions.Choice(name="monster", value="monster")
            ]
        ),
        interactions.Option(
            name="subcommand",
            description="The name of the subcommand to further inspect.",
            type=interactions.OptionType.STRING,
            choices=[
                interactions.Choice(name="add", value="add"),
                interactions.Choice(name="remove", value="remove"),
                interactions.Choice(name="event", value="event"),
                interactions.Choice(name="income", value="income"),
                interactions.Choice(name="expense", value="expense")
            ]
        )
    ]
)
async def help(ctx: interactions.CommandContext, command: str = None, subcommand: str = None):
    if command == "roll":
        desc="""
        **ability:** roll a die based on an ability from your character sheet (must have sheet linked)
        **input:** roll a die based on input
        """
    elif command == "init":
        if subcommand == "add":
            desc = """
            [DM] = DM only
            
            **all-players:** add every player who has a sheet linked to the initiative [DM]
            **player:** add a player to the initiative (must have sheet linked) [DM]
            **other:** add a non-player to the initiative [DM]
            """
        elif subcommand == "remove":
            desc = """
            [DM] = DM only
            
            **player:** remove a player from the initiative [DM]
            **other:** remove a non-player from the initiative [DM]
            """
        else:
            desc = """
            \\* = base command, has subcommands (`/help init [command]` to show)
            [DM] = DM only
    
            **add\\*:** add something to the initiative order [DM]
            **remove\\*:** remove something from the initiative order [DM]
            **list:** list the initiative order
            **next:** advance the current initiative place [DM]
            **clear:** clear the initiative order [DM]
            """
    elif command == "date":
        if subcommand == "event":
            desc = """
            [DM] = DM only
            
            **add:** add an event to a day on the timeline [DM]
            **remove:** remove an event from a day on the timeline [DM]
            **clear:** clear all events from a day on the timeline [DM]
            **clear-all:** clear all events from every day on the timeline [DM]
            **list:** list all events from a day on the time line
            **search:** search for an event by title
            """
        else:
            desc = """
            \\* = base command, has subcommands (`/help date [command]` to show)
            [DM] = DM only
            
            **next:** advance the current date [DM]
            **calendar:** set or get the calendar suffix [DM, for set]
            **current:** set or get the current day [DM, for set]
            **origin:** set or get the campaign start day [DM, for set]
            **event\\*:** base command for events
            """
    elif command == "money":
        if subcommand == "income":
            desc = """
            **add:** add a source of income
            **remove:** remove a source of income
            **list:** list your sources of income
            **clear:** remove every source of income
            """
        elif subcommand == "expense":
            desc="""
            **add:** add an expense
            **remove:** remove an expense
            **list:** list your expenses
            **clear:** remove every expense
            """
        else:
            desc = """
            \\* = base command, has subcommands (`/help money [command]` to show)
            
            **income\\*:** base command for income
            **expense\\*:** base command for expenses
            """
    elif command == "monster":
        desc = """
        **statblock:** get the statblock for a specific monster
        **search:** search for a monster with the given criteria
        """
    else:
        desc = """
        \\* = base command, has subcommands (`/help [command]` to show)

        **account:** link your Adventurer's Codex character sheet.
        **dm-role:** set the role that represents DMs.
        **roll\\*:** roll a die (dice roller courtesy of CommanderZero)
        **init\\*:** base command for initiative order
        **date\\*:** base command for date and event tracking
        **money\\*:** base command for income and expenses tracking
        **spell**: query a spell (from the dnd5e.wikidot.com library)
        **monster\\*:** search for monsters (from the 5e.tools library)
        """

    await ctx.send(embeds=interactions.Embed(title="Help" + (" '"+command+"'" if command else ""), description=desc, color=interactions.Color.blurple()), ephemeral=True)


@bot.command(
    name="dm-help",
    description="Get a help message for the DM."
)
async def dm_help(ctx: interactions.CommandContext):
    if not await check_dm(ctx, ctx.author): return

    desc = """
    Here are some tips for using this bot effectively. For more detailed descriptions, use `/help`.
    
   
    **date:** the date command allows you to keep track of events and run downtime on a day-to-day basis: make sure to set the calender suffix, campaign start, and current date, and remember you can always use relative dates instead of absolute
   
    **monster:** the monster command lets you pull up statblocks whenever you want; say goodbye to tons of tabs!
   
    **roll:** the roll command not only acts as a dice roller, but also allows you to secretly make a roll for another player [say, perception ;)]
    """

    await ctx.send(embeds=interactions.Embed(title="DM Help", description=desc, color=interactions.Color.blurple()), ephemeral=True)

@bot.command(
    name="account",
    description="Submit your Adventurer's Codex credentials.",
    options=[
        interactions.Option(
            name="link",
            description="The share link of your character sheet.",
            type=interactions.OptionType.STRING,
            required=True,
        )
    ]
)
async def account_command(ctx: interactions.CommandContext, link: str):
    # TODO make this take in account credentials instead, and figure out auth flow
    value = link[-12: len(link)]
    link = SHARE_PREFIX + value

    r = None
    try:
        r = requests.get(link)
    except requests.exceptions.ConnectionError:
        pass

    if not r or r.status_code != 200:
        await ctx.send(embeds=interactions.Embed(title="Invalid Link",
                                                 description="Link does not match format of Adventurer's Codex 'share' links",
                                                 color=interactions.Color.red()), ephemeral=True)
    else:
        await ctx.send(embeds=interactions.Embed(title="Link Saved", description="Character sheet link saved",
                                                 color=interactions.Color.green()), ephemeral=True)
        DATA[str(ctx.guild.id)][str(ctx.author.id)] = link[-12: len(link)]
        save_data()


@bot.command(
    name="dm-role",
    description="Set the role that denotes the DM.",
    default_member_permissions=interactions.Permissions.MANAGE_ROLES,
    options=[
        interactions.Option(
            name="role",
            description="DM role.",
            type=interactions.OptionType.ROLE,
            required=True,
        )
    ]
)
async def dm_role(ctx: interactions.CommandContext, role: interactions.Role):
    DATA[str(ctx.guild.id)][DM_ROLE_KEY] = str(role.id)
    save_data()
    await ctx.send(embeds=interactions.Embed(title="Role Set", description="DM role set to " + role.mention,
                                             color=interactions.Color.green()), ephemeral=True)


@bot.command(
    name="roll",
    description="Roll a die based on your ability score.",
    options=[
        interactions.Option(
            name="ability",
            description="Roll a d20 based on your ability score.",
            type=interactions.OptionType.SUB_COMMAND,
            options=[
                interactions.Option(
                    name="ability",
                    description="The ability to use.",
                    type=interactions.OptionType.STRING,
                    choices=[
                        interactions.Choice(name="Strength", value="strength"),
                        interactions.Choice(name="Dexterity", value="dexterity"),
                        interactions.Choice(name="Constitution", value="constitution"),
                        interactions.Choice(name="Intelligence", value="intelligence"),
                        interactions.Choice(name="Wisdom", value="wisdom"),
                        interactions.Choice(name="Charisma", value="charisma"),
                        interactions.Choice(name="Acrobatics", value="acrobatics"),
                        interactions.Choice(name="Animal Handling", value="animal_handling"),
                        interactions.Choice(name="Arcana", value="arcana"),
                        interactions.Choice(name="Athletics", value="athletics"),
                        interactions.Choice(name="Deception", value="deception"),
                        interactions.Choice(name="History", value="history"),
                        interactions.Choice(name="Insight", value="insight"),
                        interactions.Choice(name="Intimidation", value="intimidation"),
                        interactions.Choice(name="Investigation", value="investigation"),
                        interactions.Choice(name="Medicine", value="medicine"),
                        interactions.Choice(name="Nature", value="nature"),
                        interactions.Choice(name="Perception", value="perception"),
                        interactions.Choice(name="Performance", value="performance"),
                        interactions.Choice(name="Persuasion", value="persuasion"),
                        interactions.Choice(name="Religion", value="religion"),
                        interactions.Choice(name="Sleight of Hand", value="sleight_of_hand"),
                        interactions.Choice(name="Stealth", value="stealth"),
                        interactions.Choice(name="Survival", value="survival")
                    ],
                    required=True
                ),
                interactions.Option(
                    name="saving_throw",
                    description="Whether to roll as a saving throw or not. Only has an effect for the core attributes.",
                    type=interactions.OptionType.BOOLEAN
                ),
                interactions.Option(
                    name="player",
                    description="Player for whom to role the dice. Must be DM to use.",
                    type=interactions.OptionType.USER,
                )
            ]
        ),
        interactions.Option(
            name="input",
            description="Roll a dice based on input.",
            type=interactions.OptionType.SUB_COMMAND,
            options=[
                interactions.Option(
                    name="dice",
                    description="The dice to roll.",
                    type=interactions.OptionType.STRING,
                    required=True
                )
            ]
        )
    ]
)
async def roll(ctx: interactions.CommandContext, sub_command: str, ability: str = "", saving_throw: bool = False,
               player: interactions.Member = None, dice: str = ""):
    title = dice

    if sub_command == "ability":
        if player and not await check_dm(ctx, ctx.author): return

        user = player if player else ctx.author

        if not (await check_char_sheet(ctx, user, not player)): return

        title = ability.replace("_", " ").title().replace("Of", "of")

        ability = get_ability(DATA[str(ctx.guild.id)][str(user.id)], title, saving_throw)
        dice = "1d20" + ability[0]

        if saving_throw: title += " Saving Throw"
        if ability[1]: title += " ✓"

    try:
        await ctx.send(
            embeds=interactions.Embed(title=title, description=roll_dice(dice)[0], color=interactions.Color.blurple()),
            ephemeral=player is not None)
    except RuntimeError:
        await ctx.send(embeds=interactions.Embed(title="Error",
                                                 description="Dice error, make sure you follow the formatting rules. `/roll help` for more info",
                                                 color=interactions.Color.red()), ephemeral=True)


@bot.command(
    name="init",
    description="Initiative base command."
)
async def init(ctx: interactions.CommandContext):
    if INITIATIVE_KEY not in DATA[str(ctx.guild.id)]:
        DATA[str(ctx.guild.id)][INITIATIVE_KEY] = []
    if CURRENT_INITIATIVE_KEY not in DATA[str(ctx.guild.id)]:
        DATA[str(ctx.guild.id)][CURRENT_INITIATIVE_KEY] = 0


async def get_init_desc(ctx: interactions.CommandContext):
    guild = DATA[str(ctx.guild.id)]

    desc = ""

    for idx, value in enumerate(guild[INITIATIVE_KEY]):
        text = value[0]
        try:
            text = (await ctx.guild.get_member(int(value[0]))).mention
        except (interactions.api.error.LibraryException, ValueError):
            pass

        desc += text + " (" + value[1] + ", " + ("+" if int(value[2]) >= 0 else "") + value[2] + ")" + (
            " **<---**" if guild[CURRENT_INITIATIVE_KEY] == idx else "") + "\n"

    if desc == "": desc = "Empty"

    return desc


@init.subcommand(
    name="list",
    description="Lists the current initiative order.",
    options=[
        interactions.Option(
            name="public",
            description="Create an auto-updating public init list, with a next button",
            type=interactions.OptionType.BOOLEAN
        )
    ]
)
async def init_list(ctx: interactions.CommandContext, public: bool = False):
    if public and not await check_dm(ctx, ctx.author): return

    guild = DATA[str(ctx.guild.id)]

    components = []
    if public:
        components = interactions.Button(
                style=interactions.ButtonStyle.PRIMARY,
                label="Next",
                custom_id="initiative_next"
            )

    message = await ctx.send(components=components, embeds=interactions.Embed(title="Initiative", description=await get_init_desc(ctx), color=interactions.Color.blurple()),
                   ephemeral=not public)

    if (public):
        if INIT_EMBEDS_KEY not in guild:
            guild[INIT_EMBEDS_KEY] = {}

        guild[INIT_EMBEDS_KEY][str(message.channel_id)] = str(message.id)

        save_data()


async def update_init_embeds(ctx: interactions.CommandContext):
    guild = DATA[str(ctx.guild.id)]
    if INIT_EMBEDS_KEY in guild:
        for channel, message in guild[INIT_EMBEDS_KEY].items():
            chnl = next((c for c in (await ctx.guild.get_all_channels()) if str(c.id) == channel), None)
            if not chnl: return

            msg = await chnl.get_message(int(message))
            embed = msg.embeds[0]
            embed.description = await get_init_desc(ctx)
            await msg.edit(embeds=embed)


@init.subcommand(
    name="next",
    description="Continue through the initiative order."
)
@bot.component("initiative_next")
async def init_next(ctx):
    if not await check_dm(ctx, ctx.author): return

    guild = DATA[str(ctx.guild.id)]

    current = guild[CURRENT_INITIATIVE_KEY] = (int(guild[CURRENT_INITIATIVE_KEY]) + 1) % len(guild[INITIATIVE_KEY])

    name = text = guild[INITIATIVE_KEY][current][0]

    save_data()

    try:
        text = (await ctx.guild.get_member(int(name))).mention
    except (interactions.api.error.LibraryException, ValueError):
        pass

    modifier = guild[INITIATIVE_KEY][current][2]

    await ctx.send(embeds=interactions.Embed(title="Initiative",
                                             description="Next in initiative is: **" + text + "** (" +
                                                         guild[INITIATIVE_KEY][current][1] + ", " + (
                                                             "+" if int(modifier) >= 0 else "") + modifier + ")",
                                             color=interactions.Color.blurple()), ephemeral = type(ctx) == interactions.ComponentContext)

    await update_init_embeds(ctx)


async def init_clear_callback(ctx: interactions.ComponentContext):
    del DATA[str(ctx.guild.id)][INITIATIVE_KEY]
    del DATA[str(ctx.guild.id)][CURRENT_INITIATIVE_KEY]
    save_data()
    await ctx.send(embeds=interactions.Embed(title="Initiative Cleared",
                                             description="Initiative has been successfully cleared",
                                             color=interactions.Color.green()), ephemeral=True)

    guild = DATA[str(ctx.guild.id)]
    if INIT_EMBEDS_KEY in guild:
        for channel, message in guild[INIT_EMBEDS_KEY].items():
            chnl = next((c for c in (await ctx.guild.get_all_channels()) if str(c.id) == channel), None)
            if not chnl: return

            msg = await chnl.get_message(int(message))
            await msg.delete()

    del guild[INIT_EMBEDS_KEY]
    save_data()



@init.subcommand(
    name="clear",
    description="Clears the entire initiative."
)
async def init_clear(ctx: interactions.CommandContext):
    if not await check_dm(ctx, ctx.author): return

    await confirm_action(ctx, "clear_initiative", init_clear_callback)


@init.group(
    name="add",
    description="Add something to the initiative order."
)
async def init_add(ctx: interactions.CommandContext):
    pass


async def add_player_to_initiative(ctx: interactions.CommandContext, player: interactions.Member):
    if any(value[0] == player.id for value in DATA[str(ctx.guild.id)][INITIATIVE_KEY]):
        return None

    initiative = get_stat(DATA[str(ctx.guild.id)][str(player.id)], "Initiative")
    dice = "1d20" + ("+" + initiative if int(initiative) >= 0 else initiative)

    score = roll_dice(dice)[1]

    while not add_to_initiative(ctx.guild, str(player.id), score, int(initiative)):
        score = roll_dice(dice)[1]

    return score


@init_add.subcommand(
    name="player",
    description="Add a player to the initiative order.",
    options=[
        interactions.Option(
            name="player",
            description="The player to add.",
            type=interactions.OptionType.USER,
            required=True
        ),
        interactions.Option(
            name="score",
            description="The score to use, if provided.",
            type=interactions.OptionType.INTEGER
        )
    ]
)
async def init_add_player(ctx: interactions.CommandContext, player: interactions.Member, score: int = None):
    if not await check_dm(ctx, ctx.author): return
    if not (await check_char_sheet(ctx, player, False)): return

    exists = True
    if score:
        exists = any(value[0] == player.id for value in DATA[str(ctx.guild.id)][INITIATIVE_KEY])
    else:
        score = await add_player_to_initiative(ctx, player)

    if not score or not exists:
        await ctx.send(embeds=interactions.Embed(title="Already Added",
                                                 description=player.mention + " is already in the initiative order. Use `/init remove " + player.user.username + "#" + player.user.discriminator + "` to remove them",
                                                 color=interactions.Color.red()), ephemeral=True)
        return

    await ctx.send(embeds=interactions.Embed(title="Added to Initiative",
                                             description=f"Added {player.mention} with a score of **{score}**",
                                             color=interactions.Color.green()), ephemeral=True)

    await update_init_embeds(ctx)


@init_add.subcommand(
    name="all-players",
    description="Add every player with a character sheet linked to the initiative order."
)
async def init_add_all_players(ctx: interactions.CommandContext):
    if not await check_dm(ctx, ctx.author): return

    desc = ""
    for member in await ctx.guild.get_all_members():
        if str(member.id) in DATA[str(ctx.guild.id)]:
            score = await add_player_to_initiative(ctx, member)
            if not score: continue

            desc += ("\n" if len(desc) > 0 else "") + f"Added {member.mention} with a score of **{score}**"

    if len(desc) == 0:
        await ctx.send(embeds=interactions.Embed(title="Nobody Added",
                                                 description="Possible reasons: already being in initiative or not having a character sheet linked",
                                                 color=interactions.Color.red()), ephemeral=True)
    else:
        await ctx.send(
            embeds=interactions.Embed(title="Added to Initiative", description=desc, color=interactions.Color.green()),
            ephemeral=True)

        await update_init_embeds(ctx)


@init_add.subcommand(
    name="other",
    description="Add a non-player to the initiative order.",
    options=[
        interactions.Option(
            name="name",
            description="The name of the thing in initiative.",
            type=interactions.OptionType.STRING,
            required=True
        ),
        interactions.Option(
            name="initiative",
            description="The initiative bonus of the thing. +/- included (ex -3, 1, +0).",
            type=interactions.OptionType.STRING,
            required=True
        )
    ]
)
async def init_add_other(ctx: interactions.CommandContext, name: str, initiative: str):
    if not await check_dm(ctx, ctx.author): return
    initiative = initiative.replace(" ", "")

    try:
        await ctx.guild.get_member(int(name))
        await ctx.send(embeds=interactions.Embed(title="Same as Member ID",
                                                 description="You cannot create an initiative with the same name as a member's ID",
                                                 color=interactions.Color.red()), ephemeral=True)
        return
    except (interactions.api.error.LibraryException, ValueError):
        pass

    if any(str(member.id) == name for member in (await ctx.guild.get_all_members())):
        await ctx.send(embeds=interactions.Embed(title="Same as Member ID",
                                                 description="You cannot create an initiative with the same name as a member's ID",
                                                 color=interactions.Color.red()), ephemeral=True)
        return

    if any(value[0] == name for value in DATA[str(ctx.guild.id)][INITIATIVE_KEY]):
        await ctx.send(embeds=interactions.Embed(title="Already Added",
                                                 description="'" + name + "' is already in the initiative order. Use `/init remove " + name + "` to remove it",
                                                 color=interactions.Color.red()), ephemeral=True)
        return

    if not re.match("[+-][0-9]*", initiative):
        await ctx.send(embeds=interactions.Embed(title="Invalid Initiative",
                                                 description="Initiative parameter not in the form '+/-[number]'",
                                                 color=interactions.Color.red()), ephemeral=True)
        return

    dice = "1d20" + initiative

    score = roll_dice(dice)[1]

    while not add_to_initiative(ctx.guild, name, score, int(initiative.replace("+", ""))):
        score = roll_dice(dice)[1]

    await ctx.send(embeds=interactions.Embed(title="Added to Initiative",
                                             description="Added " + name + " with a score of **" + str(score) + "**",
                                             color=interactions.Color.green()), ephemeral=True)

    await update_init_embeds(ctx)


@init.group(
    name="remove",
    description="Remove something from the initiative order."
)
async def init_remove(ctx: interactions.CommandContext):
    pass


@init_remove.subcommand(
    name="player",
    description="Remove a player from the initiative order.",
    options=[
        interactions.Option(
            name="player",
            description="The player to remove.",
            type=interactions.OptionType.USER,
            required=True
        )
    ]
)
async def init_remove_player(ctx: interactions.CommandContext, player: interactions.Member):
    if not await check_dm(ctx, ctx.author): return

    initiative_l = DATA[str(ctx.guild.id)][INITIATIVE_KEY]

    if not any(value[0] == player.id for value in initiative_l):
        await ctx.send(embeds=interactions.Embed(title="Doesn't Exist",
                                                 description=player.mention + " is not in the initiative order",
                                                 color=interactions.Color.red()), ephemeral=True)
        return

    for idx, value in enumerate(initiative_l):
        if value[0] == str(player.id):
            del initiative_l[idx]
            await ctx.send(
                embeds=interactions.Embed(title="Removed from Initiative", description="Removed " + player.mention,
                                          color=interactions.Color.green()))

            await update_init_embeds(ctx)

            return


@init_remove.subcommand(
    name="other",
    description="Remove a non-player from the initiative order.",
    options=[
        interactions.Option(
            name="name",
            description="The name of the thing in initiative.",
            type=interactions.OptionType.STRING,
            required=True
        )
    ]
)
async def init_remove_other(ctx: interactions.CommandContext, name: str):
    if not await check_dm(ctx, ctx.author): return

    initiative_l = DATA[str(ctx.guild.id)][INITIATIVE_KEY]

    if not any(value[0] == name for value in initiative_l):
        await ctx.send(embeds=interactions.Embed(title="Doesn't Exist",
                                                 description="'" + name + "' is not in the initiative order",
                                                 color=interactions.Color.red()), ephemeral=True)
        return

    for idx, value in enumerate(initiative_l):
        if value[0] == name:
            del initiative_l[idx]
            await ctx.send(embeds=interactions.Embed(title="Removed from Initiative", description="Removed " + name,
                                                     color=interactions.Color.green()))
            await update_init_embeds(ctx)

            return



@bot.command(
    name="spell",
    description="Get a spell from the wikidot library, either from a selection menu or by name.",
    options=[
        interactions.Option(
            name="spell",
            description="The spell name.",
            type=interactions.OptionType.STRING,
            required=True,
            autocomplete=True
        ),
        interactions.Option(
            name="public",
            description="Show response publicly.",
            type=interactions.OptionType.BOOLEAN
        )
    ]
)
async def spell_command(ctx: interactions.CommandContext, spell: str, public: bool = False):
    spell = spell.title()

    key = None
    for k in ALL_SPELLS.keys():
        if re.sub("[^a-z]", "", spell.lower()) == re.sub("[^a-z]", "", k.lower()):
            key = k
            break

    if not key:
        await ctx.send(embeds=interactions.Embed(title="Not Found", description="Could not find that spell",
                                                 color=interactions.Color.red()), ephemeral=True)
        return

    r = requests.get("http://dnd5e.wikidot.com/spell:" + ALL_SPELLS[key])

    description = re.search("Duration.+?(<p>.+?</.+?>)\n<p><strong><em>Spell Lists", r.text,
                            flags=re.RegexFlag.DOTALL).group(1)
    description = re.sub("</?p>|\n?</ul>|<ul>|</li>", "",
                         re.sub("</?strong>", "**", re.sub("</?em>", "*", re.sub("<li>", "• ", description))))

    source = re.search("<p>Source: (.+?)</p>", r.text).group(1)
    spell_lists = ", ".join([match.group(1).title() for match in re.finditer("spells:(.+?)\"", r.text)])

    level_match = re.search("<em>(([0-9].+?-level.+?)|(.+?cantrip.*?))</em>", r.text)
    level = level_match.group(1) or level_match.group(2)

    embed_desc = f"""
    *{level}*
    
    **Casting Time:** {get_spell_stat(r.text, "Casting Time")}
    **Range:** {get_spell_stat(r.text, "Range")}
    **Duration:** {get_spell_stat(r.text, "Duration")}
    **Components:** {get_spell_stat(r.text, "Components")}

    {description}
    """

    embed_desc += f"""
    *{spell_lists}*
    Source: {source}
    """

    await ctx.send(embeds=interactions.Embed(title=key, description=embed_desc, color=interactions.Color.blurple()),
                   ephemeral=not public)


@spell_command.autocomplete(
    name="spell"
)
async def autocomplete_spell(ctx: interactions.CommandContext, user_input: str = ""):
    spells = {key: ALL_SPELLS[key] for key in
              list(filter(lambda key: key.lower().startswith(user_input.lower()), ALL_SPELLS.keys()))[:25]}
    await ctx.populate([interactions.Choice(name=key, value=key) for key in spells.keys()])


@bot.command(
    name="monster",
    description="Base command for querying monsters."
)
async def monster_command(ctx: interactions.CommandContext):
    pass


@monster_command.subcommand(
    name="statblock",
    description="Get a monster statblock, either from a selection menu or by name.",
    options=[
        interactions.Option(
            name="monster",
            description="The monster's name.",
            type=interactions.OptionType.STRING,
            required=True,
            autocomplete=True
        ),
        interactions.Option(
            name="public",
            description="Show response publicly.",
            type=interactions.OptionType.BOOLEAN
        )
    ]
)
async def monster_statblock(ctx: interactions.CommandContext, monster: str, public: bool = False):
    name = None
    for k in MONSTER_ID_BY_NAME.keys():
        if re.sub("[^a-z]", "", monster.lower()) == re.sub("[^a-z]", "", k.lower()):
            name = k
            break

    if not name:
        await ctx.send(embeds=interactions.Embed(title="Not Found", description="Could not find that monster",
                                                 color=interactions.Color.red()), ephemeral=True)
        return

    id = MONSTER_ID_BY_NAME[name]

    url = None
    if "cdn" in MONSTER_STATS[id]:
        url = MONSTER_STATS[id]["cdn"]
        if requests.get(url).status_code != 200:
            url = None

    if url == None:
        file_name = id + ".png"
        file_path = path.join(cache_dir, file_name)

        with ZipFile(monster_statblocks_file, "r") as zip:
            zip.extract(file_name, cache_dir)

        message = await ctx.channel.send(files=interactions.File(filename=file_path))
        url = message.attachments[0].url
        await message.delete()

        os.remove(file_path)

        MONSTER_STATS[id]["cdn"] = url

    await ctx.send(
        embeds=interactions.Embed(image=interactions.EmbedImageStruct(url=url), color=interactions.Color.blurple()),
        ephemeral=not public)


@monster_command.autocomplete(
    name="monster"
)
async def autocomplete_monster(ctx: interactions.CommandContext, user_input: str = ""):
    await ctx.populate([interactions.Choice(name=key, value=key) for key in
                        filter(lambda key: key.lower().startswith(user_input.lower()), MONSTER_ID_BY_NAME.keys())][:25])


def get_speed_choices():
    choices = []
    for stats in d.values():
        for speed in stats["speeds"].keys():
            choices.append(interactions.Choice(name=speed.title(), value=speed))

    return choices


@monster_command.subcommand(
    name="search",
    description="Search for a monster, based on certain criteria. For multiple inputs, use CSV: `key1,key2,key3`",
    options=[
        interactions.Option(
            name="keywords",
            description="Search for given keywords in the name.",
            type=interactions.OptionType.STRING
        ),
        interactions.Option(
            name="cr",
            description="Search for monsters with the given CRs. Can also be provided as a range: `1/2-3,7-9`",
            type=interactions.OptionType.STRING
        ),
        interactions.Option(
            name="size",
            description="Search for monsters with the given sizes.",
            type=interactions.OptionType.STRING
        ),
        interactions.Option(
            name="alignment",
            description="Search for monsters with the given alignments.",
            type=interactions.OptionType.STRING
        ),
        interactions.Option(
            name="type",
            description="Search for monsters with the given types.",
            type=interactions.OptionType.STRING
        ),
        interactions.Option(
            name="subtype",
            description="Search for monsters with the given subtypes.",
            type=interactions.OptionType.STRING
        ),
        interactions.Option(
            name="speed",
            description="Search for monsters that have the given speed.",
            type=interactions.OptionType.STRING
        ),
        interactions.Option(
            name="source",
            description="Search for monsters from the given source.",
            type=interactions.OptionType.STRING
        )
    ]
)
async def monster_search(ctx: interactions.CommandContext, keywords: str = None, cr: str = None, size: str = None,
                         alignment: str = None, type: str = None, subtype: str = None, speed: str = None,
                         source: str = None):
    if cr:
        cr = cr.replace(" ", "")
        for challenge in cr.split(","):
            if not all([c in MONSTER_CR for c in challenge.split("-")]):
                await ctx.send(
                    embeds=interactions.Embed(title="Error", description="CR doesn't match the format `cr` or `cr-cr`",
                                              color=interactions.Color.red()), ephemeral=True)
                return

    def test(id: str):
        stats = MONSTER_STATS[id]

        if keywords:
            if not any([keyword.lower().strip() in stats["name"].lower() for keyword in keywords.split(",")]):
                return False
        if cr:
            contains = False
            for challenge in cr.split(","):
                range_ = challenge.split("-")

                if len(range_) == 2:
                    idx1 = MONSTER_CR.index(range_[0])
                    idx2 = MONSTER_CR.index(range_[1])
                    for cr_ in MONSTER_CR[idx1 if idx1 < idx2 else idx2:(idx2 if idx2 > idx1 else idx1) + 1]:
                        if stats["cr"] == cr_:
                            contains = True
                            break
                    if contains: break
                else:
                    if stats["cr"] == challenge:
                        contains = True
                        break

            if not contains: return False

        if size:
            if not any([s.lower().strip() == stats["size"].lower() for s in size.split(",")]):
                return False

        if alignment:
            if not any([("neutral" if (
                    a.lower().strip() == "neutral neutral" or a.lower().strip() == "true neutral") else a.lower().strip()) ==
                        stats["alignment"].lower() for a in alignment.split(",")]):
                return False

        if type:
            if not any([t.lower().strip() == stats["type"].lower() for t in type.split(",")]):
                return False

        if subtype:
            if not any([any([st.lower().strip() == st_.lower() for st_ in stats["subtype"]]) for st in
                        subtype.split(",")]):
                return False

        if speed:
            if not any([any([s.lower().strip() == s_.lower() for s_ in stats["speeds"].keys()]) for s in
                        speed.split(",")]):
                return False

        if source:
            if not any([s.lower().strip() == id.split("-")[-1].lower() for s in source.split(",")]):
                return False

        return True

    monsters = list(filter(test, MONSTER_STATS.keys()))

    if len(monsters) == 0:
        descs = ["None"]
    else:
        descs = []

        for id_ in monsters:
            stats = MONSTER_STATS[id_]

            desc = f"\n\n**{MONSTER_NAME_BY_ID[id_]}**"

            if cr and (len(cr.split(",")) > 1 or len(cr.split("-")) > 1):
                desc += f"\n__CR__: {stats['cr']}"
            if size and len(size.split(",")) > 1:
                desc += f"\n__Size__: {stats['size'].title()}"
            if alignment and len(alignment.split(",")) > 1:
                desc += f"\n__Alignment__: {stats['alignment'].title()}"
            if type and len(type.split(",")) > 1:
                desc += f"\n__Type__: {stats['type'].title()}"
            if subtype and len(subtype.split(",")) > 1:
                desc += f"\n__Subtypes__: {','.join([s.title() for s in stats['subtypes']])}"
            if speed and len(speed.split(",")) > 1:
                for speed_ in speed.split(","):
                    stats_speed = stats['speeds'][speed_.lower().strip()]
                    desc += f"\n__{speed_.title()} Speed__: "
                    if builtins.type(stats_speed) == dict:
                        desc += f"{stats_speed['number']} ft. {stats_speed['condition']}"
                    else:
                        desc += f"{stats_speed} ft."
            if source and len(source.split(",")) > 1:
                desc += f"\n__Source__: {id_.split('-')[-1]}"

            if len(descs) == 0 or len(desc) + len(descs[-1]) > 4096 or f"{descs[-1]}{desc}".count(
                    "\n") > 297:  # apparently embeds have a max of ~297 lines??
                descs.append(desc[2:])
            else:
                descs[-1] += desc

    for desc in descs:
        await ctx.send(embeds=interactions.Embed(description=desc, color=interactions.Color.blurple()), ephemeral=True)


@monster_command.group(
    name="search-options",
    description="List the possibilities for the `/monster search` parameters."
)
async def monster_search_options(ctx: interactions.CommandContext):
    pass


@monster_search_options.subcommand(name="cr")
async def monster_search_options_cr(ctx: interactions.CommandContext):
    await ctx.send(embeds=interactions.Embed(title="CR Options",
                                             description='\n'.join(['• ' + cr for cr in ["1/8", "1/4", "1/2", "1-30"]]),
                                             color=interactions.Color.blurple()), ephemeral=True)


@monster_search_options.subcommand(name="size")
async def monster_search_options_cr(ctx: interactions.CommandContext):
    await ctx.send(embeds=interactions.Embed(title="Size Options", description='\n'.join(
        ['• ' + size.title() for size in ["tiny", "small", "medium", "large", "huge", "gargantuan"]]),
                                             color=interactions.Color.blurple()), ephemeral=True)


@monster_search_options.subcommand(name="alignment")
async def monster_search_options_cr(ctx: interactions.CommandContext):
    await ctx.send(embeds=interactions.Embed(title="Alignment Options", description='\n'.join(
        sorted(set('• ' + stats['alignment'].title() for stats in MONSTER_STATS.values()))),
                                             color=interactions.Color.blurple()), ephemeral=True)


@monster_search_options.subcommand(name="type")
async def monster_search_options_cr(ctx: interactions.CommandContext):
    await ctx.send(embeds=interactions.Embed(title="Type Options", description='\n'.join(
        set('• ' + stats['type'].title() for stats in MONSTER_STATS.values())), color=interactions.Color.blurple()),
                   ephemeral=True)


@monster_search_options.subcommand(name="subtype")
async def monster_search_options_cr(ctx: interactions.CommandContext):
    subtypes = set()

    for stats in MONSTER_STATS.values():
        for subtype in stats['subtypes']:
            if builtins.type(subtype) == dict:
                subtypes.add("• " + subtype["prefix"].title() + " " + subtype["tag"].title())
            else:
                subtypes.add("• " + subtype.title())

    await ctx.send(embeds=interactions.Embed(title="Subtype Options", description='\n'.join(subtypes),
                                             color=interactions.Color.blurple()), ephemeral=True)


@monster_search_options.subcommand(name="speed")
async def monster_search_options_cr(ctx: interactions.CommandContext):
    speeds = set()

    for stats in MONSTER_STATS.values():
        for speed in stats['speeds'].keys(): speeds.add("• " + speed.title())

    await ctx.send(embeds=interactions.Embed(title="Speed Options", description='\n'.join(speeds),
                                             color=interactions.Color.blurple()), ephemeral=True)


@monster_search_options.subcommand(name="source")
async def monster_search_options_cr(ctx: interactions.CommandContext):
    await ctx.send(embeds=interactions.Embed(title="Source Options", description='\n'.join(
        sorted(set('• ' + stats['source'].title() for stats in MONSTER_STATS.values()))),
                                             color=interactions.Color.blurple()), ephemeral=True)


NEW_DATE_OPTIONS = [
    interactions.Option(
        name="day",
        description="The day of the month.",
        type=interactions.OptionType.INTEGER
    ),
    interactions.Option(
        name="month",
        description="The month.",
        type=interactions.OptionType.STRING,
        choices=[interactions.Choice(name=month, value=month) for month in MONTHS]
    ),
    interactions.Option(
        name="year",
        description="The year, number. To set the calendar, use `/date calendar`.",
        type=interactions.OptionType.INTEGER
    ),
    interactions.Option(
        name="days",
        description="Difference in days, positive or negative.",
        type=interactions.OptionType.INTEGER
    ),
    interactions.Option(
        name="relative",
        description="Which date it's relative to.",
        type=interactions.OptionType.STRING,
        choices=[
            interactions.Choice(
                name="Campaign Start",
                value="CS",
            ),
            interactions.Choice(
                name="Current Date",
                value="CD"
            )
        ]
    )
]
EXISTING_DATE_OPTION = interactions.Option(
    name="date",
    description="The date to use. Format as 'day month year' or 'days CS[campaign start]/CD[current date]'.",
    type=interactions.OptionType.STRING,
    required=True,
    autocomplete=True
)


@bot.command(
    name="date",
    description="Base command for modifying the timeline."
)
async def date_command(ctx: interactions.CommandContext):
    if DATES_KEY not in DATA[str(ctx.guild.id)]:
        DATA[str(ctx.guild.id)][DATES_KEY] = {TIMELINE_KEY: {}}


async def check_date(ctx: interactions.CommandContext, day: int, month: str, year: int):
    if day < 1 or day > 30 or year < 1:
        await ctx.send(
            embeds=interactions.Embed(title="Error", description="Invalid day or year. 1 <= day <= 30, year > 0.",
                                      color=interactions.Color.red()))
        return None

    return f"{day}-{MONTHS.index(month)}-{year}"


async def convert_and_check_date(ctx: interactions.CommandContext, date: str):
    relative = re.compile("-?[0-9]* (CS|CD)")
    absolute = re.compile(f"(30|2[0-9]|1[0-9]|[1-9]) ({'|'.join(MONTHS)}), [0-9]+")

    if relative.match(date):
        date = date.split(" ")
        return await relative_to_absolute_date(ctx, int(date[0]), date[1])
    elif absolute.match(date):
        date = date.replace(",", "").split(" ")
        return await check_date(ctx, int(date[0]), date[1], int(date[2]))
    else:
        dates = DATA[str(ctx.guild.id)][DATES_KEY]
        await ctx.send(embeds=interactions.Embed(title="Error",
                                                 description=f"Date must follow the format 'day month year' or 'days CS[campagin start]/CD[current date]'.\n\n__Examples:__ '1 {MONTHS[0]} 1{' ' + dates[CALENDAR_KEY] if CALENDAR_KEY in dates else ''}', '5 CS', '-5 CD'.",
                                                 color=interactions.Color.red()), ephemeral=True)

        return None


def rollover_date_number(place1: int, place2: int, low_bound: int, high_bound: int):
    while place1 < low_bound or place1 > high_bound:
        place2_mod = 1
        if place1 < low_bound:
            place2_mod = -1

        place2 += place2_mod
        place1 += place2_mod * -1 * high_bound

    return place1, place2


async def relative_id_to_key(ctx: interactions.CommandContext, relative: str):
    key = None

    if relative == "CD":
        key = CURRENT_DATE_KEY
    elif relative == "CS":
        key = CAMPAIGN_START_KEY

    if key and key not in DATA[str(ctx.guild.id)][DATES_KEY]:
        await ctx.send(embeds=interactions.Embed(title="Error", description=f"{'Current' if key == CURRENT_DATE_KEY else 'Campaign start'} date not set! `/date " + (
            "set" if key == CURRENT_DATE_KEY else "origin") + "` to set it", color=interactions.Color.red()),
                       ephemeral=True)
        return None

    return key


async def relative_to_absolute_date(ctx: interactions.CommandContext, days: int, relative: str):
    relative_key = await relative_id_to_key(ctx, relative)
    if not relative_key: return None

    date = DATA[str(ctx.guild.id)][DATES_KEY][relative_key].split("-")
    day = int(date[0])
    month = int(date[1])
    year = int(date[2])

    day, month = rollover_date_number(day + days, month, 1, 30)
    month, year = rollover_date_number(month + 1, year, 1,
                                       len(MONTHS))  # have to offset it because rollover doesn't work well with lower_bound being 0
    month -= 1

    return f"{day}-{month}-{year}"


async def check_new_date(ctx: interactions.CommandContext, day: int, month: str, year: int, days: int, relative: str):
    if (days and not relative) or (relative and not days) or (day and (not month or not year)) or (
            month and (not day or not year)) or (year and (not day or not month)) or (
            not days and not relative and not day and not month and not year):
        await ctx.send(embeds=interactions.Embed(title="Error",
                                                 description="Must have either `days` and `relative` or `day`, `month`, and `year`.",
                                                 color=interactions.Color.red()), ephemeral=True)
        return None

    if days and relative:
        return await relative_to_absolute_date(ctx, days, relative)
    else:
        return await check_date(ctx, day, month, year)


async def set_date_command(ctx: interactions.CommandContext, days: int, relative: str, day: int, month: str, year: int,
                           key: str):
    if not await check_dm(ctx, ctx.author): return None

    date = await check_new_date(ctx, day, month, year, days, relative)
    if not date: return None

    DATA[str(ctx.guild.id)][DATES_KEY][key] = date
    save_data()
    return date


@date_command.subcommand(
    name="origin",
    description="Set or get the date for the campaign start.",
    options=NEW_DATE_OPTIONS
)
async def date_origin(ctx: interactions.CommandContext, days: int = None, relative: str = None, day: int = None,
                      month: str = None, year: int = None):
    if not (days or relative or day or month or year):
        dates = DATA[str(ctx.guild.id)][DATES_KEY]
        if CAMPAIGN_START_KEY in dates:
            await ctx.send(embeds=interactions.Embed(title="Campaign Start", description="Campaign start date is "+format_date(ctx.guild, dates[CAMPAIGN_START_KEY]), color=interactions.Color.blurple()), ephemeral=True)
        else:
            await ctx.send(embeds=interactions.Embed(title="Not Set", description="Campaign start date is not set yet", color=interactions.Color.red()), ephemeral=True)

        return

    date = await set_date_command(ctx, days, relative, day, month, year, CAMPAIGN_START_KEY)

    if date:
        await ctx.send(embeds=interactions.Embed(title="Date Set",
                                                 description="Campaign start date successfully set to **" + format_date(
                                                     ctx.guild, date) + "**", color=interactions.Color.green()),
                       ephemeral=True)


@date_command.subcommand(
    name="current",
    description="Set the current date.",
    options=NEW_DATE_OPTIONS
)
async def date_current(ctx: interactions.CommandContext, days: int = None, relative: str = None, day: int = None,
                       month: str = None, year: int = None):
    if not (days or relative or day or month or year):
        dates = DATA[str(ctx.guild.id)][DATES_KEY]
        if CURRENT_DATE_KEY in dates:
            await ctx.send(embeds=interactions.Embed(title="Current Date", description="Current date is " + format_date(ctx.guild, dates[CURRENT_DATE_KEY]),
                                                     color=interactions.Color.blurple()), ephemeral=True)
        else:
            await ctx.send(embeds=interactions.Embed(title="Not Set", description="Current date is not set yet",
                                                     color=interactions.Color.red()), ephemeral=True)

        return

    date = await set_date_command(ctx, days, relative, day, month, year, CURRENT_DATE_KEY)

    if date:
        await ctx.send(embeds=interactions.Embed(title="Date Set",
                                                 description="Current date successfully set to **" + format_date(
                                                     ctx.guild, date) + "**", color=interactions.Color.green()),
                       ephemeral=True)


@date_command.subcommand(
    name="next",
    description="Advance the current date.",
    options=[
        interactions.Option(
            name="downtime",
            description="Applies daily income and expenses automatically.",
            type=interactions.OptionType.BOOLEAN
        )
    ]
)
async def date_next(ctx: interactions.CommandContext, downtime: bool = False):
    date = await set_date_command(ctx, 1, "CD", None, None, None, CURRENT_DATE_KEY)

    if date:
        await ctx.send(embeds=interactions.Embed(title="Date Set",
                                                 description="Current date advanced to **" + format_date(ctx.guild,
                                                                                                         date) + "**",
                                                 color=interactions.Color.green()), ephemeral=True)

        if downtime:
            if MONEY_KEY not in DATA[str(ctx.guild.id)]: return

            money = DATA[str(ctx.guild.id)][MONEY_KEY]

            money_gained = {}

            for key in money:
                for user in money[key]:
                    for item in money[key][user]:
                        m = 1
                        if key == EXPENSES_KEY:
                            m = -1

                        if user not in money_gained:
                            money_gained[user] = {"pp": 0, "gp": 0, "ep": 0, "sp": 0, "cp": 0}

                        money_gained[user][item[3]] += m * int(item[2])

            # TODO: automatically apply money?
            desc = ""
            content = "||"
            for user, gained in money_gained.items():
                content += f"<@{user}> "
                desc += f"<@{user}>: {' '.join([f'**{gained[key]}** {key.upper()}' for key in gained])}\n"

            await ctx.send(content=content[:-1] + "||",
                           embeds=interactions.Embed(title="Daily Income", description=desc[:-1],
                                                     color=interactions.Color.blurple()))


@date_command.subcommand(
    name="calendar",
    description="Set the calender suffix.",
    options=[
        interactions.Option(
            name="suffix",
            description="The suffix to use (e.g. DR)",
            type=interactions.OptionType.STRING
        )
    ]
)
async def date_calendar(ctx: interactions.CommandContext, suffix: str = None):
    if not await check_dm(ctx, ctx.author): return

    dates = DATA[str(ctx.guild.id)][DATES_KEY]
    if not suffix:
        if CALENDAR_KEY in dates:
            await ctx.send(embed=interactions.Embed(title="Calendar", description="The callendar suffix is "+dtes[CALENDAR_KEY], color=interactions.Color.blurple()), ephemeral=True)
        else:
            await ctx.send(embed=interactions.Embed(title="Not Set", description="The callendar suffix is not set yet", color=interactions.Color.red()), ephemeral=True)

        return

    dates[CALENDAR_KEY] = suffix
    save_data()
    await ctx.send(embeds=interactions.Embed(title="Calendar Set",
                                             description="Calendar suffix successfully set to **" + suffix + "**",
                                             color=interactions.Color.green()))


@date_command.group(
    name="event",
    description="Manage events on the timeline"
)
async def date_event(ctx: interactions.CommandContext):
    pass


@date_event.subcommand(
    name="add",
    description="Add an event to the timeline.",
    options=[
                interactions.Option(
                    name="title",
                    description="The title of the event.",
                    type=interactions.OptionType.STRING,
                    required=True
                ),
                interactions.Option(
                    name="description",
                    description="The description of the event.",
                    type=interactions.OptionType.STRING,
                    required=True
                )
            ] + NEW_DATE_OPTIONS
)
async def date_event_add(ctx: interactions.CommandContext, title: str, description: str, day: int, month: str,
                         year: int, days: int, relative: str):
    if not await check_dm(ctx, ctx.author): return

    date = await check_new_date(ctx, day, month, year, days, relative)
    if not date: return

    timeline = DATA[str(ctx.guild.id)][DATES_KEY][TIMELINE_KEY]

    if date not in timeline:
        timeline[date] = {}

    if title in timeline[date]:
        await ctx.send(embeds=interactions.Embed(title="Already Exists",
                                                 description="An event with that name on that date already exists. `/date event remove` to remove it",
                                                 color=interactions.Color.red()), ephemeral=True)
        return

    timeline[date][title] = description
    await ctx.send(embeds=interactions.Embed(title="Event Added",
                                             description="**" + title + "** has been added on **" + format_date(
                                                 ctx.guild, date) + "**", color=interactions.Color.green()),
                   ephemeral=True)


@date_event.subcommand(
    name="remove",
    description="Remove an event from the timeline.",
    options=[
        interactions.Option(
            name="title",
            description="The title of the event.",
            type=interactions.OptionType.STRING,
            required=True,
            autocomplete=True
        ),
        EXISTING_DATE_OPTION
    ]
)
async def date_event_remove(ctx: interactions.CommandContext, title: str, date: str):
    if not await check_dm(ctx, ctx.author): return

    date = await convert_and_check_date(ctx, date)
    if not date: return

    timeline = DATA[str(ctx.guild.id)][DATES_KEY][TIMELINE_KEY]

    if date not in timeline or title not in timeline[date]:
        await ctx.send(embeds=interactions.Embed(title="Doesn't Exist",
                                                 description="Cannot find an event with that title on that date",
                                                 color=interactions.Color.red()), ephemeral=True)
        return

    del timeline[date][title]
    await ctx.send(embeds=interactions.Embed(title="Event Removed",
                                             description="**" + title + "** has been removed from **" + format_date(
                                                 ctx.guild, date) + "**", color=interactions.Color.green()),
                   ephemeral=True)


@date_event.subcommand(
    name="list",
    description="List the events on a date.",
    options=[EXISTING_DATE_OPTION]
)
async def date_event_list(ctx: interactions.CommandContext, date: str):
    date = await convert_and_check_date(ctx, date)
    if not date: return

    timeline = DATA[str(ctx.guild.id)][DATES_KEY][TIMELINE_KEY]

    events = ""

    if date not in timeline or len(timeline[date]) == 0:
        events = "Empty"
    else:
        for title, description in timeline[date].items():
            events += f"**{title}**\n{description}\n\n"

        events = events[:-2]

    await ctx.send(embeds=interactions.Embed(title=format_date(ctx.guild, date), description=events,
                                             color=interactions.Color.blurple()), ephemeral=True)


async def clear_date_events_callback(ctx: interactions.ComponentContext):
    date = ctx.custom_id.split("|")[1]

    del DATA[str(ctx.guild.id)][DATES_KEY][TIMELINE_KEY][date]
    save_data()

    await ctx.send(embeds=interactions.Embed(title="Events Cleared",
                                             description=f"Removed all events on **{format_date(ctx.guild, date)}**",
                                             color=interactions.Color.green()), ephemeral=True)


@date_event.subcommand(
    name="clear",
    description="Remove every event on a date.",
    options=[EXISTING_DATE_OPTION]
)
async def date_event_clear(ctx: interactions.CommandContext, date: str):
    if not await check_dm(ctx, ctx.author): return

    date = await convert_and_check_date(ctx, date)
    if not date: return

    timeline = DATA[str(ctx.guild.id)][DATES_KEY][TIMELINE_KEY]

    if date not in timeline or len(timeline[date]) == 0:
        await ctx.send(embeds=interactions.Embed(title="No Events", description="No events found!",
                                                 color=interactions.Color.red()), ephemeral=True)
        return

    await confirm_action(ctx, f"clear_date_events|{date}|", clear_date_events_callback)


async def clear_all_events_callback(ctx: interactions.ComponentContext):
    del DATA[str(ctx.guild.id)][DATES_KEY][TIMELINE_KEY]
    save_data()

    await ctx.send(embeds=interactions.Embed(title="Events Cleared",
                                             description=f"Removed **every** event",
                                             color=interactions.Color.green()), ephemeral=True)


@date_event.subcommand(
    name="clear-all",
    description="Remove every event."
)
async def date_event_clear_all(ctx: interactions.CommandContext):
    if not await check_dm(ctx, ctx.author): return

    await confirm_action(ctx, "clear_all_events", clear_all_events_callback)


@date_event.subcommand(
    name="search",
    description="Search for an event by title.",
    options=[
        interactions.Option(
            name="title",
            description="The title of the event (case insensitive, perfect match only, not partial).",
            type=interactions.OptionType.STRING,
            required=True,
            autocomplete=True
        )
    ]
)
async def date_event_search(ctx: interactions.CommandContext, title: str):
    timeline = DATA[str(ctx.guild.id)][DATES_KEY][TIMELINE_KEY]

    desc = ""

    for date in timeline:
        events = {}
        for event in timeline[date]:
            if title.lower() == event.lower():
                events[event] = timeline[date][event]

        if len(events) > 0:
            desc += ("\n\n" if len(desc) > 0 else "") + f"__**{format_date(ctx.guild, date)}**__\n"
            for title_, description in events.items():
                desc += f"**{title_}**\n{description}\n\n"
        desc = desc[:-2]

    await ctx.send(embeds=interactions.Embed(title=title, description=desc, color=interactions.Color.blurple()),
                   ephemeral=True)


@date_event.autocomplete(
    "date")  # TODO: a way to make this work only for date_event_remove and take into accout the `event` param?
async def autocomplete_date(ctx: interactions.CommandContext, user_input: str = ""):
    dates = [format_date(ctx.guild, date) for date in DATA[str(ctx.guild.id)][DATES_KEY][TIMELINE_KEY]]
    if re.match("-?[0-9]+ ?", user_input):
        space = "" if user_input.endswith(" ") else " "
        dates = [user_input + space + "CS", user_input + space + "CD"] + dates

    await ctx.populate([interactions.Choice(name=date, value=date) for date in
                        filter(lambda key: user_input.lower() in key.lower(), dates)][:25])


@date_event.autocomplete("title")
async def autocomplete_event_title(ctx: interactions.CommandContext, user_input: str = ""):
    timeline = DATA[str(ctx.guild.id)][DATES_KEY][TIMELINE_KEY]
    titles = set()

    for date in timeline:
        for title in filter(lambda key: key.lower().startswith(user_input.lower()), timeline[date].keys()):
            titles.add(title.lower())

    await ctx.populate([interactions.Choice(name=title.title(), value=title.title()) for title in titles][:25])


@bot.command(
    name="money",
    description="Base command for money tracking."
)
async def money_command(ctx: interactions.CommandContext):
    guild = DATA[str(ctx.guild.id)]

    if MONEY_KEY not in guild:
        guild[MONEY_KEY] = {}
    if INCOME_KEY not in guild[MONEY_KEY]:
        guild[MONEY_KEY][INCOME_KEY] = {}


@money_command.group(
    name="expense",
    description="Command for daily expense tracking."
)
async def money_expense(ctx: interactions.CommandContext):
    money = DATA[str(ctx.guild.id)][MONEY_KEY]
    if EXPENSES_KEY not in money:
        money[EXPENSES_KEY] = {}

    if str(ctx.author.id) not in money[EXPENSES_KEY]:
        money[EXPENSES_KEY][str(ctx.author.id)] = []


@money_expense.subcommand(
    name="add",
    description="Add a daily expense.",
    options=[
        interactions.Option(
            name="title",
            description="Title of the expense.",
            type=interactions.OptionType.STRING,
            required=True
        ),
        interactions.Option(
            name="description",
            description="Description of the expense.",
            type=interactions.OptionType.STRING,
            required=True
        ),
        interactions.Option(
            name="amount",
            description="Amount of money.",
            type=interactions.OptionType.INTEGER,
            required=True
        ),
        interactions.Option(
            name="unit",
            description="Unit of money.",
            type=interactions.OptionType.STRING,
            required=True,
            choices=[
                interactions.Choice(
                    name="PP",
                    value="pp"
                ),
                interactions.Choice(
                    name="GP",
                    value="gp"
                ),
                interactions.Choice(
                    name="EP",
                    value="ep"
                ),
                interactions.Choice(
                    name="SP",
                    value="sp"
                ),
                interactions.Choice(
                    name="CP",
                    value="cp"
                )
            ]
        )
    ]
)
async def money_expense_add(ctx: interactions.CommandContext, title: str, description: str, amount: int, unit: str):
    if amount < 1:
        await ctx.send(embeds=interactions.Embed(title="Invalid Amount", description="Amount must be greater than 0",
                                                 color=interactions.Color.red()), ephemeral=True)
        return

    expenses = DATA[str(ctx.guild.id)][MONEY_KEY][EXPENSES_KEY]

    if any([title.lower() == e[0].lower() for e in expenses[str(ctx.author.id)]]):
        await ctx.send(
            embeds=interactions.Embed(title="Already Exists", description="An expense with that title already exists",
                                      color=interactions.Color.red()), ephemeral=True)
        return

    expenses[str(ctx.author.id)].append([title, description, amount, unit])

    await ctx.send(embeds=interactions.Embed(title="Expense Added",
                                             description=f"Added expense **{title}** ({amount} {unit.upper()})",
                                             color=interactions.Color.green()), ephemeral=True)


@money_expense.subcommand(
    name="remove",
    description="Remove an expense.",
    options=[
        interactions.Option(
            name="title",
            description="The title of the expense",
            type=interactions.OptionType.STRING,
            required=True,
            autocomplete=True
        )
    ]
)
async def money_expense_remove(ctx: interactions.CommandContext, title: str):
    expenses = DATA[str(ctx.guild.id)][MONEY_KEY][EXPENSES_KEY][str(ctx.author.id)]

    for expense in expenses:
        if expense[0].lower() == title.lower():
            await ctx.send(
                embeds=interactions.Embed(title="Expense Removed", description=f"Removed expense **{expense[0]}**",
                                          color=interactions.Color.green()), ephemeral=True)
            return

    await ctx.send(embeds=interactions.Embed(title="Not Found", description="Could not find an expense by that title",
                                             color=interactions.Color.red()), ephemeral=True)


@money_expense.subcommand(
    name="list",
    description="List all your expenses.",
    options=[
        interactions.Option(
            name="player",
            description="Player for which to list the sources. Only DM may use.",
            type=interactions.OptionType.USER
        )
    ]
)
async def money_expense_list(ctx: interactions.CommandContext, player: interactions.Member = None):
    if player and not await check_dm(ctx, ctx.author): return

    user = player if player else ctx.author

    try:
        expenses = DATA[str(ctx.guild.id)][MONEY_KEY][EXPENSES_KEY][str(user.id)]
    except KeyError:
        expenses = []

    desc = f"{player.mention}\n\n" if player else ""

    if len(expenses) == 0:
        desc += "None"
    else:
        for expense in expenses:
            desc += f"**{expense[0]}** *{expense[2]} {expense[3].upper()}*\n{expense[1]}\n\n"

        desc = desc[:-2]

    await ctx.send(embeds=interactions.Embed(title="Expenses", description=desc, color=interactions.Color.green()),
                   ephemeral=True)


async def expense_clear_callback(ctx: interactions.ComponentContext):
    del DATA[str(ctx.guild.id)][MONEY_KEY][EXPENSES_KEY][str(ctx.author.id)]
    save_data()
    await ctx.send(embeds=interactions.Embed(title="Expenses Cleared",
                                             description="Expenses have been successfully cleared",
                                             color=interactions.Color.green()), ephemeral=True)


@money_expense.subcommand(
    name="clear",
    description="Clears every expense."
)
async def money_expense_clear(ctx: interactions.CommandContext):
    await confirm_action(ctx, "clear_expense", expense_clear_callback)


@money_command.group(
    name="income",
    description="Command for daily income tracking."
)
async def money_income(ctx: interactions.CommandContext):
    money = DATA[str(ctx.guild.id)][MONEY_KEY]
    if INCOME_KEY not in money:
        money[INCOME_KEY] = {}

    if str(ctx.author.id) not in money[INCOME_KEY]:
        money[INCOME_KEY][str(ctx.author.id)] = []


@money_income.subcommand(
    name="add",
    description="Add a daily income source.",
    options=[
        interactions.Option(
            name="title",
            description="Title of the source.",
            type=interactions.OptionType.STRING,
            required=True
        ),
        interactions.Option(
            name="description",
            description="Description of the source.",
            type=interactions.OptionType.STRING,
            required=True
        ),
        interactions.Option(
            name="amount",
            description="Amount of money.",
            type=interactions.OptionType.INTEGER,
            required=True
        ),
        interactions.Option(
            name="unit",
            description="Unit of money.",
            type=interactions.OptionType.STRING,
            required=True,
            choices=[
                interactions.Choice(
                    name="PP",
                    value="pp"
                ),
                interactions.Choice(
                    name="GP",
                    value="gp"
                ),
                interactions.Choice(
                    name="EP",
                    value="ep"
                ),
                interactions.Choice(
                    name="SP",
                    value="sp"
                ),
                interactions.Choice(
                    name="CP",
                    value="cp"
                )
            ]
        )
    ]
)
async def money_income_add(ctx: interactions.CommandContext, title: str, description: str, amount: int, unit: str):
    if amount < 1:
        await ctx.send(embeds=interactions.Embed(title="Invalid Amount", description="Amount must be greater than 0",
                                                 color=interactions.Color.red()), ephemeral=True)
        return

    incomes = DATA[str(ctx.guild.id)][MONEY_KEY][INCOME_KEY]

    if any([title.lower() == e[0].lower() for e in incomes[str(ctx.author.id)]]):
        await ctx.send(embeds=interactions.Embed(title="Already Exists",
                                                 description="An income source with that title already exists",
                                                 color=interactions.Color.red()), ephemeral=True)
        return

    incomes[str(ctx.author.id)].append([title, description, amount, unit])

    await ctx.send(embeds=interactions.Embed(title="Income Added",
                                             description=f"Added income source **{title}** ({amount} {unit.upper()})",
                                             color=interactions.Color.green()), ephemeral=True)


@money_income.subcommand(
    name="remove",
    description="Remove an income source.",
    options=[
        interactions.Option(
            name="title",
            description="The title of the source",
            type=interactions.OptionType.STRING,
            required=True,
            autocomplete=True
        )
    ]
)
async def money_income_remove(ctx: interactions.CommandContext, title: str):
    incomes = DATA[str(ctx.guild.id)][MONEY_KEY][INCOME_KEY][str(ctx.author.id)]

    for income in incomes:
        if income[0].lower() == title.lower():
            await ctx.send(
                embeds=interactions.Embed(title="Income Removed", description=f"Removed income source **{income[0]}**",
                                          color=interactions.Color.green()), ephemeral=True)
            return

    await ctx.send(
        embeds=interactions.Embed(title="Not Found", description="Could not find an income source by that title",
                                  color=interactions.Color.red()), ephemeral=True)


@money_income.subcommand(
    name="list",
    description="List all your income sources.",
    options=[
        interactions.Option(
            name="player",
            description="Player for which to list the sources. Only DM may use.",
            type=interactions.OptionType.USER
        )
    ]
)
async def money_income_list(ctx: interactions.CommandContext, player: interactions.Member = None):
    if player and not await check_dm(ctx, ctx.author): return

    user = player if player else ctx.author

    try:
        incomes = DATA[str(ctx.guild.id)][MONEY_KEY][INCOME_KEY][str(user.id)]
    except KeyError:
        incomes = []

    desc = f"{player.mention}\n\n" if player else ""

    if len(incomes) == 0:
        desc = "None"
    else:
        for income in incomes:
            desc += f"**{income[0]}** *{income[2]} {income[3].upper()}*\n{income[1]}\n\n"

        desc = desc[:-2]

    await ctx.send(
        embeds=interactions.Embed(title="Income Sources", description=desc, color=interactions.Color.green()),
        ephemeral=True)


async def income_clear_callback(ctx: interactions.ComponentContext):
    del DATA[str(ctx.guild.id)][MONEY_KEY][INCOME_KEY][str(ctx.author.id)]
    save_data()
    await ctx.send(embeds=interactions.Embed(title="Incoome Cleared",
                                             description="Income sources have been successfully cleared",
                                             color=interactions.Color.green()), ephemeral=True)


@money_income.subcommand(
    name="clear",
    description="Clears every income source."
)
async def money_income_clear(ctx: interactions.CommandContext):
    await confirm_action(ctx, "clear_income", income_clear_callback)


@money_expense_remove.autocomplete("title")
async def expense_and_income_title_autocomplete(ctx: interactions.CommandContext, user_input: str = ""):
    if ctx.data.options[0].name != "expense" and ctx.data.options[0].name != "income": return

    try:
        expenses = \
        DATA[str(ctx.guild.id)][MONEY_KEY][EXPENSES_KEY if ctx.data.options[0].name == "expense" else INCOME_KEY][
            str(ctx.author.id)]
    except KeyError:
        await ctx.populate([])
        return

    titles = [e[0] for e in expenses]

    await ctx.populate([interactions.Choice(name=title, value=title) for title in
                        filter(lambda key: key.lower().startswith(user_input.lower()), titles)][:25])


def confirm_quit():
    if askyesno("Confirm", "Are you sure you want to exit?"):
        quit_app()


if __name__ == '__main__':
    menu = (
        pystray.MenuItem("Confirm Quit", confirm_quit, default=True, visible=False),
        pystray.MenuItem("Quit", quit_app)
    )
    icon = pystray.Icon(name=appname, icon=Image.open(icon_file), title=appname, menu=menu)

    atexit.register(quit_app)
    signal.signal(signal.SIGTERM, quit_app)
    signal.signal(signal.SIGINT, quit_app)

    icon.run(lambda thing: bot.start())
