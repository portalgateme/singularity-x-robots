import os
import re
import tweepy
import asyncio
import logging
from web3 import Web3
from dotenv import load_dotenv
from database import create_pool, get_referral_code

load_dotenv()
log_filename = os.getenv('LOG_FILENAME', 'error.log')

X_BEARER_TOKEN = os.getenv('X_BEARER_TOKEN')
TARGET_X_ID = os.getenv('X_TWEET_ID')
X_USER_ID = os.getenv('X_USER_ID')


logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    filename=log_filename,
                    filemode='a')

auth = tweepy.OAuth2BearerHandler(X_BEARER_TOKEN)
api = tweepy.API(auth)

def is_valid_evm_address(address):
    return Web3.isAddress(address) and Web3.isChecksumAddress(address)

def extract_address_from_text(text):
    match = re.search(r'0x[a-fA-F0-9]{40}', text)
    return match.group(0) if match else None

async def handle_reply(status, pool):
    reply_text = status.text
    address = extract_address_from_text(reply_text)
    if address and is_valid_evm_address(address):
        ref_code = await get_referral_code(status.user.screen_name, pool)
        ref_link = f"https://app.thesingularity.network/referral/{ref_code}"
        reply_message = f"@{status.user.screen_name} Thank you! Here is your referral link: app.thesingularity.network{ref_link}"
    else:
        reply_message = ""
    return reply_message

class StreamListener(tweepy.StreamListener):
    def __init__(self, pool):
        super().__init__()
        self.pool = pool

    def on_status(self, status):
        if hasattr(status, 'in_reply_to_status_id_str') and status. in_reply_to_status_id_str == TARGET_X_ID:
            asyncio.run(self.process_reply(status))

    async def process_reply(self, status):
        try:
            reply_message = await handle_reply(status, self.pool)
            if reply_message != "":
                api.update_status(status=reply_message, in_reply_to_status_id=status.id)
        except Exception as e:
            raise e

    def on_error(self, status_code):
        logging.error(f"Stream encountered error: {status_code}")
        if status_code == 420 or status_code == 429:
            self.retry_count += 1
            wait_time = min(60 * 2 ** self.retry_count, 900)  # 最大 15 分钟
            logging.info(f"Rate limit exceeded, retrying in {wait_time} seconds")
            asyncio.sleep(wait_time)
            return True  # 返回 True 以重新连接流
        else:
            return False  # 断开连接

async def main():
    pool = await create_pool()
    refLinkListner = StreamListener(pool)
    stream = tweepy.Stream(auth=api.auth, listener=refLinkListner)
    while True:
        try:
            stream.filter(follow=[X_USER_ID])
        except Exception as e:
            logging.error(f"Stream encountered error: {e}")
            await asyncio.sleep(30)
    
if __name__ == "__main__":
    asyncio.run(main())