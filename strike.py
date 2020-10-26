import discord
from discord.ext import commands
import asyncio
import datetime
from math import floor
import redis

strikesdb = redis.StrictRedis(host = 'localhost', port = 6379, db = 0)
punishments = redis.StrictRedis(host = 'localhost', port = 6379, db = 1)

bot = commands.Bot(command_prefix='?', description = """Every time someone is jailed using strikesy, they gain a strike. At certain numbers of strikes, punishments automatically occur.
PLEASE send ALL complaints and suggestions to me, through DM.""")

####################################################
# #THIS CODE IS WHOLLY STOLEN FROM ROWBOAT. THANKS #
####################################################
UNITS = {
    's': lambda v: v,
    'm': lambda v: v * 60,
    'h': lambda v: v * 60 * 60,
    'd': lambda v: v * 60 * 60 * 24,
    'w': lambda v: v * 60 * 60 * 24 * 7,
}


def parse_duration(raw, source=None, negative=False):
    if raw == '-':
        return None

    value = 0
    digits = ''

    for char in raw:
        if char.isdigit():
            digits += char
            continue

        if char not in UNITS or not digits:
            if safe:
                return None
            raise CommandError('Invalid duration')

        value += UNITS[char](int(digits))
        digits = ''

    if negative:
        value = value * -1

    return datetime.timedelta(seconds=value + 1)

#########################################
# NO LONGER STOLEN FROM ROWBOAT. THANKS #
#########################################

async def check_punishments(member, mesg = ""):
    if   strikesdb.get(member.id) == b'3':
        await dayjail(member, 1, mesg)
    elif strikesdb.get(member.id) == b'4':
        await dayjail(member, 2, mesg)
    elif strikesdb.get(member.id) == b'5':
        await permjail(member, mesg)
    elif strikesdb.get(member.id) == b'6':
        await weekban(member, mesg)
    elif strikesdb.get(member.id) == b'7':
        await permban(member, mesg)
    else:
        await reports.send(mesg + ".")

def add_punishment(ptype, person, timedelta):
    punishments.zadd(ptype, floor((datetime.datetime.utcnow() +
timedelta).timestamp()), person.id)


async def get_member(person):
    try:
        return server.get_member(person)
    except:
        return discord.utils.get([i.user for i in server.bans()], id = person)

async def dayjail(person, days, mesg):
    await reports.send(mesg + " but gained too many strikes and is jailed for " + str(days) + " days.")
    try:
        await person.remove_roles(jail)
    except:
        pass
    await person.add_roles(jail)
    await person.remove_roles(memer)
    add_punishment("unjail", person, datetime.timedelta(days = 1))

async def permjail(person, mesg):
    await reports.send(mesg + " but gained too many strikes and is jailed until they write an essay to get out.")
    await person.add_roles(jail)
    await person.remove_roles(memer)
    await punishments.zrem("unjail", person.id)


async def unjail(person):
    await reports.send(f"{person.name}(`{person.id}`) is unjailed!")
    await person.remove_roles(jail)
    await person.add_roles(memer)

async def unsolitary(person):
    await reports.send(f"{person.name}(`{person.id}`) is released from solitary confinement!")
    await person.remove_roles(solitary)
    await person.add_roles(memer)

async def unban(person):
    await reports.send(f"{person.name}(`{person.id}`) is unbanned!")
    await server.unban(person)

async def weekban(person, mesg):
    await reports.send(mesg + " but gained too many strikes and is banned for a week.")
    await server.ban(person)
    add_punishment("unban", person, datetime.timedelta(weeks = 1))

async def permban(person, mesg):
    await reports.send(mesg + " but gained too many strikes and is permanently banned.")
    await server.ban(person)

async def strike_decay(person):
    await reports.send(f"{person.name}(`{person.id}`) has lost a strike due to strike decay!")
    if strikesdb.get(person.id) != b'0':
        strikesdb.decr(person.id)
        add_punishment("strike_decay", person, datetime.timedelta(weeks = 1))



