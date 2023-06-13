"""
Created December 21st, 2016
@author: Yaakov Gesher
@version: 0.9.0
@license: Apache
"""
import json
import logging
import os
import sys
import time
from abc import ABCMeta, abstractmethod
from typing import Callable

import boto3
import boto3.session

# ================
# start class
# ================
from sqs_queue import SqsQueue

# ================
# start imports
# ================

sqs_logger = logging.getLogger('sqs_listener')


class SqsListener(object):
    __metaclass__ = ABCMeta

    def __init__(self, queue: SqsQueue, **kwargs):
        """
        :param queue: (SQSQueue) queue to listen to
        :param kwargs: options for fine tuning. see below
        """
        aws_access_key = queue.access_token or kwargs.get('aws_access_key', '')
        aws_secret_key = queue.secret_token or kwargs.get('aws_secret_key', '')

        if not aws_access_key or not aws_secret_key:
            raise Exception("Access token and secret token are missing.")

        boto3_session = boto3.Session(
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key
        )

        boto3_dead_queue_session = None
        if queue.dead_queue_secret_token and queue.dead_queue_access_token:
            boto3_dead_queue_session = boto3.Session(
                aws_access_key_id=queue.dead_queue_access_token,
                aws_secret_access_key=queue.dead_queue_secret_token
            )

        self._queue_name = queue.name
        self._poll_interval = kwargs.get("interval", 60)
        self._queue_visibility_timeout = kwargs.get('visibility_timeout', '600')
        self._dead_queue_visibility_timeout = kwargs.get('error_visibility_timeout', '10000')
        self._queue_url = queue.url or kwargs.get('queue_url', None)  # use queue url if available
        self._dead_queue_url = queue.dead_queue_url or None  # use dead queue url if available
        self._dead_queue_name = queue.dead_queue_name or None  # use dead queue name if available
        self._message_attribute_names = kwargs.get('message_attribute_names', [])
        self._attribute_names = kwargs.get('attribute_names', [])
        self._force_delete = kwargs.get('force_delete', False)
        self._endpoint_name = kwargs.get('endpoint_name', None)
        self._wait_time = kwargs.get('wait_time', 0)
        self._max_number_of_messages = kwargs.get('max_number_of_messages', 1)
        self._deserializer = kwargs.get("deserializer", json.loads)
        self._run_while_idle = kwargs.get('run_while_idle', None)
        self._listening = True

        # must come last
        if boto3_session:
            self._session = boto3_session
        else:
            self._session = boto3.session.Session()

        if boto3_dead_queue_session or False:
            self._dead_queue_session = boto3_dead_queue_session
        else:
            self._dead_queue_session = None

        self._region_name = kwargs.get('region_name', self._session.region_name)
        self._client, self._dead_queue_client = self._initialize_client()

    def _initialize_client(self):
        # new session for each instantiation
        ssl = True
        if self._region_name == 'elasticmq':
            ssl = False

        sqs = self._session.client('sqs', region_name=self._region_name, endpoint_url=self._endpoint_name, use_ssl=ssl)

        dead_queue_sqs = None
        if self._dead_queue_session:
            dead_queue_sqs = self._dead_queue_session.client('sqs', region_name=self._region_name,
                                                             endpoint_url=self._endpoint_name, use_ssl=ssl)

        # Skip queue discovery process if queue_url and dead_queue_url are provided
        if self._queue_url and (self._dead_queue_url or self._dead_queue_url is None):
            return sqs, dead_queue_sqs

        queues = sqs.list_queues(QueueNamePrefix=self._queue_name)
        main_queue_exists = False
        error_queue_exists = False
        if 'QueueUrls' in queues:
            for q in queues['QueueUrls']:
                qname = q.split('/')[-1]
                if qname == self._queue_name:
                    main_queue_exists = True
                if self._dead_queue_name and qname == self._dead_queue_name:
                    error_queue_exists = True

        if not main_queue_exists:
            sqs_logger.warning("main queue not found, creating now")

            # create queue if necessary.
            if self._queue_name.endswith(".fifo"):
                fifo_queue = "true"
                q = sqs.create_queue(
                    QueueName=self._queue_name,
                    Attributes={
                        'VisibilityTimeout': self._queue_visibility_timeout,  # 10 minutes
                        'FifoQueue': fifo_queue
                    }
                )
            else:
                # need to avoid FifoQueue property for normal non-fifo queues
                q = sqs.create_queue(
                    QueueName=self._queue_name,
                    Attributes={
                        'VisibilityTimeout': self._queue_visibility_timeout,  # 10 minutes
                    }
                )
            self._queue_url = q['QueueUrl']

        if self._dead_queue_name and not error_queue_exists and dead_queue_sqs:
            sqs_logger.warning("error queue not found, creating now")
            q = dead_queue_sqs.create_queue(
                QueueName=self._dead_queue_name,
                Attributes={
                    'VisibilityTimeout': self._queue_visibility_timeout  # 10 minutes
                }
            )
            self._dead_queue_url = q['QueueUrl']  # update the error queue url

        if not self._queue_url:
            if os.environ.get('AWS_ACCOUNT_ID', None):
                qs = sqs.get_queue_url(QueueName=self._queue_name,
                                       QueueOwnerAWSAccountId=os.environ.get('AWS_ACCOUNT_ID', None))
            else:
                qs = sqs.get_queue_url(QueueName=self._queue_name)
            self._queue_url = qs['QueueUrl']
        return sqs, dead_queue_sqs

    def _start_listening(self):
        # TODO consider incorporating output processing from here: https://github.com/debrouwere/sqs-antenna/blob/master/antenna/__init__.py
        self._listening = True
        while self._listening:
            # calling with WaitTimeSecconds of zero show the same behavior as
            # not specifiying a wait time, ie: short polling
            messages = self._client.receive_message(
                QueueUrl=self._queue_url,
                MessageAttributeNames=self._message_attribute_names,
                AttributeNames=self._attribute_names,
                WaitTimeSeconds=self._wait_time,
                MaxNumberOfMessages=self._max_number_of_messages
            )
            if 'Messages' in messages:

                sqs_logger.debug(messages)
                sqs_logger.info("{} messages received".format(len(messages['Messages'])))
                for m in messages['Messages']:
                    receipt_handle = m['ReceiptHandle']
                    m_body = m['Body']
                    message_attribs = None
                    attribs = None

                    try:
                        deserialized = self._deserializer(m_body)
                    except:
                        sqs_logger.exception("Unable to parse message")
                        continue

                    if 'MessageAttributes' in m:
                        message_attribs = m['MessageAttributes']
                    if 'Attributes' in m:
                        attribs = m['Attributes']
                    try:
                        if self._force_delete:
                            self._client.delete_message(
                                QueueUrl=self._queue_url,
                                ReceiptHandle=receipt_handle
                            )
                            self.handle_message(deserialized, message_attribs, attribs)
                        else:
                            self.handle_message(deserialized, message_attribs, attribs)
                            self._client.delete_message(
                                QueueUrl=self._queue_url,
                                ReceiptHandle=receipt_handle
                            )
                    except Exception as ex:
                        sqs_logger.exception(ex)
                        if self._dead_queue_name:
                            exc_type, exc_obj, exc_tb = sys.exc_info()

                            sqs_logger.info("Pushing exception to dead queue")

                            self._dead_queue_client.send_message(
                                QueueUrl=self._dead_queue_url,
                                MessageBody=json.dumps({
                                    'exception_type': str(exc_type),
                                    'error_message': str(ex.args)
                                }),
                            )
            else:
                if isinstance(self._run_while_idle, Callable):
                    self._run_while_idle()
                time.sleep(self._poll_interval)
        sqs_logger.info("Stopped listening to queue " + self._queue_name)

    def listen(self):
        sqs_logger.info("Listening to queue " + self._queue_name)
        if self._dead_queue_name:
            sqs_logger.info("Using error queue " + self._dead_queue_name)

        self._start_listening()

    def stop_listening(self):
        self._listening = False

    def _prepare_logger(self):
        logger = logging.getLogger('eg_daemon')
        logger.setLevel(logging.INFO)

        sh = logging.StreamHandler(sys.stdout)
        sh.setLevel(logging.INFO)

        formatstr = '[%(asctime)s - %(name)s - %(levelname)s]  %(message)s'
        formatter = logging.Formatter(formatstr)

        sh.setFormatter(formatter)
        logger.addHandler(sh)

    @abstractmethod
    def handle_message(self, body, attributes, messages_attributes):
        """
        Implement this method to do something with the SQS message contents
        :param body: dict
        :param attributes: dict
        :param messages_attributes: dict
        :return:
        """
        return
