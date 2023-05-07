import requests
import json
import logging 

log = logging.getLogger('JIRAREPORTS')
class NoTokenAquired(Exception):
    """
        Exception raised if no token aquired.
        Attributes:
            reason -- input salary which caused the error
            message -- explanation of the error
    """
    def __init__(self, reason, message="No Token was Aquired:"):
        self.reason = reason
        self.message = message
        super().__init__(self.message + "\n" + self.reason)

class MailNotSent(Exception):
    """
        Exception raised if issue occured while trying to send the mail.
        Attributes:
            reason -- input salary which caused the error
            message -- explanation of the error
    """
    def __init__(self, reason, message="Mail not sent :"):
        self.reason = reason
        self.message = message
        super().__init__(self.message + "\n" + self.reason)

class MsGraph:
    def __init__(self, args):
        self.cliendId = args['cliendId']
        self.scope =  args['scope']
        self.clientSecret = args['clientSecret']
        self.grantType = args['grantType']
        self.tanent = args['tanent']
        self.authUrlBase = args['authUrlBase']
        self.authUrl = self.authUrlBase + self.tanent + args['oAuthExt']
        self.sendUrl = args['sendUrl'] + args['onBehalf'] + args['sendMailExt']
        self.token = ''
        self.to = []
        for recip in args['mailto'].split(','):
            self.to.append({
                    "emailAddress": {
                        "address": recip.replace(' ','')
                    }
                })

    def getToken(self):
        log.info('start getToken()')
        headers ={'Content-Type' : 'application/x-www-form-urlencoded'}
        params = {'client_id' : self.cliendId,
                  'scope' : self.scope,
                  'client_secret' : self.clientSecret,
                  'grant_type' : self.grantType}
        authResponse = requests.request("POST", url=self.authUrl, headers=headers, data=params)
        if authResponse.status_code != 200:
            log.info('Something went wrong with the ms graph authentication')
            raise NoTokenAquired(reason = authResponse.text)
        try:
            self.token = authResponse.json()['access_token']
            log.info('Finished getToken()')
        except KeyError:
            log.info('Something went wrong with the ms graph authentication')
            raise NoTokenAquired(reason = authResponse.text)

    def generateAttachments(self, images):
        """
           generateAttachments(self, images) - helper method to generate the attachments json part
           Attributes:
                images - a dictionary with images unique name and the base64 encoded image data
           Returns:
                a json with all the attachments in it
        """
        attachments = []
        for name, img in images.items():
            attachment = {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": name,
                    "contentType": "image/png",
                    "contentId" : name.replace(' ',''),
                    "contentBytes": img
                }
            attachments.append(attachment)
        return attachments


    def sendMail(self, attachments, body, subject):
        if self.token == '':
            raise NoTokenAquired(reason = 'No token found, run getToken() again')
        sendHeaders = {'Authorization': 'bearer ' + self.token,
                       'Content-Type': 'application/json'}
        #body = "<h1>A mail with an embedded image <br><img src='cid:thumbsUp' alt='Thumbs up' /></h1>"
        #encoded = base64.b64encode(open(r'/mnt/c/Users/ebenitk/Desktop/test.png', "rb").read())
        message = {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": str(body)
            },
            "toRecipients": self.to,
            "attachments": attachments
        }
        sendParams = json.dumps({'message' : message})
        #print(json.dumps(json.loads(sendParams), sort_keys=True, indent=4, separators=(",", ": ")))
        sendResp = requests.request("POST", url=self.sendUrl, headers=sendHeaders, data=sendParams, verify=False)
        if sendResp.status_code != 202:
            raise MailNotSent(reason = sendResp.text)


    def generateBody(self,startTime, endTime, results):
        body = r'<html xmlns:v=\"urn:schemas-microsoft-com:vml\" xmlns:o=\"urn:schemas-microsoft-com:office:office\" xmlns:w=\"urn:schemas-microsoft-com:office:word\" xmlns:m=\"http://schemas.microsoft.com/office/2004/12/omml\" xmlns=\"http://www.w3.org/TR/REC-html40\"><head><meta http-equiv=Content-Type content=\"text/html; charset=us-ascii\"><meta name=Generator content=\"Microsoft Word 15 (filtered medium)\"><!--\[if !mso]><style>v\:* {behavior:url(#default#VML);}o\:* {behavior:url(#default#VML);}w\:* {behavior:url(#default#VML);}.shape {behavior:url(#default#VML);}</style><![endif]--><style><!--/* Font Definitions */@font-face{font-family:\"Cambria Math\";panose-1:2 4 5 3 5 4 6 3 2 4;}@font-face{font-family:Calibri;panose-1:2 15 5 2 2 2 4 3 2 4;}/* Style Definitions */p.MsoNormal, li.MsoNormal, div.MsoNormal{margin:0cm;margin-bottom:.0001pt;font-size:11.0pt;font-family:\"Calibri\",sans-serif;}span.EmailStyle17{mso-style-type:personal-compose;font-family:\"Calibri\",sans-serif;color:windowtext;}.MsoChpDefault{mso-style-type:export-only;font-family:\"Calibri\",sans-serif;}@page WordSection1{size:612.0pt 792.0pt;margin:72.0pt 90.0pt 72.0pt 90.0pt;}div.WordSection1{page:WordSection1;}--></style><!--[if gte mso 9]><xml><o:shapedefaults v:ext=\"edit\" spidmax=\"1026\" /></xml><![endif]--><!--[if gte mso 9]><xml><o:shapelayout v:ext=\"edit\"><o:idmap v:ext=\"edit\" data=\"1\" /></o:shapelayout></xml><![endif]--></head><body lang=EN-US link=\"#0563C1\" vlink=\"#954F72\"><div class=WordSection1><p class=MsoNormal>Hi All<o:p/></p><p class=MsoNormal><o:p>&nbsp;</o:p></p><p class=MsoNormal>This mail is sent automatically please do not reply.<br>Below is the JIRA report generated between' + startTime + ' and ' + endTime + ':<o:p/><br></p>'
        for result in results:
            body = body + "<br><p class=MsoNormal>"+ result.name + ":<o:p/></p><br><p class=MsoNormal"
            for s in result.series:
                cnt = str(s.cnt)
                if s.type == 'duration':
                    cnt = "{:.2f}".format(s.avg)
                #body = body + "<p class=MsoNormal style=\"color:" + s.color + "\">" + s.name + " &#8211; " + cnt + "<o:p/></p>"
                body = body + "<span style=\"color:" + s.color + "\">" + s.name + " &#8211; " + cnt + "&nbsp;&#x3b;</span>"
            body = body + "<o:p/></p><p class=MsoNormal><o:p>&nbsp;</o:p></p><p class=MsoNormal><img width=1515 height=482 style='width:15.7812in;height:5.0208in'  src=\"cid:" + result.name.replace(' ','') + "\" alt=\"" + result.name +"\"><o:p/></p>"
        body = body + "<p class=MsoNormal><o:p>&nbsp;</o:p></p><p class=MsoNormal>This email is auto generated by Benny Itkin via Office365, please do not reply to this email<o:p/></p><p class=MsoNormal>BR<o:p/></p><p class=MsoNormal><o:p>&nbsp;</o:p></p><p class=MsoNormal>Benny Itkin<o:p/></p><p class=MsoNormal><o:p>&nbsp;</o:p></p></div></body></html>"
        return body