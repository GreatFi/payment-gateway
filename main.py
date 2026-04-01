import stripe
import dotenv
import os
from fastapi import FastAPI, Depends, HTTPException, Request
from typing import Annotated
from pydantic import BaseModel
from models import Payment, engine
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import update, select
import json
import logging
from datetime import datetime, timezone
dotenv.load_dotenv()

endpoint_secret = os.environ.get("webhook_secret")

app = FastAPI()

def get_db():
    db = Session(engine)
    try:
        yield db
    finally:
        db.close()

stripe.api_key = os.environ.get("STRIPE_API_KEY")

class checkoutRequest(BaseModel):
    amount: int
    currency: str 
    customer_id : int
    order_id : int

class checkoutResponse(BaseModel):
    status: str

    class Config:
        from_attributes = True


@app.post("/checkout/")
async def payment_intent(request: checkoutRequest, db:Annotated[Session, Depends(get_db)]):

    payment_obj = Payment(
        amount=request.amount,
        currency=request.currency,
        customer_id=request.customer_id,
        order_id=request.order_id,
    )
    db.add(payment_obj)
    db.commit()
    response = checkoutResponse.model_validate(
        payment_obj
    )

    payment_intent = stripe.PaymentIntent.create(
        amount=request.amount,
        currency=request.currency,
        idempotency_key=f'{request.order_id}',
        metadata={'order_id': request.order_id},
        payment_method='pm_card_visa',
        payment_method_types=['card'],
        confirm = True
    )

    statement = update(Payment).where(Payment.id == payment_obj.id).values(payment_intent_id=payment_intent['id'])
    db.execute(statement)
    db.commit()
    return response

@app.post("/webhook/")
async def webhook_handler(request:Request, db:Annotated[Session, Depends(get_db)]):
    event = None
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except stripe.error.SignatureVerificationError as e:
        print('Webhook signature verification failed.' + str(e))
        raise HTTPException(status_code=400, detail="Webhook signature verification failed.")
    except Exception as e:
        print("Invalid payload", str(e))
        raise HTTPException(status_code=400, detail="Invalid payload")
        
    if event['type'] == 'payment_intent.succeeded':
        
        payment_intent = event['data']['object']
        succeeded_at = datetime.fromtimestamp(payment_intent['created'], tz=timezone.utc)
        statement = update(Payment).where(Payment.order_id == payment_intent['metadata']['order_id']).values(status='succeeded', succeeded_at=succeeded_at)
        result = db.execute(statement)
        print("Rows affected:", result.rowcount)
        db.commit()
        return {"success": True}
    
    else:
        print('Unhandled event type {}'.format(event['type']))
    return {"success":True}


@app.post("/refund/{id}")
async def refund(db:Annotated[Session, Depends(get_db)], id:str):

    statement = select(Payment).where(Payment.payment_intent_id == id)
    row = db.scalars(statement).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Row not found")
    elif row.status == 'succeeded':
        try:
            refund = stripe.Refund.create(
                payment_intent=id
            )
            statement = update(Payment).where(Payment.id == row.id).values(status = 'refunded')
            db.execute(statement)
            db.commit() 
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail="Stripe error: " + str(e))
        except SQLAlchemyError as e:
            logging.error(f"Database error: \n payment_id:{id},\n refund_id:{refund['id']}")
            raise HTTPException(status_code=500, detail="Database error" + str(e))
        return {"success":True}
        
    
@app.get("/payments/{payment_intent_id}", response_model=checkoutResponse)
async def get_payment(payment_id:str, db:Annotated[Session, Depends(get_db)]):
    statement = select(Payment).where(payment_id == Payment.payment_intent_id)
    single_payment = db.scalars(statement).one_or_none()

    if single_payment is None:
        raise HTTPException(status_code=404, detail="Payment with this id isnt found")
    return single_payment

@app.get("/payments/")
async def all_payments(db:Annotated[Session, Depends(get_db)]):
    statement = select(Payment)
    all_payments = db.scalars(statement).all()

    return all_payments
