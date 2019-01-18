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
notify_success = os.environ["NOTIFY_SUCCESS"]

# access
la_token = os.environ["MONITOR_KEY"]


# define what app to be monitoring
app_url = api_base_url + app_os + app_package

# Set authorization for Lab Auto API
token = "Bearer " + la_token
headers = {'Authorization': token}

# turn different functionalities on or off
slack_summary_active = True


def monitor_for_report():
    # URL request to get a list of asssesments
    assessment_url = app_url + "/assessment/" + \
        "?group=" + os.environ["GROUP_ID"]

    # Get a list of assessments from the Lab Auto API and parse the JSON data
    r = requests.get(assessment_url, headers=headers)
    assessment_list = json.loads(r.text)

    # set baseline for current assessments
    num_assessments = len(assessment_list)

    # runs continuously
    while True:
        # polls the API at a set interval
        time.sleep(5)
        # pulls the list of assessments
        r2 = requests.get(assessment_url, headers=headers)
        current_list = json.loads(r2.text)
        # check and see if new assessments have been added
        print "Base assessment: " + str(num_assessments)
        print "Current assessment: " + str(len(current_list))
        if len(current_list) > num_assessments:
            print "New Assessment!"
            # check if cancelled
            try:
                if (current_list[num_assessments]["cancelled"] == True):
                    num_assessments = num_assessments + 1
                    continue
            except KeyError:
                print("no cancellation data yet")
            if (time_diff_seconds(str(current_list[num_assessments]["created"])) > 7600):
                send_slack_message(error_notify_message(str(current_list[num_assessments]["task"]), str(
                    current_list[num_assessments]["package"])))
                num_assessments = num_assessments + 1
            # check to see if something failed
            if ((str(current_list[num_assessments]["status"]["static"]["state"]) == "failed") or (str(current_list[num_assessments]["status"]["dynamic"]["state"]) == "failed")):
                send_slack_message(error_notify_message(str(current_list[num_assessments]["task"]), str(
                    current_list[num_assessments]["package"])))
                num_assessments = num_assessments + 1
                continue
            # check to make sure the new assessment has finished entirely
            if ((str(current_list[num_assessments]["status"]["static"]["state"]) == "completed") & (str(current_list[num_assessments]["status"]["dynamic"]["state"]) == "completed")):
                if notify_success:
                    print "New completed assesssment, sending report"
                    # get the new assessment
                    report_url = app_url + \
                        "/assessment/" + \
                        str(current_list[num_assessments]["task"]) + \
                        "/results" + "?group=" + str(os.environ["GROUP_ID"])
                    r3 = requests.get(report_url, headers=headers)
                    parsed_report = json.loads(r3.text)
                    issue_count = count_errors(parsed_report)
                    # sends slack message if set to true
                    if slack_summary_active:
                        code = send_slack_message(summary_slack_message(
                            parsed_report, current_list, num_assessments, issue_count))
                        if code == 200:
                            print "Slack Message sent successfully"
                        else:
                            print "Error, slack message not sent - error code " + code

                    # checks for automation errors - future functionality
                    # if(automation_error_checking == True):
                        # error_notify(assessment_url + str(current_list[num_assessments]["task"]))

                    # increment assessment counter
                else:
                    print("successful report, but no message sent")
                num_assessments = num_assessments + 1
            else:
                # There is a new assessment started, but has not completed both dynamic and static
                print "Assessment in progress, not completed"
        else:
            print "No new assessments"

# future functionality


def time_diff(start_time):
    time1 = datetime.datetime.strptime(
        start_time, "%Y-%m-%dT%H:%M:%S.%fZ")
    time2 = datetime.datetime.strptime(
        str(datetime.datetime.now()), "%Y-%m-%d %H:%M:%S.%f")
    diff = time1 - time2
    return (diff.seconds)/60


def error_notify_message(task_id, application_name):
    slack_data = {
        "text": "An application assessment has failed.\nApplication Name: " + application_name + "\nTask ID: " + task_id,
        "channel": slack_channel,
    }
    return slack_data


def count_errors(report):
    high = 0
    low = 0
    medium = 0
    info = 0
    # loop through the results and increment issue counters
    try:
        for children in report:
            try:
                if children["severity"] == "high":
                    high += 1
                    print children["title"] + " found - high risk"
                if children["severity"] == "medium":
                    medium += 1
                    print children["title"] + " found - medium risk"
                if children["severity"] == "low":
                    low += 1
                    print children["title"] + " found - low risk"
                if children["severity"] == "info":
                    info += 1
                    print children["title"] + " found - info only"
                # title = children["title"]
            except:
                pass
    except:
        pass
    return {'low': low, 'medium': medium, 'high': high, 'info': info}


# creates slack message to send as summary of new report
def summary_slack_message(parsed_report, current_list, num_assessments, issue_count):

    print "Creating message"
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
    # create the link back to the report
    # need to rework post-RBAC web URL
    # weburl = web_base_url + app_os + app_package + "/assessment/" + str(current_list[num_assessments]["task"])

    # what slack channel do we want this to go to?

    slack_data = {
        "text": "The " + app_os[1:] + " app " + app_package[1:] + " has just completed an assessment on the NowSecure Auto platform.",
        "channel": slack_channel,
        "attachments": [
            {
                "fallback": "NowSecure Automation",
                "title": "Summary results of latest assessment:",
                "color": color,
                # "title_link": weburl,
                # "text": "The following security issues were found:",
                "fields": [
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
                "footer": "<!date^" + str(now) + "^{date} at {time}|Error reading date>"
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
        print r4.message
    return r4.status_code


monitor_for_report()
