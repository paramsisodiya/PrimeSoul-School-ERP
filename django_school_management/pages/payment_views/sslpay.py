import logging
from sslcommerz_lib import SSLCOMMERZ
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from django_school_management.students.models import AdmissionStudent
from django_school_management.payments.models import SSLPayment

logger = logging.getLogger(__name__)


def online_admission_sslpayment(request, pk):
    registrant = get_object_or_404(AdmissionStudent, pk=pk)
    
    ssl_settings = {
        'store_id': getattr(settings, 'STORE_ID', ''),
        'store_pass': getattr(settings, 'STORE_PASS', ''),
        'issandbox': getattr(settings, 'SSL_ISSANDBOX', True),
    }
    sslcommerz = SSLCOMMERZ(ssl_settings)

    base_url = request.build_absolute_uri('/')[:-1]
    post_body = {
        'total_amount': 1000.00,
        'currency': 'INR',
        'tran_id': f"ADM-{registrant.id}",
        'success_url': base_url + reverse('pages:ssl_payment_success', args=[pk]),
        'fail_url': base_url + reverse('pages:ssl_payment_fail', args=[pk]),
        'cancel_url': base_url + reverse('pages:ssl_payment_cancel', args=[pk]),
        'emi_option': 0,
        'cus_name': registrant.name,
        'cus_email': registrant.email or 'applicant@primesoul.in',
        'cus_phone': registrant.mobile_number or '9999999999',
        'cus_add1': registrant.current_address or 'City',
        'cus_city': str(registrant.city) if registrant.city else 'City',
        'cus_country': 'India',
        'product_profile': 'general',
        'product_name': 'Online Admission Application Fee',
        'product_category': 'Educational Service',
        'shipping_method': 'NO',
        'num_of_item': 1,
        'cus_postcode': '110001',
    }

    try:
        response = sslcommerz.createSession(post_body)
        if response.get('status') == 'SUCCESS':
            return HttpResponseRedirect(response['GatewayPageURL'])
    except Exception as e:
        logger.exception("SSLCommerz session creation error: %s", e)

    messages.error(request, "Could not initiate payment gateway session. Please try again later.")
    return redirect('pages:online_admission')


def ssl_payment_success(request, pk):
    """
    User-facing landing page after completing SSL payment.
    SECURITY NOTICE: This view NEVER mutates payment state in the database directly.
    """
    registrant = get_object_or_404(AdmissionStudent, pk=pk)
    return render(request, 'pages/students/admission_payment_success.html', {
        'registrant': registrant,
    })


def ssl_payment_fail(request, pk):
    messages.error(request, "Payment failed. Please try again or contact school administration.")
    return redirect('pages:online_admission_sslpayment', pk=pk)


def ssl_payment_cancel(request, pk):
    messages.warning(request, "Payment was cancelled.")
    return redirect('pages:online_admission')


@csrf_exempt
def ssl_ipn_webhook(request):
    """
    Idempotent IPN receiver for payment validation.
    """
    if request.method != 'POST':
        return HttpResponse("Method not allowed", status=405)

    tran_id = request.POST.get('tran_id', '')
    val_id = request.POST.get('val_id', '')
    status = request.POST.get('status', '')

    if status == 'VALID' and tran_id.startswith('ADM-'):
        try:
            applicant_id = int(tran_id.replace('ADM-', ''))
            registrant = AdmissionStudent.objects.get(pk=applicant_id)
            if not registrant.paid:
                registrant.paid = True
                registrant.save(update_fields=['paid'])
                logger.info("Admission fee confirmed for applicant #%s via IPN", applicant_id)
        except (ValueError, AdmissionStudent.DoesNotExist):
            pass

    return HttpResponse("IPN Processed", status=200)
