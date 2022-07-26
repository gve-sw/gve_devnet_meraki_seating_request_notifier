''' Copyright (c) 2022 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at
           https://developer.cisco.com/docs/licenses
All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied. '''

import json
from dotenv import load_dotenv
import dateutil.parser as dp
from flask import Flask, render_template, request
from flask_mqtt import Mqtt
import time

load_dotenv()

app = Flask(__name__)

#setup MQTT Client
app.config['MQTT_BROKER_URL'] = "127.0.0.1" #"test.mosquitto.org"
app.config['MQTT_BROKER_PORT'] = 1883
#app.config['MQTT_USERNAME'] = ''  # Set this item when you need to verify username and password
#app.config['MQTT_PASSWORD'] = ''  # Set this item when you need to verify username and password
app.config['MQTT_TLS_ENABLED'] = False  # If your server supports TLS, set it to True
app.config['MQTT_CLEAN_SESSION'] = True
mqtt = Mqtt(app, connect_async=True)

settings_path = 'settings.json'


SETTINGS = {}
MVS = [] # array of cameras 

last_mv_review = [{'timestamp': 0, 'guest_count': 0},
                  {'timestamp': 0, 'guest_count': 0}]

last_notification_timestamp = 0
last_mt_timestamp = 0

guest_status=0 # 0 = no guests waiting, 1 = guests waiting - first notification sent, 2 = guests waiting - second or more notifications sent
active_request=False # user requested help actively via button
detected_guests = False #camera detected > 0 guests on both cameras
disable_count = 0 # count to make sure that no people were detected for 3 reviewing intervals before stopping the alterting


@app.route('/', methods=['GET', 'POST'])
def statusDashboard():
    """Route for status dashboard, which displays the current status and status level."""
    
    return render_template('status_dashboard.html')


@app.route('/status', methods=['GET'])
def status():
    """Route to request status updates via get request. Used by the status dashboard page for automatic updates every x seconds."""
    global guest_status, active_request, detected_guests

    status_options = ['ok', 'info', 'danger'] # 0/ok = no guests waiting, info/1 = guests waiting - first notification sent, danger/2 = guests waiting - second or more notifications sent
    status_string = status_options[guest_status]

    status_summary = {
        'status_string': status_string,
        'active_request': active_request,
        'detected_guests': detected_guests
    }
        
    return status_summary


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """Route for settings page"""

    try:
        settings = read_settings()

        if request.method == 'GET':
            
            return render_template('settings.html', settings=settings)

        elif request.method == 'POST':

            # only uppercase strings recognized as correct topic
            settings['SERIAL_MV_FRONT'] = request.form.get("input-serial-camera1").upper() or ""
            settings['ZONE_MV_FRONT'] = request.form.get("input-zone-camera1") or 0
            settings['SERIAL_MV_BACK'] = request.form.get("input-serial-camera2").upper() or ""
            settings['ZONE_MV_BACK'] = request.form.get("input-zone-camera2") or 0
            settings['MT_BUTTON_MAC'] = request.form.get("input-button-mac").upper() or ""
            settings['MT_BUTTON_LOCAL_ID'] = request.form.get("input-button-local-id").upper() or ""
            settings['REVIEWING_INTERVAL_SECONDS'] = request.form.get("input-review-interval") or 300  
            settings['NOTIFIYING_INTERVAL_SECONDS'] = request.form.get("input-notification-interval") or 10000

            write_settings(settings)
            load_settings_from_storage()
            update_topic_subscriptions()

            return render_template('settings.html', settings=settings, success=True, successmessage="Successfully updated settings.")

    except Exception as e:
            print(e)
            return render_template('settings.html', error=True, errorcode=e)


def load_settings_from_storage():
    '''Load settings values from json file into script.'''
    global SETTINGS, MVS
    
    SETTINGS = read_settings()
    MVS = [SETTINGS['SERIAL_MV_FRONT'], SETTINGS['SERIAL_MV_BACK']] 


'''
@mqtt.on_log()
def handle_logging(client, userdata, level, buf):
    print('MQTT Log: {}'.format(buf))
'''

@mqtt.on_connect()
def handle_connect(client, userdata, flags, rc):
    '''Subscribe to topics for both cameras and button on connect.'''

    if rc==0:
        print("MQTT client connected")
    else:
        print("MQTT Bad connection. Returned code=",rc)

    update_topic_subscriptions()


@mqtt.on_message()
def on_message(client, userdata, message):
    """ Every incoming mqtt message will call this function """

    mqtt_message = json.loads(message.payload.decode("utf-8"))

    if 'counts' in mqtt_message:
        source_serial = message.topic.split('/')[2]
        on_mv_message(mqtt_message, source_serial)

    if 'action' in mqtt_message:
        on_mt_message(mqtt_message)


