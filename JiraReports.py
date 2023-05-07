import matplotlib.pyplot as plt
import matplotlib as mpl
import requests
import json
import argparse
import configparser
import MsGraphMail
import io
import base64
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from requests.auth import HTTPBasicAuth
from datetime import datetime
from datetime import date
from datetime import timedelta
import calendar


"""
    JiraReports - basic html tool to fetch reports from Jira cloud based on jira RESTful API.

    usage: JiraReports [-h] [-s STARTDATE] [-e ENDDATE] [-m] [-p] [-r REPORTS [REPORTS ...]] [-b BREAKDOWN] [-g]

           optional arguments:
             -h, --help            show this help message and exit
             -s STARTDATE          Start date for the report in the format of : YYYY-MM-DD
             -e ENDDATE            End date for teh report in the format of : YYYY-MM-DD
             -m                    Print reports menu
             -p                    Flag for periodic reports (used for CRON jobs)
             -r REPORTS [REPORTS ...] List of reports seperated by space
             -b BREAKDOWN          Break Down resolution - 'd' for day 'w' for week and 'm' for month
             -g                    Flag to generate graphical reports
"""


class Set:
    """
        Set - helper class, contains one set of a series.
    """

    def __init__(self, name, color):
        self.name = name
        self.color = color
        self.x = list()
        self.y = list()
        self.avg = 0
        self.cnt = 0
        self.type = None

    def calcMetrics(self):
        """
            calcMetrics() - a function to calculate the count and the average of all values to the set y values
        """
        for elem in self.y:
            self.cnt = self.cnt + elem
        self.avg = self.cnt / len(self.y)


class Report:
    """
        Report - helper class contains all the series in a report
    """

    def __init__(self, name):
        self.name = name
        self.series = list()

    def addSet(self, set):
        """
        addSet - addes a set to the serries
        """
        set.calcMetrics()
        self.series.append(set)


def initLogger(logFile):
    logging.basicConfig(
        handlers=[RotatingFileHandler(logFile, maxBytes=1000000, backupCount=5)],
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
        datefmt='%Y-%m-%dT%H:%M:%S')
    log = logging.getLogger("JIRAREPORTS")
    log.setLevel(logging.DEBUG)

    return log


def printMenu():
    """
        Print the menu , used for cli operation
    """
    print("{0:<10}{1:<11}{2:<11}".format("Report #", "|", "Description"))
    print('-' * 32)
    print("{0:<10}{1:<11}{2:<11}".format("15", "|", "Create vs Resolved"))
    print("{0:<10}{1:<11}{2:<11}".format("17", "|", "SLA Met vs Breached"))
    print("{0:<10}{1:<11}{2:<11}".format("25", "|", "SLA - Time"))
    print("{0:<10}{1:<11}{2:<11}".format("26", "|", "Cr by Type"))
    print("{0:<10}{1:<11}{2:<11}".format("27", "|", "Work Load"))


def parseInput(startTime, endTime, breakDown, reports):
    if not startTime:
        startTime = input("Please insert start date for the report (please set input as : YYYY-MM-DD)\n")
    if not endTime:
        endTime = input("Please insert end date for teh report (please set input as : YYYY-MM-DD)\n")
    if not breakDown:
        breakDown = input("Please insert report break down (d - date, w - week, m - month)\n")
    if not reports:
        print("please insert report number , multiple report can be selected by seperating them with a comma \",\":")
        printMenu()
        reports = input("Report(s): ").split(',')
    return startTime, endTime, breakDown, reports


def checkDate(value):
    y, m, d = value.split('-')
    if ((date.today() - datetime.strptime(value, "%Y-%m-%d").date()).days < 0):
        raise argparse.ArgumentTypeError("%s date can only be smaller than today" % value)
    return value


