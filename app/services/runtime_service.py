import asyncio
import os
import time
import ctypes
import random
import logging
from datetime import datetime, timezone

logger = logging.getLogger('CryptoBot')

# --- SETTINGS ---
SEARCH_WINDOW_HOURS = 4
MAX_QUEUE_AGE_HOURS = 4
# ----------------

cycle_ready = asyncio.Event()


def disable_quickedit():
    if os.name != 'nt':
        return
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-10)
        mode = ctypes.c_uint32()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        mode.value &= ~0x0040
        kernel32.SetConsoleMode(handle, mode)
        logger.info("🛡 Windows QuickEdit Mode отключен.")
    except Exception as e:
        logger.warning(f"Не удалось отключить QuickEdit: {e}")


class CycleState:
    def __init__(self):
        self.published = 0
        self.attempts = 0
        self.start_time = datetime.now(timezone.utc)
        self.is_resumed = False
        self.active = False


STATE = CycleState()


def calculate_hype_score(post):
    try:
        views = post['views'] or 0
        comments = post['comments'] or 0
        subs = post['subscribers'] or 100000
        dt_val = post['date_posted']
        if isinstance(dt_val, str):
            dt = datetime.fromisoformat(str(dt_val))
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt_val

        age = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        if age < 0:
            age = 0
        score = ((views + comments * 10) / (subs if subs > 0 else 100000)) / (age + 2)
        return score * 10000
    except Exception:
        return 0


def cleanup_temp_files():
    try:
        now = time.time()
        deleted = 0
        folder = 'temp'
        if os.path.exists(folder):
            for f in os.listdir(folder):
                path = os.path.join(folder, f)
                if os.path.isfile(path):
                    if now - os.path.getmtime(path) > 86400:
                        try:
                            os.remove(path)
                            deleted += 1
                        except Exception:
                            pass
        if deleted > 0:
            logger.info(f"🧹 Уборщик: Удалено {deleted} старых файлов из temp.")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")


async def scheduler(spy, db, ai, channels):
    while True:
        await db.cleanup_old_records(days=3)
        cleanup_temp_files()
        await ai.pick_best_model()

        # --- ЖЕСТКИЙ СБРОС ЦИКЛА ---
        # Если мы не восстановились после сбоя, а начинаем новый круг - сбрасываем счетчики
        if not STATE.is_resumed:
            logger.info("🔄 НАЧАЛО НОВОГО ЦИКЛА. Сброс счетчиков.")
            STATE.published = 0
            STATE.attempts = 0
            STATE.start_time = datetime.now(timezone.utc)
            await db.save_state(STATE.start_time, 0, 0)
        else:
            STATE.is_resumed = False
            logger.info(f"♻️ Продолжение цикла. Опубликовано: {STATE.published}/3")

        STATE.active = True
        cycle_ready.clear()

        logger.info(f'🔄 СБОРЩИК: Ищу новости за {SEARCH_WINDOW_HOURS}ч...')

        for ch in channels:
            try:
                await spy.harvest_channel(ch, db, hours=SEARCH_WINDOW_HOURS)
            except Exception as e:
                if "Security error" in str(e) or "Connection" in str(e):
                    logger.error(f"🚨 КРИТИЧЕСКИЙ СБОЙ TELEGRAM: {e}. Перезапуск клиента...")
                    await spy.restart()
                    await asyncio.sleep(10)
                else:
                    logger.error(f"Ошибка сбора {ch}: {e}")

            await asyncio.sleep(random.randint(5, 12))

        candidates = await db.get_raw_candidates()
        fresh_candidates = []
        now = datetime.now(timezone.utc)

        for c in candidates:
            try:
                dt_val = c['date_posted']
                if isinstance(dt_val, str):
                    dt = datetime.fromisoformat(str(dt_val))
                    if not dt.tzinfo:
                        dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt_val

                age_hours = (now - dt).total_seconds() / 3600
                if age_hours > SEARCH_WINDOW_HOURS:
                    await db.set_status(c['id'], 'expired')
                    continue
                fresh_candidates.append(c)
            except Exception:
                pass

        if fresh_candidates:
            ranked = sorted(fresh_candidates, key=calculate_hype_score, reverse=True)
            logger.info(f'📊 Анализ {len(ranked)} свежих новостей...')
            history = await db.get_recent_history(days=3)

            for news in ranked:
                await asyncio.sleep(2)
                try:
                    is_dupe = await ai.check_duplicate(news['text_1'], history)
                except Exception:
                    is_dupe = False

                if is_dupe:
                    await db.set_status(news["id"], 'rejected')
                    logger.info(f'⛔ ID {news["id"]} - Дубликат.')
                else:
                    await db.set_status(news["id"], 'queued')
                    history.append(news['text_1'])
                    logger.info(f'✅ ID {news["id"]} прошел в очередь.')
        else:
            logger.info('💤 Свежих новостей нет.')

        logger.info('✅ Сбор завершен. Запускаю Цех.')
        cycle_ready.set()

        # Спим 4 часа перед следующим новым циклом
        await asyncio.sleep(4 * 3600)


