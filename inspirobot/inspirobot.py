# Developed by Ben for RED
# http://solero.me

import discord
from discord.ext import commands
import functools
import requests
import asyncio
import os, sys, re 

class Inspirobot:

	def __init__(self, bot):
		self.bot = bot;

	@commands.command(pass_context=True)
	async def inspire(self, ctx):
		loop = asyncio.get_event_loop()
		inspiro_future = loop.run_in_executor(None, requests.get, 'http://inspirobot.me/api?generate=true')
		response_uri = await inspiro_future
		
		embed = discord.Embed()
		embed.set_image(url=response_uri.text)

		await self.bot.send_message(ctx.message.channel, embed=embed)

	
def setup(bot):
	bot.add_cog(Inspirobot(bot))