import asyncio
import json
import sys
import os
import os.path as path
import platform
from tkinter import *
from tkinter.messagebox import askyesno

import re
import requests
import subprocess
import interactions
import interactions.ext.tasks as tasks
import pystray
from PIL import Image
from appdirs import *
from dotenv import get_key, set_key

from ZSDR import roll_dice

SHARE_PREFIX = "https://app.adventurerscodex.com/share/"
DM_ROLE_KEY = "dm_role"
PLAYER_ROLE_KEY = "player_role"
INITIATIVE_KEY = "initiative"
CURRENT_INITIATIVE_KEY = "current_initiative"
ALL_SPELLS = {}
SPELLS_BY_CLASS_AND_LEVEL = {}


def populate_spells():
    global ALL_SPELLS

    r = requests.get("http://dnd5e.wikidot.com/spells")
    pattern = re.compile("<a href=\"/spell:(.*?)\">(.*?)</a>")

    for match in pattern.finditer(r.text):
        ALL_SPELLS[match.group(2)] = match.group(1)

        # spell_r = requests.get("http://dnd5e.wikidot.com/spell:"+match.group(1))
        # spell_pattern = re.compile("spells:(.*?)\"")
        #
        # level_match = re.search("<em>([0-9]).*?-level|(cantrip).*?<\/em>", spell_r.text)
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
        data = json.load(f)
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
            i = i.strip

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
        await ctx.send(embeds=interactions.Embed(title="DM Role Not Found", description="Use `/dm-role` to set a DM role before using the `player` paremeter", color=interactions.Color.red()), ephemeral=True)
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

    pattern = re.compile("[> ]" + ability + "[<\n].*?"+("Saving Throw.*?" if saving_throw else "")+" ([+-] ?[0-9])", re.RegexFlag.DOTALL)
    return pattern.search(r.text).group(1).replace(" ", "")


def get_stat(player_id: str, stat: str):
    r = requests.get(SHARE_PREFIX + player_id)

    pattern = re.compile("(?<=[> ]" + stat + "[<\n]).*? (-?[0-9])", re.RegexFlag.DOTALL)
    return pattern.search(r.text).group(1)


def add_to_initiative(guild: interactions.Guild, name: str, initiative: int, modifier: int):
    initiative_l = data[str(guild.id)][INITIATIVE_KEY]
    new_value = [name, str(initiative), str(modifier)]

    if len(initiative_l) == 0:
        initiative_l.append(new_value)
        return True

    for idx, value in enumerate(initiative_l):
        if initiative > int(value[1]) or (initiative == int(value[1]) and modifier > int(value[2])):
            initiative_l.insert(idx, new_value)
            return True
        elif idx == len(initiative_l)-1:
            initiative_l.append(new_value)
            return True

    return False


def get_spell_stat(text: str, stat: str):
    return re.search("<strong>"+stat+":</strong> (.*?)<", text).group(1)


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
    scope=bot.guilds,
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
    scope=bot.guilds,
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
    scope=bot.guilds,
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
        await ctx.send(embeds=interactions.Embed(title=title, description=str(roll_dice(dice)), color=interactions.Color.blurple()), ephemeral=player is not None)
    except RuntimeError:
        await ctx.send(embeds=interactions.Embed(title="Error", description="Dice error, make sure you follow the formatting rules. `/roll help` for more info", color=interactions.Color.red()), ephemeral=True)


@bot.command(
    name="init",
    description="Initiative base command.",
    scope=bot.guilds
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


@init.subcommand(
    name="clear",
    description="Clears the entire initiative."
)
async def init_clear(ctx: interactions.CommandContext):
    if not (await check_dm(ctx, ctx.author)): return

    message = await ctx.send(embeds=interactions.Embed(title=":warning: Confirm :warning:", description="Are you sure you want to clear the initiative? This action cannot be undone", color=interactions.Color.yellow()), components=[interactions.Button(style=interactions.ButtonStyle.PRIMARY, label="Cancel", custom_id="cancel_clear_initiative"), interactions.Button(style=interactions.ButtonStyle.DANGER, label="Confirm", custom_id="clear_initiative")])
    await asyncio.sleep(10)
    try:
        await message.message.delete()
    except interactions.api.error.LibraryException:
        pass


@bot.component("cancel_clear_initiative")
async def cancel_clear_initiative_button(ctx: interactions.ComponentContext):
    if ctx.author.id != ctx.message.interaction.user.id:
        await ctx.send(embeds=interactions.Embed(title="Error", description="You aren't allowed to do that", color=interactions.Color.red()), ephemeral=True)
        return

    await ctx.message.delete()


@bot.component("clear_initiative")
async def clear_initiative_button(ctx: interactions.ComponentContext):
    if ctx.author.id != ctx.message.interaction.user.id:
        await ctx.send(embeds=interactions.Embed(title="Error", description="You aren't allowed to do that", color=interactions.Color.red()), ephemeral=True)
        return

    await ctx.message.delete()

    del data[str(ctx.guild.id)][INITIATIVE_KEY]
    await ctx.send(embeds=interactions.Embed(title="Initiative Cleared", description="Initiative has been successfully cleared", color=interactions.Color.green()), ephemeral=True)


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

    score = roll_dice("1d20"+("+"+initiative if int(initiative) >= 0 else initiative))
    score = int(re.search("[0-9]*", score[::-1]).group()[::-1])

    while not add_to_initiative(ctx.guild, str(player.id), score, int(initiative)):
        score = roll_dice("1d20" + ("+" + initiative if int(initiative) >= 0 else initiative))
        score = int(re.search("[0-9]*", score[::-1]).group()[::-1])

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

    score = roll_dice("1d20"+initiative)
    score = int(re.search("[0-9]*", score[::-1]).group()[::-1])

    while not add_to_initiative(ctx.guild, name, score, int(initiative.replace("+", ""))):
        score = roll_dice("1d20"+initiative)
        score = int(re.search("[0-9]*", score[::-1]).group()[::-1])

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
    scope=bot.guilds,
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

    description = re.search("Duration.*?<p>(.*?)</p>", r.text, flags=re.RegexFlag.DOTALL).group(1)
    source = re.search("<p>Source: (.*?)</p>", r.text).group(1)
    spell_lists = ", ".join([match.group(1).title() for match in re.finditer("spells:(.*?)\"", r.text)])

    higher_level_match = re.search("At Higher Levels.*? (.*?)</p>", r.text)
    higher_level = None if not higher_level_match else higher_level_match.group(1)

    level_match = re.search("<em>(([0-9].*?-level.*?)|(.*?cantrip.*?))</em>", r.text)
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


@bot.autocomplete(
    command=spell_command.name,
    name="spell"
)
async def autocomplete_spell(ctx: interactions.CommandContext, user_input: str = ""):
    spells = {key: ALL_SPELLS[key] for key in list(filter(lambda key: key.lower().startswith(user_input.lower()), ALL_SPELLS.keys()))[0:25]}
    await ctx.populate([interactions.Choice(name=key, value=value) for key, value in spells.items()])


def confirm_quit():
    if askyesno("Confirm", "Are you sure you want to exit?"):
        quit_app()


menu = (
    pystray.MenuItem("Confirm Quit", confirm_quit, default=True, visible=False),
    pystray.MenuItem("Quit", quit_app)
)
icon = pystray.Icon(name=appname, icon=Image.open(icon_file), title=appname, menu=menu)

icon.run(lambda thing: bot.start())
