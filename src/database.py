import asyncpg
from nanoid import generate
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONNECTION_STRING = os.getenv('POSTGRES_URL')
MAX_REFERRAL_COUNT = int(os.getenv('MAX_REFERRAL_COUNT', 50))


async def create_pool():
    return await asyncpg.create_pool(DB_CONNECTION_STRING)

async def ref_code_exists(ref_code, connection):
    result = await connection.fetch('SELECT * FROM ref_code WHERE ref_code = $1', ref_code)
    return bool(result)

async def get_referral_code(wallet, pool):
    async with pool.acquire() as connection:
        result = await connection.fetchrow('SELECT ref_code FROM ref_code WHERE wallet = $1', wallet)
        if result:
            return result['ref_code']

        alphabet = '0123456789abcdefghijklmnopqrstuvwxyz'
        size = 16
        for _ in range(3):
            ref_code = generate(alphabet, size)
            if not await ref_code_exists(ref_code, connection):
                await connection.execute('INSERT INTO ref_code (wallet, ref_code) VALUES ($1, $2)', wallet, ref_code)
                return ref_code

        raise Exception('Failed to create referral code, please retry')

def is_address_equals(address1, address2):
    return address1.lower() == address2.lower()