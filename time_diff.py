import datetime
# 2018-11-13T21:36:51.906Z


def time_diff_seconds(time1):
    time1 = datetime.datetime.strptime(time1, "%Y-%m-%dT%H:%M:%S.%fZ")
    time2 = datetime.datetime.strptime(
        datetime.datetime.now(), "%Y-%m-%d %H:%M:%S.%f")
    diff = time1 - time2
    return diff.days
