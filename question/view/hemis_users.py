import time
import logging
import requests
import datetime
import os
from django.http import StreamingHttpResponse
from django.views import View
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from question.models import SystemSetting

# Logging sozlamalari
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

User = get_user_model()

class ImportStudentsFromHemisStreamView(View):
    def get(self, request):
        def stream():
            logger.info("🔄 [START] Talabalarni HEMIS'dan import qilish boshlandi")

            # Sozlamalarni tekshirish
            setting = SystemSetting.objects.filter(is_active=True).first()
            if not setting or not setting.hemis_url or not setting.hemis_api_key:
                msg = "❌ HEMIS sozlamalari topilmadi."
                logger.error(msg)
                yield f'data: {{"status": "{msg}", "progress": 0}}\n\n'
                return

            base_url = setting.hemis_url.rstrip('/') + '/rest/v1/data/student-list'
            headers = {
                'accept': 'application/json',
                'Authorization': f'Bearer {setting.hemis_api_key}'
            }

            # Umumiy talaba sonini aniqlash
            try:
                logger.info("🔍 1-sahifani yuklab, umumiy sonni aniqlash...")
                r = requests.get(f'{base_url}?page=1&limit=1', headers=headers, timeout=10)
                if r.status_code != 200:
                    msg = f"❌ API xato (1-sahifa): {r.status_code}"
                    logger.error(msg)
                    yield f'data: {{"status": "{msg}", "progress": 0}}\n\n'
                    return

                total_count = r.json().get('data', {}).get('pagination', {}).get('totalCount', 0)
                logger.info(f"📊 Umumiy talaba soni: {total_count}")

                if total_count == 0:
                    yield 'data: {"status": "🚫 Talabalar topilmadi", "progress": 0}\n\n'
                    return
            except Exception as e:
                logger.error(f"❌ JSON parsing xatolik: {e}")
                yield f'data: {{"status": "❌ Parsing xatosi: {str(e)}", "progress": 0}}\n\n'
                return

            page = 1
            limit = 200
            total_processed = 0
            to_create = []
            to_update = []

            while True:
                try:
                    # Sahifani yuklash
                    url = f'{base_url}?page={page}&limit={limit}'
                    logger.info(f"📥 So‘rov: {url}")
                    response = requests.get(url, headers=headers, timeout=10)
                    if response.status_code != 200:
                        msg = f"❌ Sahifa {page} yuklab bo‘lmadi: {response.status_code}"
                        logger.error(msg)
                        yield f'data: {{"status": "{msg}", "progress": 0}}\n\n'
                        return

                    items = response.json().get('data', {}).get('items', [])
                    if not items:
                        logger.info(f"⛔ {page}-sahifada studentlar yo‘q.")
                        break

                    # Mavjud foydalanuvchilarni yuklash
                    sids = [s.get('student_id_number') for s in items if s.get('student_id_number')]
                    existing_users = {u.username: u for u in User.objects.filter(username__in=sids)}

                    for student in items:
                        sid = student.get('student_id_number')
                        if not sid:
                            continue

                        # Tug‘ilgan sana
                        birth_date_ts = student.get('birth_date')
                        birth_date = (
                            datetime.datetime.utcfromtimestamp(birth_date_ts).date()
                            if isinstance(birth_date_ts, int) and birth_date_ts > 0
                            else None
                        )

                        # Talaba ma'lumotlari
                        defaults = {
                            "full_name": student.get('full_name'),
                            "first_name": student.get('first_name'),
                            "second_name": student.get('second_name'),
                            "date_of_birth": birth_date,
                            "gender": student.get('gender', {}).get('code'),
                            "nationality": student.get('citizenship', {}).get('name'),
                            "is_student": True,
                            "student_id_number": sid,
                            "group_name": student.get('group', {}).get('name'),
                            "specialty": student.get('specialty', {}).get('name'),
                            "education_level": student.get('level', {}).get('name'),
                            "education_type": student.get('educationType', {}).get('name'),
                            "payment_form": student.get('paymentForm', {}).get('name'),
                            "education_year": student.get('educationYear', {}).get('name'),
                        }

                        # Yangi yoki yangilanishi kerak bo‘lgan talaba
                        if sid in existing_users:
                            user = existing_users[sid]
                            for key, value in defaults.items():
                                setattr(user, key, value)
                            to_update.append(user)
                        else:
                            user = User(username=sid, **defaults)
                            user.set_password('namdpi451')
                            to_create.append(user)

                        # Rasm yuklash (sinxron)
                        image_url = student.get('image')
                        if image_url and image_url.startswith('http'):
                            try:
                                img_response = requests.get(image_url, timeout=5)
                                if img_response.status_code == 200:
                                    file_name = os.path.basename(image_url.split('?')[0])
                                    user.profile_picture.save(file_name, ContentFile(img_response.content), save=False)
                                    user.save()  # Faqat rasm saqlanganda qo‘shimcha save
                                    logger.info(f"Rasm saqlandi: {sid}")
                                else:
                                    logger.warning(f"Rasm yuklashda xato (SID: {sid}): Status {img_response.status_code}")
                            except Exception as e:
                                logger.error(f"Rasm yuklashda xato (SID: {sid}): {str(e)}")

                        total_processed += 1
                        progress = round((total_processed / total_count) * 100)
                        yield f'data: {{"status": "{total_processed} ta talaba import qilindi", "progress": {progress}}}\n\n'

                    # Ommaviy saqlash
                    if to_create:
                        User.objects.bulk_create(to_create, batch_size=100)
                        logger.info(f"🆕 {len(to_create)} ta yangi talaba saqlandi")
                        to_create = []
                    if to_update:
                        User.objects.bulk_update(to_update, fields=defaults.keys(), batch_size=100)
                        logger.info(f"🔁 {len(to_update)} ta talaba yangilandi")
                        to_update = []

                    logger.info(f"✅ Sahifa {page} yakunlandi. Jami: {total_processed} ta")
                    page += 1
                    time.sleep(0.01)  # API cheklovlari uchun minimal pauza

                except Exception as e:
                    logger.error(f"❌ Sahifa {page} ishlovida xato: {e}")
                    yield f'data: {{"status": "❌ Sahifa {page} xatoligi: {str(e)}", "progress": 0}}\n\n'
                    break

            logger.info(f"🎉 Import tugadi. Jami: {total_processed} ta talaba saqlandi.")
            yield f'data: {{"status": "✅ Yakunlandi. Jami: {total_processed}", "progress": 100}}\n\n'

        return StreamingHttpResponse(stream(), content_type='text/event-stream')

