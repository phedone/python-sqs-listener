from typing import Optional


class SqsQueue:
    """Class to represent a queue."""

    def __init__(
            self,
            name: str,
            url: Optional[str] = None,
            secret_token: Optional[str] = None,
            access_token: Optional[str] = None,
            dead_queue_name: Optional[str] = None,
            dead_queue_url: Optional[str] = None,
            dead_queue_secret_token: Optional[str] = None,
            dead_queue_access_token: Optional[str] = None,
    ):
        """
        Initialize a Queue instance.

        :param name: Name of the queue.
        :type name: str
        :param url: URL of the queue.
        :type url: Optional[str]
        :param secret_token: Secret token
        :type secret_token: Optional[str]
        :param access_token: Access token
        :type access_token: Optional[str]
        :param dead_queue_name: Name of the dead queue.
        :type dead_queue_name: str
        :param dead_queue_url: URL of the dead queue.
        :type dead_queue_url: Optional[str]
        :param dead_queue_secret_token: Dead queue secret token
        :type dead_queue_secret_token: Optional[str]
        :param dead_queue_access_token: Dead queue access token
        :type dead_queue_access_token: Optional[str]

        """
        self.name = name
        self.url = url
        self.secret_token = secret_token
        self.access_token = access_token
        self.dead_queue_name = dead_queue_name
        self.dead_queue_url = dead_queue_url
        self.dead_queue_secret_token = dead_queue_secret_token
        self.dead_queue_access_token = dead_queue_access_token
