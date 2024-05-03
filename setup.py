from setuptools import setup

setup(
    name='franka_buttons',
    version='0.0.1',
    description='Read the state of the franka buttons',
    author='Giovanni Franzese',
    author_email='g.franzese@tudelft.nl',
    packages=['ILoSA', 'franka_gripper.msg', 'franka_msgs.msg'],
    install_requires=[],
    # Add other dependencies here
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
)
