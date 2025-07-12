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
from question.models import SystemSetting

logger = logging.getLogger(__name__)
User = get_user_model()

class BaseHemisImportView(View):
    endpoint = None
    id_field = None
    role_field = None
    model_fields = {}
    group_filter = None

    def get(self, request):
        def stream():
            setting = SystemSetting.objects.filter(is_active=True).first()
            if not setting or not setting.hemis_url or not setting.hemis_api_key:
                yield f'data: {{"status": "HEMIS sozlamalari topilmadi", "progress": 0}}\n\n'
                return

            base_url = setting.hemis_url.rstrip('/') + f'/rest/v1/data/{self.endpoint}'
            headers = {'accept': 'application/json', 'Authorization': f'Bearer {setting.hemis_api_key}'}
            params = {'page': 1, 'limit': 1}
            if self.group_filter:
                params['_group'] = self.group_filter

            try:
                r = requests.get(base_url, headers=headers, params=params, timeout=10)
                if r.status_code != 200:
                    yield f'data: {{"status": "API xato: {r.status_code}", "progress": 0}}\n\n'
                    return
                total_count = r.json().get('data', {}).get('pagination', {}).get('totalCount', 0)
                if total_count == 0:
                    yield f'data: {{"status": "Ma\'lumot topilmadi", "progress": 0}}\n\n'
                    return
            except Exception as e:
                yield f'data: {{"status": "Parsing xatosi: {str(e)}", "progress": 0}}\n\n'
                return

            page = 1
            limit = 500
            total_processed = 0
            to_create = []
            to_update = []

            while True:
                try:
                    params = {'page': page, 'limit': limit}
                    if self.group_filter:
                        params['_group'] = self.group_filter
                    response = requests.get(base_url, headers=headers, params=params, timeout=10)
                    if response.status_code != 200:
                        yield f'data: {{"status": "Sahifa {page} xatosi: {response.status_code}", "progress": {round(total_processed / total_count * 100)}}}\n\n'
                        return

                    items = response.json().get('data', {}).get('items', [])
                    if not items:
                        break

                    ids = []
                    for item in items:
                        id_field = item.get('student_id_number') if self.role_field == 'is_student' else item.get('employee_id_number')
                        if id_field:
                            ids.append(id_field)

                    existing_users = {u.username: u for u in User.objects.filter(username__in=ids).only('username', 'student_id_number', *self.model_fields.keys())}

                    for item in items:
                        id_field = item.get('student_id_number') if self.role_field == 'is_student' else item.get('employee_id_number')
                        if not id_field:
                            continue

                        birth_date = (
                            datetime.datetime.utcfromtimestamp(item.get('birth_date')).date()
                            if isinstance(item.get('birth_date'), int) and item.get('birth_date') > 0
                            else None
                        )

                        defaults = {
                            'student_id_number': item.get('student_id_number', '') if self.role_field == 'is_teacher' else id_field
                        }
                        for k, v in self.model_fields.items():
                            value = item.get(v)
                            defaults[k] = value.get('name', '') if isinstance(value, dict) else value if value is not None else ''
                        defaults.update({
                            'date_of_birth': birth_date,
                            'gender': item.get('gender', {}).get('code', ''),
                            'nationality': item.get('citizenship', {}).get('name', 'O‘zbekiston'),
                            self.role_field: True
                        })

                        if id_field in existing_users:
                            user = existing_users[id_field]
                            for k, v in defaults.items():
                                setattr(user, k, v)
                            to_update.append(user)
                        else:
                            user = User(username=id_field, **defaults)
                            user.set_password('namdpi451')  # TODO: Secure password
                            to_create.append(user)

                        image_url = item.get('image')
                        if image_url and image_url.startswith('http'):
                            try:
                                img_response = requests.get(image_url, timeout=5)
                                if img_response.status_code == 200:
                                    file_name = os.path.basename(image_url.split('?')[0])
                                    user.profile_picture.save(file_name, ContentFile(img_response.content), save=False)
                            except Exception:
                                pass

                        total_processed += 1
                        yield f'data: {{"status": "{total_processed} ta import qilindi", "progress": {round(total_processed / total_count * 100)}}}\n\n'

                    with transaction.atomic():
                        if to_create:
                            User.objects.bulk_create(to_create, batch_size=500)
                            to_create = []
                        if to_update:
                            User.objects.bulk_update(to_update, fields=list(defaults.keys()), batch_size=500)
                            to_update = []

                    page += 1
                    time.sleep(0.01)

                except Exception as e:
                    yield f'data: {{"status": "Sahifa {page} xatosi: {str(e)}", "progress": {round(total_processed / total_count * 100)}}}\n\n'
                    break

            yield f'data: {{"status": "Yakunlandi: {total_processed} ta", "progress": 100}}\n\n'

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
        'student_id_number': 'student_id_number'  # employee uchun student_id_number saqlanadi
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