# ARG parser
def parseArgs():
    parser = argparse.ArgumentParser(prog='JiraReports', description='Fetch reports from Jira.')
    parser.add_argument('-s', dest="startDate", type=checkDate,
                        help='Start date for the report in the format of : YYYY-MM-DD')
    parser.add_argument('-e', dest='endDate', type=str, action='store',
                        help='End date for teh report in the format of : YYYY-MM-DD')
    parser.add_argument('-m', dest='menu', action='store_true', help='Print reports menu')
    parser.add_argument('-p', dest='periodic', action='store_true',
                        help='Flag for periodic reports (used for CRON jobs)')
    parser.add_argument('-r', dest='reports', type=str, action='store', nargs='+',
                        help='List of reports seperated by space')
    parser.add_argument('-b', dest='breakDown', type=str, action='store',
                        help='Break Down resolution - \'d\' for day \'w\' for week and \'m\' for month')
    parser.add_argument('-g', dest='graph', action='store_true', default=False,
                        help='Flag to generate graphical reports')

    return parser.parse_args()


def retriveReports(uri, auth, headers, startTime, endTime, breakDown, reports):
    log = logging.getLogger('JIRAREPORTS')
    log.info("Starting retriveReports from JIRA")
    result = list()
    for rep in reports:
        url = uri + rep + "/date-range?startDate=" + startTime + "&endDate=" + endTime + "&timeBreakdown=" + breakDown
        response = requests.request("GET", url, headers=headers, auth=auth)
        if response.status_code != 200:
            log.info('some issu occured with the JIRA API')
            log.info(response.text)
            sys.exit(0)
        jsn = response.json()
        reportLocal = Report(jsn["name"])
        for ser in jsn['series']:
            seriesLocal = Set(ser['label'], ser['color'])
            seriesLocal.type = ser["seriesType"]["yaxis"]['typeKey'].split('.')[-1]
            for ln in ser['data']:
                # adjust the winter time time zone
                addTime = timedelta(hours=2)
                seriesLocal.x.append((datetime.fromtimestamp(ln['x'] / 1e3) + addTime).date())
                multVal = 1
                if (seriesLocal.type == "duration"):
                    multVal = (0.001 / 3600)
                seriesLocal.y.append(ln['y'] * multVal)
            reportLocal.addSet(seriesLocal)
        result.append(reportLocal)

    return result


def plotGraph(results):
    mpl.style.use('seaborn')
    fig, axs = plt.subplots(len(results))
    if (len(results) == 1):
        axs = [axs]
    i = 0
    for rep in results:
        for ser in rep.series:
            if ser.type == 'duration':
                val = ser.avg
            else:
                val = ser.cnt
            axs[i].plot(ser.x, ser.y, 'o-', color=ser.color, label=ser.name + ' - ' + str(val))
        axs[i].legend(bbox_to_anchor=(1.01, 0.66), loc="upper left")
        axs[i].set_title(rep.name)
        i = i + 1
    plt.show()


def generateGraphs(results):
    graphs = dict()
    mpl.style.use('seaborn')
    for rep in results:
        plt.clf()
        for ser in rep.series:
            if ser.type == 'duration':
                val = ser.avg
            else:
                val = ser.cnt
            plt.plot(ser.x, ser.y, 'o-', color=ser.color, label=ser.name + ' - ' + str(val))
        buff = io.BytesIO()
        locs, labels = plt.xticks()
        plt.xticks(mpl.dates.date2num(ser.x), labels=ser.x, rotation=45)
        plt.savefig(buff, format='png', dpi=300, edgecolor='black', bbox_inches='tight')
        imgEncoded = base64.b64encode(buff.getvalue()).decode("utf-8").replace("\n", "")
        graphs[rep.name] = imgEncoded
    return graphs