def on_mv_message(mqtt_message, source_serial):
    """MV message handler"""

    global MVS, guest_status, last_mv_review, active_request

    current_timestamp = mqtt_message['ts']
    current_guest_count = mqtt_message['counts']['person']

    if source_serial in MVS:
        mv_id = MVS.index(source_serial)

        if message_newer_next_reviewing_timestamp(current_timestamp, mv_id):
            
            print(mqtt_message)

            update_reviewing_cache(current_timestamp, current_guest_count, mv_id)

            if mv_guest_count_on_both_mvs_g0_or_0():

                print(f'**Camera detection results matching.')
                
                if new_guests_recently_arrived(current_guest_count):
                    
                    print(f'** New guest/s is/are waiting in the entry area.')
                    
                    if not active_request: #skip if button click request notification was already sent.
                        start_or_repeat_notification(current_timestamp)
                    update_detected_person_flag(True)

                elif guests_have_been_waiting_too_long(current_timestamp, current_guest_count):
                    
                    print(f'** Guest/s has/have been waiting for quite some time.')
                    start_or_repeat_notification(current_timestamp)

                elif all_guests_were_seated(current_guest_count):

                    if (no_detection_for_three_reviewing_intervals()):
                        print(f'**Number of guest decreased. No guest are waiting anymore.')
                        stop_notification(current_timestamp)
                
            #else:
                #print(f'Camera detection results not matching.')

 
def on_mt_message(mqtt_message):
    """MT message handler"""

    current_action = mqtt_message["action"]
    current_timestamp = iso_to_epoch_timestamp(mqtt_message['ts'])

    if(mt_messages_older_than_1_min(current_timestamp) == False and is_duplicate_mt_message(current_timestamp) == False):
        print(f"Guests are waiting and have actively asked for care. {current_action}")
        
        update_active_request_flag(True)
        update_mt_timestamp_cache(current_timestamp)
        start_or_repeat_notification(current_timestamp)


# Scenarios function
def new_guests_recently_arrived(current_guest_count):
    """New guest arrived. Before this state no guests have been present"""

    global guest_status

    return guest_status==0 and current_guest_count > 0


def guests_have_been_waiting_too_long(current_timestamp, current_guest_count):
    """Already waiting guest waited for more then the notification interval value."""
    
    return notify_interval_passed(current_timestamp) and current_guest_count > 0


def all_guests_were_seated(current_guest_count):
    """All guest have been seated"""

    global guest_status

    return guest_status >= 1 and current_guest_count == 0


def start_or_repeat_notification(current_timestamp):
    """Method to start notification"""
    
    reset_disable_counter()
    escalate_waiting_status()
    update_notification_cache(current_timestamp)

    print(f'** Notifed staff.')
        

def stop_notification(current_timestamp):
    """Method to stop notification"""

    reset_status_variables()
    update_notification_cache(current_timestamp)

    print(f'** Stopped notification.')


#Helpers
def update_detected_person_flag(status):
    '''Set flag for detected guests'''
    global detected_guests

    detected_guests = status


def update_active_request_flag(status):
    '''Set flag for actively triggered seating request'''
    global active_request

    active_request = status


def reset_disable_counter():
    '''Disable counter.Used to indicate no detected people for a certain amount of time.'''
    global disable_count

    disable_count = 0


def escalate_waiting_status():
    '''Increase guest status indicator in case it isn't the maximum value already'''
    global guest_status

    if guest_status < 2:
        guest_status += 1


def reset_status_variables():
    '''Reset the status variables'''
    
    global guest_status, active_request, disable_count, detected_guests

    guest_status = 0 
    active_request = False # active seating request
    detected_guests = False # detected guests via camera 
    disable_count = 0 # disable counter


def is_duplicate_mt_message(current_timestamp):
    '''Filters duplicate mt messages based on timestamp'''
    global last_mt_timestamp

    return current_timestamp == last_mt_timestamp


def mt_messages_older_than_1_min(current_timestamp):
    '''Check if mt message is older than 1 min to prevent that old messages are outputted. '''

    now  = time.time()

    if current_timestamp < (now - 60):
        return True
    else:
        return False


def no_detection_for_three_reviewing_intervals():
    '''Increases a counter. Used to make sure both cameras detect no objects for 3 reviewing intervals.'''
    
    global disable_count

    if disable_count == 3:
        return True
    else:
        disable_count += 1
        print(f'No people detected. Round: {disable_count}')
        return False
        

def mv_guest_count_on_both_mvs_g0_or_0():
    '''Checks if the guest count identified by both camera is 0 on both cameras or greater 0 on both cameras'''

    global last_mv_review

    return (last_mv_review[0]['guest_count'] > 0 and last_mv_review[1]['guest_count'] > 0) or (last_mv_review[0]['guest_count'] == 0 and last_mv_review[1]['guest_count'] == 0)


