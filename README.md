# franka_buttons
This is a ROS repo to read the state of the buttons of franka robot.

To read the state of the buttons of the robot, you need to run the following command:
```

roslaunch franka_buttons read_buttons.launch robot_ip:=<robot_ip> username:=<username> password:=<password>

```
where `<robot_ip>` is the ip of the robot. `<username>` and `<password>` are the username and password of the robot that you have in the Desk.

The node will publish the state of the buttons in the topic `/franka/buttons` as a `Int32MultiArray` message.
