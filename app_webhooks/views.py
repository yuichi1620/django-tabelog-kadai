from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from app_webhooks.services.stripe_webhook_service import parse_event, process_event


@csrf_exempt
@require_POST
def stripe_webhook(request):
    payload = request.body
    signature = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    try:
        event = parse_event(payload=payload, signature=signature)
    except Exception:
        return HttpResponse(status=400)
    return HttpResponse(status=process_event(event))
