import logging
import stripe
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from django_school_management.students.models import AdmissionStudent
from django_school_management.students.tasks import send_admission_confirmation_email

logger = logging.getLogger(__name__)


def online_admission_stripepayment(request, pk):
    stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
    registrant = get_object_or_404(AdmissionStudent, pk=pk)

    if request.method == 'POST':
        success_url = request.build_absolute_uri(
            reverse('pages:stripe_payment_success', kwargs={'pk': pk})
        )
        cancel_url = request.build_absolute_uri(
            reverse('pages:stripe_payment_cancel', kwargs={'pk': pk})
        )
        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                mode="payment",
                client_reference_id=str(pk),
                line_items=[{
                    "price_data": {
                        "currency": "inr",
                        "product_data": {"name": "School Admission Application Fee"},
                        "unit_amount": 100000,  # 1000.00 INR in paise
                    },
                    "quantity": 1,
                }],
                success_url=success_url,
                cancel_url=cancel_url,
            )
            return redirect(checkout_session.url, code=303)
        except Exception as e:
            logger.exception("Stripe checkout session creation failed: %s", e)
            messages.error(request, "Could not initiate payment. Please try again.")
            return redirect('pages:online_admission')

    context = {
        'registrant': registrant,
        'stripe_publishable_key': getattr(settings, 'STRIPE_PUBLISHABLE_KEY', ''),
    }
    return render(request, 'pages/students/admission_stripe_payment.html', context)


def stripe_payment_success(request, pk):
    """
    User-facing landing page after completing Stripe checkout.
    SECURITY NOTICE: This view NEVER mutates payment state in the database.
    Payment verification and status mutation happens exclusively via `stripe_webhook`.
    """
    registrant = get_object_or_404(AdmissionStudent, pk=pk)
    return render(request, 'pages/students/admission_payment_success.html', {
        'registrant': registrant,
    })


def stripe_payment_cancel(request, pk):
    registrant = get_object_or_404(AdmissionStudent, pk=pk)
    return render(request, 'pages/students/admission_payment_cancel.html', {
        'registrant': registrant,
    })


@csrf_exempt
def stripe_webhook(request):
    """
    Cryptographically verified, idempotent webhook receiver for Stripe payment events.
    Verifies the webhook signature before marking any applicant as paid.
    """
    if request.method != 'POST':
        return HttpResponse("Method not allowed", status=405)

    payload = request.body
    sig_header = request.headers.get('Stripe-Signature', '')
    endpoint_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')

    if not endpoint_secret:
        logger.error("STRIPE_WEBHOOK_SECRET is not configured.")
        return JsonResponse({"error": "Webhook secret unconfigured"}, status=500)

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        logger.warning("Invalid webhook payload received.")
        return JsonResponse({"error": "Invalid payload"}, status=400)
    except stripe.error.SignatureVerificationError:
        logger.warning("Stripe webhook signature verification failed.")
        return JsonResponse({"error": "Invalid signature"}, status=400)

    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        client_reference_id = session.get('client_reference_id')

        if client_reference_id and str(client_reference_id).isdigit():
            try:
                registrant = AdmissionStudent.objects.get(pk=int(client_reference_id))
                if not registrant.paid:
                    registrant.paid = True
                    registrant.save(update_fields=['paid'])
                    logger.info("Payment confirmed via Stripe webhook for applicant #%s", registrant.pk)
                    try:
                        send_admission_confirmation_email.delay(registrant.id)
                    except Exception:
                        pass
            except AdmissionStudent.DoesNotExist:
                logger.error("Applicant #%s not found for Stripe webhook", client_reference_id)

    return JsonResponse({"status": "success"}, status=200)
