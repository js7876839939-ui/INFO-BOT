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
    @commands.hybrid_command(name="testinfo")
    async def testinfo(self, ctx):
        await ctx.send("Test OK")
@commands.hybrid_command(name="info", description="Displays Free Fire player info")
@app_commands.describe(uid="FREE FIRE UID")
async def player_info(self, ctx, uid: str):
    guild_id = str(ctx.guild.id)

    if not uid.isdigit() or len(uid) < 6:
        return await ctx.reply(
            "❌ Invalid UID!\n- Only numbers allowed\n- Minimum 6 digits required",
            mention_author=False
        )

    if not await self.is_channel_allowed(ctx):
        return await ctx.send("❌ This command is not allowed in this channel.")

    cooldown = self.config_data["global_settings"]["default_cooldown"]

    if guild_id in self.config_data["servers"]:
        cooldown = self.config_data["servers"][guild_id]["config"].get(
            "cooldown", cooldown
        )

    if ctx.author.id in self.cooldowns:
        last_used = self.cooldowns[ctx.author.id]

        if (datetime.now() - last_used).seconds < cooldown:
            remaining = cooldown - (datetime.now() - last_used).seconds
            return await ctx.send(
                f"⏳ Please wait {remaining}s before using this command again"
            )

    self.cooldowns[ctx.author.id] = datetime.now()

    try:
     async with ctx.typing():
        async with self.session.get(
            f"{self.api_url}?uid={uid}&key={self.api_key}"
        ) as response:

            if response.status == 404:
                return await ctx.send(f"❌ Player not found: {uid}")

            if response.status != 200:
                return await ctx.send("❌ API Error. Try again later.")

            data = await response.json()

            basic_info = data.get("basicInfo", {})
            captain_info = data.get("captainBasicInfo", {})
            clan_info = data.get("clanBasicInfo", {})
            credit_score_info = data.get("creditScoreInfo", {})
            pet_info = data.get("petInfo", {})
            profile_info = data.get("profileInfo", {})
            social_info = data.get("socialInfo", {})

            region = basic_info.get("region", "Not Found")

            # Aage ka code...

            # =========================
            # 🔹 EMBED START
            # =========================
            embed = discord.Embed(
                title="🎮 Free Fire Player Info",
                color=discord.Color.blurple(),
                timestamp=datetime.now()
            )

            embed.set_thumbnail(url=ctx.author.display_avatar.url)

            # =========================
            # 🔹 BASIC INFO
            # =========================
            embed.add_field(name="📌 BASIC INFO", value="\n".join([
                f"**Name:** {basic_info.get('nickname', 'N/A')}",
                f"**UID:** {basic_info.get('accountId', 'N/A') or 'N/A'}",
                f"**Level:** {basic_info.get('level', 'N/A')}",
                f"**Region:** {region}",
                f"**Likes:** {basic_info.get('liked', 'N/A')}",
                f"**Honor Score:** {credit_score_info.get('creditScore', 'N/A')}",
                f"**Signature:** {social_info.get('signature', 'None') or 'None'}"
            ]), inline=False)

            # =========================
            # 🔹 ACTIVITY INFO
            # =========================
            embed.add_field(name="📊 ACTIVITY", value="\n".join([
                f"**OB Version:** {basic_info.get('releaseVersion', '?')}",
                f"**BP Badges:** {basic_info.get('badgeCnt', 'N/A')}",
                f"**BR Rank Points:** {basic_info.get('rankingPoints', '?')}",
                f"**CS Rank Points:** {basic_info.get('csRankingPoints', '?')}",
                f"**Created At:** {self.convert_unix_timestamp(int(basic_info.get('createAt', 0) or 0))}",
                f"**Last Login:** {self.convert_unix_timestamp(int(basic_info.get('lastLoginAt', 0) or 0))}"
            ]), inline=False)

            # =========================
            # 🔹 PROFILE INFO
            # =========================
            embed.add_field(name="👤 PROFILE", value="\n".join([
                f"**Avatar ID:** {profile_info.get('avatarId', 'N/A')}",
                f"**Banner ID:** {basic_info.get('bannerId', 'N/A')}",
                f"**Skills:** {profile_info.get('equipedSkills', 'N/A')}"
            ]), inline=False)

            # =========================
            # 🔹 PET INFO
            # =========================
            embed.add_field(name="🐾 PET INFO", value="\n".join([
                f"**Pet Name:** {pet_info.get('name', 'N/A')}",
                f"**Pet Level:** {pet_info.get('level', 'N/A')}",
                f"**Pet EXP:** {pet_info.get('exp', 'N/A')}",
                f"**Equipped:** {'Yes' if pet_info.get('isSelected') else 'No'}"
            ]), inline=False)

            # =========================
            # 🔹 SEND EMBED
            # =========================
            embed.set_footer(text="DEVELOPED BY JATIN")
            await ctx.send(embed=embed)
            # =========================
            # 🔹 CLAN / GUILD INFO (OPTIONAL SAFE)
            # =========================
            if clan_info:
                clan_text = [
                    f"**Clan Name:** {clan_info.get('clanName', 'N/A')}",
                    f"**Clan ID:** {clan_info.get('clanId', 'N/A')}",
                    f"**Clan Level:** {clan_info.get('clanLevel', 'N/A')}",
                    f"**Members:** {clan_info.get('memberNum', 'N/A')}/{clan_info.get('capacity', '?')}"
                ]

                if captain_info:
                    clan_text.extend([
                        "",
                        "**👑 Leader Info:**",
                        f"Leader Name: {captain_info.get('nickname', 'N/A')}",
                        f"Leader UID: {captain_info.get('accountId', 'N/A')}",
                        f"Leader Level: {captain_info.get('level', 'N/A')}"
                    ])

                embed.add_field(
                    name="🏆 CLAN INFO",
                    value="\n".join(clan_text),
                    inline=False
                )

                await ctx.send(embed=embed)

            # =========================
            # 🔹 OPTIONAL IMAGE (SAFE CHECK)
            # =========================
            try:
                image_url = f"{self.api_url}/image?uid={uid}"

                async with self.session.get(image_url) as img:
                    if img.status == 200:
                        data_bytes = await img.read()
                        file = discord.File(
                            io.BytesIO(data_bytes),
                            filename=f"ff_{uuid.uuid4().hex[:6]}.png"
                        )
                        await ctx.send(file=file)

            except Exception:
                pass

        # =========================
        # 🔹 FINAL ERROR HANDLER
        # =========================
            except Exception as e:
                await ctx.send(f"❌ Unexpected error: {e}")

            finally:
             gc.collect()
    except Exception as e:
        return await ctx.send(f"❌ Unexpected error: {e}")

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