def addMonthlyYTD(result, uri, auth, headers, startTime, endTime, reports):
    log = logging.getLogger('JIRAREPORTS')
    log.info("Starting YTD for Created VS resolved")
    rep = '15'
    if int(endTime.split("-")[1]) >= 4:
        breakDown = 'm'
    else:
        breakDown = 'w'
    if rep in reports:
        url = uri + rep + "/date-range?startDate=" + startTime.split("-")[
            0] + "-01-01&endDate=" + endTime + "&timeBreakdown=" + breakDown
        response = requests.request("GET", url, headers=headers, auth=auth)
        if response.status_code != 200:
            log.info('some issu occured with the JIRA API')
            log.info(response.text)
            sys.exit(0)
        jsn = response.json()
        reportLocal = Report(jsn["name"])
        for ser in jsn['series']:
            seriesLocal = Set(ser['label'], ser['color'])
            seriesLocal.type = ser["seriesType"]["yaxis"]['typeKey'].split('.')[-1]
            for ln in ser['data']:
                # adjust the winter time time zone
                addTime = timedelta(hours=2)
                seriesLocal.x.append((datetime.fromtimestamp(ln['x'] / 1e3) + addTime).date())
                multVal = 1
                if (seriesLocal.type == "duration"):
                    multVal = (0.001 / 3600)
                seriesLocal.y.append(ln['y'] * multVal)
            reportLocal.addSet(seriesLocal)
        result.append(reportLocal)

    return result


def main():
    dir = os.path.dirname(__file__)
    logFile = os.path.join(dir, 'log', 'JiraReports.log')
    log = initLogger(logFile)
    log.info("JiraReports is starting ...")
    args = parseArgs()
    if (args.menu):
        printMenu()
        return 0

    log.info('Starting config file parsing')
    cnf = configparser.ConfigParser()
    cnf.read('.\conf.ini')
    log.info('Finished config file parsing')
    auth = HTTPBasicAuth(cnf['JIRA']['user'], cnf['JIRA']['token'])
    headers = {"accept": "application/json"}
    url = cnf['JIRA']['url']
    if (args.periodic):
        log.info('Start periodic procedure')
        args.graph = False
        today = datetime.now().date()
        endYear = today.year
        endMonth = today.month
        if (endMonth == 1):
            startYear = endYear - 1
            startMonth = 12
            endYear = endYear -1
        else:
            startYear = endYear
            startMonth = endMonth - 1
        daysInMonth = calendar.monthrange(startYear, startMonth)[1]
        startTime = datetime(startYear, startMonth, 1).strftime("%Y-%m-%d")
        endTime = datetime(endYear, startMonth, daysInMonth).strftime("%Y-%m-%d")
        print(startTime)
        print(endTime)
        breakDown = 'w'
        reports = cnf['JIRA']['defaultReports'].split(',')
        results = retriveReports(url, auth, headers, startTime, endTime, breakDown, reports)
        results = addMonthlyYTD(results, url, auth, headers, startTime, endTime, reports)
        # images = generateGraphs(results)
        # msgraph = MsGraphMail.MsGraph(cnf['MAIL'])
        # body = msgraph.generateBody(startTime, endTime, results)
        # attach = msgraph.generateAttachments(images)
        # msgraph.getToken()
        # subject = 'JIRA report ' + startTime + ' - ' + endTime
        # msgraph.sendMail(attach, body, subject)
        # log.info('Finished periodic procedure')

    else:
        startTime, endTime, breakDown, reports = parseInput(args.startDate, args.endDate, args.breakDown, args.reports)
        results = retriveReports(url, auth, headers, startTime, endTime, breakDown, reports)
    images = generateGraphs(results)
    msgraph = MsGraphMail.MsGraph(cnf['MAIL'])
    body = msgraph.generateBody(startTime, endTime, results)
    attach = msgraph.generateAttachments(images)
    msgraph.getToken()
    subject = 'JIRA report ' + startTime + ' - ' + endTime
    msgraph.sendMail(attach, body, subject)
    log.info('Finished start-end time procedure')
    if (args.graph):
        plotGraph(results)


if __name__ == "__main__":
    main()
    # try:
        # main()
    # except Exception as e:
    #     log = logging.getLogger('JIRAREPORTS')
    #     log.error("Unhandled exception occured:")
    #     log.exception(e)

