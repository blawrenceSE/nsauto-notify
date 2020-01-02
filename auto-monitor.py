import json
import sys
import os
import time
import requests
import datetime
from time_diff import time_diff_seconds

# set base URL's to access API's
api_base_url = "https://lab-api.nowsecure.com/app"
# web_base_url = "https://lab.nowsecure.com/app"

# pull config items - can be handled however is preferable
app_os = '/' + os.environ["APP_OS"]
app_package = '/' + os.environ["APP_PACKAGE"]
slack_channel = os.environ["SLACK_CHANNEL"]
notify_error = os.environ["NOTIFY_ERROR"]
notify_success = os.environ["NOTIFY_SUCCESS"]
# options: medium, high, critical, none
notify_threshold = os.environ["NOTIFY_THRESHOLD"]

# access
la_token = os.environ["MONITOR_KEY"]


# define what app to be monitoring
app_url = api_base_url + app_os + app_package

# Set authorization for Lab Auto API
token = "Bearer " + la_token
headers = {'Authorization': token}
app_id = ""


def change_app_id(id):
    global app_id
    app_id = id
    return app_id


def monitor_for_report():
    # URL request to get a list of asssesments
    assessment_url = app_url + "/assessment/" + \
        "?group=" + os.environ["GROUP_ID"]

    # Get a list of assessments from the Lab Auto API and parse the JSON data
    r = requests.get(assessment_url, headers=headers)
    assessment_list = json.loads(r.text)
    completed_assessments = []
    # set app id for URL generation
    change_app_id(assessment_list[0]["application"])
    # populate whatever has already been done
    for report in assessment_list:
        completed_assessments.append(report["task"])

    # set baseline for current assessments
    need_processing = []
    # runs continuously
    while True:
        # polls the API at a set interval
        time.sleep(60)
        # pulls the list of assessments
        r2 = requests.get(assessment_url, headers=headers)
        current_list = json.loads(r2.text)
        for report in current_list:
            if (report["task"] not in completed_assessments) and (report["task"] not in need_processing):
                need_processing.append(report["task"])
        print("waiting to process:" + str(need_processing))
        for task in need_processing:
            if process_assessment(task):
                need_processing.remove(task)
                completed_assessments.append(task)


def process_assessment(task_id):
    report_url = app_url + "/assessment/" + \
        str(task_id) + "/report?group=" + str(os.environ["GROUP_ID"])
    r = requests.get(report_url, headers=headers)
    if r.status_code == 404:
        return False
    report_info = json.loads(r.text)
    # check if cancelled
    if (report_info["dynamic"]["state"] == "cancelled"):
        return True
    if (str(report_info["dynamic"]["state"]) == "processing") and (str(report_info["static"]["state"]) == "processing"):
        return False
    # checks to see if assessment has taken too long and just errors it out, also looks for static/dynamic failure
    if (time_diff_seconds(str(report_info["dynamic"]["created"])) > 0) or ((str(report_info["dynamic"]["state"]) == "failed") or (str(report_info["static"]["state"]) == "failed")):
        if(notify_error == 'True'):
            send_slack_message(error_notify_message(str(report_info["dynamic"]["params"]["task"]), str(
                report_info["dynamic"]["params"]["app"]["package"])))
        return True
    if ((str(report_info["dynamic"]["state"]) == "completed") and (str(report_info["static"]["state"]) == "completed")) and (str(report_info["yaap"]["state"]) == "completed"):
        if notify_success == 'True':
            print ("New completed assesssment, processing report for Task ID: " + \
                str(task_id))
            issue_count = count_errors(task_id)
            if((notify_threshold == "none") or (notify_threshold == "medium" and (issue_count["medium"] > 0 or issue_count["high"] > 0 or issue_count["critical"]) > 0) or (notify_threshold == "high" and (issue_count["high"] > 0 or issue_count["critical"]) > 0) or (notify_threshold == "critial" and issue_count["critical"] > 0)):
                code = send_slack_message(summary_slack_message(
                    report_info, issue_count))
                if code == 200:
                    print ("Slack Message sent successfully")
                else:
                    print( "Error, slack message not sent - error code " + code)
            else:
                print(
                    "Report did not meet minimum notification threshold, no message sent")
        return True


