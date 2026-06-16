import uuid
from app.database import SessionLocal, tenant_context
from app.api.v1.whatsapp import handle_whatsapp_webhook, WebhookPayload

def test():
    db = SessionLocal()
    
    # 1. Test success path
    payload_success = WebhookPayload(
        tenant_id=uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d"),
        sender_phone="+919999888877",
        message_text="Bhaiya, please deliver 50 HUL Soap immediately"
    )
    
    # Set the tenant context
    token = tenant_context.set(payload_success.tenant_id)
    try:
        print("\n--- SIMULATING SUCCESSFUL INGESTION ---")
        res_ok = handle_whatsapp_webhook(payload=payload_success, db=db)
        print("RESULT SUCCESS:", res_ok)
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        tenant_context.reset(token)

    # 2. Test failure path (unmatched product)
    payload_fail = WebhookPayload(
        tenant_id=uuid.UUID("d3b07384-d113-4956-a5d2-64be7357c11d"),
        sender_phone="+919999888877",
        message_text="10 PatanjaliDantKanti"
    )
    token = tenant_context.set(payload_fail.tenant_id)
    try:
        print("\n--- SIMULATING MISMATCHED/UNMATCHED PRODUCT INGESTION ---")
        res_fail = handle_whatsapp_webhook(payload=payload_fail, db=db)
        print("RESULT FAILURE:", res_fail)
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        tenant_context.reset(token)
        db.close()

if __name__ == "__main__":
    test()
