import base64
import io
import pickle
import numpy as np
from PIL import Image
import face_recognition
import logging

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from account.models import FaceEncoding  # app nomiga mos

logger = logging.getLogger(__name__)
CustomUser = get_user_model()


class FaceAuthBackend(ModelBackend):
    """
    face_recognition asosida yuz bilan login.
    """

    def authenticate(self, request, images=None, **kwargs):
        print("\n====== 🔍 FACE AUTH STARTED (FaceAuthBackend.authenticate) ======\n")

        print("[FACE-AUTH] Kiruvchi kwargs:", kwargs)
        print("[FACE-AUTH] images parametri turi:", type(images))

        if not images:
            print("[FACE-AUTH] ❌ Rasm kelmadi (images None yoki bo‘sh).")
            return None

        # 1) Rasmni decode qilish
        image_data = images[0]
        print("[FACE-AUTH] Birinchi rasm string uzunligi:", len(image_data))

        try:
            if "," in image_data:
                prefix, b64_part = image_data.split(",", 1)
                print("[FACE-AUTH] data URL prefix:", prefix[:30], "...")
                image_data = b64_part

            image_bytes = base64.b64decode(image_data)
            print("[FACE-AUTH] decode qilingan baytlar uzunligi:", len(image_bytes))

            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            image_np = np.array(image)
            print(f"[FACE-AUTH] 📸 Rasm o‘lchami (H, W, C): {image_np.shape}")
        except Exception as e:
            print(f"[FACE-AUTH] ❌ Base64 decode / PIL xatosi: {e}")
            return None

        # 2) Face detection + encoding
        try:
            print("[FACE-AUTH] 🔎 Yuz qidirilmoqda (face_locations)...")
            face_locations = face_recognition.face_locations(image_np)
            print(f"[FACE-AUTH] 🔎 Topilgan yuzlar soni: {len(face_locations)}")

            if len(face_locations) == 0:
                print("[FACE-AUTH] ❌ Yuz topilmadi.")
                return None
            if len(face_locations) > 1:
                print("[FACE-AUTH] ❌ Bir nechta yuz topildi, bitta bo‘lishi kerak.")
                return None

            print("[FACE-AUTH] 🧬 Encoding olinmoqda (face_encodings)...")
            encodings = face_recognition.face_encodings(image_np, known_face_locations=face_locations)
            print(f"[FACE-AUTH] Olingan encodings soni: {len(encodings)}")

            if not encodings:
                print("[FACE-AUTH] ❌ Encoding olinmadi.")
                return None

            input_encoding = np.array(encodings[0], dtype=np.float32)
            print(f"[FACE-AUTH] 🧬 Kiruvchi encoding uzunligi: {len(input_encoding)}")
        except Exception as e:
            print(f"[FACE-AUTH] ❌ Encoding jarayonida xato: {e}")
            return None

        # 3) Bazadagi encodinglarni o‘qish
        print("[FACE-AUTH] 📦 Bazadan encodinglar olinmoqda...")
        face_enc_qs = FaceEncoding.objects.filter(encoding__isnull=False)
        print("[FACE-AUTH] 📦 Queryset count:", face_enc_qs.count())

        face_encodings = face_enc_qs.values("user_id", "encoding")
        if not face_encodings.exists():
            print("[FACE-AUTH] ❌ Bazada encodinglar yo‘q.")
            return None

        stored_encodings = []
        user_ids = []

        for fe in face_encodings:
            try:
                encoding = pickle.loads(fe["encoding"])
                if len(encoding) != len(input_encoding):  # eski/format farqli encodinglarni tashlaymiz
                    print(
                        f"[FACE-AUTH] ⚠️ user_id={fe['user_id']} uchun encoding uzunligi mos emas: "
                        f"{len(encoding)} != {len(input_encoding)}"
                    )
                    continue

                stored_encodings.append(np.array(encoding, dtype=np.float32))
                user_ids.append(fe["user_id"])
            except Exception as e:
                print(f"[FACE-AUTH] ⚠️ Encoding o‘qishda xato (user_id={fe['user_id']}): {e}")
                continue

        if not stored_encodings:
            print("[FACE-AUTH] ❌ Mos keladigan encodinglar topilmadi (hammasi skip bo‘ldi).")
            return None

        stored_encodings = np.vstack(stored_encodings)
        print(f"[FACE-AUTH] 🧬 Yuklangan encodinglar soni: {len(stored_encodings)}")

        # 4) face_distance
        print("[FACE-AUTH] 🔢 face_distance hisoblanmoqda...")
        distances = face_recognition.face_distance(stored_encodings, input_encoding)

        best_idx = int(np.argmin(distances))
        best_distance = float(distances[best_idx])
        threshold = 0.6

        print(
            f"[FACE-AUTH] 👉 Best index={best_idx}, distance={best_distance:.4f}, "
            f"threshold={threshold}"
        )

        if best_distance <= threshold:
            matched_id = user_ids[best_idx]
            print(f"[FACE-AUTH] ✅ threshold ichida. matched_id={matched_id}")

            try:
                matched_user = CustomUser.objects.get(id=matched_id)

                raw_score = max(0.0, (threshold - best_distance) / threshold)
                similarity_score = round(raw_score * 100, 2)
                matched_user._face_similarity_score = similarity_score

                print(
                    f"[FACE-AUTH] ✅ Match: {matched_user.username} | "
                    f"distance={best_distance:.4f} | score={similarity_score}%"
                )
                print("\n====== ✅ AUTH SUCCESS ======\n")
                return matched_user
            except CustomUser.DoesNotExist:
                print(f"[FACE-AUTH] ❌ matched_id={matched_id} bo‘yicha user topilmadi.")
                return None

        print(f"[FACE-AUTH] ❌ Mos user topilmadi. Best distance={best_distance:.4f} > threshold.")
        print("\n====== ❌ AUTH FAILED ======\n")
        return None