import os

import discord
from discord.member import Member
import speech_recognition as sr
from gtts import gTTS
from voice_testing.FFmpegPCMAudioGTTS import FFmpegPCMAudioGTTS
from io import BytesIO
import subprocess

os.environ['PATH'] += os.pathsep + r'C:\Users\Malcolm\Downloads\ffmpeg-2022-09-07-git-e4c1272711-essentials_build\bin'

from voice_recv import *

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

voice: VoiceRecvClient

r = sr.Recognizer()


def on_packet(member: Member, packet: RTPPacket):
    

    args = [
        "ffmpeg",
        "-f", "s16le",
        "-ar", "48000",
        "-ac", "2",
        "-i", "-",
        "-f", "mp3",
        "pipe:1",
    ]
    process = subprocess.Popen(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE
    )

    out = BytesIO(process.communicate(packet.decrypted_data)[0])
    with sr.AudioFile(out) as source:
        print(r.recognize_google(r.record(source)))


@bot.event
async def on_ready():
    global voice

    for guild in bot.guilds:
        meeting = 815693947447672897
        gen1 = 815695304908079164
        gen2 = 891135432543338496
        channel = await guild.fetch_channel(gen1)
        voice = await channel.connect(cls=VoiceRecvClient)

        voice.listen(OpusD(on_packet))

        audio = gTTS(text="Hello humans, bao down to your new leader.", slow=False)
        buf = BytesIO()
        audio.write_to_fp(buf)
        buf.seek(0)
        with open(r'C:\Users\Malcolm\Downloads\test', 'wb') as f:
            f.write(buf.read())
        buf.seek(0)

        source = FFmpegPCMAudioGTTS(buf.read(), pipe=True, executable=r'C:\Users\Malcolm\Downloads\ffmpeg-2022-09-07-git-e4c1272711-essentials_build\bin\ffmpeg')
        # voice.play(source)


bot.run('MTAxMzk2NDc0MzE4NDIyODM4Mw.GrmmXR.94QvBBACgu5r0-j9pq9RsKY5e8boGluf5cIYsM')
