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

    async def handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        command = update.message.text.split()[0]
        
        if command == '/new':
            user_id = str(update.effective_chat.id)
            # We need to tell the agent to clear memory for this user/chat
            # Since we don't have direct access to the DB here easily, we can pass a special message to the agent_callback
            # Or we can handle it here if we import get_db_connection (but that creates circular import potentially if not careful)
            # Better: Send a special system instruction to the agent
            
            # Actually, the user wants to clear "Current Conversation Memory".
            # In our system, conversation is based on conversation_id.
            # For TG, we usually map user_id to a conversation_id.
            # If we want to "clear", we should just create a NEW conversation_id for this user.
            
            # Let's pass a special flag to agent_callback?
            # agent_callback signature: async def callback(user_id, message, reply_func)
            # We can send a message "/new" and let the agent handle it.
            
            await self.agent_callback(user_id, "/new", self.create_reply_func(update, context))
            return

    def create_reply_func(self, update, context):
        async def reply_func(text):
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
        return reply_func

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_chat.id)
        user_message = update.message.text
        
        if not user_message:
            return
            
        if user_message.startswith('/'):
            # It's a command we didn't catch with CommandHandler?
            # We should probably register /new as a command handler.
            pass

        # Send "typing" action
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
        
        # Call the agent
        try:
            await self.agent_callback(user_id, user_message, self.create_reply_func(update, context))
        except Exception as e:
            await self.create_reply_func(update, context)(f"Error processing message: {str(e)}")

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
        new_handler = CommandHandler('new', self.handle_command)
        message_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message)
        
        self.application.add_handler(start_handler)
        self.application.add_handler(new_handler)
        self.application.add_handler(message_handler)
        
        print("Starting Telegram Bot...")
        self.application.run_polling()

    def start_in_thread(self):
        self.running = True
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
