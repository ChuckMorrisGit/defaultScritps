#!/usr/bin/env python3


import paho.mqtt.client as mqtt
import os
from enum import Enum
import sys
import subprocess
import argparse
from datetime import datetime
import configparser

config = configparser.ConfigParser()
config.read('config.ini')


def run_command(command):   
    os.system(f"nohup {command} &") 
    #try:
    #    result = subprocess.check_output(command, shell=True)
    #    return result.decode('utf-8')
    #except Exception as e:
    #    return "COMMAND"

def get_commit_count():
    try:
        count = subprocess.check_output(["git", "rev-list", "--count", "HEAD"]).strip().decode('utf-8')
        return count
    except Exception as e:
        return "COMMAND"
    
VERSION = "1.0." + str(get_commit_count())

hostname = os.uname()[1]

verbose = False
client = None


class Status(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    RUNNING = "running"
    STOPPED = "stopped"
    REBOOTING = "rebooting"
    SHUTTING_DOWN = "shutting down"
    UPDATING = "updating"
    ERROR = "error"
    COMMAND = "Command running"

def getIpAddress():
    try:
        ip = subprocess.check_output(["hostname", "-I"]).strip().decode('utf-8')
        return ip
    except Exception as e:
        return "COMMAND"
    
def getLoad():
    try:
        load = subprocess.check_output(["uptime"]).strip().decode('utf-8')
        return load
    except Exception as e:
        return "COMMAND"

def setRunLevel(runlevel_new):
    global runLevel
    
    runLevel = runlevel_new
    print_datetime(runLevel)
    result = client.publish(topic_runlevel, runLevel, retain=True)
    print_datetime(f"Set Runlevel to {runLevel} with result {result.rc}")    
    
def print_datetime(additional_text=""):
    now = datetime.now()
    current_time = now.strftime("%Y-%m-%d %H:%M:%S")
    print(f"{current_time}: " + additional_text, end="")
    if additional_text != "":
        print()


def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    now = datetime.now()

    client.subscribe("devices/" + hostname + "/cmd")
    client.subscribe("devices/all/cmd")
    client.publish(topic_status, Status.ONLINE.value, retain=True)
    client.publish(topic_version, VERSION, retain=True)
    client.publish(topic_startuptime, now.strftime("%Y-%m-%d %H:%M:%S"), retain=True)
    client.publish(topic_network, str(getIpAddress()), retain=True)
    client.publish(topic_load, str(getLoad()), retain=True)
    setRunLevel(Status.RUNNING.value)


def on_message(client, userdata, msg):
    
    payload = str(msg.payload.decode('ascii'))
    print_datetime(f"Received message on topic {msg.topic} with payload >{payload}<")


##### Heartbeat Commands #####
    if payload == "status":
        print_datetime("Status request")
        client.publish(topic_status, Status.ONLINE.value, retain=True)
        client.publish(topic_network, str(getIpAddress()), retain=True)
        client.publish(topic_load, str(getLoad()), retain=True)
        return
        
    if payload == "ping":
        print_datetime("Ping request")
        client.publish(topic_status, Status.ONLINE.value, retain=True)
        client.publish(topic_load, str(getLoad()), retain=True)
        return
        
    if payload == "restart_script":
        print_datetime("Restart Script")
        print("\n")
        sys.exit(1)
    
##### Device Commands #####    
    print_datetime("Check for reboot/shutdown/update")

    if payload == "reboot":
        print_datetime("Rebooting")
        client.publish(topic_status, Status.REBOOTING.value, retain=True)
        run_command("./reboot.sh")
        
    if payload == "shutdown":   
        print_datetime("Shutting down")
        client.publish(topic_status, Status.SHUTTING_DOWN.value, retain=True)
        run_command("./shutdown.sh")
    
    if payload == "upgrade":
        print_datetime("Update request")
        client.publish(topic_status, Status.UPDATING.value, retain=True)
        run_command("./upgrade.sh")


    print_datetime("END: Check for command")
        
        
def print_version():
    print(f"Version: {VERSION}")



#####   MAIN PROGRAM #####

parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbosity", help="increase output verbosity", action="store_true")
parser.add_argument("--version", help="show Version", action="store_true")
parser.add_argument("--set_runlevel", help="Set Runlevel from Extern script", action="store")
parser.add_argument("--mqtt_host", help="MQTT Hostname", action="store")
parser.add_argument("--mqtt_port", help="MQTT Port", action="store")
parser.add_argument("--mqtt_user", help="MQTT Username", action="store")
parser.add_argument("--mqtt_pass", help="MQTT Password", action="store")

args = parser.parse_args()
if args.verbosity:
    verbose = True

if args.version:
    print(f"Version: {VERSION}")
    sys.exit(0)
    
    
### MQTT Section ###
mqtt_host = args.mqtt_host if args.mqtt_host else config['MQTT']['host']
mqtt_port = int(args.mqtt_port) if args.mqtt_port else int(config['MQTT']['port'])
mqtt_user = args.mqtt_user if args.mqtt_user else config['MQTT']['user']
mqtt_password = args.mqtt_pass if args.mqtt_pass else config['MQTT']['password']


topic_status = "devices/" + hostname + "/status"
topic_runlevel = "devices/" + hostname + "/runlevel"
topic_version = "devices/" + hostname + "/version"
topic_startuptime = "devices/" + hostname + "/startuptime"
topic_network = "devices/" + hostname + "/network"
topic_load = "devices/" + hostname + "/load"

runLevel = ""
### END MQTT Section ###
    
client = mqtt.Client(client_id="heartbeat_" + hostname)
client.on_connect = on_connect
client.on_message = on_message

client.will_set(topic_status, "offline", retain=True)

print_datetime()
client.connect(mqtt_host, 1883, 60)
    

if args.set_runlevel:
    setRunLevel(args.set_runlevel)
    sys.exit(0)

rc = 0

while rc == 0:
    rc = client.loop()
    #print_datetime()
    
print("rc: " + str(rc))