import logging
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import threading
import time

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

class TelegramBot:
    def __init__(self, token, agent_callback):
        """
        Initialize the Telegram Bot.
        
        Args:
            token (str): The Telegram Bot API Token.
            agent_callback (function): A function to call when a message is received.
                                       Signature: async def callback(user_id, message, reply_func)
        """
        self.token = token
        self.agent_callback = agent_callback
        self.application = None
        self.running = False
        self.loop = None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="你好！我是 1052 AI。请直接发送消息与我对话。")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_chat.id)
        user_message = update.message.text
        
        if not user_message:
            return

        # Define a reply function that the agent can use to send messages back
        async def reply_func(text):
            # Telegram has a message length limit (4096 chars)
            # Simple chunking
            # IMPORTANT: We use None for parse_mode by default to avoid Markdown parsing errors
            # which are very common with LLM output (e.g. unclosed asterisks, underscores inside words)
            # Or we can try to escape it, but raw text is safer for stability.
            
            chunk_size = 4000
            if len(text) > chunk_size:
                for i in range(0, len(text), chunk_size):
                    try:
                        await context.bot.send_message(chat_id=update.effective_chat.id, text=text[i:i+chunk_size])
                    except Exception as e:
                        print(f"TG Send Error: {e}")
            else:
                try:
                    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
                except Exception as e:
                    print(f"TG Send Error: {e}")

        # Send "typing" action
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
        
        # Call the agent
        # Note: agent_callback might be long running, so we await it
        try:
            await self.agent_callback(user_id, user_message, reply_func)
        except Exception as e:
            await reply_func(f"Error processing message: {str(e)}")

    def run(self):
        """
        Run the bot in a separate thread/loop.
        """
        if not self.token:
            print("Telegram Token not provided. Bot not started.")
            return

        # Create a new event loop for this thread
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.application = ApplicationBuilder().token(self.token).build()
        
        start_handler = CommandHandler('start', self.start_command)
        message_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message)
        
        self.application.add_handler(start_handler)
        self.application.add_handler(message_handler)
        
        print("Starting Telegram Bot...")
        self.application.run_polling()

    def start_in_thread(self):
        self.running = True
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
