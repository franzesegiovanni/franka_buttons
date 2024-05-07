#! /usr/bin/env python3
"Code originally inspiered by https://github.com/JeanElsner/panda-py/blob/main/src/panda_py/__init__.py. All the credits to the author. This is just a code that will read the buttons and stream it in ROS for the ROS users."

import base64
import dataclasses
import hashlib
import json as json_module
import logging
import os
import ssl
import threading
import typing
from urllib import parse

import requests #pip install requests
from requests.packages import urllib3
from websockets.sync.client import connect #pip install --upgrade websockets

import rospy
from std_msgs.msg import Bool, Float32
_logger = logging.getLogger('desk')

TOKEN_PATH = '~/token.conf'
"""
Path to the configuration file holding known control tokens.
If :py:class:`Desk` is used to connect to a control unit's
web interface and takes control, the generated token is stored
in this file under the unit's IP address or hostname.
"""


@dataclasses.dataclass
class Token:
  """
  Represents a Desk token owned by a user.
  """
  id: str = ''
  owned_by: str = ''
  token: str = ''


class Button:
  """
  Connects to the control unit running the web-based Desk interface
  to manage the robot. Use this class to interact with the Desk
  from Python, e.g. if you use a headless setup. This interface
  supports common tasks such as unlocking the brakes, activating
  the FCI etc.

  Newer versions of the system software use role-based access
  management to allow only one user to be in control of the Desk
  at a time. The controlling user is authenticated using a token.
  The :py:class:`Desk` class saves those token in :py:obj:`TOKEN_PATH`
  and will use them when reconnecting to the Desk, retaking control.
  Without a token, control of a Desk can only be taken, if there is
  no active claim or the controlling user explicitly relinquishes control.
  If the controlling user's token is lost, a user can take control
  forcefully (cf. :py:func:`Desk.take_control`) but needs to confirm
  physical access to the robot by pressing the circle button on the
  robot's Pilot interface.
  """

  def __init__(self) -> None:
    urllib3.disable_warnings()
    self._session = requests.Session()
    self._session.verify = False
    self._hostname = rospy.get_param('/buttons_node/robot_ip')
    self._username = rospy.get_param('/buttons_node/username')
    self._password = rospy.get_param('/buttons_node/password')
    self._logged_in = False
    self._listening = False
    self._listen_thread = None
    self.login()
    self._legacy = False

    self.button_x_publisher = rospy.Publisher('franka_buttons/x', Float32, queue_size=10)
    self.button_y_publisher = rospy.Publisher('franka_buttons/y', Float32, queue_size=10)
    self.button_circle_publisher = rospy.Publisher('franka_buttons/circle', Bool, queue_size=10)
    self.button_cross_publisher = rospy.Publisher('franka_buttons/cross', Bool, queue_size=10)
    self.button_check_publisher = rospy.Publisher('franka_buttons/check', Bool, queue_size=10)

  @staticmethod
  def encode_password(username: str, password: str) -> bytes:
    """
    Encodes the password into the form needed to log into the Desk interface.
    """
    bytes_str = ','.join([
        str(b) for b in hashlib.sha256((
            f'{password}#{username}@franka').encode('utf-8')).digest()
    ])
    return base64.encodebytes(bytes_str.encode('utf-8')).decode('utf-8')

  def login(self) -> None:
    """
    Uses the object's instance parameters to log into the Desk.
    The :py:class`Desk` class's constructor will try to connect
    and login automatically.
    """
    login = self._request(
        'post',
        '/admin/api/login',
        json={
            'login': self._username,
            'password': self.encode_password(self._username, self._password)
        })
    self._session.cookies.set('authorization', login.text)
    self._logged_in = True
    _logger.info('Login succesful.')

  def _request(self,
               method: typing.Literal['post', 'get', 'delete'],
               url: str,
               json: typing.Dict[str, str] = None,
               headers: typing.Dict[str, str] = None,
               files: typing.Dict[str, str] = None) -> requests.Response:
    fun = getattr(self._session, method)
    response: requests.Response = fun(parse.urljoin(f'https://{self._hostname}',
                                                    url),
                                      json=json,
                                      headers=headers,
                                      files=files)
    if response.status_code != 200:
      raise ConnectionError(response.text)
    return response

  def _listen(self, cb, timeout):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with connect(
        f'wss://{self._hostname}/desk/api/navigation/events',
        ssl_context=ctx,
        additional_headers={
            'authorization': self._session.cookies.get('authorization')
        }) as websocket:
      self._listening = True
      while self._listening:
        try:
          event: typing.Dict = json_module.loads(websocket.recv(timeout))
          cb(event)
        except TimeoutError:
          pass

  def listen(self, cb: typing.Callable[[typing.Dict], None]) -> None:
    """
    Starts a thread listening to Pilot button events. All the Pilot buttons,
    except for the `Pilot Mode` button can be captured. Make sure Pilot Mode is
    set to Desk instead of End-Effector to receive direction key events. You can
    change the Pilot mode by pressing the `Pilot Mode` button or changing the mode
    in the Desk. Events will be triggered while buttons are pressed down or released.
    
    Args:
      cb: Callback fucntion that is called whenever a button event is received from the
        Desk. The callback receives a dict argument that contains the triggered buttons
        as keys. The values of those keys will depend on the kind of event, either True
        for a button pressed down or False when released.
        The possible buttons are: `circle`, `cross`, `check`, `left`, `right`, `down`,
        and `up`.
    """
    self._listen_thread = threading.Thread(target=self._listen, args=(cb, 1.0))
    self._listen_thread.start()


  def stop_listen(self) -> None:
    """
    Stop listener thread (cf. :py:func:`panda_py.Desk.listen`).
    """
    self._listening = False
    if self._listen_thread is not None:
      self._listen_thread.join()

  def callback(self, event: typing.Dict) -> None:
      # print("Received event:", event)
      feedback_x = 0
      feedback_y = 0
      feedback_circle = False
      feedback_cross = False
      feedback_check = False
      # buttons=['circle', 'cross', 'check','up', 'down', 'right', 'left']

      read_events=list(event.keys())
      for i in range(len(read_events)):
          if read_events[i] == 'down':
            if event[read_events[i]] == True:
              feedback_x = 1
          if read_events[i] == 'up':
            if event[read_events[i]] == True:
              feedback_x = -1
          if read_events[i] == 'right':
            if event[read_events[i]] == True:
              feedback_y = 1
          if read_events[i] == 'left':
            if event[read_events[i]] == True:
              feedback_y = -1
          if read_events[i] == 'circle':
            if event[read_events[i]] == True:
              feedback_circle = True
          if read_events[i] == 'cross':
            if event[read_events[i]] == True:
              feedback_cross = True
          if read_events[i] == 'check':
            if event[read_events[i]] == True:
              feedback_check = True
      msg_x = Float32(data=feedback_x)
      msg_y = Float32(data=feedback_y)
      msg_circle = Bool(data=feedback_circle)
      msg_cross = Bool(data=feedback_cross)
      msg_check = Bool(data=feedback_check)
      self.button_x_publisher.publish(msg_x)
      self.button_y_publisher.publish(msg_y)
      self.button_circle_publisher.publish(msg_circle)
      self.button_cross_publisher.publish(msg_cross)
      self.button_check_publisher.publish(msg_check)     

          


if __name__ == "__main__":
    #Start ROS node
    rospy.init_node('button_listener', anonymous=True)
    rospy.sleep(1)
    
    button=Button()
    button.listen(button.callback)
