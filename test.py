import json
import os

from dotenv import load_dotenv

# Load the environment variables from .env file
from sqs_launcher import SqsLauncher
from sqs_listener import SqsListener
from sqs_queue import SqsQueue

load_dotenv()

# Read environment variables
dead_queue_name = os.getenv('DEAD_QUEUE_NAME', "default_d")
dead_queue_url = os.getenv('DEAD_QUEUE_URL', "http://localhost:4566/000000000000/test_queue_d")
dead_queue_access_token = os.getenv('DEAD_QUEUE_ACCESS_TOKEN', "test")
dead_queue_secret_token = os.getenv('DEAD_QUEUE_SECRET_TOKEN', "test")

queue_name = os.getenv('QUEUE_NAME', "default")
queue_url = os.getenv('QUEUE_URL', "http://localhost:4566/000000000000/test_queue")
queue_access_token = os.getenv('QUEUE_ACCESS_TOKEN', "test")
queue_secret_token = os.getenv('QUEUE_SECRET_TOKEN', "test")

endpoint_url = os.getenv('ENDPOINT_URL', "http://localhost:4566/")
endpoint_region = os.getenv('ENDPOINT_REGION', "ap-northeast-1")


def setup_queue() -> SqsQueue:
    return SqsQueue(
        name=queue_name,
        url=queue_url,
        secret_token=queue_secret_token,
        access_token=queue_access_token,
        dead_queue_name=dead_queue_name,
        dead_queue_url=dead_queue_url,
        dead_queue_secret_token=dead_queue_secret_token,
        dead_queue_access_token=dead_queue_access_token,
    )


def dead_queue_from_queue(regular_queue: SqsQueue) -> SqsQueue:
    return SqsQueue(
        name=regular_queue.dead_queue_name,
        url=regular_queue.dead_queue_url,
        secret_token=regular_queue.dead_queue_secret_token,
        access_token=regular_queue.dead_queue_access_token,
    )


def test_send_message_to_scaleway(queue: SqsQueue):
    launcher = SqsLauncher(queue, region_name=endpoint_region, endpoint_name=endpoint_url)
    response = launcher.launch_message({'param1': 'hello', 'param2': 'this is a test :)'})


def test_listen_queue_on_scaleway(queue: SqsQueue, should_throw: bool = False):
    class MyListener(SqsListener):
        def handle_message(self, body, attributes, messages_attributes, message_id):
            print(f"MessageId : {message_id}")
            print(json.dumps(body))
            listener.stop_listening()
            if should_throw:
                raise Exception("Big error")

    listener = MyListener(queue, region_name=endpoint_region, endpoint_name=endpoint_url, interval=1)
    listener.listen()


def test_listen_dead_queue_on_scaleway(queue: SqsQueue):
    class MyListener(SqsListener):
        def handle_message(self, body, attributes, messages_attributes, message_id):
            print(f"MessageId : {message_id}")
            print(json.dumps(body))
            listener.stop_listening()

    listener = MyListener(dead_queue_from_queue(queue), region_name=endpoint_region, endpoint_name=endpoint_url, interval=1)
    listener.listen()


if __name__ == "__main__":
    queue = setup_queue()

    # First run
    test_send_message_to_scaleway(queue)
    test_listen_queue_on_scaleway(queue)

    # Second run, sending to dead queue
    test_send_message_to_scaleway(queue)
    test_listen_queue_on_scaleway(queue, True)

    # Then third run, test dead queue
    test_listen_dead_queue_on_scaleway(queue)
