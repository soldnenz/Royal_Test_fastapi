from datetime import datetime
from bson import ObjectId

def get_subscription_model():
    return {
        "_id": ObjectId,
        "user_id": ObjectId,
        "iin": str,
        "subscription_type": str,
        "expires_at": datetime,
        "created_at": datetime,
        "updated_at": datetime,
        "is_active": bool,
        "issued_by": {
            "admin_iin": str,
            "full_name": str
        },
        "activation_method": str,
        "note": str,
        "duration_days": int,
        "cancelled_at": datetime,
        "cancelled_by": str,
        "cancel_reason": str,
        "payment": {
            "payment_id": ObjectId,
            "price": int,
            "payment_method": str
        }
    }
