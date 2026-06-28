import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from datetime import datetime
import json
import os
import asyncio
import io
import uuid
import gc
from datetime import datetime

CONFIG_FILE = "info_channels.json"


class InfoCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # ✅ NEW HL GAMING API (UPDATED)
        self.api_url = "https://proapis.hlgamingofficial.com/main/games/freefire/account/api"

        # ⚠️ BEST PRACTICE: use environment variables (Railway)
        self.dev_uid = os.getenv("HL_DEV_UID")
        self.api_key = os.getenv("HL_API_KEY")

        self.session = aiohttp.ClientSession()
        self.config_data = self.load_config()
        self.cooldowns = {}

   

    

    def convert_unix_timestamp(self ,timestamp: int) -> str:
        return datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')



    def check_request_limit(self, guild_id):
        try:
            return self.is_server_subscribed(guild_id) or not self.is_limit_reached(guild_id)
        except Exception as e:
            print(f"Error checking request limit: {e}")
            return False

    def load_config(self):
        default_config = {
            "servers": {},
            "global_settings": {
                "default_all_channels": False,
                "default_cooldown": 30,
                "default_daily_limit": 30
            }
        }

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    loaded_config = json.load(f)
                    loaded_config.setdefault("global_settings", {})
                    loaded_config["global_settings"].setdefault("default_all_channels", False)
                    loaded_config["global_settings"].setdefault("default_cooldown", 30)
                    loaded_config["global_settings"].setdefault("default_daily_limit", 30)
                    loaded_config.setdefault("servers", {})
                    return loaded_config
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading config: {e}")
                return default_config
        return default_config

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=4, ensure_ascii=False)
        except IOError as e:
            print(f"Error saving config: {e}")



    async def is_channel_allowed(self, ctx):
        try:
            guild_id = str(ctx.guild.id)
            allowed_channels = self.config_data["servers"].get(guild_id, {}).get("info_channels", [])

            # Autoriser tous les salons si aucun salon n'a été configuré pour ce serveur
            if not allowed_channels:
                return True

            # Sinon, vérifier si le salon actuel est dans la liste autorisée
            return str(ctx.channel.id) in allowed_channels
        except Exception as e:
            print(f"Error checking channel permission: {e}")
            return False

    @commands.hybrid_command(name="setinfochannel", description="Allow a channel for !info commands")
    @commands.has_permissions(administrator=True)
    async def set_info_channel(self, ctx, channel: discord.TextChannel):
        guild_id = str(ctx.guild.id)
        self.config_data["servers"].setdefault(guild_id, {"info_channels": [], "config": {}})
        if str(channel.id) not in self.config_data["servers"][guild_id]["info_channels"]:
            self.config_data["servers"][guild_id]["info_channels"].append(str(channel.id))
            self.save_config()
            await ctx.send(f"✅ {channel.mention} is now allowed for `!info` commands")
        else:
            await ctx.send(f"ℹ️ {channel.mention} is already allowed for `!info` commands")

    @commands.hybrid_command(name="removeinfochannel", description="Remove a channel from !info commands")
    @commands.has_permissions(administrator=True)
    async def remove_info_channel(self, ctx, channel: discord.TextChannel):
        guild_id = str(ctx.guild.id)
        if guild_id in self.config_data["servers"]:
            if str(channel.id) in self.config_data["servers"][guild_id]["info_channels"]:
                self.config_data["servers"][guild_id]["info_channels"].remove(str(channel.id))
                self.save_config()
                await ctx.send(f"✅ {channel.mention} has been removed from allowed channels")
            else:
                await ctx.send(f"❌ {channel.mention} is not in the list of allowed channels")
        else:
            await ctx.send("ℹ️ This server has no saved configuration")

    @commands.hybrid_command(name="infochannels", description="List allowed channels")
    async def list_info_channels(self, ctx):
        guild_id = str(ctx.guild.id)

        if guild_id in self.config_data["servers"] and self.config_data["servers"][guild_id]["info_channels"]:
            channels = []
            for channel_id in self.config_data["servers"][guild_id]["info_channels"]:
                channel = ctx.guild.get_channel(int(channel_id))
                channels.append(f"• {channel.mention if channel else f'ID: {channel_id}'}")

            embed = discord.Embed(
                title="Allowed channels for !info",
                description="\n".join(channels),
                color=discord.Color.blue()
            )
            cooldown = self.config_data["servers"][guild_id]["config"].get("cooldown", self.config_data["global_settings"]["default_cooldown"])
            embed.set_footer(text=f"Current cooldown: {cooldown} seconds")
        else:
            embed = discord.Embed(
                title="Allowed channels for !info",
                description="All channels are allowed (no restriction configured)",
                color=discord.Color.blue()
            )
    @commands.hybrid_command(
        name="info",
        description="Displays Free Fire player info"
    )
    @app_commands.describe(uid="FREE FIRE UID")
    async def player_info(self, ctx, uid: str):

    # UID Validation
        if not uid.isdigit():
            return await ctx.reply("❌ Invalid UID.")

        # Allowed Channel Check
        if not await self.is_channel_allowed(ctx):
            return await ctx.reply("❌ This command is not allowed in this channel.")

        await ctx.defer()

        params = {
            "uid": uid,
            "key": self.api_key,
            "dev": self.dev_uid
        }

        try:
            async with self.session.get(self.api_url, params=params, timeout=20) as resp:
                print("STATUS:", resp.status)
                print("URL:", resp.url)
                print(await resp.text())
                if resp.status != 200:
                    return await ctx.send("❌ API Error.")

                data = await resp.json()

        except Exception as e:
            return await ctx.send(f"❌ API Error:\n```{e}```")

        if "result" not in data:
            return await ctx.send("❌ Player not found.")

        result = data["result"]

        acc = result.get("AccountInfo", {})
        social = result.get("socialinfo", {})
        pet = result.get("petInfo", {})

        embed = discord.Embed(
            title=f"🎮 {acc.get('AccountName','Unknown')}",
            color=0x00ff99
        )

        embed.add_field(
            name="👤 Basic",
            value=(
                f"**UID:** {social.get('AccountID','N/A')}\n"
                f"**Level:** {acc.get('AccountLevel','N/A')}\n"
                f"**Region:** {acc.get('AccountRegion','N/A')}\n"
                f"**Likes:** {acc.get('AccountLikes','N/A')}"
            ),
            inline=False
        )

        embed.add_field(
            name="🏆 Rank",
            value=(
                f"BR Points: {acc.get('BrRankPoint','N/A')}\n"
                f"CS Points: {acc.get('CsRankPoint','N/A')}"
            ),
            inline=False
        )

        embed.add_field(
            name="🐶 Pet",
            value=(
                f"ID: {pet.get('id','N/A')}\n"
                f"Level: {pet.get('level','N/A')}"
            ),
            inline=False
        )

        embed.add_field(
            name="📝 Signature",
            value=social.get("AccountSignature", "No Signature"),
            inline=False
        )

        embed.set_footer(text="Powered by HL Gaming Official API")

        await ctx.send(embed=embed)

    async def cog_unload(self):
        await self.session.close()

    async def _send_player_not_found(self, ctx, uid):
        embed = discord.Embed(
            title="❌ Player Not Found",
            description=(
                f"UID `{uid}` not found or inaccessible.\n\n"
                "⚠️ **Note:** IND servers are currently not working."
            ),
            color=0xE74C3C
        )
        embed.add_field(
            name="Tip",
            value="- Make sure the UID is correct\n- Try a different UID",
            inline=False
        )
        await ctx.send(embed=embed, ephemeral=True)

    async def _send_api_error(self, ctx):
        await ctx.send(embed=discord.Embed(
            title="⚠️ API Error",
            description="The Free Fire API is not responding. Try again later.",
            color=0xF39C12
        ))



async def setup(bot):
    await bot.add_cog(InfoCommands(bot))