class ImportStaffFromHemisStreamView(View):
    def get(self, request):
        def stream():
            logger.info("🔄 [START] Hodimlarni HEMIS'dan import qilish boshlandi")

            setting = SystemSetting.objects.filter(is_active=True).first()
            if not setting or not setting.hemis_url or not setting.hemis_api_key:
                msg = "❌ HEMIS sozlamalari topilmadi."
                logger.error(msg)
                yield f'data: {{"status": "{msg}", "progress": 0}}\n\n'
                return

            base_url = setting.hemis_url.rstrip('/') + '/rest/v1/data/employee-list?type=all'
            headers = {
                'accept': 'application/json',
                'Authorization': f'Bearer {setting.hemis_api_key}'
            }

            try:
                logger.info("🔍 1-sahifani yuklab, umumiy sonni aniqlash...")
                r = requests.get(f'{base_url}&page=1&limit=1', headers=headers, timeout=10)
                if r.status_code != 200:
                    msg = f"❌ API xato (1-sahifa): {r.status_code}"
                    logger.error(msg)
                    yield f'data: {{"status": "{msg}", "progress": 0}}\n\n'
                    return

                total_count = r.json().get('data', {}).get('pagination', {}).get('totalCount', 0)
                logger.info(f"📊 Umumiy hodim soni: {total_count}")
                if total_count == 0:
                    yield 'data: {"status": "🚫 Hodimlar topilmadi", "progress": 0}\n\n'
                    return
            except Exception as e:
                logger.error(f"❌ JSON parsing xatolik: {e}")
                yield f'data: {{"status": "❌ Parsing xatosi: {str(e)}", "progress": 0}}\n\n'
                return

            page = 1
            limit = 200
            total_processed = 0
            to_create, to_update = [], []

            while True:
                try:
                    url = f'{base_url}&page={page}&limit={limit}'
                    logger.info(f"📥 So‘rov: {url}")
                    response = requests.get(url, headers=headers, timeout=10)
                    if response.status_code != 200:
                        msg = f"❌ Sahifa {page} yuklab bo‘lmadi: {response.status_code}"
                        logger.error(msg)
                        yield f'data: {{"status": "{msg}", "progress": 0}}\n\n'
                        return

                    items = response.json().get('data', {}).get('items', [])
                    if not items:
                        logger.info(f"⛔ {page}-sahifada hodimlar yo‘q.")
                        break

                    eids = [s.get('employee_id_number') for s in items if s.get('employee_id_number')]
                    existing_users = {u.username: u for u in User.objects.filter(username__in=eids)}

                    for staff in items:
                        eid = staff.get('employee_id_number')
                        if not eid:
                            continue

                        birth_ts = staff.get('birth_date')
                        birth_date = datetime.datetime.utcfromtimestamp(birth_ts).date() if isinstance(birth_ts, int) and birth_ts > 0 else None

                        defaults = {
                            "full_name": staff.get('full_name'),
                            "first_name": staff.get('first_name'),
                            "second_name": staff.get('second_name'),
                            "date_of_birth": birth_date,
                            "gender": staff.get('gender', {}).get('code'),
                            "nationality": "O‘zbekiston",
                            "is_teacher": True,
                            "job_title": staff.get('staffPosition', {}).get('name'),
                            "company_name": staff.get('department', {}).get('name'),
                        }

                        if eid in existing_users:
                            user = existing_users[eid]
                            for k, v in defaults.items():
                                setattr(user, k, v)
                            to_update.append(user)
                        else:
                            user = User(username=eid, **defaults)
                            user.set_password('namdpi451')
                            to_create.append(user)

                        image_url = staff.get('image')
                        if image_url and image_url.startswith('http'):
                            try:
                                img_response = requests.get(image_url, timeout=5)
                                if img_response.status_code == 200:
                                    file_name = os.path.basename(image_url.split('?')[0])
                                    user.profile_picture.save(file_name, ContentFile(img_response.content), save=False)
                            except Exception as e:
                                logger.warning(f"⚠️ Rasm yuklashda xato (EID: {eid}): {e}")

                        total_processed += 1
                        progress = round((total_processed / total_count) * 100)
                        yield f'data: {{"status": "{total_processed} ta hodim import qilindi", "progress": {progress}}}\n\n'

                    if to_create:
                        User.objects.bulk_create(to_create, batch_size=100)
                        logger.info(f"🆕 {len(to_create)} ta yangi hodim saqlandi")
                        to_create.clear()

                    if to_update:
                        User.objects.bulk_update(to_update, fields=list(defaults.keys()), batch_size=100)
                        logger.info(f"🔁 {len(to_update)} ta hodim yangilandi")
                        to_update.clear()

                    logger.info(f"✅ Sahifa {page} yakunlandi. Jami: {total_processed} ta")
                    page += 1
                    time.sleep(0.01)

                except Exception as e:
                    logger.error(f"❌ Sahifa {page} ishlovida xato: {e}")
                    yield f'data: {{"status": "❌ Sahifa {page} xatosi: {str(e)}", "progress": 0}}\n\n'
                    break

            logger.info(f"🎉 Import tugadi. Jami: {total_processed} ta hodim saqlandi.")
            yield f'data: {{"status": "✅ Yakunlandi. Jami: {total_processed}", "progress": 100}}\n\n'

        return StreamingHttpResponse(stream(), content_type='text/event-stream')
