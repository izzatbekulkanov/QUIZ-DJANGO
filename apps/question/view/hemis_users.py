import time
import logging
import requests
import datetime
import os
import traceback
from django.http import StreamingHttpResponse, JsonResponse
from django.views import View
from django.core.files.base import ContentFile
from django.contrib.auth import get_user_model
from django.db import transaction
from apps.question.models import SystemSetting

logger = logging.getLogger(__name__)
User = get_user_model()


class BaseHemisImportView(View):
    endpoint = None          # masalan: 'student-list'
    id_field = None          # masalan: 'student_id_number' yoki 'employee_id_number'
    role_field = None        # 'is_student' yoki 'is_teacher'
    model_fields = {}        # CustomUser field -> HEMIS field map
    group_filter = None      # faqat guruh bo‘yicha filterda ishlatiladi (students by group)

    # Necha kishidan keyin progress yuborish (SSE)
    PROGRESS_EVERY = 10

    # Rasmlarni mavjud userlar uchun ham yuklash-yo‘qligi
    DOWNLOAD_IMAGE_FOR_EXISTING = False

    def get(self, request):

        def stream():
            print("=== [START] HEMIS import boshlandi ===")

            # Sozlamalar
            setting = SystemSetting.objects.filter(is_active=True).first()
            if not setting or not setting.hemis_url or not setting.hemis_api_key:
                print("[XATO] HEMIS sozlamalari topilmadi!")
                yield 'data: {"status": "HEMIS sozlamalari topilmadi", "progress": 0}\n\n'
                return

            print(f"[INFO] HEMIS URL: {setting.hemis_url}")
            print(f"[INFO] Import turi: {self.role_field}")

            base_url = setting.hemis_url.rstrip('/') + f'/rest/v1/data/{self.endpoint}'

            # 1️⃣ Bitta Session ishlatamiz — TCP connection qayta-qayta ochilmaydi
            session = requests.Session()
            session.headers.update({
                'accept': 'application/json',
                'Authorization': f'Bearer {setting.hemis_api_key}',
            })

            # Jami sonni olish
            params = {'page': 1, 'limit': 1}
            if self.group_filter:
                params['_group'] = self.group_filter

            try:
                print("[INFO] Jami elementlar soni olinmoqda...")
                r = session.get(base_url, params=params, timeout=10)
                print(f"[DEBUG] API status: {r.status_code}")

                if r.status_code != 200:
                    print(f"[XATO] API xato status: {r.status_code}")
                    yield f'data: {{"status": "API xato: {r.status_code}", "progress": 0}}\n\n'
                    return

                total_count = r.json().get('data', {}).get('pagination', {}).get('totalCount', 0)
                print(f"[INFO] Jami topildi: {total_count} ta")

                if total_count == 0:
                    print("[INFO] Ma’lumot topilmadi")
                    yield 'data: {"status": "Ma\'lumot topilmadi", "progress": 0}\n\n'
                    return
            except Exception as e:
                print(f"[XATO] Pagination olishda xato: {e}")
                yield f'data: {{"status": "Parsing xatosi: {str(e)}", "progress": 0}}\n\n'
                return

            # -------- ASOSIY PAGINATION LOOP --------
            page = 1
            limit = 500
            total_processed = 0
            to_create = []
            to_update = []

            # bulk_update uchun maydonlar ro‘yxatini oldindan tayyorlab qo‘yamiz
            base_update_fields = list(self.model_fields.keys()) + [
                'date_of_birth',
                'gender',
                'nationality',
                self.role_field,
                'profile_picture',
            ]

            while True:
                try:
                    print(f"\n=== [PAGE] {page} yuklanmoqda... ===")

                    params = {'page': page, 'limit': limit}
                    if self.group_filter:
                        params['_group'] = self.group_filter

                    response = session.get(base_url, params=params, timeout=10)
                    print(f"[DEBUG] Sahifa {page} status: {response.status_code}")

                    if response.status_code != 200:
                        print(f"[XATO] Sahifa {page} xatosi: {response.status_code}")
                        yield (
                            f'data: {{"status": "Sahifa {page} xatosi", '
                            f'"progress": {round(total_processed / total_count * 100)}}}\n\n'
                        )
                        return

                    data = response.json().get('data', {})
                    items = data.get('items', [])
                    print(f"[INFO] {len(items)} ta obyekt olindi")

                    if not items:
                        print("[INFO] Boshqa sahifa yo'q. Import tugadi.")
                        break

                    # -------- HODIMLAR UCHUN DEBUG --------
                    if self.role_field == "is_teacher":
                        print(f"--- [STAFF DEBUG] {len(items)} ta xodim yuklandi ---")
                        for item in items[:3]:
                            print(f"   Xodim ID: {item.get('employee_id_number')}, FIO: {item.get('full_name')}")

                    # 🚨 HEMIS xodimni bir nechta bo‘limda yuborishi mumkin
                    # shu sababli sahifa ichida username (ID) bo‘yicha birlashtiramiz
                    merged_by_username = {}

                    for item in items:
                        raw_id = (
                            item.get('student_id_number')
                            if self.role_field == 'is_student'
                            else item.get('employee_id_number')
                        )
                        if raw_id is None:
                            continue

                        username = str(raw_id).strip()
                        if not username:
                            continue

                        # Agar bu username birinchi marta kelsa — to‘liq itemni saqlaymiz
                        if username not in merged_by_username:
                            merged_by_username[username] = item
                        else:
                            # Agar xodim bo'lsa, masalan bo‘lim nomlarini birlashtirish mumkin
                            # Hozircha oddiy: avvalgi va yangi itemlarni ustunlar bo‘yicha merge qilish.
                            existing = merged_by_username[username]

                            # Agar model_fields ichida department / company_name bo‘lsa,
                            # bo‘lim nomlarini birlashtirishni xohlasang shu yerga yozishing mumkin.
                            # Hozir oddiy qilib: agar oldingi bo‘sh bo‘lsa, yangisini qo‘yib ketamiz.
                            for k in self.model_fields.values():
                                old_val = existing.get(k)
                                new_val = item.get(k)
                                if not old_val and new_val:
                                    existing[k] = new_val

                    # Endi faqat noyob username'lar bo‘yicha ishlaymiz
                    unique_items = list(merged_by_username.items())  # [(username, item), ...]

                    print(f"[DEBUG] Sahifa ichida {len(unique_items)} ta noyob username aniqlandi")

                    # DBdan mavjud userlarni olish (username bo‘yicha)
                    usernames = [u for u, _ in unique_items]
                    existing_users = User.objects.in_bulk(usernames, field_name='username')
                    print(f"[DEBUG] DB'dan {len(existing_users)} ta mavjud user topildi")

                    # -------- ITEMLARNI QAYTA ISHLASH --------
                    for username, item in unique_items:
                        # Tug‘ilgan sana
                        raw_birth = item.get('birth_date')
                        birth_date = (
                            datetime.datetime.utcfromtimestamp(raw_birth).date()
                            if isinstance(raw_birth, int) and raw_birth > 0
                            else None
                        )

                        # Foydalanuvchi uchun default ma'lumotlar
                        defaults = {}
                        for field_name, hemis_key in self.model_fields.items():
                            val = item.get(hemis_key)
                            defaults[field_name] = (
                                val.get('name', '') if isinstance(val, dict) else (val or '')
                            )

                        defaults.update({
                            'date_of_birth': birth_date,
                            'gender': item.get('gender', {}).get('code', ''),
                            'nationality': item.get('citizenship', {}).get('name', 'O‘zbekiston'),
                            self.role_field: True,
                        })

                        if self.role_field == "is_teacher":
                            print(f"[STAFF] ID: {username} → {defaults.get('full_name')}")

                        is_new = username not in existing_users

                        # Mavjud user bo'lsa — update
                        if not is_new:
                            user = existing_users[username]
                            for k, v in defaults.items():
                                setattr(user, k, v)
                            to_update.append(user)
                        else:
                            user = User(username=username, **defaults)
                            user.set_password('namdpi451')
                            to_create.append(user)

                        # RASM yuklash
                        image_url = item.get('image')
                        if image_url and image_url.startswith('http'):
                            if is_new or self.DOWNLOAD_IMAGE_FOR_EXISTING:
                                try:
                                    img_response = session.get(image_url, timeout=3)
                                    if img_response.status_code == 200:
                                        file_name = os.path.basename(image_url.split('?')[0]) or f"{username}.jpg"
                                        user.profile_picture.save(
                                            file_name,
                                            ContentFile(img_response.content),
                                            save=False,
                                        )
                                except Exception as e:
                                    print(f"[RASM XATO] {e}")

                        total_processed += 1

                        # Har foydalanuvchida emas, N-chi foydalanuvchida progress yuboramiz
                        if total_processed % self.PROGRESS_EVERY == 0:
                            yield (
                                f'data: {{"status": "{total_processed} ta import qilindi", '
                                f'"progress": {round(total_processed / total_count * 100)}}}\n\n'
                            )

                    # -------- BULK OPERATION --------
                    with transaction.atomic():
                        if to_create:
                            print(f"[DB] {len(to_create)} ta yangi user yaratish uchun tayyor")
                            User.objects.bulk_create(to_create, batch_size=500)
                            print(f"[DB] {len(to_create)} ta yangi user yaratildi")
                            to_create = []

                        if to_update:
                            print(f"[DB] {len(to_update)} ta user yangilash uchun tayyor")
                            User.objects.bulk_update(
                                to_update,
                                fields=base_update_fields,
                                batch_size=500,
                            )
                            print(f"[DB] {len(to_update)} ta user yangilandi")
                            to_update = []

                    page += 1
                    time.sleep(0.01)

                except Exception as e:
                    print(f"[XATO] Sahifa {page} xatosi: {e}")
                    traceback.print_exc()
                    yield (
                        f'data: {{"status": "Sahifa {page} xatosi: {str(e)}", '
                        f'"progress": {round(total_processed / total_count * 100)}}}\n\n'
                    )
                    break

            print("=== [YAKUNLANDI] Import tugadi ===")
            yield (
                f'data: {{"status": "Yakunlandi: {total_processed} ta", '
                f'"progress": 100}}\n\n'
            )

        return StreamingHttpResponse(stream(), content_type='text/event-stream')

