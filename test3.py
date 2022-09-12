import discord
from gtts import gTTS
from io import BytesIO
import speech_recognition as sr
from time import sleep
import wave

import threading
import os
import re
import requests

os.environ['PATH'] += os.pathsep + r'C:\Users\Malcolm\Downloads\ffmpeg-2022-09-07-git-e4c1272711-essentials_build\bin'

from FFmpegPCMAudioGTTS import FFmpegPCMAudioGTTS

intents = discord.Intents.default()
bot = discord.Client(intents=intents)

r = sr.Recognizer()
voice: discord.VoiceClient = None


class BufSink(discord.sinks.Sink):
    def __init__(self):
        # if filters is None:
        #     filters = discord.sinks.default_filters
        # self.filters = filters
        # discord.sinks.Filters.__init__(self, **self.filters)
        #
        # self.encoding = "none"
        # self.vc = None
        # self.audio_data = {}
        super().__init__()

        self.bytearr_buf = bytearray()
        self.sample_width = 2
        self.sample_rate = 96000
        self.bytes_ps = 192000

    def write(self, data, user):
        self.bytearr_buf += data

    def freshen(self, idx):
        self.bytearr_buf = self.bytearr_buf[idx:]


async def callback(sink: discord.sinks.Sink):
    print('callback')

    await bot.close()


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


conversation = ""


def check_convo():
    global conversation

    convo = " ".join(conversation.split(" ")[-7:])
    print("testing: "+convo)

    if ("d&d" in convo or "d and d" in convo or "dnd" in convo or "indie" in convo or "indy" in convo) and ("bot" in convo or "bar" in convo or "debot" in convo):
        if "roll" in convo:
            split = convo[convo.index("roll") + 4:]
            if "d" in split:
                split = split.split("d")
            elif "to" in split:
                split = split.split("to")
            elif "day" in split:
                split = split.split("day")
            try:
                amt = int(re.sub('[^0-9]', '', split[0]))
                dice = int(re.sub('[^0-9]', '', split[1]))
                play(f"Rolling {amt}d{dice}")

                conversation = ""
            except (IndexError, ValueError) as e:
                pass


def thread(sink):
    global conversation

    while True:
        SECONDS = 4
        if len(sink.bytearr_buf) > sink.bytes_ps*SECONDS:
            idx = sink.bytes_ps * SECONDS
            slice = sink.bytearr_buf[:idx]

            if any(slice):
                idx_strip = slice.index(next(filter(lambda x: x != 0, slice)))
                if idx_strip:
                    sink.freshen(idx_strip)
                    slice = sink.bytearr_buf[:idx]
                audio = sr.AudioData(bytes(slice), sink.sample_rate,
                                     sink.sample_width)

                print('recognizing: ', end='')
                msg: str = None
                try:
                    msg = r.recognize_wit(audio, key='6QS5GTMV2B4FAPGVBA3OQTK45MN7HESX').lower()
                except sr.UnknownValueError:
                    print("ERROR: Couldn't understand.")
                except sr.RequestError as e:
                    print("ERROR: Could not request results from Wit.ai service; {0}".format(e))

                if msg:
                    print(msg)

                    conversation += " " + msg.replace("zero", "0").replace("one", "1").replace("two", "2").replace("three", "3").replace("four", "4").replace("five", "5").replace("six", "6").replace("seven", "7").replace("eight", "8").replace("nine", "9")
                    check_convo()

            sink.freshen(idx)


bot.run('MTAxMzk2NDc0MzE4NDIyODM4Mw.GrmmXR.94QvBBACgu5r0-j9pq9RsKY5e8boGluf5cIYsM')
