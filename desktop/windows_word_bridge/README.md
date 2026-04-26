# Quiz Office Helper

Bu yordamchi dastur Windows kompyuterda lokal ishlaydi va brauzer sahifasiga ochiq Word, Excel va PowerPoint oynalarini berib turadi.

## Nega kerak

Ubuntu server foydalanuvchining Windows kompyuteridagi ochiq `Microsoft Office` oynalarini ko'ra olmaydi. Shu sabab web ilova `localhost` dagi lokal yordamchi bilan gaplashadi:

1. Foydalanuvchi Windows'da Word, Excel yoki PowerPoint faylini ochadi.
2. `Quiz Office Helper` ochiq Office oynalarini `http://127.0.0.1:8765` orqali beradi.
3. Django sahifasi yordamchidan hujjat HTML va text mazmunini olib, server parseriga yuboradi.
4. Parser preview va batch save oqimini bajaradi.

## Eng qulay usul

1. [build_exe.bat](D:/Github/QUIZ-DJANGO/desktop/windows_word_bridge/build_exe.bat) yoki [build_exe.ps1](D:/Github/QUIZ-DJANGO/desktop/windows_word_bridge/build_exe.ps1) bilan `dist\QuizOfficeHelper.exe` ni yig'ing.
2. `QuizOfficeHelper.exe` ni ishga tushiring.
3. Dastur system tray ichida orqa fonda ishlaydi.
4. `/administrator/tests/<id>/questions/add/` sahifasiga qayting.
5. `Ochiq oynalarni yangilash` ni bosing.
6. Kerakli Office faylini tanlab `Tanlangan oynadan olish` ni bosing.

## Python bilan ishga tushirish

Windows kompyuterda:

```powershell
cd D:\Github\QUIZ-DJANGO\desktop\windows_word_bridge
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python bridge.py
```

`pystray` o'rnatilgan bo'lsa yordamchi tray ikon bilan yashirin ishlaydi. Aks holda oddiy console server sifatida ishga tushadi.

Yoki yanada osoni:

- [start_bridge.bat](D:/Github/QUIZ-DJANGO/desktop/windows_word_bridge/start_bridge.bat)
- [start_bridge.ps1](D:/Github/QUIZ-DJANGO/desktop/windows_word_bridge/start_bridge.ps1)

## Endpointlar

- `GET /health`
- `GET /api/office/windows`
- `POST /api/office/document-content`

## Frontend bilan ishlash

`/administrator/tests/<id>/questions/add/` sahifasidagi:

- `Worddan tez olish`
- `Katta Word yoki Office faylidan yuklash`

oqimi shu yordamchi bilan ishlaydi.

## O'qituvchi uchun eng oson usul

Ko'p hollarda yordamchi ham kerak bo'lmaydi:

1. Word ichida savollarni belgilang
2. `Ctrl+C` bosing
3. Sahifada `Worddan tez olish` ni bosing
4. Preview chiqadi
5. `Barchasini saqlash` ni bosing

## Muhim eslatma

Yordamchi dastur Windows kompyuterda ishlashi kerak. Ubuntu serverdagi Django process Office oynalarini ko'ra olmaydi.
