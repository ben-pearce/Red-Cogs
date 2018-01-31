# Developed by Ben for RED
# http://solero.me

import discord
from discord.ext import commands
from cogs.utils import checks
from .utils.dataIO import dataIO
from random import choice, shuffle, random
import functools
import asyncio
import os, sys, re 

try:
    import markovify
except:
    markovify = False

try:
    import feedparser
except:
    feedparser = False

DEFAULT_SETTINGS = {
    "max_corpus": 10000000
}

DEFAULT_SERVER_SETTINGS = {
    "toggle": True,
    "mention": False,
    "typing_delay": True,
    "solo": False,
    "learn_channels": [],
    "speak_channels": []
}

class MarkovError(Exception):
    pass

class CorpusOverflow(MarkovError):
    pass

class Markov:

    def __init__(self, bot):
        self.bot = bot

        self.chains = {}

    @commands.group(name="markov", invoke_without_command=True, no_pm=True, pass_context=True)
    async def _markov(self, ctx):
        """Displays help for markov cog"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @_markov.command(name="maxsize")
    @checks.is_owner()
    async def _markov_max_size(self, bites: int):
        """Sets max corpus size"""
        self.update_setting("max_corpus", bites)
        await self.bot.say("Max corpus size set to `{0}`".format(self.sizeof_fmt(bites)))

    @_markov.command(name="alearn", pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(administrator=True)
    async def _markov_add_ch(self, ctx, channel: discord.Channel = None):
        """Sets a new learning channel for markov chain"""
        if channel.server == ctx.message.server:
            channels = self.get_setting("learn_channels", channel.server)
            if channel.id in channels:
                await self.bot.say("<#{0}> is currently a learning channel".format(channel.id))
                return
            channels.append(channel.id)
            self.update_setting("learn_channels", channels, channel.server)
            await self.bot.say("Set <#{0}> as a learning channel for markov".format(channel.id))

    @_markov.command(name="rlearn", pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(administrator=True)
    async def _markov_remove_ch(self, ctx, channel: discord.Channel = None):
        """Removes a learning channel for markov chain"""
        if channel.server == ctx.message.server:
            channels = self.get_setting("learn_channels", channel.server)
            if channel.id not in channels:
                await self.bot.say("<#{0}> is not currently a learning channel".format(channel.id))
                return
            channels.remove(channel.id)
            self.update_setting("learn_channels", channels, channel.server)
            await self.bot.say("Removed <#{0}> as a learning channel for markov".format(channel.id))

    @_markov.command(name="aspeak", pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(administrator=True)
    async def _markov_add_sch(self, ctx, channel: discord.Channel = None):
        """Sets a new speaking channel for markov chain"""
        if channel.server == ctx.message.server:
            channels = self.get_setting("speak_channels", channel.server)
            if channel.id in channels:
                await self.bot.say("<#{0}> is currently a speak channel".format(channel.id))
                return
            channels.append(channel.id)
            self.update_setting("speak_channels", channels, channel.server)
            await self.bot.say("Set <#{0}> as a speak channel for markov".format(channel.id))

    @_markov.command(name="rspeak", pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(administrator=True)
    async def _markov_remove_sch(self, ctx, channel: discord.Channel = None):
        """Removes a speaking channel for markov chain"""
        if channel.server == ctx.message.server:
            channels = self.get_setting("speak_channels", channel.server)
            if channel.id not in channels:
                await self.bot.say("<#{0}> is not currently a speak channel".format(channel.id))
                return
            channels.remove(channel.id)
            self.update_setting("speak_channels", channels, channel.server)
            await self.bot.say("Removed <#{0}> as a speak channel for markov".format(channel.id))

    @_markov.command(name="mention", pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(administrator=True)
    async def _markov_mention(self, ctx):
        """Toggles mentioning of users"""
        mention = self.get_setting("mention", ctx.message.server)
        mention = False if mention else True
        self.update_setting("mention", mention, ctx.message.server)

        await self.bot.say("I will now mention users back" if mention else "I will no longer mention users back")

    @_markov.command(name="delay", pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(administrator=True)
    async def _markov_typing_delay(self, ctx):
        """Toggles realistic typing delay"""
        typing_delay = self.get_setting("typing_delay", ctx.message.server)
        typing_delay = False if typing_delay else True
        self.update_setting("typing_delay", typing_delay, ctx.message.server)

        await self.bot.say("I'll type realisticly" if typing_delay else "I will respond instantly")

    @_markov.command(name="solo", pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(administrator=True)
    async def _markov_solo(self, ctx):
        """Toggles solo speaking"""
        solo = self.get_setting("solo", ctx.message.server)
        solo = False if solo else True
        self.update_setting("solo", solo, ctx.message.server)

        await self.bot.say("I will speak on my own!" if solo else "I'll only respond to mentions")

    @_markov.command(name="channels", pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(administrator=True)
    async def _markov_list(self, ctx):
        """Lists learning & speak channels"""
        learn_channels = self.get_setting("learn_channels", ctx.message.server)
        speak_channels = self.get_setting("speak_channels", ctx.message.server)

        if len(learn_channels) == 0:
            await self.bot.say("There are currently no learning channels")
        else:
            learn_channels = ", ".join(["<#{0}>".format(x) for x in learn_channels])
            await self.bot.say("Learning channels: {0}".format(learn_channels))

        
        if len(speak_channels) == 0:
            await self.bot.say("There are currently no speak channels, I will speak in every channel")
        else:
            speak_channels = ", ".join(["<#{0}>".format(x) for x in speak_channels])
            await self.bot.say("Speak channels: {0}".format(speak_channels))

    @_markov.command(name="usage", pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(administrator=True)
    async def _markov_usage(self, ctx):
        """Get corpus usage"""
        corpus = self.get_corpus(ctx.message.server).to_json()
        max_corpus = self.get_setting("max_corpus")
        usage = self.sizeof_str(corpus)
        percentage = int(usage / max_corpus * 100)
        await self.bot.say("You have used `{0}` of your `{1}` allowance (`{2}%`)".format(self.sizeof_fmt(usage), 
            self.sizeof_fmt(max_corpus), percentage))

    @_markov.command(name="wipe", pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(administrator=True)
    async def _markov_wipe(self, ctx):
        """Clears corpus for your server"""
        file_name = "data/markov/corpus/{0}.json".format(ctx.message.server.id)
        os.remove(file_name)
        await self.bot.say("Corpus wiped.")

    @_markov.command(name="rss", pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(administrator=True)
    async def _markov_cpy_rss(self, ctx, url):
        """Copy an rss feed into server corpus"""
        await self.bot.say("Downloading & parsing feed!")
        feed = feedparser.parse(url)
        corpus = str()
        for item in feed["items"]:
            clean_content = re.sub(r'<[^<]+?>|&(#\d|\w)+;', '', item["content"][0]["value"]);
            clean_content = re.sub(r'\s{2}.+', '', clean_content)
            clean_content = self.clean_message(clean_content)
            corpus += clean_content + "\n"

        try:
            self.append_to_corpus(ctx.message.server, corpus)
        except CorpusOverflow:
            await self.bot.say("Corpus has reached max size (`{0}`) clear corpus or ask "
                "adminisrator to raise your allowance!".format(self.sizeof_fmt(self.get_setting("max_corpus"))))
            return

        corpus_size = self.sizeof_str(corpus)
        await self.bot.say("Loaded `{0}` of data into server corpus!".format(self.sizeof_fmt(corpus_size)))

    @_markov.command(name="messages", pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(administrator=True)
    async def _markov_cpy_msg(self, ctx, channel: discord.Channel, limit: int):
        """Copy channel messages into server corpus"""
        await self.bot.say("Copying messages...")
        counter = 0
        async for message in self.bot.logs_from(channel, limit = limit):
            if not self.is_valid_message(message):
                continue
            clean_content = self.clean_message(message.clean_content)
            self.append_to_corpus(ctx.message.server, clean_content + "\n")
            counter += 1
        await self.bot.say("Copied `{0}` messages to corpus.".format(counter))

    async def on_message(self, message):
        if message.server is None:
            return

        if not self.is_valid_message(message):
            return

        solo = True if random() < 0.1 and self.get_setting("solo", message.server) else False

        clean_content = message.clean_content
        author = message.author
        mention = "@" + author.server.me.display_name
        if mention in clean_content or solo:
            channels = self.get_setting("speak_channels", message.server)
            if message.channel.id not in channels and channels:
                return

            mention_back = self.get_setting("mention", message.server)
            typing_delay = self.get_setting("typing_delay", message.server)
            text_model = self.get_corpus(message.server)

            await self.bot.send_typing(message.channel)

            clean_content = clean_content.replace(mention, str())

            inspiration = message.author.display_name if not clean_content else choice(clean_content.split(" "))

            try:
                response = text_model.make_sentence_with_start(inspiration, strict=False)
            except KeyError:
                response = None

            if response is None:
                response = text_model.make_short_sentence(140)

            if response is not None:
                if mention_back:
                    response = "<@{0}> ".format(message.author.id) + response

                if typing_delay:
                    await asyncio.sleep(len(response) * 0.05)
                await self.bot.send_message(message.channel, response)
            else:
                await self.bot.send_message(message.channel, "Use `!markov messages` or `!markov rss` to build a "
                    "corpus, or add a learning channel")
        else:
            channels = self.get_setting("learn_channels", message.server)
            if message.channel.id not in channels:
                return

            clean_content = self.clean_message(clean_content)

            try:
                self.append_to_corpus(message.server, clean_content + "\n")
            except CorpusOverflow:
                return

    def is_valid_message(self, message):
        if message.author.id == self.bot.user.id:
            return False
        elif message.content == str():
            return False
        elif message.content[0] in self.bot.settings.prefixes:
            return False
        return True

    def get_corpus(self, server):
        if server.id in self.chains:
            return self.chains[server.id]

        try:
            with open("data/markov/corpus/{0}.json".format(server.id), "r", encoding='utf8') as file:
                raw_json_model = file.read()
                model = markovify.NewlineText.from_json(raw_json_model)
        except FileNotFoundError:
            model = markovify.NewlineText("empty\nchain")

        self.chains[server.id] = model
        return model

    def append_to_corpus(self, server, data):
        file_name = "data/markov/corpus/{0}.json".format(server.id)

        if server.id not in self.chains:
            self.get_corpus(server)

        try:
            model = markovify.NewlineText(data)
        except KeyError:
            return

        self.chains[server.id] = markovify.combine(models=[self.chains[server.id], model])

        data = self.chains[server.id].to_json()
        data_size = self.sizeof_str(data)
        max_corpus = self.get_setting("max_corpus")

        try:
            file_size = os.path.getsize(file_name)
            if file_size + data_size > max_corpus:
                raise CorpusOverflow()
            with open(file_name, "w", encoding='utf8') as file:
                file.write(data)
        except FileNotFoundError:
            if data_size > max_corpus:
                raise CorpusOverflow()
            with open(file_name, "w", encoding='utf8') as file:
                file.write(data)      


    def update_setting(self, key, value, server=None):
        if server is None:
            file_name = "data/markov/settings.json"
            default_settings = DEFAULT_SETTINGS
        else:
            file_name = "data/markov/{0}.json".format(server.id)
            default_settings = DEFAULT_SERVER_SETTINGS
        try:
            settings = dataIO.load_json(file_name)
            settings[key] = value
            dataIO.save_json(file_name, settings)
        except FileNotFoundError:
            default_settings[key] = value
            dataIO.save_json(file_name, default_settings)

    def get_setting(self, key, server=None):
        if server is None:
            file_name = "data/markov/settings.json"
            default_settings = DEFAULT_SETTINGS
        else:
            file_name = "data/markov/{0}.json".format(server.id)
            default_settings = DEFAULT_SERVER_SETTINGS
        try:
            settings = dataIO.load_json(file_name)
            return settings[key]
        except FileNotFoundError:
            return default_settings[key]

    @staticmethod
    def sizeof_str(string):
        return len(string.encode("utf-8"))

    @staticmethod
    def clean_message(message):
        message = re.sub(r'\n\s*\n', '\n', message)
        message = message.replace(". ", "\n")
        return message

    @staticmethod
    def sizeof_fmt(num, suffix='B'):
        for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
            if abs(num) < 1024.0:
                return "%3.1f%s%s" % (num, unit, suffix)
            num /= 1024.0
        return "%.1f%s%s" % (num, 'Yi', suffix)


def check_folders():
    if not os.path.exists("data/markov"):
        print("Creating data/markov folder...")
        os.makedirs("data/markov")
    if not os.path.exists("data/markov/corpus"):
        print("Creating data/markov folder...")
        os.makedirs("data/markov/corpus")

def setup(bot):
    if markovify is False:
        raise RuntimeError("You need the markovify module to use this.\n")
    elif feedparser is False:
        raise RuntimeError("You need the feedparser module to use this.\n")
    check_folders()
    bot.add_cog(Markov(bot))