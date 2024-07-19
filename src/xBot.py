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
X_API_KEY = os.getenv('X_API_KEY')
X_API_SECRET_KEY = os.getenv('X_API_SECRET_KEY')
X_ACCESS_TOKEN = os.getenv('X_ACCESS_TOKEN')
X_ACCESS_TOKEN_SECRET = os.getenv('X_ACCESS_TOKEN_SECRET')

TARGET_X_ID = os.getenv('TARGET_X_ID')
X_USER_ID = os.getenv('X_USER_ID')


logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    filename=log_filename,
                    filemode='a')

client = tweepy.Client(bearer_token=X_BEARER_TOKEN,
                       consumer_key=X_API_KEY,
                       consumer_secret=X_API_SECRET_KEY,
                       access_token=X_ACCESS_TOKEN,
                       access_token_secret=X_ACCESS_TOKEN_SECRET)

def is_valid_evm_address(address):
    return Web3.is_address(address) and Web3.is_checksum_address(address)

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
    try:
        reply_text = tweet.text
        address = extract_address_from_text(reply_text)
        if address and is_valid_evm_address(address):
            ref_code = await get_referral_code(address, pool)
            ref_link = f"https://app.thesingularity.network/referral/{ref_code}"
            reply_message = f"Thank you! Here is your referral link: {ref_link}"
            logging.info(f"Address: {address}, Reply: {reply_message}")
        else:
            reply_message = ""
    except Exception as e:
        raise e
    
    return reply_message


async def main():
    pool = await create_pool()
    last_reply_id = None

    while True:
        try:
            query = f"to:{X_USER_ID} conversation_id:{TARGET_X_ID}"
            if last_reply_id:
                mentions = client.search_recent_tweets(query=query, since_id=last_reply_id, max_results=100)
            else:
                mentions = client.search_recent_tweets(query=query, max_results=100)
            if mentions.data:
                for tweet in mentions.data:
                    reply_message = await handle_reply(tweet, pool)
                    if reply_message:
                        print(f"Replying to tweet: {tweet.id}")
                        client.create_tweet(text=reply_message, in_reply_to_tweet_id=tweet.id)
                        print(f"Replied to tweet: {tweet.id}")
                last_reply_id = mentions.data[0].id

        except Exception as e:
            logging.error(f"Error in main loop: {e}")

        await asyncio.sleep(60)  # 每分钟检查一次新的回复
    
if __name__ == "__main__":
    asyncio.run(main())