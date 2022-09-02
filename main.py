import asyncio
import json
import sys
import os
import os.path as path
import platform
from tkinter import *
from tkinter.messagebox import askyesno

import re
import uuid
import requests
import subprocess
import interactions
import interactions.ext.tasks as tasks
import pystray
from PIL import Image
from appdirs import *
from dotenv import get_key, set_key

from ZSDR import roll_dice

# TODO: make all embeds use the same formatting (periods, bolded inputs, etc)
# TODO: make most set commands also work as querying

SHARE_PREFIX = "https://app.adventurerscodex.com/share/"

DM_ROLE_KEY = "dm_role"
PLAYER_ROLE_KEY = "player_role"

INITIATIVE_KEY = "initiative"
CURRENT_INITIATIVE_KEY = "current_initiative"

DATES_KEY = "dates"
TIMELINE_KEY = "timeline"
CAMPAIGN_START_KEY = "campaign_start"
CURRENT_DATE_KEY = "current_date"
CALENDAR_KEY = "calendar"

MONEY_KEY = "money"
EXPENSES_KEY = "expenses"
INCOME_KEY = "income"

MONTHS = ["Hammer", "Alturiak", "Ches", "Tarsakh", "Mirtul", "Kythorn", "Flamerule", "Eleasis", "Eleint", "Marpenoth", "Uktar", "Nightal"]
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
        data = json.load(f)  # TODO: make this convert the proper string integers into integers
    except json.JSONDecodeError:
        data = {}


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


def quit_app():
    with open(data_file, "w") as f:
        json.dump(data, f)

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
        if str(guild.id) not in data:
            data[str(guild.id)] = {}


@bot.event
async def on_guild_join(guild):
    data[str(guild.id)] = {}


@bot.event
async def on_guild_remove(guild):
    del data[str(guild.id)]


async def check_dm(ctx: interactions.CommandContext, player: interactions.Member):
    if DM_ROLE_KEY not in data[str(ctx.guild.id)]:
        await ctx.send(embeds=interactions.Embed(title="DM Role Not Found", description="Use `/dm-role` to set a DM role doing this", color=interactions.Color.red()), ephemeral=True)
        return False

    dm_role_id = int(data[str(ctx.guild.id)][DM_ROLE_KEY])
    if dm_role_id not in player.roles:
        await ctx.send(embeds=interactions.Embed(title="Must be DM", description="You must have "+(await ctx.guild.get_role(dm_role_id)).mention+" to do this", color=interactions.Color.red()), ephemeral=True)
        return False

    return True


async def check_char_sheet(ctx: interactions.CommandContext, player: interactions.Member, self: bool = True):
    if not str(player.id) in data[str(ctx.guild.id)]:
        await ctx.send(embeds=interactions.Embed(title="No Character Sheet Linked",
                                                 description="Use `/link` to link your Adventurer's Codex character sheet" if self else player.mention + " does not have an Adventurer's Codex character sheet linked",
                                                 color=interactions.Color.red()), ephemeral=True)
        return False

    return True


def get_ability(player_id: str, ability: str, saving_throw: bool = False):
    if not (ability == "Strength" or ability == "Dexterity" or ability == "Constitution" or ability == "Intelligence" or ability == "Wisdom" or ability == "Charisma"):
        saving_throw = False

    r = requests.get(SHARE_PREFIX + player_id)

    pattern = re.compile("[> ]" + ability + "[<\n].+?"+("Saving Throw.+?" if saving_throw else "")+" ([+-] ?[0-9])", re.RegexFlag.DOTALL)
    return pattern.search(r.text).group(1).replace(" ", "")


def get_stat(player_id: str, stat: str):
    r = requests.get(SHARE_PREFIX + player_id)

    pattern = re.compile("(?<=[> ]" + stat + "[<\n]).+? (-?[0-9])", re.RegexFlag.DOTALL)
    return pattern.search(r.text).group(1)


def add_to_initiative(guild: interactions.Guild, name: str, initiative: int, modifier: int):
    initiative_l = data[str(guild.id)][INITIATIVE_KEY]
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
        elif idx == len(initiative_l)-1:
            initiative_l.append(new_value)

            index = len(initiative_l)-1
            break

    if index and index <= int(data[str(guild.id)][CURRENT_INITIATIVE_KEY]):
        data[str(guild.id)][CURRENT_INITIATIVE_KEY] = int(data[str(guild.id)][CURRENT_INITIATIVE_KEY]) + 1
    return index is not None

