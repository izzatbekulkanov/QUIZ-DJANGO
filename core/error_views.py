from django.http import HttpResponse
from django.template.loader import render_to_string


ERROR_PAGE_COPY = {
    400: {
        "title": "So'rov noto'g'ri",
        "eyebrow": "400",
        "message": "Yuborilgan so'rovni qayta ishlashda muammo bor. Sahifani yangilab qayta urinib ko'ring.",
    },
    403: {
        "title": "Ruxsat yo'q",
        "eyebrow": "403",
        "message": "Bu sahifani ko'rish uchun sizda yetarli ruxsat mavjud emas.",
    },
    404: {
        "title": "Sahifa topilmadi",
        "eyebrow": "404",
        "message": "Bu manzil mavjud emas yoki sizga ko'rsatilmaydi.",
    },
    500: {
        "title": "Server xatosi",
        "eyebrow": "500",
        "message": "Serverda kutilmagan xatolik yuz berdi. Iltimos, birozdan keyin qayta urinib ko'ring.",
    },
}


def render_error_page(request, status_code=500, title=None, message=None):
    page = ERROR_PAGE_COPY.get(status_code, ERROR_PAGE_COPY[500]).copy()
    if title:
        page["title"] = title
    if message:
        page["message"] = message

    content = render_to_string(
        "errors/error.html",
        {
            "status_code": status_code,
            **page,
        },
    )
    return HttpResponse(content, status=status_code)


def bad_request(request, exception):
    return render_error_page(request, status_code=400)


def permission_denied(request, exception):
    return render_error_page(request, status_code=403)


def page_not_found(request, exception):
    return render_error_page(request, status_code=404)


def server_error(request):
    return render_error_page(request, status_code=500)
