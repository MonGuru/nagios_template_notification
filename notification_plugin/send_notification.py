#!/usr/bin/env python 
import sys
import traceback
import logging
import time
import math
import smtplib
import hmac
import hashlib
import json
import os

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import jinja2
import requests
import dns.resolver

FROM_ADDRESS="notification@mongu.ru"

SCHEMA_WEBSERVICE_URL = 'https://monguru-apps.appspot.com/email'
PRIVATE_KEY = 'sss'

GOOGLE_SERVERS = ['aspmx.l.google.com.', 'aspmx.l.google.com',
                  'aspmx2.googlemail.com.', 'aspmx2.googlemail.com',
                  'aspmx3.googlemail.com.', 'aspmx3.googlemail.com.',
                  'alt1.aspmx.l.google.com.', 'alt1.aspmx.l.google.com',
                  'alt2.aspmx.l.google.com.', 'alt2.aspmx.l.google.com',
                ]

TEMPLATE_FILE = 'templates/mail_%s.html'

ARGUMENTS = [
             'to',
             'notify_type',
             'host_name',
             'host_alias' ,
             'host_address',
             'long_date',
             'instance_key',
        ]

SPECIFIC_ARGUMENTS = {
        'host': [
                   'host_state', 'host_output',
                   'totalup',
                   'totaldown',
           ],
        'service': [
                   'serv_output',
                   'serv_desc',
                   'serv_state',
                   'duration',
                   'exectime',
                   'total_warnings',
                   'total_criticals',
                   'total_unknowns',
                   'last_service_ok',
                   'last_warning',
                   'attempts',
                   ]
        }

SUBJECT = {
            'host': '%(notify_type)s Host:%(host_name)s is %(host_state)s""',
            'service': '%(notify_type)s Service:%(host_name)s/%(serv_desc)s [%(serv_state)s]""',
        }

def retry(tries=5, delay=3, backoff=2):
    if backoff <= 1:
        raise ValueError("backoff must be greater than 1")
    tries = math.floor(tries)
    if tries < 0:
        raise ValueError("tries must be 0 or greater")
    if delay <= 0:
        raise ValueError("delay must be greater than 0")
    def deco_retry(f):
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay # make mutable
            rv = f(*args, **kwargs) # first attempt
            while mtries > 0:
                if rv is True: # Done on success
                    return True
                mtries -= 1      # consume an attempt
                time.sleep(mdelay) # wait...
                mdelay *= backoff  # make future wait longer
                rv = f(*args, **kwargs) # Try again
            return False # Ran out of tries :-(
        return f_retry # true decorator -> decorated function
    return deco_retry  # @retry(arg[, ...]) -> true decorator



class BaseSender(object):


    args = []
    items = {}
    obj_type = ''

    def __init__(self, args, obj_type):
        self.args = args
        self.obj_type = obj_type

    def _mount_data(self):
        for key, value in self._mount_pairs():
            self.items[key] = value
        self.items['subject'] = SUBJECT[self.obj_type] % self.items


    def _mount_pairs(self):
        pairs = []
        pairs.append(('type', self.obj_type))
        def _iterate_args(args_to_expect, cline_args):
            pair = []
            times = len(args_to_expect)
            for time in xrange(0, times):
                pair.append((args_to_expect[0], cline_args[0]))
                args_to_expect.pop(0)
                cline_args.pop(0)
            return pair

        pairs.extend(_iterate_args(ARGUMENTS, self.args))
        pairs.extend(_iterate_args(SPECIFIC_ARGUMENTS[self.obj_type], self.args))
        return pairs

    def _mount_template(self):
        template_file = 'templates/mail_%s_template.html' % self.obj_type
        jinja_environment = jinja2.Environment(
            loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))
        template = jinja_environment.get_template(template_file)
        email_body = template.render({'items': self.items})
        return email_body
    #@retry(1)
    def run(self):
        self._mount_data()
        try:
            self._send_action()
        #TODO: loggin
        except Exception:
            logging.error('Error sendind notigication, class: %s, items: %s, traceback: %s' %
                    (self, str(self.items), traceback.format_exc()))
            return False
        return True


class HTMLEmail(BaseSender):

    def _send_action(self):
        msg = MIMEMultipart('alternative')
        msg['Subject'] = self.items['subject']
        msg['From'] = FROM_ADDRESS
        msg['To'] = self.items['to']
        body = self._mount_template()
        part1 = MIMEText(body, 'html')
        msg.attach(part1)
        s = smtplib.SMTP('localhost')
        s.sendmail(FROM_ADDRESS, self.items['to'], msg.as_string())
        s.quit()

class SchemaWebService(BaseSender):

    def hmac_hash(self, msg, private_key=PRIVATE_KEY):
        digest = hmac.new(private_key,
                            msg=msg,
                            digestmod=hashlib.sha256).hexdigest()
        return digest

    def _send_action(self):
        data = {}
        response = {}
        response['to'] = self.items['to']
        response['subject'] = self.items['subject']
        response['email_body'] = self._mount_template()
        data['json-data'] = json.dumps(response)
        data['hash'] = self.hmac_hash(data['json-data'])
        http_req = requests.post(
            SCHEMA_WEBSERVICE_URL,
            data=data)
        if http_req.status_code != 200:
            logging.error(http_req.text)
            raise ValueError('http status is not 200')

def decide_service():
    send_cls = HTMLEmail
    domain = sys.argv[2].split('@')[1]
    if domain != 'gmail.com':
        resolver = dns.resolver.Resolver()
        records = []
        try:
            data = resolver.query(domain, 'MX')
            if data:
                for mx in data:
                    records.append(str(mx).split()[1].lower())
        except:
            pass
        for record in records:
            if record in GOOGLE_SERVERS:
                send_cls = SchemaWebService
                break
    else:
        send_cls = SchemaWebService
    sender = send_cls(sys.argv[2:], sys.argv[1])
    sender.run()


if __name__ == '__main__':
    decide_service()