def check_action(actionbytes):
    if actionbytes == b'unpunish':
        return unpunish
    elif actionbytes == b'unjail':
        return unjail
    elif actionbytes == b'unsolitary':
        return unsolitary
    elif actionbytes == b'strike_decay':
        return strike_decay
    elif actionbytes == b'unban':
        return unban

@bot.command(name = "strike")
@commands.has_role("Moderator")
async def command_strike(ctx, member: discord.Member, *, reason = ""):
    """Strikes a member."""
    if member.top_role >= ctx.author.top_role:
        return
    await ctx.send('striking...')
    await strike(member, f"{member.name}(`{member.id}`) was striked by {ctx.author.name}(`{ctx.author.id}`) for: {reason}")

async def strike(member, mesg = None):
    if member.id == bot.user.id:
        return
    if mesg == None:
        mesg = person.name + " did some bad thing and got striked"
    strikesdb.incr(member.id)
    add_punishment("strike_decay", member, datetime.timedelta(weeks = 1))
    await check_punishments(member, mesg)

@bot.command(name = "unstrike")
@commands.has_role("Moderator")
async def command_unstrike(ctx, member: discord.Member, *, reason = ""):
    """Unstrikes a member. You can't go beneath 0 strikes, so don't even try, OK?"""
    if member.top_role >= ctx.author.top_role:
        return
    await ctx.send('destriking...')
    await unstrike(member)
    await reports.send(f"{member.name}(`{member.id}`) has been unstriked by {ctx.author.name}(`{ctx.author.id}`) for: {reason}")

async def unstrike(member):
    current_strikes = strikesdb.get(member.id)
    if current_strikes != b'0' and current_strikes != None:
        strikesdb.decr(member.id)

@bot.command(name = "strikes")
async def strikes(ctx, member: discord.Member=None):
    """Tells you the strikes of a member, or of yourself if no member is supplied."""
    if member == None:
        member = ctx.author
    a = strikesdb.get(member.id)
    if a == None:
        await ctx.send("0")
    else:
        await ctx.send(a.decode("utf-8"))

@bot.command(name = "jail")
@commands.has_role("Moderator")
async def jail(ctx, member: discord.Member, duration: str, *, reason = ""):
    """Jails the member given for the duration given (in the familiar M0DBOT format). Optionally, add a reason which goes in #police_reports.
    One interesting thing is that consecutive jails override each other, allowing you to extend sentences."""
    if member.top_role >= ctx.author.top_role:
        return
    await member.add_roles(jail)
    await member.remove_roles(memer)
    durat = parse_duration(duration)
    if durat != None:
        add_punishment("unjail", member, parse_duration(duration))
    await ctx.send("this is being removed, as it was not posted in good faith")
    await strike(member, f"{member.name}(`{member.id}`) was jailed for {duration} by: {ctx.author.name}(`{ctx.author.id}`) because: {reason}")


@bot.command(name = "jale", aliases = ["softjail", "jaiI"])
@commands.has_role("Moderator")
async def jale(ctx, member: discord.Member, duration: str, *, reason = ""):
    """Jails the member given for the duration given without a strike. Optionally, add a reason which goes in #police_reports.
    One interesting thing is that consecutive jails override each other, allowing you to extend sentences."""
    if member.top_role >= ctx.author.top_role:
        return
    await member.add_roles(jail)
    await member.remove_roles(memer)
    durat = parse_duration(duration)
    if durat != None:
        add_punishment("unjail", member, parse_duration(duration))
    await ctx.send("this is being removed, as it was not posted in good faith")
    await reports.send(f"{member.name}(`{member.id}`) was jailed for {duration} by: {ctx.author.name}(`{ctx.author.id}`) because: {reason}")


@bot.command(name="pardon", aliases=["unjail"])
@commands.has_role("Moderator")
async def pardon(ctx, member: discord.Member):
    "Unjails no matter what."
    if member.top_role >= ctx.author.top_role:
        return
    await unjail(member)
    await ctx.send("Releasing the prisoner.")


