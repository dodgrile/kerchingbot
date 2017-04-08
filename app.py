import os
import sys
import json
import stripe

import requests
from flask import Flask, request, render_template, url_for
from flask_sqlalchemy import SQLAlchemy

#https://blog.hartleybrody.com/fb-messenger-bot/
#https://gist.github.com/amfeng/3517668

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
db = SQLAlchemy(app)

#db.create_all()

#minimal db
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    stripe_key = db.Column(db.String())
    stripe_customer_id = db.Column(db.String())

    def __init__(self, username, stripe_key, stripe_customer_id):
        self.stripe_key = stripe_key
        self.username = username
        self.stripe_customer_id = stripe_customer_id

    def __repr__(self):
        return '<User %r>' % self.stripe_id
#
# class Event(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     event_type = db.Column(db.String())
#     event_description = db.Column(db.String())
#
#     def __init__(self, type, desc):
#         self.event_type = type
#         self.event_description = desc
#
#     def __repr__(self):
#         return '<event %r>' % self.event_type


my_fb_id = os.environ['FB_ID'] #used for testing messages
stripe_client_id = os.environ['STRIPE_CLIENT_ID']

#facebook bot stuff
@app.route('/', methods=['GET'])
def verify():
    # when the endpoint is registered as a webhook, it must echo back
    # the 'hub.challenge' value it receives in the query arguments
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == os.environ["VERIFY_TOKEN"]:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200

    return "Hello world", 200

@app.route('/', methods=['POST'])
def webhook():

    # endpoint for processing incoming messaging events

    data = request.get_json()
    log(data)  # you may not want to log every incoming message in production, but it's good for testing

    if data["object"] == "page":

        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:

                if messaging_event.get("message"):  # someone sent us a message

                    sender_id = messaging_event["sender"]["id"]        # the facebook ID of the person sending you the message
                    recipient_id = messaging_event["recipient"]["id"]  # the recipient's ID, which should be your page's facebook ID
                    message_text = messaging_event["message"]["text"]  # the message's text

                    send_message(sender_id, "got it, thanks!")

                if messaging_event.get("delivery"):  # delivery confirmation
                    pass

                if messaging_event.get("optin"):  # optin confirmation
                    pass

                if messaging_event.get("postback"):  # user clicked/tapped "postback" button in earlier message
                    pass

    return "ok", 200

@app.route('/test')
def test_stripe_webhook():
    send_message(my_fb_id,"oh lol!")
    return "lololol"

@app.route('/recieve', methods=['POST'])
def stripe_webhook():
    data = request.get_json()
    #send_message("1282574258468483",data['type'])

    if data['type'] == "charge.succeeded":
        charge_object = data['data']['object']
        charge_id = charge_object['id']
        charge_amount = charge_object['amount']
        charge_currency = charge_object['currency']

        send_message(my_fb_id,"You received a new payment! \n ID: " + charge_id + ": \n")
    elif data['type'] == "charge.dispute.created":
        dispute_object = data['data']['object']
        dispute_charge_id = dispute_object['charge']
        dispute_charge_amount = dispute_object['amount']
        dispute_reason = dispute_object['reason']

        message_to_send = "Oh noes! A charge has been disputed \n ID: " + dispute_charge_id + " \n Reason: " + dispute_reason

        send_message(my_fb_id, message_to_send)

    elif data['type'] == "transfer.paid":
        transfer_object = data['data']['object']
        transfer_amount = transfer_object['amount']
        transfer_currency = transfer_object['currency']

        message_to_send = "Good news everyone! A transfer should now be in your bank \n" + str(transfer_amount) + transfer_currency
        send_message(my_fb_id, message_to_send)
    else:
        send_message(my_fb_id, "whut? \n + received: " + data['type'])

    return "ok", 200

def send_message(recipient_id, message_text):

    log("sending message to {recipient}: {text}".format(recipient=recipient_id, text=message_text))

    params = {
        "access_token": os.environ["PAGE_ACCESS_TOKEN"]
    }
    headers = {
        "Content-Type": "application/json"
    }
    data = json.dumps({
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": message_text
        }
    })
    r = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=data)
    if r.status_code != 200:
        log(r.status_code)
        log(r.text)


#Stripe oAuth
@app.route('/connect')
def stripe_connect():
    return render_template('connect.html',client_id = stripe_client_id )

@app.route('/connect/result')
def stripe_connect_result():
    code = request.args.get('code')
    payload = {
        'client_secret': os.environ['STRIPE_SECRET'],
        'grant_type': 'authorization_code',
        'client_id': os.environ['STRIPE_CLIENT_ID'],
        'code': code
    }

    token_uri = 'https://connect.stripe.com/oauth/token'

    r = requests.post(token_uri, params=payload)

    response_data = json.loads(r.text)
    token = response_data['access_token']

    new_user = User("atest", token, "blah")
    db.session.add(new_user)
    db.session.commit()

    return token, 200

#internal pages
@app.route('/user/settings', methods=['GET','POST'])
def user_settings():
    return render_template('settings.html')


def log(message):  # simple wrapper for logging to stdout on heroku
    print str(message)
    sys.stdout.flush()


if __name__ == '__main__':
    app.run(debug=True)
