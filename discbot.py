import asyncio 
import discord 
from discord.ext import commands 
import yt_dlp as youtube_dl 
import os
import logging 
import atexit

logging.basicConfig(level=logging.INFO) 

intents = discord.Intents.default() 
intents.messages = True 
intents.guilds = True 
intents.voice_states = True 
intents.message_content = True  

bot = commands.Bot(command_prefix='/', intents=intents) 
tree = bot.tree 
last_song = None
 
youtube_dl.utils.bug_reports_message = lambda: '' 
ytdl_format_options = { 

    'format': 'bestaudio/best', 
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s', 
    'restrictfilenames': True, 
    'noplaylist': True, 
    'nocheckcertificate': True, 
    'ignoreerrors': False, 
    'logtostderr': False, 
    'quiet': True, 
    'no_warnings': True, 
    'default_search': 'auto', 
    'source_address': '0.0.0.0'
} 
ffmpeg_options = { 
    'options': '-vn' 
} 

ytdl = youtube_dl.YoutubeDL(ytdl_format_options) 
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, requester):
        super().__init__(source)
        self.data = data
        self.requester = requester

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False, requester=None):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            data = data['entries'][0]
        
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data, requester=requester)

# FUNKTIOT
queue = [] 
async def play_next_song(arg):
    global queue
    global last_song

    if len(queue) > 0:
        player = queue.pop(0)
        last_song = player.data
        if isinstance(arg, discord.Interaction):
            voice_client = arg.guild.voice_client
        else:
            voice_client = arg
        voice_client.play(player, after=lambda e: bot.loop.create_task(play_next_song(voice_client)))

async def get_voice_client(interaction: discord.Interaction): 
    if interaction.guild.voice_client is not None: 
        return interaction.guild.voice_client 
    elif interaction.user.voice: 
        channel = interaction.user.voice.channel 
        return await channel.connect() 

downloaded_files = []
def clear_downloaded_files():
    global downloaded_files
    for filename in downloaded_files:
        try:
            os.remove(filename)
        except OSError as e:
            print(f"Error deleting file {filename}: {e.strerror}")
    downloaded_files = []    

