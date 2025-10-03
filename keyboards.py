from pyrogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    ReplyKeyboardMarkup
)

def get_main_keyboard():
    """Main menu keyboard"""
    return ReplyKeyboardMarkup(
        [
            ["📤 Upload File", "📥 Download File"],
            ["📺 Stream", "📋 List Files"],
            ["🔄 Test Connection", "ℹ️ Help"]
        ],
        resize_keyboard=True
    )

def get_file_options_keyboard(file_id):
    """File options inline keyboard"""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📥 Download", callback_data=f"download_{file_id}"),
                InlineKeyboardButton("📺 Stream", callback_data=f"stream_{file_id}")
            ],
            [
                InlineKeyboardButton("🎬 MX Player", callback_data=f"mxplayer_{file_id}"),
                InlineKeyboardButton("🔵 VLC", callback_data=f"vlc_{file_id}")
            ],
            [
                InlineKeyboardButton("🌐 Web Player", callback_data=f"web_{file_id}"),
                InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_{file_id}")
            ]
        ]
    )

def get_streaming_keyboard(file_id, stream_url):
    """Streaming options keyboard"""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🎬 Open in MX Player", url=f"intent://{stream_url}#Intent;package=com.mxtech.videoplayer.ad;scheme=http;end"),
                InlineKeyboardButton("🔵 Open in VLC", url=f"vlc://{stream_url}")
            ],
            [
                InlineKeyboardButton("📥 Direct Download", url=stream_url),
                InlineKeyboardButton("🔙 Back", callback_data=f"back_{file_id}")
            ]
        ]
    )

def get_confirmation_keyboard(file_id):
    """Delete confirmation keyboard"""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Yes", callback_data=f"confirm_delete_{file_id}"),
                InlineKeyboardButton("❌ No", callback_data=f"cancel_delete_{file_id}")
            ]
        ]
  )