def iso_to_epoch_timestamp(timestamp):
    '''Translated a iso timestamp to an epoch timestamp'''

    parsed_timestamp = dp.parse(timestamp)
    timestamp_in_seconds = parsed_timestamp.timestamp()
    return timestamp_in_seconds


def notify_interval_passed(current_timestamp):
    '''Check if notification interval passed'''

    NOTIFIYING_INTERVAL_SECONDS = int(SETTINGS['NOTIFIYING_INTERVAL_SECONDS'])
    global last_notification_timestamp

    next_notification_timestamp = last_notification_timestamp + NOTIFIYING_INTERVAL_SECONDS

    return current_timestamp > next_notification_timestamp


def message_newer_next_reviewing_timestamp(current_timestamp, mv_id):
    '''Checks if a received message is REVIEWING_INTERVAL_SECONDS seconds newer than the last reviewed message'''

    REVIEWING_INTERVAL_SECONDS = int(SETTINGS['REVIEWING_INTERVAL_SECONDS'])
    global last_mv_review
    
    last_review_timestamp = last_mv_review[mv_id]['timestamp']

    next_review_timestamp = last_review_timestamp + REVIEWING_INTERVAL_SECONDS

    return current_timestamp > next_review_timestamp


def update_mt_timestamp_cache(current_timestamp):
    '''Update the mt timestamp cache'''
    global last_mt_timestamp

    last_mt_timestamp = current_timestamp 


def update_notification_cache(current_timestamp):
    '''Updated the notification cache'''

    global last_notification_timestamp

    last_notification_timestamp = current_timestamp


def update_reviewing_cache(current_timestamp, current_guest_count, mv_id):
    '''Updated the reviewing cache'''

    global last_mv_review

    last_mv_review[mv_id]['timestamp'] = current_timestamp
    last_mv_review[mv_id]['guest_count'] = current_guest_count
    

def generate_topic_strings():
    """Generates the topic strings bases on settings."""
    
    # only uppercase strings recognized as correct topic
    SERIAL_MV_FRONT = SETTINGS['SERIAL_MV_FRONT']
    SERIAL_MV_BACK = SETTINGS['SERIAL_MV_BACK']

    # 0 for full screen or zone ID for zone
    ZONE_MV_FRONT = SETTINGS['ZONE_MV_FRONT']
    ZONE_MV_BACK = SETTINGS['ZONE_MV_BACK']

    MT_BUTTON_MAC = SETTINGS['MT_BUTTON_MAC']
    MT_BUTTON_LOCAL_ID = SETTINGS['MT_BUTTON_LOCAL_ID']

    MQTT_TOPIC_MV_FRONT = generate_MV_topic_string(
        SERIAL_MV_FRONT, ZONE_MV_FRONT)
    MQTT_TOPIC_MV_BACK = generate_MV_topic_string(
        SERIAL_MV_BACK, ZONE_MV_BACK)
    MQTT_TOPIC_MT_BUTTON = generate_MT_topic_string(
        MT_BUTTON_MAC, MT_BUTTON_LOCAL_ID)

    return MQTT_TOPIC_MV_FRONT, MQTT_TOPIC_MV_BACK, MQTT_TOPIC_MT_BUTTON


def generate_MV_topic_string(SERIAL_MV, ZONE_MV):
    return f'/merakimv/{SERIAL_MV}/{ZONE_MV}'

def generate_MT_topic_string(MT_BUTTON_MAC, MT_BUTTON_LOCAL_ID):
    return f'meraki/v1/mt/{MT_BUTTON_LOCAL_ID}/ble/{MT_BUTTON_MAC}/buttonReleased/#'


def update_topic_subscriptions():
    '''Replace topic subscriptions for cameras and button'''
    mqtt.unsubscribe_all()

    MQTT_TOPIC_MV_FRONT, MQTT_TOPIC_MV_BACK, MQTT_TOPIC_MT_BUTTON = generate_topic_strings()

    mqtt.subscribe(MQTT_TOPIC_MV_FRONT)
    mqtt.subscribe(MQTT_TOPIC_MV_BACK)
    mqtt.subscribe(MQTT_TOPIC_MT_BUTTON)

    print('Updated MQTT topics subscriptions')


"""Read settings from settings.json"""
def read_settings():
	with open(settings_path, 'r') as f:
		jsondata = json.loads(f.read())
		f.close()
	return jsondata


"""Write settings from settings.json"""
def write_settings(data):
    with open(settings_path, 'w') as f:
        json.dump(data, f)
        f.close()


#Main Function
if __name__ == "__main__":
    load_settings_from_storage()
    app.run(host='0.0.0.0',use_reloader=False, debug=False)
    # important: Do not use reloader because this will create two Flask instances.
    # Flask-MQTT only supports running with one instance





    