import numpy as np
from django.contrib.auth.backends import ModelBackend
from .models import FaceEncoding, CustomUser
from deepface import DeepFace
import logging
import base64
import io
from PIL import Image
import pickle
from scipy.spatial import distance

logger = logging.getLogger(__name__)

class FaceAuthBackend(ModelBackend):
    # Modelni keshlash uchun sinf atributi
    _model_initialized = False
    _arcface_model = None

    def __init__(self):
        if not FaceAuthBackend._model_initialized:
            try:
                # Modelni bir marta yuklash
                DeepFace.represent(
                    np.zeros((112, 112, 3)),  # Dummy rasm
                    model_name='ArcFace',
                    enforce_detection=False,
                    detector_backend='opencv'  # Tezroq detektor
                )
                FaceAuthBackend._model_initialized = True
                logger.info("[INFO] ArcFace modeli yuklandi")
            except Exception as e:
                logger.error(f"[ERROR] ArcFace modelini yuklashda xato: {str(e)}")
                raise

    def authenticate(self, request, images=None, **kwargs):
        if not images or len(images) == 0:
            logger.debug("[DEBUG] Hech qanday rasm berilmadi")
            return None

        # Birinchi rasmni qayta ishlash
        image_data = images[0]
        try:
            image_data = base64.b64decode(image_data.split(',')[1])
            image = Image.open(io.BytesIO(image_data)).convert('RGB')
            image_np = np.array(image)
            embedding = DeepFace.represent(
                img_path=image_np,
                model_name='ArcFace',
                enforce_detection=True,
                detector_backend='opencv'  # Tezroq detektor
            )
            input_encoding = np.array(embedding[0]['embedding'], dtype=np.float32)
        except Exception as e:
            logger.error(f"[ERROR] Rasmni qayta ishlash xatosi: {str(e)}")
            return None

        # Ma’lumotlar bazasidan embeddinglarni olish
        try:
            face_encodings = FaceEncoding.objects.values('user_id', 'encoding')
            if not face_encodings.exists():
                logger.debug("[DEBUG] Ma’lumotlar bazasida encodinglar yo‘q")
                return None

            # Embeddinglarni keshlash va vektorlashtirish
            stored_encodings = []
            user_ids = []
            for face_encoding in face_encodings:
                try:
                    encoding = pickle.loads(face_encoding['encoding'])
                    if len(encoding) == len(input_encoding):
                        stored_encodings.append(np.array(encoding, dtype=np.float32))
                        user_ids.append(face_encoding['user_id'])
                except Exception:
                    continue

            if not stored_encodings:
                logger.debug("[DEBUG] Mos encodinglar topilmadi")
                return None

            # Vektorlashtirilgan kosinus masofasini hisoblash
            stored_encodings = np.array(stored_encodings)
            input_norm = np.linalg.norm(input_encoding)
            stored_norms = np.linalg.norm(stored_encodings, axis=1)
            cos_similarities = np.dot(stored_encodings, input_encoding) / (stored_norms * input_norm)
            distances = 1 - cos_similarities  # Kosinus masofasi
            threshold = 0.6  # ArcFace uchun moslangan

            # Eng yaxshi moslikni topish
            best_idx = np.argmin(distances)
            best_distance = distances[best_idx]
            if best_distance < threshold:
                best_match = user_ids[best_idx]
                try:
                    user = CustomUser.objects.get(id=best_match)
                    logger.info(f"[INFO] Foydalanuvchi topildi: {user.username}, kosinus masofasi: {best_distance:.3f}")
                    return user
                except CustomUser.DoesNotExist:
                    logger.error(f"[ERROR] Foydalanuvchi ID {best_match} topilmadi")
                    return None

            logger.debug("[DEBUG] Mos foydalanuvchi topilmadi")
            return None
        except Exception as e:
            logger.error(f"[ERROR] Ma’lumotlar bazasi so‘rovida xato: {str(e)}")
            return None
