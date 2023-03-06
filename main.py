from config import *

import discord,datetime,io,wave,openai,subprocess,os,random,threading,time
from discord.ext import tasks
openai.api_key = OPENAI_KEY

from TTS.api import TTS
from pydub import AudioSegment
from pydub.silence import detect_nonsilent

def may_contain_speech(mp3_bytes):
    audio = AudioSegment.from_file(mp3_bytes, format="mp3")
    audio_duration = len(audio) / 1000  # convert milliseconds to seconds
    audio_rms = audio.dBFS
    non_silent = detect_nonsilent(audio, min_silence_len=1000, silence_thresh=audio_rms-16)
    total_nonsilent_duration = sum([segment[1] - segment[0] for segment in non_silent])
    if total_nonsilent_duration > 1500:
        return True  # the file may contain speech
    else:
        return False  # the file does not contain speech
    
def wav_to_mp3(wav_bytes):
    # Create a BytesIO object to hold the WAV data
    wav_buffer = io.BytesIO(wav_bytes)

    # Convert the WAV data to MP3 using ffmpeg
    process = subprocess.Popen(
        ["ffmpeg", "-i", "-", "-f", "mp3", "-"], 
        stdin=subprocess.PIPE, 
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    stdout, stderr = process.communicate(input=wav_buffer.read())
    if process.returncode != 0:
        raise Exception(f"Failed to convert WAV to MP3: {stderr.decode()}")

    # Return the MP3 data as a byte string
    return stdout


bot = discord.Bot()
connections = {}
user_is_speaking = {}
user_was_speaking = {}
channel_by_user = {}
user_was_speaking_at = {}
memory = []

audio_data = {}

class CustomSink(discord.sinks.Sink):
    def __init__(self):
        super().__init__()
        
    def write(self, data, user):
        channel_by_user[user] = self.vc
        user_is_speaking[user] = True
        user_was_speaking_at[user] = datetime.datetime.now()
        if user not in audio_data.keys():
            file = io.BytesIO()
            audio_data.update({user: discord.sinks.AudioData(file)})

        file = audio_data[user]
        file.write(data)

@bot.event
async def on_ready():
    check.start()

tts = TTS('tts_models/en/vctk/vits')

@tasks.loop(seconds=0.2)
async def check():
    global memory,tts

    user_is_speaking_keys = [k for k in user_is_speaking.keys()]
    for user in user_is_speaking_keys:
        if user not in user_was_speaking.keys():
            user_was_speaking.update({user: False})
        
        if user_is_speaking[user] and not user_was_speaking[user]:
            # print('user',user,'started speaking at',datetime.datetime.now())
            user_was_speaking[user] = True
        elif not user_is_speaking[user] and user_was_speaking[user]:
            # check that user has been silent for 1 second
            if (datetime.datetime.now() - user_was_speaking_at[user]).total_seconds() < 0.4:
                return
            user_was_speaking[user] = False

            def proc():
                global memory,tts
                timer = datetime.datetime.now()
                # save audio data to wav
                if user not in audio_data.keys():
                    return
                
                # audio = audio_data[user].copy()
                audio = audio_data[user]
                del audio_data[user]
                
                audio.cleanup()
                data = audio.file

                with wave.open(data, 'wb') as f:
                    vc = channel_by_user[user]
                    f.setnchannels(vc.decoder.CHANNELS)
                    f.setsampwidth(vc.decoder.SAMPLE_SIZE // vc.decoder.CHANNELS)
                    f.setframerate(vc.decoder.SAMPLING_RATE)

                data.seek(0)
                audio.on_format('wav')
                data.seek(0)
                as_mp3 = io.BytesIO(wav_to_mp3(data.read()))

                if not may_contain_speech(as_mp3):
                    print('user',user,'did not speak')
                    return
                
                print('audio processing took',datetime.datetime.now() - timer,'seconds')
                timer = datetime.datetime.now()
                
                as_mp3.seek(0)
                as_mp3.name = 'in.mp3'
                transcription = openai.Audio.transcribe("whisper-1", as_mp3)
                text = transcription['text']
                print('user',user,'said',text)
                
                if len(text) < 20 or len(text) > 500:
                    print('user',user,'did wrong speak')
                    return
                
                print('transcription took',datetime.datetime.now() - timer,'seconds')
                timer = datetime.datetime.now()

                # get user by id
                # TODO: this does not work
                username = bot.get_user(user)
                print(username)
                if not username:
                    username = 'unknown'
                memory.append({'user': username, 'text': text, 'is_bot': False})
                if len(memory) > 10:
                    memory = memory[1:]

                if any([name.lower() in text.lower() for name in NAMES]):
                    completion = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo", 
                        messages=[
                            {"role": "system", "content": "you are addressed as " + ', '.join(NAMES) + ". only say yes or no wether the following message is addressed to you"},
                            {"role": "user", "content": text},
                        ]
                    )

                    print('intent took',datetime.datetime.now() - timer,'seconds')
                    timer = datetime.datetime.now()

                    response = completion.choices[0]['message']['content']
                    print('intent:',response)
                    if 'yes' not in response.lower():
                        return
                
                messages = [{"role": "system", "content": PERSONALITY_PROMPTS[0]}]
                for message in memory:
                    messages.append({"role": "user" if message['is_bot'] else "assistant", "content": message['user'] + ': ' + message['text']})
                messages.append({"role": "system", "content": PERSONALITY_PROMPTS[1]})

                completion = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo", 
                    messages=messages
                )

                print('response took',datetime.datetime.now() - timer,'seconds')
                timer = datetime.datetime.now()

                response = completion.choices[0]['message']['content']
                print(response)

                # probably do this in memory but whatever
                filename = f'{random.randint(0,999999999)}.mp3'
                tts.tts_to_file(text=response, speaker=tts.speakers[0], file_path=filename)

                print('audio generation took',datetime.datetime.now() - timer,'seconds')
                timer = datetime.datetime.now()

                channel_by_user[user].play(discord.FFmpegPCMAudio(filename))
                while channel_by_user[user].is_playing():
                    time.sleep(0.1)
                print('audio playback took',datetime.datetime.now() - timer,'seconds')
                os.remove(filename)

            threading.Thread(target=proc).start()

    for user in user_is_speaking.keys():
        user_is_speaking[user] = False

@bot.command()
async def join(ctx: discord.ApplicationContext):
    voice = ctx.author.voice

    if not voice:
        await ctx.respond("You aren't in a voice channel!")

    vc = await voice.channel.connect()
    connections.update({ctx.guild.id: vc})

    vc.start_recording(
        CustomSink(),
        once_done,
        ctx.channel
    )

    await ctx.reply("I have joined", ephemeral=True)

async def once_done(sink: discord.sinks, channel: discord.TextChannel, *args):
    recorded_users = [
        f"<@{user_id}>"
        for user_id, audio in sink.audio_data.items()
    ]
    await sink.vc.disconnect()

@bot.command()
async def leave(ctx):
    if ctx.guild.id in connections:
        vc = connections[ctx.guild.id]
        vc.stop_recording()
        del connections[ctx.guild.id]
        await ctx.delete()

bot.run(BOT_TOKEN)