# KOMENNOT
@tree.command(name='play', description='Plays a song from YouTube')
async def play(interaction: discord.Interaction, search: str):
    global queue
    try:
        voice_client = await get_voice_client(interaction)
        if not voice_client:
            await interaction.response.send_message("You need to be in a voice channel to play music.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)  
        
        # Log the search term
        print(f'Play command received with search: {search}')
        
        if not search.startswith(('http://', 'https://')):
            search = f"ytsearch1:{search}"

        # Attempt to create a player using the YTDLSource class
        player = await YTDLSource.from_url(search, loop=bot.loop, stream=True, requester=interaction.user)
        
        # Log the player created
        print(f'Player created: {player}')
        
        queue.append(player)
        if not voice_client.is_playing():
            await play_next_song(interaction)

        embed = discord.Embed(title="Now playing", description=f"[{player.data['title']}]({player.data['webpage_url']})", color=discord.Color.blue())
        embed.set_thumbnail(url=player.data['thumbnail'])
        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

        await interaction.followup.send(embed=embed)
    except Exception as e:
        # Log any exception that occurs
        print(f'Error in play command: {e}')
        await interaction.followup.send(f'An error occurred: {e}')


@tree.command(name='replay', description='Replays the last song')
async def replay(interaction: discord.Interaction):
    global last_song
    if last_song is None:
        await interaction.response.send_message("There is no song to replay.", ephemeral=True)
        return
    voice_client = await get_voice_client(interaction)
    if not voice_client:
        await interaction.response.send_message("You need to be in a voice channel to replay music.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)  
    player = await YTDLSource.from_url(last_song['webpage_url'], loop=bot.loop, stream=True, requester=interaction.user)
    queue.insert(0, player)  
    if not voice_client.is_playing():
        await play_next_song(interaction)
    embed = discord.Embed(title="Replaying", description=f"[{last_song['title']}]({last_song['webpage_url']})", color=discord.Color.blue())
    embed.set_thumbnail(url=last_song['thumbnail'])
    embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
    await interaction.followup.send(embed=embed)

@tree.command(name='pause', description='Pauses the current song') 
async def pause(interaction: discord.Interaction): 
    voice_client = interaction.guild.voice_client 
    if voice_client and voice_client.is_playing(): 
        voice_client.pause() 
        await interaction.response.send_message("Paused the current song.")
    else: 
        await interaction.response.send_message("Nothing is currently playing.", ephemeral=True) 

@tree.command(name='resume', description='Resumes the current song') 
async def resume(interaction: discord.Interaction): 
    voice_client = interaction.guild.voice_client 
    if voice_client and voice_client.is_paused(): 
        voice_client.resume() 
        await interaction.response.send_message("Resumed the song.") 
    else: 
        await interaction.response.send_message("The song is not paused.", ephemeral=True) 

@tree.command(name='skip', description='Skips the current song') 
async def skip(interaction: discord.Interaction): 
    voice_client = interaction.guild.voice_client 
    if voice_client and voice_client.is_playing(): 
        voice_client.stop() 
        await interaction.followup.send("Skipped the current song.") 
        await play_next_song(interaction) 
    else: 
        await interaction.followup.send("Nothing is currently playing.", ephemeral=True) 

@tree.command(name='join', description='Bot joins the voice channel') 
async def join(interaction: discord.Interaction): 
    if interaction.user.voice: 
        channel = interaction.user.voice.channel 
        voice_client = interaction.guild.voice_client 
        if voice_client: 
            if voice_client.channel.id != channel.id: 
                await voice_client.move_to(channel) 
                await interaction.response.send_message(f"Moved to {channel.name}")
        else: 
            await channel.connect() 
            await interaction.response.send_message(f"Joined {channel.name}")
    else: 
        await interaction.response.send_message("You are not connected to a voice channel.", ephemeral=True) 

@tree.command(name='stop', description='Stops playing song and clears the queue')
async def stop(interaction: discord.Interaction):
    global queue
    voice_client = interaction.guild.voice_client
    queue.clear()
    clear_downloaded_files()

    if voice_client:
        voice_client.stop()
        await interaction.response.send_message("Stopped the song and cleared the queue.")
    else:
        await interaction.response.send_message("The bot is not connected to a voice channel.", ephemeral=True)

@tree.command(name='leave', description='Bot leaves the voice channel')
async def leave(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
        clear_downloaded_files()
        await interaction.response.send_message("Disconnected from the voice channel.")
    else:
        await interaction.response.send_message("The bot is not connected to a voice channel.", ephemeral=True)

@tree.command(name='info', description='Displays information about the bot')
async def info(interaction: discord.Interaction):
    embed = discord.Embed(title=f"{bot.user.name} Information", color=discord.Color.blue())
    embed.add_field(name="General", value="Botti rullaa ja rokkaa", inline=False)
    embed.add_field(name="/play", value="voi käyttää hakuja joko hakusanalla tai URL osoitteella", inline=False)
    embed.add_field(name="/stop", value="lopettaa toistamisen", inline=False)
    embed.add_field(name="/pause", value="pysäyttää kappaleen kyseiseen kohtaan", inline=False)
    embed.add_field(name="/resume", value="jatkaa pysäytettyä kappaletta", inline=False)
    embed.add_field(name="/skip", value="siirtyy seuraavaan kappaleeseen", inline=False)
    embed.add_field(name="/replay", value="toistaa edellisen kappaleen", inline=False)
    embed.add_field(name="/join & /leave", value="on kanava komentoja jotka suoritetaan /play ja /stop komennoissa", inline=False)
    
    await interaction.response.send_message(embed=embed)

@tree.error 
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError): 
    if isinstance(error, discord.app_commands.MissingPermissions): 
        await interaction.followup.send("You do not have the required permissions to use this command.") 
    elif isinstance(error, discord.app_commands.BotMissingPermissions): 
        await interaction.followup.send("I do not have the required permissions to execute this command.") 
    else: 
        await interaction.followup.send(f"An error occurred while executing the command: {error}") 

@bot.event 
async def on_ready(): 
    await bot.tree.sync()
    print(f'Logged in as {bot.user.name} (ID: {bot.user.id})') 
    print('------')

bot.run('MTE3MDMyNjM1OTc4MDg5Njc2OA.G2DAvT.9TTPLvZTLFDkznzpqhUyfJzkG3jPmMHuzEhFpI') 
atexit.register(clear_downloaded_files)