async def production(db, ai, img, spy, bot_mgr, config):
    logger.info('🏭 Цех готов.')
    was_busy_log = False

    while True:
        await cycle_ready.wait()

        if STATE.published >= 3:
            if STATE.active:
                logger.info(f'🎉 ПЛАН ВЫПОЛНЕН ({STATE.published}/3). Жду следующий цикл.')
                STATE.active = False
            await asyncio.sleep(10)
            continue

        if STATE.attempts >= 5:
            if STATE.active:
                logger.info('🛑 ЛИМИТ ПОПЫТОК (5/5). Жду следующий цикл.')
                STATE.active = False
            await asyncio.sleep(10)
            continue

        if await db.is_busy():
            if not was_busy_log:
                logger.info("⏳ Цех: Жду решения модератора...")
                was_busy_log = True
            await asyncio.sleep(5)
            continue
        else:
            was_busy_log = False

        candidates = await db.get_queued_news()
        if not candidates:
            if STATE.active:
                logger.info("💤 Цех: Очередь пуста.")
                STATE.active = False
            await asyncio.sleep(10)
            continue

        target = candidates[0]

        # Проверка свежести
        try:
            dt_val = target['date_posted']
            if isinstance(dt_val, str):
                dt = datetime.fromisoformat(str(dt_val))
                if not dt.tzinfo:
                    dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt_val
            age = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
            if age > MAX_QUEUE_AGE_HOURS:
                logger.warning(f"🗑 ID {target['id']} устарел ({age:.1f}ч). Skip.")
                await db.set_status(target['id'], 'expired')
                continue
        except Exception:
            pass

        logger.info(f'⚙️ В РАБОТЕ ID {target["id"]} (Try {STATE.attempts+1}/5)')

        t1, t2 = await ai.generate_variants(target['text_1'])
        if not t1:
            await db.set_status(target['id'], 'rejected')
            continue

        logger.info('🎨 Рисуем...')
        prompt = await ai.generate_image_prompt(target['text_1'])
        i1_path = await img.get_image(prompt, style_type=config['style_1'])
        if not i1_path:
            logger.warning(f"🎨 Не удалось сгенерировать стиль 1 ({config['style_1']}).")
        await asyncio.sleep(20)
        i2_path = await img.get_image(prompt, style_type=config['style_2'])
        if not i2_path:
            logger.warning(f"🎨 Не удалось сгенерировать стиль 2 ({config['style_2']}).")

        i3 = None
        i4_path = None
        try:
            m = await spy.client.get_messages(target['channel'], ids=target['msg_id'])
            if m and m.media:
                i3 = await spy.client.download_media(m, file=bytes)
                logger.info('📥 Оригинал скачан.')
                desc = await ai.describe_image_for_remake(i3)
                if desc and desc != "crypto art":
                    i4_path = await img.get_image(desc, style_type=config['style_remake'])
                    if not i4_path:
                        logger.warning(f"🎨 Не удалось сгенерировать ремейк ({config['style_remake']}).")
        except Exception as e:
            logger.error(f"Media error: {e}")

        await db.update_assets(
            target['id'],
            t1,
            t2,
            None,
            None,
            i3,
            None,
            p1=i1_path,
            p2=i2_path,
            p3=None,
            p4=i4_path
        )
        await bot_mgr.send_studio(await db.get_post(target['id']))

        STATE.attempts += 1
        await db.save_state(STATE.start_time, STATE.published, STATE.attempts)
        logger.info(f'📨 Отправлено в студию...')

        while True:
            s = (await db.get_post(target['id']))['status']
            if s == 'published':
                STATE.published += 1
                await db.save_state(STATE.start_time, STATE.published, STATE.attempts)
                logger.info(f'✅ ОПУБЛИКОВАНО. ({STATE.published}/3)')
                break
            elif s == 'rejected':
                logger.info('❌ ОТКЛОНЕНО.')
                break
            await asyncio.sleep(2)