def is_date_later(date, check):
    date = [int(s) for s in date.split("-")]
    check = [int(s) for s in check.split("-")]

    return check[2] >= date[2] and check[1] >= date[1] and check[0] > date[0]


def get_spell_stat(text: str, stat: str):
    return re.sub("<.+?>|\n", "", re.search("<strong>"+stat+":</strong> (.+?)<[^/]+?>", text, flags=re.RegexFlag.DOTALL).group(1))


def format_date(guild: interactions.Guild, date):
    dates = data[str(guild.id)][DATES_KEY]

    date = [int(s) for s in date.split("-")]

    return f"{date[0]} {MONTHS[date[1]]}, {date[2]}{' ' + dates[CALENDAR_KEY] if CALENDAR_KEY in dates else ''}"


@bot.component("confirm_cancel")
async def confirm_cancel(ctx: interactions.ComponentContext):
    if ctx.author.id != ctx.message.interaction.user.id:
        await ctx.send(embeds=interactions.Embed(title="Error", description="You aren't allowed to do that",
                                                 color=interactions.Color.red()), ephemeral=True)
        return False

    await ctx.message.delete()
    return True


CALLBACK_IDS = {}
async def confirm_action(ctx, id: str, callback):  # TODO: make this use a Modal rather than a confirm button
    if id not in CALLBACK_IDS: CALLBACK_IDS[id] = 0
    confirm_button = interactions.Button(style=interactions.ButtonStyle.DANGER, label="Confirm", custom_id=f"{id}-{CALLBACK_IDS[id]}")
    CALLBACK_IDS[id] += 1

    @bot.component(confirm_button)
    async def confirm_callback(ctx: interactions.ComponentContext):
        if not await confirm_cancel(ctx):
            return

        await callback(ctx)

    embed = interactions.Embed(title=":warning: Confirm :warning:", description="Are you sure you want to continue? This action **cannot be undone**!\n\n*10*", color=interactions.Color.yellow())
    message = await ctx.send(embeds=embed, components=[interactions.Button(style=interactions.ButtonStyle.PRIMARY, label="Cancel", custom_id="confirm_cancel"), confirm_button])


    try:
        i = 10
        while i > 0:
            embed.description = embed.description.replace(str(i), str(i-1))
            await message.edit(embeds=embed)

            i -= 1
            await asyncio.sleep(1)

        await message.delete()
    except interactions.api.error.LibraryException:
        return


# Commands
@bot.command(
    name="link",
    description="Link your Adventurer's Codex character sheet.",
    options=[
        interactions.Option(
            name="link",
            description="The share link of your character sheet.",
            type=interactions.OptionType.STRING,
            required=True,
        )
    ]
)
async def link_command(ctx: interactions.CommandContext, link: str):
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
        data[str(ctx.guild.id)][str(ctx.author.id)] = link[-12: len(link)]


@bot.command(
    name="player-role",
    description="Set the role that denotes players.",
    options=[
        interactions.Option(
            name="role",
            description="Player role.",
            type=interactions.OptionType.ROLE,
            required=True,
        )
    ]
)
async def player_role(ctx: interactions.CommandContext, role: interactions.Role):
    data[str(ctx.guild.id)][PLAYER_ROLE_KEY] = str(role.id)
    await ctx.send(embeds=interactions.Embed(title="Role Set", description="Player role set to "+role.mention, color=interactions.Color.green()), ephemeral=True)


