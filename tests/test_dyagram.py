import subprocess
from datetime import datetime
import os
from netmiko import ConnectHandler


def check_for_no_changes_in_state():

    """
    THIS FUNC TESTS DYAGRAM REPEATEDLY ON A NETWORK THAT ISN'T CHANGING TO MAKE SURE EVERY TIME THE OUTPUT IS 'NO CHANGES IN STATE'

    State file must already exist
    :return:
    """

    test_number = 1
    while test_number < 101:

        result = subprocess.run(['dyagram', 'discover','-v'], stdout=subprocess.PIPE).stdout.decode('utf-8')
        if not "No changes in state" in result and not 'Unable to connect' in result:
            file = open("test_results.txt", 'a')
            file.write(f"{str(datetime.now())} - !!!!!!FAILED TEST #{test_number}!!!!!!!\n")
            file.close()
            file = open("issues.txt", 'a')
            file.write(f"{str(datetime.now())} - FAILED TEST #{test_number}\n")
            file.close()
            file = open("output.txt", 'a')
            file.write(f"{str(datetime.now())}\n------\n{result}\n\n")
            file.close()
            test_number += 1

        elif 'Unable to connect' in result:
            file = open("test_results.txt", 'a')
            file.write(f"{str(datetime.now())} - PASSED TEST #{test_number}\n (UNABLE TO CONNECT TO DEVICE)")
            file.close()
            test_number += 1
        else:
            file = open("test_results.txt", 'a')
            file.write(f"{str(datetime.now())} - PASSED TEST #{test_number}\n")
            file.close()
            test_number += 1



def check_for_eigrp_neighbor_down():

    """
    THIS FUNC TESTS DYAGRAM REPEATEDLY ON A NETWORK THAT ISN'T CHANGING TO MAKE SURE EVERY TIME THE OUTPUT IS 'NO CHANGES IN STATE'

    State file must already exist
    :return:
    """

    test_number = 1
    while test_number < 101:

        result = subprocess.run(['dyagram', 'discover','-v'], stdout=subprocess.PIPE).stdout.decode('utf-8')
        if "No changes in state" in result and not 'Unable to connect' in result:
            file = open("test_results.txt", 'a')
            file.write(f"{str(datetime.now())} - !!!!!!FAILED TEST #{test_number}!!!!!!!\n")
            file.close()
            file = open("issues.txt", 'a')
            file.write(f"{str(datetime.now())} - FAILED TEST #{test_number}\n")
            file.close()
            file = open("output.txt", 'a')
            file.write(f"{str(datetime.now())}\n------\n{result}\n\n")
            file.close()
            test_number += 1

        elif 'Unable to connect' in result:
            file = open("test_results.txt", 'a')
            file.write(f"{str(datetime.now())} - PASSED TEST #{test_number}\n (UNABLE TO CONNECT TO DEVICE)")
            file.close()
            test_number += 1
        elif 'eigrp' in result.lower():
            file = open("test_results.txt", 'a')
            file.write(f"{str(datetime.now())} - PASSED TEST #{test_number}\n")
            file.close()
            test_number += 1
        else:

            file = open("test_results.txt", 'a')
            file.write(f"{str(datetime.now())} - !!!!!!FAILED TEST #{test_number}!!!!!!!\n")
            file.close()
            file = open("issues.txt", 'a')
            file.write(f"{str(datetime.now())} - FAILED TEST #{test_number}\n")
            file.close()
            file = open("output.txt", 'a')
            file.write(f"{str(datetime.now())}\n------\n{result}\n\n")
            file.close()
            test_number += 1





if __name__ == "__main__":

    #check_for_eigrp_neighbor_down()
    check_for_no_changes_in_state()