import asyncio
import os
from dotenv import load_dotenv
from telegram import Bot

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def get_chat_id():
    if not TOKEN:
        print("TELEGRAM_BOT_TOKEN is missing in .env")
        return

    bot = Bot(token=TOKEN)
    print(f"Checking updates for Bot: {TOKEN[:5]}...")
    
    try:
        # Get updates (long polling is not needed, just a fetch)
        updates = await bot.get_updates()
        
        if not updates:
            print("No updates found.")
            print("Please send a message (e.g., 'Hello') to your bot in Telegram app NOW, then run this script again.")
            return

        print("\nFound recent messages! Here are the Chat IDs:")
        print("-" * 40)
        found = False
        for update in updates:
            if update.message:
                chat = update.message.chat
                user = update.message.from_user
                print(f"From: {user.first_name} (@{user.username})")
                print(f"Chat ID: {chat.id}")
                print(f"Text: {update.message.text}")
                print("-" * 40)
                found = True
        
        if found:
            print("Copy the 'Chat ID' above and paste it into your .env file as TELEGRAM_CHAT_ID.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(get_chat_id())