class ImportStudentsFromHemisStreamView(BaseHemisImportView):
    endpoint = 'student-list'
    id_field = 'student_id_number'
    role_field = 'is_student'
    model_fields = {
        'full_name': 'full_name',
        'first_name': 'first_name',
        'second_name': 'second_name',
        'group_name': 'group',
        'specialty': 'specialty',
        'education_level': 'level',
        'education_type': 'educationType',
        'payment_form': 'paymentForm',
        'education_year': 'educationYear'
    }


class ImportStaffFromHemisStreamView(BaseHemisImportView):
    endpoint = 'employee-list?type=all'
    id_field = 'employee_id_number'
    role_field = 'is_teacher'
    model_fields = {
        'full_name': 'full_name',
        'first_name': 'first_name',
        'second_name': 'second_name',
        'job_title': 'staffPosition',
        'company_name': 'department',
        'student_id_number': 'student_id_number'
    }

class ImportStudentsByGroupStreamView(BaseHemisImportView):
    endpoint = 'student-list'
    id_field = 'student_id_number'
    role_field = 'is_student'
    model_fields = {
        'full_name': 'full_name',
        'first_name': 'first_name',
        'second_name': 'second_name',
        'group_name': 'group',
        'specialty': 'specialty',
        'education_level': 'level',
        'education_type': 'educationType',
        'payment_form': 'paymentForm',
        'education_year': 'educationYear'
    }

    def get(self, request):
        self.group_filter = request.GET.get('group_id')
        if not self.group_filter:
            return JsonResponse({'status': 'error', 'message': 'Guruh ID kiritilmadi'}, status=400)
        return super().get(request)

