import os
import re
import tweepy
import asyncio
import logging
from web3 import Web3
from dotenv import load_dotenv
from database import create_pool, get_referral_code

load_dotenv()

X_BEARER_TOKEN = os.getenv('X_BEARER_TOKEN')
TARGET_X_ID = os.getenv('X_TWEET_ID')
X_USER_ID = os.getenv('X_USER_ID')

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
        if hasattr(status, 'in_reply_to_status_id_str') and status.in_reply_to_status_id_str == TARGET_X_ID:
            asyncio.run(self.process_reply(status))

    async def process_reply(self, status):
        try:
            reply_message = await handle_reply(status, self.pool)
            if reply_message != "":
                self.reply(status, reply_message)
                api.update_status(status=reply_message, in_reply_to_status_id=status.id)
        except Exception as e:
            print(f"Error on reply: {str(e)}")

    def on_error(self, status_code):
        if status_code == 420:
            return False

# 主函数
async def main():
    pool = await create_pool()
    myStreamListener = StreamListener(pool)
    myStream = tweepy.Stream(auth=api.auth, listener=myStreamListener)
    myStream.filter(follow=[X_USER_ID])

if __name__ == "__main__":
    asyncio.run(main())