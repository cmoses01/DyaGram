import subprocess
from datetime import datetime


def check_for_no_changes_in_state():

    """
    THIS FUNC TESTS DYAGRAM REPEATEDLY ON A NETWORK THAT ISN'T CHANGING TO MAKE SURE EVERY TIME THE OUTPUT IS 'NO CHANGES IN STATE'

    State file must already exist
    :return:
    """

    test_number = 1
    while True:

        result = subprocess.run(['dyagram', 'discover','-v'], stdout=subprocess.PIPE).stdout.decode('utf-8')
        if not "No changes in state" in result:
            file = open("test_results.txt", 'a')
            file.write(f"{str(datetime.now())} - !!!!!!FAILED TEST #{test_number}!!!!!!!\n")
            file.close()
            file = open("issues.txt", 'a')
            file.write(f"{str(datetime.now())} - FAILED TEST #{test_number}\n")
            file.close()
            test_number += 1

        else:
            file = open("test_results.txt", 'a')
            file.write(f"{str(datetime.now())} - PASSED TEST #{test_number}\n")
            file.close()
            test_number += 1


