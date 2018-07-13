
import os
import time
import re
import logging
from logging.handlers import RotatingFileHandler
import praw, prawcore
from submission_recorder import record_submission

logger = logging.getLogger(__name__)
log_file = './logs/' + os.path.splitext(os.path.basename(__file__))[0] + '.log'
log_format = '%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s'
logging_config = {
    'filename': log_file,
    'encoding': 'utf-8',
    'maxBytes': 5*1024*1024, # 5 megabytes
    'backupCount': 8
}

os.chdir(os.path.dirname(os.path.abspath(__file__)))
logger.disabled = not os.path.isdir(os.path.dirname(logging_config['filename']))

if not logger.disabled:
    rotation_handler = RotatingFileHandler(**logging_config)
    formatter = logging.Formatter(log_format)
    rotation_handler.setFormatter(formatter)

    logger.setLevel(logging.DEBUG)
    logger.addHandler(rotation_handler)

    logger.debug('Logging enabled: ' + os.path.abspath(logging_config['filename']))


praw_config = {
    'client_id': '[redacted]',
    'client_secret': '[redacted]',
    'username': 'BatchBot',
    'password': '[redacted]',
    'user_agent': 'BatchBot by /u/Pyprohly'
}
reddit_permalink_qualifier = 'https://old.reddit.com'
subreddit_names = ['Pyprohly_test1', 'Batch']

pattern = (r'^('
           r'@echo off *'
           r'''|if (\/i )?(not )?((exist|defined|errorlevel) )?[\"\'\.\w%!-]+ ?(==|EQU|NEQ|LSS|LEQ|GTR|GEQ) ?[\"\'\.\w%!-]+ ?\('''
           r'|goto :?\w+'
           r'|set (\/a |\/p )?[\"\w]+=[\"\w ]{0,18}'
           r')$'
)
needle = re.compile(pattern, re.I | re.M)

response_subs = {
    'owner': 'Pyprohly',
    'coding_language': 'Batch file',
    'example': '''    This is normal text.

        @echo off
        echo This is code!

> This is normal text.
>
>     @echo off
>     echo This is code!'''
}
response = '''Hi {redditor},

It looks like your {coding_language} code isn’t wrapped in a code block. To format code correctly on **new.reddit.com**, highlight your code and select *Code Block* in the editing toolbar.

If you’re on **old.reddit.com**, separate the code from your text with a blank line then precede each line of code with **4 spaces** or a **tab**. E.g.,

{example}

***

^(*Beep-boop. I am a bot, and this action was performed automatically. If I have done something silly please contact*) [*^(the owner)*](https://www.reddit.com/message/compose?to={owner}&subject=/u/BatchBot%20feedback)^.
'''

reddit = praw.Reddit(**praw_config)
self_name = reddit.user.me().name
subreddit = reddit.subreddit('+'.join(subreddit_names))

resume_time = start_time = time.time()

reply_shear_value = 0
reply_shear_threshold = 4
reply_shear_distance = 60 * 60 # hourly
reply_shear_focus = time.time()
while 1:
    try:
        for submission in subreddit.stream.submissions(pause_after=0):
            if reply_shear_value > 0:
                if time.time() - reply_shear_focus > reply_shear_distance:
                    reply_shear_value -= 1
                    reply_shear_focus += reply_shear_distance

                if reply_shear_value > reply_shear_threshold:
                    logger.error('Made too many responses over time')
                    raise SystemExit
            else:
                reply_shear_focus = time.time()

            if submission is None:
                continue
            if not submission.is_self:
                logger.info('Skip (external link): {}'.format(reddit_permalink_qualifier + submission.permalink))
                continue

            has_needle = False
            if needle.search(submission.selftext):
                has_needle = True

            if submission.created_utc < resume_time:
                msg = 'earlier submission'
                if has_needle:
                    msg = 'earlier submission - with needle'
                logger.info(('Skip (' + msg + '): {}').format(reddit_permalink_qualifier + submission.permalink))
                continue
            if not needle.search(submission.selftext):
                logger.info('Skip (no needle): {}'.format(reddit_permalink_qualifier + submission.permalink))
                continue

            submission.comments.replace_more(limit=0)
            if any(comment for comment in submission.comments.list()
               if comment.author.name == self_name):
                continue

            submission.reply(response.format(redditor=submission.author.name, **response_subs))
            logger.info('Respond: {}'.format(reddit_permalink_qualifier + submission.permalink))
            record_submission(submission)
            reply_shear_value += 1

    except praw.exceptions.APIException as e:
        resume_time = time.time()

        if e.error_type == 'RATELIMIT':
            logger.error('Exception: Ratelimit exceeded: {}'.format(e.message))

            for _ in range(12*60):
                time.sleep(.5)
                time.sleep(.5)
        else:
            logger.warning('Exception: Unhandled APIException', exc_info=True)
            raise

    except prawcore.ResponseException as e:
        resume_time = time.time()

        logger.warning('Exception: ResponseException: {}'.format(e.response))

        for _ in range(5*60):
            time.sleep(.5)
            time.sleep(.5)

    except prawcore.RequestException as e:
        resume_time = time.time()

        logger.warning('Exception: RequestException: {}'.format(e.original_exception))

        for i in range(3):
            for _ in range(5*60):
                time.sleep(.5)
                time.sleep(.5)

            try:
                next(subreddit.new(limit=1))
                break
            except prawcore.RequestException:
                if i >= 2:
                    logger.warning('Failed to fetch submission {}.'.format(submission.id))
                    raise

                logger.debug('Failed to fetch submission {}, retrying.'.format(submission.id))

    except Exception as e:
        logger.error('Exception: Unhandled exception', exc_info=True)
        raise
