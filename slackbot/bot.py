import os
import subprocess
from flask import Flask, redirect, url_for

app = Flask(__name__)


def status():
    get_status = 'systemctl status airtable | grep Active | awk \'{print $2}\''
    temp = subprocess.Popen([get_status], stdout = subprocess.PIPE)
    # get the output as a string
    output = str(temp.communicate())

    if output == 'active':
        return "AirTable is running"
    elif output == 'inactive':
        return "AirTable is not running"
    else:
        return "Unknown status"

@app.route("/status", methods=["POST"])
def flask_status():
    return status(), 200

@app.route("/slack-redirect", methods=["GET"])
def redirect_to():

    return redirect(
        'https://slack.com/oauth/authorize?scope=chat:write,commands,incoming-webhook&client_id=3044900749.3998822956149'
    )

def server():
    app.run(host="0.0.0.0", port=7659)


server()