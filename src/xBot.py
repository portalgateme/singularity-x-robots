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

client = tweepy.Client(bearer_token=X_BEARER_TOKEN)


def is_valid_evm_address(address):
    return Web3.isAddress(address) and Web3.isChecksumAddress(address)

def extract_address_from_text(text):
    match = re.search(r'0x[a-fA-F0-9]{40}', text)
    return match.group(0) if match else None

def is_follower(user_id, target_user_id):
    pagination_token = None
    while True:
        followers = client.get_users_followers(target_user_id, pagination_token=pagination_token)
        if followers.data:
            for follower in followers.data:
                if follower.id == user_id:
                    return True
        if 'next_token' in followers.meta:
            pagination_token = followers.meta['next_token']
        else:
            break
    return False

async def handle_reply(tweet, pool):
    reply_text = tweet.text
    address = extract_address_from_text(reply_text)
    if address and is_valid_evm_address(address) and is_follower(tweet.author_id, X_USER_ID):
        ref_code = await get_referral_code(tweet.author.username, pool)
        ref_link = f"https://app.thesingularity.network/referral/{ref_code}"
        reply_message = f"@{tweet.author.username} Thank you! Here is your referral link: {ref_link}"
    else:
        reply_message = ""
    return reply_message

class StreamListener(tweepy.StreamingClient):
    def __init__(self, bearer_token, pool):
        super().__init__(bearer_token)
        self.pool = pool
        self.retry_count = 0

    def on_tweet(self, tweet):
        if tweet.in_reply_to_user_id == TARGET_X_ID:
            asyncio.run(self.process_reply(tweet))

    async def process_reply(self, tweet):
        try:
            reply_message = await handle_reply(tweet, self.pool)
            if reply_message != "":
                client.create_tweet(text=reply_message, in_reply_to_tweet_id=tweet.id)
        except Exception as e:
            raise e

    def on_errors(self, status_code):
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

    refLinkListner = StreamListener(X_BEARER_TOKEN,pool)
    
    while True:
        try:
            refLinkListner.add_rules(tweepy.StreamRule(f"to:{X_USER_ID}"))
            refLinkListner.filter()
        except Exception as e:
            logging.error(f"Error: {e}")
            await asyncio.sleep(30)
    
if __name__ == "__main__":
    asyncio.run(main())