class GroupListView(View):
    def get(self, request):
        logger.info("🔄 [START] Akademik guruhlar ro‘yxatini olish")

        # Sozlamalarni tekshirish
        setting = SystemSetting.objects.filter(is_active=True).first()
        if not setting or not setting.hemis_url or not setting.hemis_api_key:
            logger.error("❌ HEMIS sozlamalari topilmadi")
            return JsonResponse({'status': 'error', 'message': 'HEMIS sozlamalari topilmadi'}, status=400)

        base_url = setting.hemis_url.rstrip('/') + '/rest/v1/data/group-list'
        headers = {
            'accept': 'application/json',
            'Authorization': f'Bearer {setting.hemis_api_key}'
        }

        groups = []
        page = 1
        limit = 100

        while True:
            try:
                params = {'page': page, 'limit': limit}
                logger.info(f"📥 So‘rov: {base_url} params={params}")

                response = requests.get(base_url, headers=headers, params=params, timeout=10)
                if response.status_code != 200:
                    logger.error(f"❌ API xato (sahifa {page}): {response.status_code}")
                    return JsonResponse({'status': 'error', 'message': f'API xato: {response.status_code}'}, status=response.status_code)

                response_data = response.json()
                logger.debug(f"API javobi: {response_data}")

                if not response_data.get('success', False):
                    logger.error(f"❌ API muvaffaqiyatsiz: {response_data.get('error', 'Noma`lum xato')}")
                    return JsonResponse({'status': 'error', 'message': 'API muvaffaqiyatsiz'}, status=500)

                data = response_data.get('data', {})
                items = data.get('items', [])
                if not items:
                    logger.info(f"⛔ {page}-sahifada guruhlar yo‘q")
                    break

                # Guruh nomi va ID ni olish
                for item in items:
                    group_id = item.get('id')
                    group_name = item.get('name', '').strip()
                    if group_id and group_name:
                        groups.append({'id': group_id, 'name': group_name})

                # Pagination ni tekshirish
                pagination = data.get('pagination', {})
                total_pages = pagination.get('pageCount', 1)
                if page >= total_pages:
                    break

                page += 1
                time.sleep(0.01)  # API cheklovlariga hurmat

            except Exception as e:
                logger.error(f"❌ Guruhlar ro‘yxatini olishda xato: {str(e)}\n{traceback.format_exc()}")
                return JsonResponse({'status': 'error', 'message': f'Guruhlar ro‘yxatini olishda xato: {str(e)}'}, status=500)

        # Guruhlarni A-Z bo‘yicha saralash
        groups.sort(key=lambda x: x['name'].lower())

        logger.info(f"🎉 Jami {len(groups)} ta guruh topildi")
        return JsonResponse(groups, safe=False)