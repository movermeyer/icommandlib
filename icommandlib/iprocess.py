from icommandlib import exceptions
import threading
import psutil
import os
from icommandlib import messages as message
from icommandlib.run import IProcessHandle
import queue


class IProcess(object):
    def __init__(self, icommand):
        self._icommand = icommand
        self._request_queue = queue.Queue()
        self._response_queue = queue.Queue()
        self._handle = threading.Thread(
            target=IProcessHandle,
            args=(icommand, self._request_queue, self._response_queue)
        )
        self._handle.start()

        self._running_process = self._expect_message(message.ProcessStartedMessage)

        self._pid = self._running_process._pid
        self._master_fd = self._running_process._stdin
        self._async_send = self._expect_message(message.AsyncSendMethodMessage)

    def _expect_message(self, of_kind):
        response = self._response_queue.get()
        if isinstance(response, message.TimeoutMessage):
            raise exceptions.IProcessTimeout(
                "Timed out after {0} seconds.".format(response.value)
            )
        if not isinstance(response, of_kind):
            raise Exception(
                "Threading error expected {0} got {1}".format(
                    type(of_kind), type(of_kind)
                )
            )
        return response.value

    def wait_until_output_contains(self, text):
        self._request_queue.put(message.Condition(
            lambda iscreen: text in iscreen.raw_bytes.decode('utf8')
        ))
        self._async_send()
        self._expect_message(message.OutputMatched)

    def wait_until_on_screen(self, text):
        self._request_queue.put(message.Condition(
            lambda iscreen: len([line for line in iscreen.display if text in line]) > 0
        ))
        self._async_send()
        self._expect_message(message.OutputMatched)

    def send_keys(self, text):
        os.write(self._master_fd, text.encode('utf8'))

    def screenshot(self):
        self._request_queue.put(message.TakeScreenshot())
        self._async_send()
        return self._expect_message(message.Screenshot)

    def wait_for_finish(self):
        psutil.Process(self._pid).wait()