@bot.command(name="murder", aliases=["ban"])
@commands.has_role("Moderator")
async def murder(ctx, member: discord.Member, *, reason="unspecified reasons"):
    "Bans no matter what, say `yes` to confirm the ban."
    
    def verify_user(message):
        if message.author == ctx.message.author and message.channel == ctx.message.channel:
            return True
        else:
            return False

    if member.top_role >= ctx.author.top_role:
        return
    try:
        await ctx.send(f"You are about to ban {member.name}(`{member.id}`) for {reason}, are you sure? Say `yes` to confirm.")
        choice = await bot.wait_for('message', check=verify_user, timeout=30)
    
    except asyncio.TimeoutError:
        await ctx.send(f"No input found, not banning.")
        return
    if choice.content == "yes":
        await ctx.send("Removing their privilege to life.")
        await reports.send(f"{member.name}(`{member.id}`) did an oopsie woopsie and has been banned for {reason}. Forever.")
        await server.ban(member,reason=reason,delete_message_days=0)
    else:
        await ctx.send(f"You did not say 'yes', you said '{choice.content}' - they live to see another day.")



@bot.command(name = "solitary")
@commands.has_role("Moderator")
async def solitary(ctx, member: discord.Member, duration: str, *, reason = ""):
    """Puts the member given in solitary for the duration given (in the familiar M0DBOT format). Optionally, add a reason which goes in #police_reports.
    One interesting thing is that consecutive solitaries override each other, allowing you to extend sentences."""
    if member.top_role >= ctx.author.top_role:
        return
    try:
        await member.remove_roles(jail)
    except:
        pass
    await member.add_roles(solitary)
    await member.remove_roles(memer)
    durat = parse_duration(duration)
    await ctx.send('confined inside a void from which no screams can escape. thanks')
    if durat != None:
        add_punishment("unsolitary", member, parse_duration(duration))
    await strike(member, f"{member.name}(`{member.id}`) was put in solitary confinement {duration} by: {ctx.author.name}(`{ctx.author.id}`) because: {reason}")
async def unpunish_loop():
    global reports
    global server
    global jail
    global solitary
    while 1:
        if reports is None:
            server = bot.get_guild(302953345105002496)
            #server = bot.get_guild(330518039961403393)
            reports = bot.get_channel(267150859605901314)
            #reports = bot.get_channel(450122812435202048)
            jail = discord.utils.get(server.roles, id=285615006442192896)
            #jail = discord.utils.get(server.roles, id =450377477949227018)
            solitary = discord.utils.get(server.roles, id=394608676276535296)
            authorised = discord.utils.get(server.roles, id=431368741197053953)
            #authorised = discord.utils.get(server.roles, id = 450384394667163650)
        for i in punishments.keys():
            action = check_action(i)
            timey = floor(datetime.datetime.utcnow().timestamp())
            unpunish_set = punishments.zrangebyscore(i, min = 0, max = timey)
            punishments.zremrangebyscore(i, min = 0, max = timey)
            for i in unpunish_set:
                member = await get_member(int(i))
                if member is not None:
                    await action(member)
        await asyncio.sleep(10)

@bot.event
async def on_ready():
    print('We have logged in as {0.user}'.format(bot))
    global server
    global reports
    global jail
    global memer
    global solitary
    global authorised
    global moderator
    server = bot.get_guild(231084230808043522)
    reports = bot.get_channel(267150859605901314)
    jail = discord.utils.get(server.roles, id=285615006442192896)
    memer = discord.utils.get(server.roles, id=590791241034366986)
    solitary = discord.utils.get(server.roles, id=394608676276535296)
    authorised = discord.utils.get(server.roles, id=431368741197053953)
    moderator = discord.utils.get(server.roles, id=431368741197053953)
    asyncio.ensure_future(unpunish_loop())

@bot.event
async def on_message(message):
    if message.content.startswith("!!tempmute"):
        await message.channel.send("Use me, not M0DBOT for jails!")
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.CommandNotFound):
        pass
    elif isinstance(error, commands.errors.CheckFailure):
        await ctx.send("Not authorised. thanks")
    else:
        await ctx.send("Something went wrong. Please try again, doing it a different way this time. The problem: " + str(error))


token = open("token.txt", 'r')
token = token.read()
token = token.strip()
bot.run(token, bot=True, reconnect=True)
