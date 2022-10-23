import discord  # also needs PyNaCl
from gtts import gTTS
from io import BytesIO
import speech_recognition as sr
from time import sleep

import threading
import os
import re
import requests
import json
import platform

WIT_TOKEN="PE237IFDN3ZR4EZOHJG2RDTWZG3AP74N"

os.environ['PATH'] += os.pathsep + (
                      r'C:\Users\Malcolm\Downloads\ffmpeg-2022-09-07-git-e4c1272711-essentials_build\bin' if platform.platform() == 'Windows'
                      else r'/Users/malcolmroalson/Downloads/ffmpeg'
                    )
from voice_testing.FFmpegPCMAudioGTTS import FFmpegPCMAudioGTTS

intents = discord.Intents.default()
bot = discord.Client(intents=intents)

r = sr.Recognizer()
voice: discord.VoiceClient = None


class BufSink(discord.sinks.Sink):
    def __init__(self):
        super().__init__()

        self.data = {}
        self.sample_width = 2
        self.sample_rate = 96000
        self.bytes_ps = 192000

    def write(self, data, user):
        if user not in self.data:
            self.data[user] = bytearray()

        self.data[user] += data


async def callback(sink: discord.sinks.Sink):
    print('callback')

    os._exit(0)


def play(text: str):
    if voice.is_playing(): return

    audio = gTTS(text=text, slow=False)

    buf = BytesIO()
    audio.write_to_fp(buf)
    buf.seek(0)

    source = FFmpegPCMAudioGTTS(buf.read(), pipe=True)
    voice.play(source)


@bot.event
async def on_ready():
    global voice

    for guild in bot.guilds:
        meeting = 815693947447672897
        gen1 = 815695304908079164
        gen2 = 891135432543338496
        # cyrus = (await guild.fetch_member(724456177420730448)).voice.channel.id
        malcolmb = (await guild.fetch_member(501212640392118272)).voice.channel.id
        channel = await guild.fetch_channel(malcolmb)
        voice = await channel.connect()

        sink = BufSink()
        voice.start_recording(sink, callback)

        threading.Thread(target=thread, args=[sink]).start()


conversations = {}


def check_words(user):
    orig = conversations[user].split(" ")[-7:]
    words = "%20".join(orig)

    print(f'{user} parsing: {" ".join(orig)}')
    return
    req = requests.get(f'https://api.wit.ai/message?v=20220915&q={words}', headers={'authorization': f'Bearer {WIT_TOKEN}'})
    entities = json.loads(req.text)['entities']

    if 'begin:begin' in entities and 'roll:roll' in entities and 'roll:amount' in entities and 'roll:dice' in entities:
        amt = int(re.sub('[^0-9]', '', entities['roll:amount'][0]['value']))
        dice = int(re.sub('[^0-9]', '', entities['roll:dice'][0]['value']))
        play(f"Rolling {amt}d{dice}")

        conversations[user] = conversations[user].replace(" ".join(orig), "", 1)

    # if ("d&d" in words or "d and d" in words or "dnd" in words or "indie" in words or "indy" in words) and ("bot" in words or "bar" in words or "debot" in words):
    #     split = None
    #     if "roll" in words:
    #         split = words[words.index("roll") + 4:]
    #     elif "raw" in words:
    #         split = words[words.index("raw") + 3:]
    #
    #     if split:
    #         if "d" in split:
    #             split = split.split("d")
    #         elif "b" in split:
    #             split = split.split("b")
    #         elif "to" in split:
    #             split = split.split("to")
    #         elif "day" in split:
    #             split = split.split("day")
    #         try:
    #             amt = int(re.sub('[^0-9]', '', split[0]))
    #             dice = int(re.sub('[^0-9]', '', split[1]))
    #             play(f"Rolling {amt}d{dice}")
    #
    #             conversations[user] = ""
    #         except (IndexError, ValueError) as e:
    #             pass


def parse_user(sink, user):
    data = sink.data[user]
    sink.data[user] = bytearray()

    if any(data):
        idx_strip = data.index(next(filter(lambda x: x != 0, data)))
        if idx_strip:
            data = data[idx_strip:]

        data = data[::-1]

        idx_strip = data.index(next(filter(lambda x: x != 0, data)))
        if idx_strip:
            data = data[idx_strip:]

        data = data[::-1]

        audio = sr.AudioData(bytes(data), sink.sample_rate,
                             sink.sample_width)

        print(f'{user} starting recognition')
        try:
            msg = r.recognize_wit(audio, key=WIT_TOKEN).lower()
        except sr.UnknownValueError:
            print(f"{user}: ERROR: Couldn't understand.")
        except sr.RequestError as e:
            print(f"{user}: ERROR: Could not request results from Wit.ai service; {e}")
        else:
            msg = msg.replace("zero", "0").replace("one", "1").replace("two", "2").replace(
                "three", "3").replace("four", "4").replace("five", "5").replace("six", "6").replace(
                "seven", "7").replace("eight", "8").replace("nine", "9")
            print(f"{user} recognized: {msg}")
            if user not in conversations:
                conversations[user] = ""

            conversations[user] += " " + msg
            check_words(user)


SECONDS = 5
def thread(sink):
    while True:
        try:
            for user in sink.data:
                threading.Thread(target=parse_user, args=[sink, user]).start()

            sleep(SECONDS)
        except RuntimeError:
            pass


bot.run('MTAxMzk2NDc0MzE4NDIyODM4Mw.GVj16Y.WMSzIsU3I8gKvtAlwbb1xcyLssbS_oXvoFTjXQ')
