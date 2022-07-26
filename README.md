# gve_devnet_meraki_seating_request_notifier
The purpose of this sample code is to notify restaurant staff members about guests in the entry area that are waiting to be seated. 
Thereby, guests are detected via two Meraki MV cameras and a Meraki MT30 button sensor. The detection data is delivered via MQTT. A notification can be displayed on one or more tablets, mobile phones or screens within the restaurant.
Multiple scenarios and statuses are supported: no guests present, new guests arrived, guests have been waiting for quite some time and guests actively asked for seating. 

## Contacts
* Ramona Renner

## Solution Components
* Two Meraki MV cameras
* Meraki MT30 button sensor
* Meraki MV or MX as gateway for MT sensor
* Meraki Dashboard access
* Local or online MQTT broker e.g. Mosquitto 

## Workflow

![/IMAGES/giturl.png](/IMAGES/High_level_workflow.png)

## Architecture

![/IMAGES/giturl.png](/IMAGES/High_level_design.png)


## Prerequisites
#### MQTT Broker

MQTT is a Client-Server publish/subscribe messaging transport protocol. This sample code requires the setup of a locally installed or use of an online MQTT broker that gathers the data from all cameras and sensors and publish it to our sample script. 
Popular MQTT brokers are for example: Mosquitto or HiveMQ.

> Note: Some online MQTT brokers can involve major delays in data delivery. Delays can strongly affect the quality of this demo.

#### Meraki MQTT Setup

After the MQTT broker is successfully set up, some configurations in the Meraki Dashboard are required. Follow the [MV Sense MQTT Instructions](https://developer.cisco.com/meraki/mv-sense/#!mqtt/what-is-mqtt) to configure MQTT for both cameras and [MT MQTT Setup Guide](https://documentation.meraki.com/MT/MT_General_Articles/MT_MQTT_Setup_Guide) to configure MQTT for the MT sensor. 

> Note: For demo purposes, use **None** as value for the field **Security** in both cases. Please be aware that it is recommended to use TLS in production setups. Further adaptions of this code are required for the latter. 

#### (Optional) Zone or Privacy Window

This sample code allows to optionally narrow the camera and detection view via Meraki MV Privacy Windows and Zones. Follow the [Instructions for Privacy Windows](https://documentation.meraki.com/MV/Initial_Configuration/Privacy_Windows) or [Instructions for MV Zones](https://developer.cisco.com/meraki/mv-sense/#!zones) to set these up.

## Installation/Configuration
1. Make sure Python 3 and Git is installed in your environment, and if not, you may download Python 3 [here](https://www.python.org/downloads/) and Git as described [here](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git).
2. Create and activate a virtual environment for the project ([Instructions](https://docs.python.org/3/tutorial/venv.html)).
3. Access the created virtual environment folder
    ```
    cd [add name of virtual environment here] 
    ```
4. Clone this Github repository:  
  ```git clone [add github link here]```
  * For Github link: 
      In Github, click on the **Clone or download** button in the upper part of the page > click the **copy icon**  
      ![/IMAGES/giturl.png](/IMAGES/giturl.png)
  * Or simply download the repository as zip file using 'Download ZIP' button and extract it
4. Access the downloaded folder:  
    ```cd gve_devnet_meraki_seating_request_notifier```

5. Install all dependencies:  
  ```pip3 install -r requirements.txt```

7. Define the MQTT broker to use for this script. Therefore, open the **app.py** file and adapt the following lines 25 and 26:

```
app.config['MQTT_BROKER_URL'] = "[Fill in ip of locally installed MQTT broker or URL for online MQTT broker]"
app.config['MQTT_BROKER_PORT'] = [Fill in MQTT port]
```

## Starting the Application

Run the script by using the command:
```
python3 app.py
```

## Configuring the Settings

Assuming you kept the default parameters for starting the Flask application, the address to navigate would be: http://localhost:5000/settings

![/IMAGES/giturl.png](/IMAGES/screenshot2.png)

Fill in all settings form fields and save the changes. 

Form field descriptions:

* MV Camera 1/2 - Serial Number: Serial number of Meraki MV Camera
* MV Camera 1/2 - Zone: Use 0 for full screen with or without privacy windows or zone ID for Camera MV zone. Zone ID available under **Cameras** > **[Choose Camera]** > **Settings Tab** > **Sense Tab ** > **/merakimv/xxxx-xxxx-xxxx/{zone ID}**.

* MT30 Button - Mac Address: Mac address of Meraki MT30 sensor in format XX:XX:XX:XX:XX:XX
* MT30 Button - Local ID: Local ID of Meraki button sensor - available under **Environment** > **MQTT Broker** > **MQTT Topics** > **meraki/v1/mt/{local ID}/...**.

* Reviewing Interval (ms): Milliseconds interval in which received MQTT MV messages are reviewed based on the timestamp of the message.
* Notification Interval (ms): Time span between the first and second/escalated notification in milliseconds.


## Access Notification Dashboard

Navigate to http://localhost:5000/ to access the notification dashboard. 
Enter the camera view of both cameras and optionally press the button to trigger a notification. 

![/IMAGES/giturl.png](/IMAGES/screenshot1.png)

The dashboard supports the following scenarios and statuses:

![/IMAGES/giturl.png](/IMAGES/Detailed_Workflow.png)

### LICENSE

Provided under Cisco Sample Code License, for details see [LICENSE](LICENSE.md)

### CODE_OF_CONDUCT

Our code of conduct is available [here](CODE_OF_CONDUCT.md)

### CONTRIBUTING

See our contributing guidelines [here](CONTRIBUTING.md)

#### DISCLAIMER:
<b>Please note:</b> This script is meant for demo purposes only. All tools/ scripts in this repo are released for use "AS IS" without any warranties of any kind, including, but not limited to their installation, use, or performance. Any use of these scripts and tools is at your own risk. There is no guarantee that they have been through thorough testing in a comparable environment and we are not responsible for any damage or data loss incurred with their use.
You are responsible for reviewing and testing any scripts you run thoroughly before use in any non-testing environment.