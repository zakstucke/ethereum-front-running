import subprocess

subprocess.check_output("TEST=True python manage.py test backend/ --debug-mode -v 2", shell=True)