def time_diff(start_time):
    time1 = datetime.datetime.strptime(
        start_time, "%Y-%m-%dT%H:%M:%S.%fZ")
    time2 = datetime.datetime.strptime(
        str(datetime.datetime.now()), "%Y-%m-%d %H:%M:%S.%f")
    diff = time1 - time2
    return (diff.seconds)/60


def error_notify_message(task_id, application_name):
    # weburl = "https://lab.nowsecure.com/app/" + app_id + \
    #    "/assessment/" + str(task_id)
    slack_data = {
        "text": "Application: " + application_name + "\nLode Runner link: https://lode-runner.nws-prd-west.nowsecure.io/dashboard/jobs/" + task_id + " \nhas failed to complete successfully, we may want to investigate",
        "channel": slack_channel
    }
    return slack_data


def count_errors(task_id):
    report_url = app_url + "/assessment/" + \
        str(task_id) + "/results?group=" + str(os.environ["GROUP_ID"])
    r3 = requests.get(report_url, headers=headers)
    report = json.loads(r3.text)
    high = 0
    low = 0
    medium = 0
    info = 0
    critical = 0
    # loop through the results and increment issue counters
    try:
        for children in report:
            try:
                if children["severity"] == "high":
                    high += 1
                    print (children["title"] + " found - high risk")
                if children["severity"] == "critical":
                    critical += 1
                    print (children["title"] + " found - critical risk")
                if children["severity"] == "medium":
                    medium += 1
                    print (children["title"] + " found - medium risk")
                if children["severity"] == "low":
                    low += 1
                    print (children["title"] + " found - low risk")
                if children["severity"] == "info":
                    info += 1
                    print (children["title"] + " found - info only")
                # title = children["title"]
            except:
                pass
    except:
        pass
    return {'low': low, 'medium': medium, 'high': high, 'info': info, 'critical': critical}


# creates slack message to send as summary of new report
def summary_slack_message(parsed_report, issue_count):

    print ("Creating message")
    # create the slack message
    now = int(time.time())
    color = ""
    if issue_count['info'] > 0:
        color = "#808080"
    if issue_count['low'] > 0:
        color = "#008080"
    if issue_count['medium'] > 0:
        color = "#FFC300"
    if issue_count['high'] > 0:
        color = "#FF0000"
    if issue_count['critical'] > 0:
        color = "#8c0101"
    # create the link back to the report
    # need to rework post-RBAC web URL
    weburl = "https://lab.nowsecure.com/app/" + app_id + \
        "/assessment/" + str(parsed_report["dynamic"]["params"]["task"])

    slack_data = {
        "text": "The " + app_os[1:] + " app " + app_package[1:] + " has just completed an assessment on the NowSecure Platform.",
        "channel": slack_channel,
        "attachments": [
            {
                "fallback": "NowSecure Automation",
                "title": "Click here to view the full report",
                "color": color,
                "title_link": weburl,
                "text": "The following security issues were found:",
                "fields": [
                    {
                        "value": str(issue_count['critical']) + " critical risk",
                        "short": "true"
                    },
                    {
                        "value": str(issue_count['high']) + " high risk",
                        "short": "true"
                    },
                    {
                        "value": str(issue_count['medium']) + " medium risk",
                        "short": "true"
                    },
                    {
                        "value": str(issue_count['low']) + " low risk",
                        "short": "true"
                    },
                    {
                        "value": str(issue_count['info']) + " informational",
                        "short": "true"
                    }
                ],
                "footer": "<!date^" + str(now) + "^{date} at {time}|Error reading date> "
            }
        ]
    }
    return slack_data

# just to send messages to slack


def send_slack_message(text_to_send):
    slack_url = os.environ["SLACK_WEBHOOK"]
    # slack_header = 'Content-type: application/json'
    r4 = requests.post(slack_url, json=text_to_send)
    if r4.status_code != 200:
        print ("Slack webhook error " + r4.message)
    return r4.status_code


monitor_for_report()
