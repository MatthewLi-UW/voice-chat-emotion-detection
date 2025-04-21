import logging
import os
from collections import defaultdict
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot configuration
BOT_PREFIX = '!'
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Whisper model configuration
WHISPER_MODEL_SIZE = "base"  # Options: "tiny", "base", "small", "medium", "large"

# LLM configuration
SENTIMENT_MODEL = "distilbert/distilbert-base-uncased-finetuned-sst-2-english"

# Tilt configuration
TILT_DECAY_RATE = 5  # Points per minute that tilt score decreases
MAX_SAMPLES = 10  # Maximum number of voice samples to store per user
DEFAULT_TILT_SCORE = 50  # Default starting tilt score

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('JustFF')

# Global state
user_tilt_scores = defaultdict(lambda: {"score": DEFAULT_TILT_SCORE, "last_updated": time.time(), "samples": [], "triggers": []})
voice_clients = {}  # Store voice clients for each guild
processing_queues = {}  # Audio processing queues

# Tilt keywords and their weights
TILT_KEYWORDS = {
    r'\bf+\s*(?:u+|you+)\b': 10,  # f u, f you
    r'\bwhat\s+(?:the\s+)?(?:f+|hell|heck)\b': 7,  # what the f, what the hell
    r'\bbs\b': 5,  # bs
    r'\b(?:this|that)\s+is\s+(?:bs|bullshit)\b': 8,  # this is bs
    r'\bgarbage\b': 6,  # garbage
    r'\btrash\b': 6,  # trash
    r'\bthrow(?:ing)?\b': 5,  # throw, throwing
    r'\bfeeding\b': 5,  # feeding
    r'\bint(?:ing)?\b': 5,  # int, inting
    r'\btoxic\b': 6,  # toxic
    r'\buninstall\b': 8,  # uninstall
    r'\bdumb\b': 5,  # dumb
    r'\bstupid\b': 5,  # stupid
    r'\breport\b': 4,  # report
    r'\brage\b': 7,  # rage
    r'\bquit(?:ting)?\b': 7,  # quit
    r'\bdc\b': 3,  # dc (disconnect)
    r'\bafk\b': 3,  # afk
    r'\btilt(?:ed)?\b': 5,  # tilt, tilted
    r'\bgg\s+(?:wp|ez)\b': 4,  # gg wp, gg ez
    r'\bomg\b': 3,  # omg
    r'\bomfg\b': 5,  # omfg
    r'\bunbelievable\b': 4,  # unbelievable
    r'\bunreal\b': 4,  # unreal
    r'\blagg?(?:ing)?\b': 3,  # lag, lagging
    r'\bwhy\b': 2,  # why (context dependent but often used in frustration)
    r'\bcan\'?t\s+believe\b': 4,  # can't believe
    r'\bseriously\b': 3,  # seriously
    r'\bwow\b': 2,  # wow (context dependent)
    r'\bunplayable\b': 6,  # unplayable
    r'\bbroken\b': 5,  # broken
    r'\bnerf\b': 3,  # nerf
    r'\bop\b': 2,  # op (overpowered)
    r'\bbad\b': 3,  # bad
    r'\bworst\b': 5,  # worst
    r'\bhate\b': 6,  # hate
    r'\bfeed(?:ing)?\b': 5,  # feed, feeding
    r'\bsmurf\b': 4,  # smurf
    r'\bhack(?:s|er|ing)?\b': 7,  # hack, hacker, hacking
    r'\bscript(?:er|ing)?\b': 7,  # script, scripter, scripting
    r'\bbot\b': 3,  # bot (as an insult)
    r'\bnoob\b': 4,  # noob
    r'\bretard(?:ed)?\b': 9,  # retard
    r'\bidiot\b': 7,  # idiot
    r'\bmoron\b': 7,  # moron
    r'!!+': 3,  # Multiple exclamation marks
    r'\bcmon\b': 3,  # cmon
    r'\bcome\s+on\b': 3,  # come on
    r'\bdude\b': 2,  # dude (context dependent)
    r'\bwtf\b': 6,  # wtf
    r'\bomg\b': 3,  # omg
    r'\bholy\s+(?:shit|crap)\b': 7,  # holy shit, holy crap
    r'\bare\s+you\s+(?:serious|kidding)\b': 5,  # are you serious, are you kidding
    r'\bwhat\s+are\s+you\s+doing\b': 4,  # what are you doing
    r'\bliterally\b': 3,  # literally (often used in frustration)
    r'\bno\s+way\b': 3,  # no way
    r'\bthrowing\b': 5,  # throwing
    r'\bno\s+(?:cs|farm)\b': 4,  # no cs, no farm
    r'\bgank\b': 3,  # gank (context dependent)
    r'\bjungle\s+(?:diff|gap)\b': 5,  # jungle diff/gap
    r'\b(?:mid|top|bot|adc|supp?)\s+(?:diff|gap)\b': 5,  # lane diff/gap
    r'\bjustff\b': 5, # just ff
}

# Add this after your TILT_KEYWORDS dictionary
POSITIVE_KEYWORDS = {
    r'\bgood\s+(?:job|play|kill|shot|ult|move|call)\b': 3,  # good job, good play, etc.
    r'\bnice\s+(?:job|play|kill|shot|ult|move|call)\b': 3,  # nice job, nice play, etc.
    r'\bgreat\s+(?:job|play|kill|shot|ult|move|call)\b': 4,  # great job, great play, etc.
    r'\bwell\s+played\b': 4,  # well played
    r'\bwell\s+done\b': 3,  # well done
    r'\bgood\s+try\b': 2,  # good try
    r'\bthank\s+(?:you|u)\b': 2,  # thank you
    r'\bthanks\b': 1,  # thanks
    r'\bwe\s+can\s+(?:win|do)\s+(?:this)\b': 4,  # we can win this, we can do this
    r'\bwe\s+got\s+this\b': 3,  # we got this
    r'\bno\s+(?:problem|worries)\b': 2,  # no problem, no worries
    r'\byou\'?re?\s+(?:good|great|amazing|awesome)\b': 3,  # you're good, you're great
    r'\bnp\b': 1,  # np (no problem)
    r'\bI\'?ll?\s+help\b': 3,  # I'll help
    r'\blet\'?s\s+group\b': 2,  # let's group
    r'\bstick\s+together\b': 2,  # stick together
    r'\bI\s+believe\b': 3,  # I believe
    r'\bcomeback\b': 2,  # comeback
    r'\bwinnable\b': 2,  # winnable
    r'\bthat\s+was\s+(?:awesome|amazing|sick|insane)\b': 4,  # that was awesome
    r'\bgood\s+game\b': 2,  # good game (not sarcastic)
    r'\bgg\b': 1,  # gg (not "gg ez")
    r'\bcarry\s+(?:on|us)\b': 3,  # carry on, carry us
    r'\bhave\s+fun\b': 2,  # have fun
}

# Voice indicators of tilt
VOICE_TILT_INDICATORS = {
    'amplitude': {'threshold': 0.7, 'score': 5},  # Loud volume
    'speaking_rate': {'threshold': 3.5, 'score': 3},  # Fast speaking
    'interruptions': {'threshold': 2, 'score': 4},  # Interrupting others
}