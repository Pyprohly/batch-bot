
import os
import time
import re
from string import Template
import logging
from logging.handlers import RotatingFileHandler
import praw, prawcore
from submission_recorder import record_submission

logger = logging.getLogger(__name__)
log_file = './logs/' + os.path.basename(__file__) + '.log'
log_format = '%(asctime)s %(levelname)s %(funcName)s:%(lineno)d | %(message)s'
logging_rfh_config = {
    'filename': log_file,
    'encoding': 'utf-8',
    'maxBytes': 5*1024*1024, # 5 megabytes
    'backupCount': 8
}

os.chdir(os.path.dirname(os.path.abspath(__file__)))
logger.disabled = not os.path.isdir(os.path.dirname(log_file))
if not logger.disabled:
    rotation_handler = RotatingFileHandler(**logging_rfh_config)
    formatter = logging.Formatter(log_format)
    rotation_handler.setFormatter(formatter)

    logger.setLevel(logging.DEBUG)
    logger.addHandler(rotation_handler)

    logger.debug('Logging: ' + os.path.abspath(log_file))

register = {
    'author': 'Pyprohly',
    'bot_name': 'BatchBot',
    'description': 'Tells redditors in /r/Batch to wrap their code in a code block.',
    'target_subreddits': ['Pyprohly_test1', 'Batch']
}
praw_config = {
    'client_id': '[redacted]',
    'client_secret': '[redacted]',
    'username': 'BatchBot',
    'password': '[redacted]',
    'user_agent': 'BatchBot by /u/Pyprohly'
}

response = '''Hi ${redditor},

It looks like your ${coding_language} code isn’t wrapped in a code block. To format code correctly on **new.reddit.com**, highlight your code and select *Code Block* in the editing toolbar.

If you’re on **old.reddit.com**, separate the code from your text with a blank line and precede each line of code with **4 spaces** or a **tab**. E.g.,

${example}

---

^(*Beep-boop. I am a bot, and this action was performed automatically. If I have done something silly please contact*) [*^(the owner)*](https://www.reddit.com/message/compose?to=${owner}&subject=/u/${bot_name}%20feedback)^.
'''
response_subs = {
    'owner': '%s' % register['author'],
    'coding_language': 'Batch file',
    'example': '''    This is normal text.

        @echo off
        echo This is code!

> This is normal text.
>
>     @echo off
>     echo This is code!'''
}

pattern = (r'^('
           r'@echo off *'
           r'''|if (\/i )?(not )?((exist|defined|errorlevel) )?[\"\'\.\w%!-]+ ?(==|EQU|NEQ|LSS|LEQ|GTR|GEQ) ?[\"\'\.\w%!-]+ ?\('''
           r'|goto :?\w+'
           r'|set (\/a |\/p )?[\"\w]+=[\"\w ]{0,18}'
           r')$')

response = Template(response)
regex_pattern = re.compile(pattern, re.I | re.M)

reddit = praw.Reddit(**praw_config)
me = reddit.user.me()
subreddit = reddit.subreddit('+'.join(register['target_subreddits']))

def main():
    start_time = resume_time = time.time()

    # A fail-safe in case the bot goes rouge and produces comments too quickly.
    # Set `reply_shear` to `False` to disable.
    reply_shear = True
    reply_shear_value = 0
    reply_shear_threshold = 4
    reply_shear_distance = 60 * 60 # i.e., hourly
    reply_shear_focus = time.time()
    while 1:
        try:
            for submission in subreddit.stream.submissions(pause_after=0):
                if reply_shear:
                    if reply_shear_value > 0:
                        if time.time() - reply_shear_focus > reply_shear_distance:
                            reply_shear_value -= 1
                            reply_shear_focus += reply_shear_distance

                        if reply_shear_value > reply_shear_threshold:
                            logger.error('Quitting: made too many responses over time')
                            raise SystemExit
                    else:
                        reply_shear_focus = time.time()

                if submission is None:
                    continue

                # Make sure submission is not a link submission
                if not submission.is_self:
                    logger.info('Skip: link submission: {}'.format(submission.permalink))
                    continue

                matches = regex_pattern.search(submission.selftext)

                if submission.created_utc < resume_time:
                    msg = 'earlier item' + (' (with match)' if matches else '')
                    logger.info('Skip: ' + msg + ': {}'.format(submission.permalink))
                    continue

                if not matches:
                    logger.info('Skip: no match: {}'.format(submission.permalink))
                    continue

                # Quick check to see if it hasn't replied already
                submission.comments.replace_more(limit=0)
                if any(1 for comment in submission.comments.list() if comment.author == me):
                    logger.info('Skip: already replied to: {}'.format(submission.permalink))
                    continue

                logger.info('Match: {}'.format(submission.permalink))

                submission.reply(response.safe_substitute(redditor=submission.author.name,
                                                          bot_name=me.name,
                                                          **response_subs,
                                                          **register))

                logger.info('Respond: {}'.format(submission.permalink))

                record_submission(submission)
                reply_shear_value += 1

        except praw.exceptions.APIException as e:
            resume_time = time.time()

            if e.error_type == 'RATELIMIT':
                logger.error('Exception: ratelimit exceeded: {}'.format(e.message))

                for _ in range(12*60):
                    time.sleep(1)
            else:
                logger.warning('Exception: unhandled APIException:', exc_info=True)
                raise

        except prawcore.ResponseException as e:
            resume_time = time.time()

            logger.warning('Exception: ResponseException: {}'.format(e.response))

            for _ in range(5*60):
                time.sleep(1)

        except prawcore.RequestException as e:
            resume_time = time.time()

            logger.warning('Exception: RequestException: {}'.format(e.original_exception))

            for i in range(3):
                for _ in range(5*60):
                    time.sleep(1)

                try:
                    next(subreddit.new(limit=1))
                    break
                except prawcore.RequestException:
                    if i >= 2:
                        logger.warning('Quitting: failed to fetch: {}'.format(submission.id))
                        raise

                    logger.debug('Retrying: failed to fetch: {}'.format(submission.id))

        except Exception as e:
            logger.error('Exception: unhandled exception:', exc_info=True)
            raise

if __name__ == '__main__':
    main()

