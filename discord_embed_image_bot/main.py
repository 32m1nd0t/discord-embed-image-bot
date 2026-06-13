import discord
from discord.ext import commands
from threading import Thread
from flask import Flask
import os
import logging

# 1. Render 호환을 위한 가짜 웹 서버(Flask) 설정
app = Flask('')

# 🔒 [Render 전용] UptimeRobot이 찌르는 무의미한 웹 접속 로그(Werkzeug) 숨기기
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()


# ------------------ [1. 데이터 저장 및 관리소] ------------------

# 유저가 버튼을 누른 상호작용(토큰)을 보관하여 나중에 원격으로 창을 수정할 때 씁니다.
user_interactions = {}

# 유저별로 관리자방에 생성된 '예비 알림(오렌지색)' 메시지 객체를 기억했다가 승인 시 지웁니다.
pending_admin_messages = {}


# ------------------ [2. 관리자 전용 승인 시스템] ------------------

class AdminApprovalView(discord.ui.View):
    def __init__(self, applicant_id: int):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id # 신청한 유저 ID 기억

    @discord.ui.button(label="승인", style=discord.ButtonStyle.success, custom_id="admin_approve_btn")
    async def approve_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 관리자 권한 확인
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 관리자만 이 버튼을 사용할 수 있습니다.", ephemeral=True)
            return

        guild = interaction.guild
        member = guild.get_member(self.applicant_id)
        guild_role = discord.utils.get(guild.roles, name="길드원")

        if not guild_role:
            await interaction.response.send_message("❌ '길드원' 역할을 찾을 수 없습니다.", ephemeral=True)
            return

        # 1. 역할 부여 및 시간 계산
        if member:
            await member.add_roles(guild_role)

        from zoneinfo import ZoneInfo
        from datetime import datetime
        kst_now = datetime.now(ZoneInfo("Asia/Seoul"))
        time_str = kst_now.strftime('%Y-%m-%d %H:%M:%S')

        # 2. 오렌지색 '신규 길드 인증 요청' 예비 알림 메시지 삭제
        if self.applicant_id in pending_admin_messages:
            try:
                old_msg = pending_admin_messages[self.applicant_id]
                await old_msg.delete()
            except:
                pass
            del pending_admin_messages[self.applicant_id]

        # 3. 🖼️ 사진 고정: 기존 보라색 임베드에 들어있던 사진 주소를 그대로 가져옵니다.
        existing_img_url = None
        if interaction.message.embeds and interaction.message.embeds[0].image:
            existing_img_url = interaction.message.embeds[0].image.url

        # 4. 🔒 관리자 로그 임베드 수정 (보라색 -> 초록색)
        approved_embed = discord.Embed(
            title="🔒 인증 완료",
            description=f"{member.mention if member else '퇴장한 유저'} 님의 인증이 성공적으로 완료되었습니다.\n\n"
                        f"⚙️ **처리 관리자:** {interaction.user.mention}\n"
                        f"⏰ **인증 일시:** {time_str}\n"
                        f"👑 **부여된 직책:** [길드원]",
            color=0x2ecc71
        )
        
        # 사진을 지우지 않고 그 자리에 그대로 다시 꽂아줍니다.
        if existing_img_url:
            approved_embed.set_image(url=existing_img_url)

        # 관리자방 메시지 수정 (버튼 제거)
        await interaction.response.edit_message(embed=approved_embed, view=None)

        # 5. ⭐️ 유저의 에페메럴 창을 '완료 안내'로 실시간 수정
        if self.applicant_id in user_interactions:
            saved_interaction = user_interactions[self.applicant_id]
            try:
                await saved_interaction.edit_original_response(
                    content=f"🎉 {member.mention if member else ''}님께 **[길드원]** 직책이 부여되었습니다.\n"
                            f"⏰ **인증 일시:** {time_str}\n\n"
                            f"📌 이제 서버의 모든 채널을 이용하실 수 있습니다. 공지사항을 확인해 주세요! 👉 [공지사항 확인하기](https://discord.com/channels/1497469875243847680/1501555795937202187/1511718041333927940)",
                    embed=None,
                    view=None
                )
            except:
                pass
            del user_interactions[self.applicant_id]


# ------------------ [3. 유저용 입장 및 인증 버튼 클래스] ------------------

class GuestFollowUpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="길드 인증 신청", style=discord.ButtonStyle.primary, custom_id="guild_auth_btn")
    async def guild_auth(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 중복 체크
        has_guild_role = discord.utils.get(interaction.user.roles, name="길드원")
        if has_guild_role:
            await interaction.response.send_message(content="이미 **[길드원]** 역할이 부여되었습니다!", ephemeral=True)
            return

        # 상호작용 객체 보관
        user_interactions[interaction.user.id] = interaction

        # 관리자 채널에 오렌지색 예비 알림 전송
        admin_channel = discord.utils.get(interaction.guild.text_channels, name="인증채널-관리자")
        if admin_channel:
            admin_embed = discord.Embed(
                title="🔔 신규 길드 인증 요청",
                description=f"{interaction.user.mention} 님이 길드 인증을 요청했습니다.\n현재 유저가 사진 업로드를 진행 중입니다.",
                color=0xe67e22
            )
            sent_msg = await admin_channel.send(embed=admin_embed)
            pending_admin_messages[interaction.user.id] = sent_msg
        
        user_embed = discord.Embed(
            title="📸 길드 인증사진 업로드 안내",
            description="왁타버스 관련 길드원이 맞는지 확인하기 위해 **인증사진**이 필요합니다.\n"
                        "**지금 현재 이 채널에 그대로 사진을 올려주세요!**\n",
            color=0x3498db
        )
        user_embed.add_field(
            name="📌 업로드 방법", 
            value="1. 길드창과 캐릭터창이 동시에 나온 사진을 캡쳐해서 올려주세요.\n"
                  "2. 사진이 올라가면 봇이 관리자에게 전달하며, 승인 시 이 안내 창이 완료 메시지로 자동 변경됩니다.\n\n"
                  "※ 원본 사진은 보안을 위해 즉시 삭제됩니다.", 
            inline=False
        )
        user_embed.set_image(url="https://message.style/cdn/images/797cb342c135ad2f3a755c479532c55a2f20db4211c751c8b0b6ccbd63d24e00.png")
        await interaction.response.send_message(embed=user_embed, ephemeral=True)


class MainWelcomeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="손님으로 입장", style=discord.ButtonStyle.secondary, custom_id="welcome_guest_btn")
    async def guest_entry(self, interaction: discord.Interaction, button: discord.ui.Button):
        guest_role = discord.utils.get(interaction.guild.roles, name="손님")
        if guest_role:
            await interaction.user.add_roles(guest_role)
        await interaction.response.send_message(
            content="임시 **[손님]** 역할이 부여되었습니다!\n길드원이시라면 아래 버튼을 통해 길드 인증을 이어서 진행해주세요.",
            view=GuestFollowUpView(),
            ephemeral=True
        )

    @discord.ui.button(label="버추얼로 입장", style=discord.ButtonStyle.success, custom_id="welcome_vip_btn")
    async def vip_entry(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 중복 체크
        has_vip_role = discord.utils.get(interaction.user.roles, name="버추얼")
        if has_vip_role:
            await interaction.response.send_message(content="이미 **[버추얼]** 역할이 부여되었습니다!", ephemeral=True)
            return

        vip_role = discord.utils.get(interaction.guild.roles, name="버추얼") 
        if vip_role:
            await interaction.user.add_roles(vip_role)
            admin_channel = discord.utils.get(interaction.guild.text_channels, name="인증채널-관리자")
            if admin_channel:
                from zoneinfo import ZoneInfo
                from datetime import datetime
                kst_now = datetime.now(ZoneInfo("Asia/Seoul"))
                admin_embed = discord.Embed(
                    title="👑 버추얼 역할 부여 알림",
                    description=f"{interaction.user.mention} 님이 **[버추얼로 입장]** 버튼을 눌러 **[버추얼]** 역할이 자동으로 부여되었습니다.",
                    color=0xe91e63 
                )
                admin_embed.set_footer(text=f"일시: {kst_now.strftime('%Y-%m-%d %H:%M:%S')}")
                await admin_channel.send(embed=admin_embed)
            await interaction.response.send_message(content="✨ 버추얼 인증이 완료되었습니다! 공지사항을 필독해주세요.", ephemeral=True)
        else:
            await interaction.response.send_message(content="❌ '버추얼' 역할을 찾을 수 없습니다.", ephemeral=True)


# ------------------ [4. 디스코드 봇 설정 및 이벤트] ------------------

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True 
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'봇 로그인 완료: {bot.user.name}')
    bot.add_view(MainWelcomeView())
    bot.add_view(GuestFollowUpView())

@bot.event
async def on_message(message):
    if message.author.bot: return

    if message.channel.name == "인증채널": 
        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith("image/"):
                    admin_channel = discord.utils.get(message.guild.text_channels, name="인증채널-관리자")
                    if admin_channel:
                        # 사진 데이터 백업
                        file = await attachment.to_file()
                        from zoneinfo import ZoneInfo
                        from datetime import datetime
                        kst_now = datetime.now(ZoneInfo("Asia/Seoul"))
                        
                        admin_embed = discord.Embed(
                            title="🖼️ 인증사진 로그 접수",
                            description=f"**신청자:** {message.author.mention}\n**일시:** {kst_now.strftime('%Y-%m-%d %H:%M:%S')}\n\n사진 확인 후 아래 **[승인]** 버튼을 눌러주세요.",
                            color=0x9b59b6
                        )
                        admin_embed.set_image(url=f"attachment://{attachment.filename}")
                        
                        # 유저 대기 상태 업데이트
                        if message.author.id in user_interactions:
                            saved_interaction = user_interactions[message.author.id]
                            try:
                                await saved_interaction.edit_original_response(
                                    content="✅ **인증사진 접수 완료!**\n현재 관리자가 확인 중입니다. 잠시만 기다려주세요... ⏰",
                                    embed=None, view=None
                                )
                            except: pass
                        
                        # 관리자방 전송
                        await admin_channel.send(embed=admin_embed, file=file, view=AdminApprovalView(message.author.id))
                        # 원본 삭제
                        await message.delete()
                        return
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(f"❌ {ctx.author.mention}님, 이 명령어는 관리자만 사용할 수 있습니다.", delete_after=3)
        await ctx.message.delete()

@bot.command()
@commands.has_permissions(administrator=True)
async def 입장패널생성(ctx):
    embed = discord.Embed(
        title="⚔️ 서버 입장 안내",
        description="방문 목적에 맞는 버튼을 눌러주세요.\n\n**• 버추얼로 입장:** [버추얼] 역할 부여\n**• 손님으로 입장:** 임시 [손님] 역할 부여",
        color=0x2ecc71
    )
    await ctx.send(embed=embed, view=MainWelcomeView())
    await ctx.message.delete()

# ------------------ [5. 봇 구동] ------------------
keep_alive()
token = os.environ.get("DISCORD_TOKEN")
bot.run(token)