@bot.command(
    name="dm-role",
    description="Set the role that denotes the DM.",
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
    data[str(ctx.guild.id)][DM_ROLE_KEY] = str(role.id)
    await ctx.send(embeds=interactions.Embed(title="Role Set", description="DM role set to "+role.mention, color=interactions.Color.green()), ephemeral=True)


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
                interactions.Option(  # TODO: make this somehow integrate into the above option, or be a subcommand?
                    name="saving_throw",
                    description="Whether to roll as a saving throw or not. Only has effect for the core attributes.",
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
async def roll(ctx: interactions.CommandContext, sub_command: str, ability: str = "", saving_throw: bool = False, player: interactions.Member = None, dice: str = ""):
    title = dice

    if sub_command == "ability":
        if player and not (await check_dm(ctx, ctx.author)): return

        user = player if player else ctx.author

        if not (await check_char_sheet(ctx, user, not player)): return

        title = ability.replace("_", " ").title().replace("Of", "of")
        dice = "1d20" + get_ability(data[str(ctx.guild.id)][str(user.id)], title, saving_throw)

        if saving_throw: title += " Saving Throw"
        # TODO: add ✓ to title if proficient?

    try:
        await ctx.send(embeds=interactions.Embed(title=title, description=roll_dice(dice)[0], color=interactions.Color.blurple()), ephemeral=player is not None)
    except RuntimeError:
        await ctx.send(embeds=interactions.Embed(title="Error", description="Dice error, make sure you follow the formatting rules. `/roll help` for more info", color=interactions.Color.red()), ephemeral=True)


@bot.command(
    name="init",
    description="Initiative base command."
)
async def init(ctx: interactions.CommandContext):
    if INITIATIVE_KEY not in data[str(ctx.guild.id)]:
        data[str(ctx.guild.id)][INITIATIVE_KEY] = []
    if CURRENT_INITIATIVE_KEY not in data[str(ctx.guild.id)]:
        data[str(ctx.guild.id)][CURRENT_INITIATIVE_KEY] = 0


@init.subcommand(
    name="list",
    description="Lists the current initiative order."
)
async def init_list(ctx: interactions.CommandContext):
    guild = data[str(ctx.guild.id)]

    desc = ""

    for idx, value in enumerate(guild[INITIATIVE_KEY]):
        text = value[0]
        try:
            text = (await ctx.guild.get_member(int(value[0]))).mention
        except (interactions.api.error.LibraryException, ValueError):
            pass

        desc += text + " ("+value[1]+", "+("+" if int(value[2]) >= 0 else "")+value[2]+")" + (" **<---**" if guild[CURRENT_INITIATIVE_KEY] == idx else "") + "\n"

    if desc == "": desc = "Empty"

    await ctx.send(embeds=interactions.Embed(title="Initiative", description=desc, color=interactions.Color.blurple()), ephemeral=True)


@init.subcommand(
    name="next",
    description="Continue through the initiative order."
)
async def init_next(ctx: interactions.CommandContext):
    if not (await check_dm(ctx, ctx.author)): return

    guild = data[str(ctx.guild.id)]

    current = guild[CURRENT_INITIATIVE_KEY] = (int(guild[CURRENT_INITIATIVE_KEY])+1) % len(guild[INITIATIVE_KEY])

    name = text = guild[INITIATIVE_KEY][current][0]

    try:
        text = (await ctx.guild.get_member(int(name))).mention
    except (interactions.api.error.LibraryException, ValueError):
        pass

    modifier = guild[INITIATIVE_KEY][current][2]

    await ctx.send(embeds=interactions.Embed(title="Initiative", description="Next in initiative is: **"+text+"** ("+guild[INITIATIVE_KEY][current][1]+", "+("+" if int(modifier) >= 0 else "")+modifier+")", color=interactions.Color.blurple()))


async def init_clear_callback(ctx: interactions.ComponentContext):
    del data[str(ctx.guild.id)][INITIATIVE_KEY]
    del data[str(ctx.guild.id)][CURRENT_INITIATIVE_KEY]
    await ctx.send(embeds=interactions.Embed(title="Initiative Cleared",
                                             description="Initiative has been successfully cleared",
                                             color=interactions.Color.green()), ephemeral=True)


@init.subcommand(
    name="clear",
    description="Clears the entire initiative."
)
async def init_clear(ctx: interactions.CommandContext):
    if not (await check_dm(ctx, ctx.author)): return

    await confirm_action(ctx, "clear_initiative", init_clear_callback)


@init.group(
    name="add",
    description="Add something to the initiative order."
)
async def init_add(ctx: interactions.CommandContext):
    pass


@init_add.subcommand(
    name="player",
    description="Add a player to the initiative order.",
    options=[
        interactions.Option(
            name="player",
            description="The player to add.",
            type=interactions.OptionType.USER,
            required=True
        )
    ]
)
async def init_add_player(ctx: interactions.CommandContext, player: interactions.Member):
    if not (await check_dm(ctx, ctx.author)): return
    if not (await check_char_sheet(ctx, player, False)): return

    if any(value[0] == player.id for value in data[str(ctx.guild.id)][INITIATIVE_KEY]):
        await ctx.send(embeds=interactions.Embed(title="Already Added", description=player.mention+" is already in the initiative order. Use `/init remove "+player.user.username+"#"+player.user.discriminator+"` to remove them", color=interactions.Color.red()), ephemeral=True)
        return

    initiative = get_stat(data[str(ctx.guild.id)][str(player.id)], "Initiative")
    dice = "1d20"+("+"+initiative if int(initiative) >= 0 else initiative)

    score = roll_dice(dice)[1]

    while not add_to_initiative(ctx.guild, str(player.id), score, int(initiative)):
        score = roll_dice(dice)[1]

    await ctx.send(embeds=interactions.Embed(title="Added to Initiative", description="Added "+player.mention+" with a score of **"+str(score)+"**", color=interactions.Color.green()))


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
    if not (await check_dm(ctx, ctx.author)): return
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
        await ctx.send(embeds=interactions.Embed(title="Same as Member ID", description="You cannot create an initiative with the same name as a member's ID", color=interactions.Color.red()), ephemeral=True)
        return

    if any(value[0] == name for value in data[str(ctx.guild.id)][INITIATIVE_KEY]):
        await ctx.send(embeds=interactions.Embed(title="Already Added", description="'"+name+"' is already in the initiative order. Use `/init remove "+name+"` to remove it", color=interactions.Color.red()), ephemeral=True)
        return

    if not re.match("[+-][0-9]*", initiative):
        await ctx.send(embeds=interactions.Embed(title="Invalid Initiative", description="Initiative parameter not in the form '+/-[number]'", color=interactions.Color.red()), ephemeral=True)
        return

    dice = "1d20"+initiative

    score = roll_dice(dice)[1]

    while not add_to_initiative(ctx.guild, name, score, int(initiative.replace("+", ""))):
        score = roll_dice(dice)[1]

    await ctx.send(embeds=interactions.Embed(title="Added to Initiative", description="Added "+name+" with a score of **"+str(score)+"**", color=interactions.Color.green()))


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
    if not (await check_dm(ctx, ctx.author)): return

    initiative_l = data[str(ctx.guild.id)][INITIATIVE_KEY]

    if not any(value[0] == player.id for value in initiative_l):
        await ctx.send(embeds=interactions.Embed(title="Doesn't Exist", description=player.mention+" is not in the initiative order", color=interactions.Color.red()), ephemeral=True)
        return

    for idx, value in enumerate(initiative_l):
        if value[0] == str(player.id):
            del initiative_l[idx]
            await ctx.send(embeds=interactions.Embed(title="Removed from Initiative", description="Removed " + player.mention, color=interactions.Color.green()))
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
    if not (await check_dm(ctx, ctx.author)): return

    initiative_l = data[str(ctx.guild.id)][INITIATIVE_KEY]

    if not any(value[0] == name for value in initiative_l):
        await ctx.send(embeds=interactions.Embed(title="Doesn't Exist", description="'"+name+"' is not in the initiative order", color=interactions.Color.red()), ephemeral=True)
        return

    for idx, value in enumerate(initiative_l):
        if value[0] == name:
            del initiative_l[idx]
            await ctx.send(embeds=interactions.Embed(title="Removed from Initiative", description="Removed "+name, color=interactions.Color.green()))
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
        await ctx.send(embeds=interactions.Embed(title="Not Found", description="Could not find that spell", color=interactions.Color.red()), ephemeral=True)
        return

    r = requests.get("http://dnd5e.wikidot.com/spell:"+ALL_SPELLS[key])

    description = re.search("Duration.+?(<p>.+?</.+?>)\n<p><strong><em>Spell Lists", r.text, flags=re.RegexFlag.DOTALL).group(1)
    description = re.sub("</?p>|\n?</ul>|<ul>|</li>", "", re.sub("</?strong>", "**", re.sub("</?em>", "*", re.sub("<li>", "• ", description))))

    source = re.search("<p>Source: (.+?)</p>", r.text).group(1)
    spell_lists = ", ".join([match.group(1).title() for match in re.finditer("spells:(.+?)\"", r.text)])

    higher_level_match = re.search("At Higher Levels.+? (.+?)</p>", r.text)
    higher_level = None if not higher_level_match else higher_level_match.group(1)

    level_match = re.search("<em>(([0-9].+?-level.+?)|(.+?cantrip.+?))</em>", r.text)
    level = level_match.group(1) or level_match.group(2)

    embed_desc=f"""
    *{level}*
    
    **Casting Time:** {get_spell_stat(r.text, "Casting Time")}
    **Range:** {get_spell_stat(r.text, "Range")}
    **Duration:** {get_spell_stat(r.text, "Duration")}
    **Components:** {get_spell_stat(r.text, "Components")}

    {description}
    """

    if higher_level:
        embed_desc += f"***At Higher Levels.*** {higher_level}\n"

    embed_desc += f"""
    *{spell_lists}*
    Source: {source}
    """

    await ctx.send(embeds=interactions.Embed(title=key, description=embed_desc, color=interactions.Color.blurple()), ephemeral=not public)


@spell_command.autocomplete(
    name="spell"
)
async def autocomplete_spell(ctx: interactions.CommandContext, user_input: str = ""):
    spells = {key: ALL_SPELLS[key] for key in list(filter(lambda key: key.lower().startswith(user_input.lower()), ALL_SPELLS.keys()))[:25]}
    await ctx.populate([interactions.Choice(name=key, value=key) for key in spells.keys()])


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
    if DATES_KEY not in data[str(ctx.guild.id)]:
        data[str(ctx.guild.id)][DATES_KEY] = {TIMELINE_KEY: {}}


async def check_date(ctx: interactions.CommandContext, day: int, month: str, year: int):
    if day < 1 or day > 30 or year < 1:
        await ctx.send(embeds=interactions.Embed(title="Error", description="Invalid day or year. 1 <= day <= 30, year > 0.", color=interactions.Color.red()))
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
        dates = data[str(ctx.guild.id)][DATES_KEY]
        await ctx.send(embeds=interactions.Embed(title="Error", description=f"Date must follow the format 'day month year' or 'days CS[campagin start]/CD[current date]'.\n\n__Examples:__ '1 {MONTHS[0]} 1{' '+dates[CALENDAR_KEY] if CALENDAR_KEY in dates else ''}', '5 CS', '-5 CD'.", color=interactions.Color.red()), ephemeral=True)

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

    if key and key not in data[str(ctx.guild.id)][DATES_KEY]:
        await ctx.send(embeds=interactions.Embed(title="Error", description="Relative date not set! `/date "+("set" if key == CURRENT_DATE_KEY else "origin")+"` to set it", color=interactions.Color.red()), ephemeral=True)
        return None

    return key


async def relative_to_absolute_date(ctx: interactions.CommandContext, days: int, relative: str):
    relative_key = await relative_id_to_key(ctx, relative)
    if not relative_key: return None

    date = data[str(ctx.guild.id)][DATES_KEY][relative_key].split("-")
    day = int(date[0])
    month = int(date[1])
    year = int(date[2])

    day, month = rollover_date_number(day+days, month, 1, 30)
    month, year = rollover_date_number(month+1, year, 1, len(MONTHS)) # have to offset it because rollover doesn't work well with lower_bound being 0
    month -= 1

    return f"{day}-{month}-{year}"


async def check_new_date(ctx: interactions.CommandContext, day: int, month: str, year: int, days: int, relative: str):
    if (days and not relative) or (relative and not days) or (day and (not month or not year)) or (month and (not day or not year)) or (year and (not day or not month)) or (not days and not relative and not day and not month and not year):
        await ctx.send(embeds=interactions.Embed(title="Error", description="Must have either `days` and `relative` or `day`, `month`, and `year`.", color=interactions.Color.red()), ephemeral=True)
        return None

    if days and relative:
        return await relative_to_absolute_date(ctx, days, relative)
    else:
        return await check_date(ctx, day, month, year)


async def set_date_command(ctx: interactions.CommandContext, days: int, relative: str, day: int, month: str, year: int, key: str):
    if not (await check_dm(ctx, ctx.author)): return None

    date = await check_new_date(ctx, day, month, year, days, relative)
    if not date: return None

    data[str(ctx.guild.id)][DATES_KEY][key] = date
    return date


@date_command.subcommand(
    name="origin",
    description="Set the date for the campaign start.",
    options=NEW_DATE_OPTIONS
)
async def date_origin(ctx: interactions.CommandContext, days: int = None, relative: str = None, day: int = None, month: str = None, year: int = None):
    date = await set_date_command(ctx, days, relative, day, month, year, CAMPAIGN_START_KEY)

    if date:
        await ctx.send(embeds=interactions.Embed(title="Date Set", description="Campaign start date successfully set to **"+format_date(ctx.guild, date)+"**", color=interactions.Color.green()), ephemeral=True)


@date_command.subcommand(
    name="current",
    description="Set the current date.",
    options=NEW_DATE_OPTIONS
)
async def date_current(ctx: interactions.CommandContext, days: int = None, relative: str = None, day: int = None, month: str = None, year: int = None):
    date = await set_date_command(ctx, days, relative, day, month, year, CURRENT_DATE_KEY)

    if date:
        await ctx.send(embeds=interactions.Embed(title="Date Set", description="Current date successfully set to **"+format_date(ctx.guild, date)+"**", color=interactions.Color.green()), ephemeral=True)


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
        await ctx.send(embeds=interactions.Embed(title="Date Set", description="Current date advanced to **"+format_date(ctx.guild, date)+"**", color=interactions.Color.green()), ephemeral=True)

        if (downtime):
            money = data[str(ctx.guild.id)][MONEY_KEY]

            for key in money:
                for user in money[key]:
                    for item in money[key][user]:


            # TODO: apply daily income and expenses
            pass

@date_command.subcommand(
    name="calendar",
    description="Set the calender suffix.",
    options=[
        interactions.Option(
            name="suffix",
            description="The suffix to use (e.g. DR)",
            type=interactions.OptionType.STRING,
            required=True
        )
    ]
)
async def date_calendar(ctx: interactions.CommandContext, suffix: str):
    if not (await check_dm(ctx, ctx.author)): return

    data[str(ctx.guild.id)][DATES_KEY][CALENDAR_KEY] = suffix
    await ctx.send(embeds=interactions.Embed(title="Calendar Set", description="Calendar suffix successfully set to **"+suffix+"**", color=interactions.Color.green()))


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
async def date_event_add(ctx: interactions.CommandContext, title: str, description: str, day: int, month: str, year: int, days: int, relative: str):
    if not (await check_dm(ctx, ctx.author)): return

    date = await check_new_date(ctx, day, month, year, days, relative)
    if not date: return

    timeline = data[str(ctx.guild.id)][DATES_KEY][TIMELINE_KEY]

    if date not in timeline:
        timeline[date] = {}

    if title in timeline[date]:
        await ctx.send(embeds=interactions.Embed(title="Already Exists", description="An event with that name on that date already exists. `/date event remove` to remove it", color=interactions.Color.red()), ephemeral=True)
        return

    timeline[date][title] = description
    await ctx.send(embeds=interactions.Embed(title="Event Added", description="**"+title+"** has been added on **"+format_date(ctx.guild, date)+"**", color=interactions.Color.green()), ephemeral=True)


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
    if not (await check_dm(ctx, ctx.author)): return

    date = await convert_and_check_date(ctx, date)
    if not date: return

    timeline = data[str(ctx.guild.id)][DATES_KEY][TIMELINE_KEY]

    if date not in timeline or title not in timeline[date]:
        await ctx.send(embeds=interactions.Embed(title="Doesn't Exist", description="Cannot find an event with that title on that date", color=interactions.Color.red()), ephemeral=True)
        return

    del timeline[date][title]
    await ctx.send(embeds=interactions.Embed(title="Event Removed", description="**" + title +"** has been removed from **" + format_date(ctx.guild, date) + "**", color=interactions.Color.green()), ephemeral=True)


@date_event.subcommand(
    name="list",
    description="List the events on a date.",
    options=[EXISTING_DATE_OPTION]
)
async def date_event_list(ctx: interactions.CommandContext, date: str):
    date = await convert_and_check_date(ctx, date)
    if not date: return

    timeline = data[str(ctx.guild.id)][DATES_KEY][TIMELINE_KEY]

    events = ""

    if date not in timeline or len(timeline[date]) == 0:
        events = "Empty"
    else:
        for title, description in timeline[date].items():
            events += f"**{title}**\n{description}\n\n"

        events = events[:-2]

    await ctx.send(embeds=interactions.Embed(title=format_date(ctx.guild, date), description=events, color=interactions.Color.blurple()), ephemeral=True)


async def clear_date_events_callback(ctx: interactions.ComponentContext):
    date = ctx.custom_id.split("|")[1]

    del data[str(ctx.guild.id)][DATES_KEY][TIMELINE_KEY][date]

    await ctx.send(embeds=interactions.Embed(title="Events Cleared",
                                             description=f"Removed all events on **{format_date(ctx.guild, date)}**",
                                             color=interactions.Color.green()), ephemeral=True)


@date_event.subcommand(
    name="clear",
    description="Remove every event on a date.",
    options=[EXISTING_DATE_OPTION]
)
async def date_event_clear(ctx: interactions.CommandContext, date: str):
    if not (await check_dm(ctx, ctx.author)): return

    date = await convert_and_check_date(ctx, date)
    if not date: return

    timeline = data[str(ctx.guild.id)][DATES_KEY][TIMELINE_KEY]

    if date not in timeline or len(timeline[date]) == 0:
        await ctx.send(embeds=interactions.Embed(title="No Events", description="No events found!", color=interactions.Color.red()), ephemeral=True)
        return

    await confirm_action(ctx, f"clear_date_events|{date}|", clear_date_events_callback)


async def clear_all_events_callback(ctx: interactions.ComponentContext):
    del data[str(ctx.guild.id)][DATES_KEY][TIMELINE_KEY]

    await ctx.send(embeds=interactions.Embed(title="Events Cleared",
                                             description=f"Removed **every** event",
                                             color=interactions.Color.green()), ephemeral=True)


@date_event.subcommand(
    name="clear-all",
    description="Remove every event."
)
async def date_event_clear_all(ctx: interactions.CommandContext):
    if not (await check_dm(ctx, ctx.author)): return

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
    timeline = data[str(ctx.guild.id)][DATES_KEY][TIMELINE_KEY]

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

    await ctx.send(embeds=interactions.Embed(title=title, description=desc, color=interactions.Color.blurple()), ephemeral=True)


@date_event.autocomplete("date")  # TODO: a way to make this work only for date_event_remove and take into accout the `event` param?
async def autocomplete_date(ctx: interactions.CommandContext, user_input: str = ""):
    dates = [format_date(ctx.guild, date) for date in data[str(ctx.guild.id)][DATES_KEY][TIMELINE_KEY]]
    if re.match("-?[0-9]+ ?", user_input):
        space = "" if user_input.endswith(" ") else " "
        dates = [user_input+space+"CS", user_input+space+"CD"] + dates

    await ctx.populate([interactions.Choice(name=date, value=date) for date in filter(lambda key: user_input.lower() in key.lower(), dates)][:25])


@date_event.autocomplete("title")
async def autocomplete_event_title(ctx: interactions.CommandContext, user_input: str = ""):
    timeline = data[str(ctx.guild.id)][DATES_KEY][TIMELINE_KEY]
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
    guild = data[str(ctx.guild.id)]

    if MONEY_KEY not in guild:
        guild[MONEY_KEY] = {}
    if INCOME_KEY not in guild[MONEY_KEY]:
        guild[MONEY_KEY][INCOME_KEY] = {}


@money_command.group(
    name="expense",
    description="Command for daily expense tracking."
)
async def money_expense(ctx: interactions.CommandContext):
    money = data[str(ctx.guild.id)][MONEY_KEY]
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
        await ctx.send(embeds=interactions.Embed(title="Invalid Amount", description="Amount must be greater than 0", color=interactions.Color.red()), ephemeral=True)
        return

    expenses = data[str(ctx.guild.id)][MONEY_KEY][EXPENSES_KEY]

    if any([title.lower() == e[0].lower() for e in expenses[str(ctx.author.id)]]):
        await ctx.send(embeds=interactions.Embed(title="Already Exists", description="An expense with that title already exists", color=interactions.Color.red()), ephemeral=True)
        return

    expenses[str(ctx.author.id)].append([title, description, amount, unit])

    await ctx.send(embeds=interactions.Embed(title="Expense Added", description=f"Added expense **{title}** ({amount} {unit.upper()})", color=interactions.Color.green()), ephemeral=True)


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
    expenses = data[str(ctx.guild.id)][MONEY_KEY][EXPENSES_KEY][str(ctx.author.id)]

    for expense in expenses:
        if expense[0].lower() == title.lower():
            await ctx.send(embeds=interactions.Embed(title="Expense Removed", description=f"Removed expense **{expense[0]}**", color=interactions.Color.green()), ephemeral=True)
            return

    await ctx.send(embeds=interactions.Embed(title="Not Found", description="Could not find an expense by that title", color=interactions.Color.red()), ephemeral=True)


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
    if player and not (await check_dm(ctx, ctx.author)): return

    user = player if player else ctx.author

    try:
        expenses = data[str(ctx.guild.id)][MONEY_KEY][EXPENSES_KEY][str(user.id)]
    except KeyError:
        expenses = []

    desc = f"{player.mention}\n\n" if player else ""

    if len(expenses) == 0:
        desc += "None"
    else:
        for expense in expenses:
            desc += f"**{expense[0]}** *{expense[2]} {expense[3].upper()}*\n{expense[1]}\n\n"

        desc = desc[:-2]

    await ctx.send(embeds=interactions.Embed(title="Expenses", description=desc, color=interactions.Color.green()), ephemeral=True)


@money_command.group(
    name="income",
    description="Command for daily income tracking."
)
async def money_income(ctx: interactions.CommandContext):
    money = data[str(ctx.guild.id)][MONEY_KEY]
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
        await ctx.send(embeds=interactions.Embed(title="Invalid Amount", description="Amount must be greater than 0", color=interactions.Color.red()), ephemeral=True)
        return

    incomes = data[str(ctx.guild.id)][MONEY_KEY][INCOME_KEY]

    if any([title.lower() == e[0].lower() for e in incomes[str(ctx.author.id)]]):
        await ctx.send(embeds=interactions.Embed(title="Already Exists", description="An income source with that title already exists", color=interactions.Color.red()), ephemeral=True)
        return

    incomes[str(ctx.author.id)].append([title, description, amount, unit])

    await ctx.send(embeds=interactions.Embed(title="Income Added", description=f"Added income source **{title}** ({amount} {unit.upper()})", color=interactions.Color.green()), ephemeral=True)


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
    incomes = data[str(ctx.guild.id)][MONEY_KEY][INCOME_KEY][str(ctx.author.id)]

    for income in incomes:
        if income[0].lower() == title.lower():
            await ctx.send(embeds=interactions.Embed(title="Income Removed", description=f"Removed income source **{income[0]}**", color=interactions.Color.green()), ephemeral=True)
            return

    await ctx.send(embeds=interactions.Embed(title="Not Found", description="Could not find an income source by that title", color=interactions.Color.red()), ephemeral=True)


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
    if player and not (await check_dm(ctx, ctx.author)): return

    user = player if player else ctx.author

    try:
        incomes = data[str(ctx.guild.id)][MONEY_KEY][INCOME_KEY][str(user.id)]
    except KeyError:
        incomes = []

    desc = f"{player.mention}\n\n" if player else ""

    if len(incomes) == 0:
        desc = "None"
    else:
        for income in incomes:
            desc += f"**{income[0]}** *{income[2]} {income[3].upper()}*\n{income[1]}\n\n"

        desc = desc[:-2]

    await ctx.send(embeds=interactions.Embed(title="Income Sources", description=desc, color=interactions.Color.green()), ephemeral=True)


@money_expense_remove.autocomplete("title")
async def expense_and_income_title_autocomplete(ctx: interactions.CommandContext, user_input: str = ""):
    if ctx.data.options[0].name != "expense" and ctx.data.options[0].name != "income": return

    try:
        data = data[str(ctx.guild.id)][MONEY_KEY][EXPENSES_KEY if ctx.data.options[0].name == "expense" else INCOME_KEY][str(ctx.author.id)]
    except KeyError:
        await ctx.populate([])
        return

    titles = [e[0] for e in data]

    await ctx.populate([interactions.Choice(name=title, value=title) for title in filter(lambda key: key.lower().startswith(user_input.lower()), titles)][:25])


def confirm_quit():
    if askyesno("Confirm", "Are you sure you want to exit?"):
        quit_app()

menu = (
    pystray.MenuItem("Confirm Quit", confirm_quit, default=True, visible=False),
    pystray.MenuItem("Quit", quit_app)
)
icon = pystray.Icon(name=appname, icon=Image.open(icon_file), title=appname, menu=menu)

icon.run(lambda thing: bot.start())
