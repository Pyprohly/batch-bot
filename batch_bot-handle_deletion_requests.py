
import os
import time
import re
import logging
from logging.handlers import RotatingFileHandler
import praw, prawcore

def main():
    start_time = resume_time = time.time()

    while 1:
        try:
            for item in reddit.inbox.stream(pause_after=0):
                if item is None:
                    continue

                if item.was_comment:
                    continue

                matches = regexp.match(item.subject)

                if item.created_utc < resume_time:
                    msg = 'earlier item' + (' (with match)' if matches else '')
                    logger.info('Skip: ' + msg + ': {}'.format(item.name))
                    continue

                if not matches:
                    logger.info('Skip: no match: {}'.format(item.name))
                    continue

                logger.info('Recieved (from /u/{}): subject: {}'.format(item.author.name, item.subject))

                comment_id = matches.group(1)
                comment = reddit.comment(comment_id)

                try:
                    comment._fetch()
                except praw.exceptions.PRAWException as e:
                    logger.info('Not found: comment id: {}'.format(comment_id))
                    continue
                else:
                    if comment.author == me:
                        comment.delete()
                        logger.info('Success: delete: {}'.format(comment.permalink))
                    else:
                        logger.info('Not owned: {}'.format(comment.permalink))

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

        except Exception:
            logger.error('Exception: unhandled exception:', exc_info=True)
            raise

os.chdir(os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger(__name__)
log_file = './logs/' + os.path.basename(__file__) + '.log'
log_format = '%(asctime)s %(levelname)s %(funcName)s:%(lineno)d | %(message)s'
logging_rfh_config = {
    'filename': log_file,
    'encoding': 'utf-8',
    'maxBytes': 5*1024*1024, # i.e., 5 megabytes
    'backupCount': 8
}

# Only enable logging if the log directory can be found
logger.disabled = not os.path.isdir(os.path.dirname(log_file))
if not logger.disabled:
    rotation_handler = RotatingFileHandler(**logging_rfh_config)
    formatter = logging.Formatter(log_format)
    rotation_handler.setFormatter(formatter)

    logger.setLevel(logging.DEBUG)
    logger.addHandler(rotation_handler)

    logger.debug('Logging ({}): {}'.format(__name__, os.path.abspath(log_file)))

register = {
    'author': 'Pyprohly',
    'bot_name': 'BatchBot',
    'description': 'Handles deletion requests on comments by /u/BatchBot.',
    'target_subreddits': ['Pyprohly_test1', 'Batch']
}
praw_config = {
    'site_name': 'BatchBot',
    'client_id': None,
    'client_secret': None,
    'username': 'BatchBot',
    'password': None,
    'user_agent': 'BatchBot by /u/Pyprohly'
}

msg_title_pattern = r'^ *! *delete *(\w+)'
regexp = re.compile(msg_title_pattern, re.I | re.M)

reddit = praw.Reddit(**{k: v for k, v in praw_config.items() if v is not None})
me = reddit.user.me()
subreddit = reddit.subreddit('+'.join(register['target_subreddits']))

if __name__ == '__main__':
    main()
