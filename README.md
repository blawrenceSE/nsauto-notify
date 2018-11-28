# auto-monitor

Monitors an Auto application and pushes notifications

## Setup

Requires python 2.7, also `pip install requests`. This is handled by the docker container as needed. However, it is a bare bones Docker container that will require you to specify the configuration variables ahead of running anything.

Currently requires certain environment variables:

- `APP_OS` - either `ios` or `android`
- `APP_PACKAGE` - package name of the application being monitored
- `MONITOR_KEY` - Auto token generated from within the web UI
- `SLACK_WEBHOOK` - Slack generated webhook for sending incoming messages
  - Note that most of the configuration for how the message looks is contained here _except_ the icon and name of the message sender. Those should be configured within your individual slack instance.
- `SLACK_CHANNEL` - specify what channel the slack notification will be sent to. Optional if slack integration is not active.

## Other things to keep in mind

There is a 30 second delay built in to the script. You can adjust how often it checks for a new assessment by changing the `sleep` time

sample docker setup:
`docker build . -t <image_name>`

```docker run \
    -e MONITOR_KEY=<monitor_key> \
    -e APP_OS=android \
    -e SLACK_WEBHOOK=https://hooks.slack.com/services/<webhook information> \
    -e APP_PACKAGE=com.anydo \
    -e SLACK_CHANNEL="#anydomonitor" \
    -e GROUP_ID="<group-id>" \
    -e PYTHONBUFFERED=0 \
    --name <container name> \
    auto-notify

```
