from setuptools import find_packages, setup

import pathlib
req = ['bcrypt==4.0.1','cffi==1.15.1','cryptography==39.0.1','future==0.18.3',
       'netmiko==4.1.2','ntc-templates==3.2.0','paramiko==3.0.0','pycparser==2.21',
       'PyNaCl==1.5.0','pyserial==3.5','pywin32==305','PyYAML==6.0',
       'scp==0.14.5','six==1.16.0','tenacity==8.2.1', 'textfsm==1.1.2']

setup(
    name="DyaGram",
    version="0.0.16",
    author="Chris Moses",
    author_email="chrismoses121@gmail.com",
    description="IaC Tool to map out diagram of Network",
    packages=find_packages(where="modules"),
    install_requires=req,
    entry_points={
        'console_scripts': ['dyagram=modules.dyagram:main']
        ,
    }
)